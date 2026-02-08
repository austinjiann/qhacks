'use client'

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { QueueItem, FeedItem, KalshiMarket } from '@/types'
import { VIDEO_IDS, findVisualizationVideo } from '@/mystery'

const SESSION_RESULTS_KEY = 'feed_results'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10

const PINNED_IDS = ['DMRVJ2ZX-L4', 'tn9VrI5pToI', 'hLAz3y61V2I']

function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

function saveFeedResults(items: FeedItem[]) {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.setItem(SESSION_RESULTS_KEY, JSON.stringify(items))
  } catch { /* quota exceeded — non-critical */ }
}

function loadFeedResults(): Map<string, FeedItem> | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(SESSION_RESULTS_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || parsed.length === 0) return null
    const map = new Map<string, FeedItem>()
    for (const item of parsed) {
      if (item && typeof item === 'object' && item.youtube?.video_id) {
        map.set(item.youtube.video_id, item as FeedItem)
      }
    }
    return map.size > 0 ? map : null
  } catch {
    return null
  }
}

export function useVideoQueue() {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [feedItems, setFeedItems] = useState<FeedItem[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const initializedRef = useRef(false)
  const queueRef = useRef<QueueItem[]>([])

  useEffect(() => { queueRef.current = queue }, [queue])

  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    const cachedResults = loadFeedResults()
    const pinnedSet = new Set(PINNED_IDS)
    const remaining = VIDEO_IDS.filter(id => !pinnedSet.has(id))
    const shuffled = shuffleArray(remaining)
    const ordered = [...PINNED_IDS, ...shuffled]

    const initial: QueueItem[] = ordered.map(id => {
      const cached = cachedResults?.get(id)
      if (cached) {
        return { video_id: id, status: 'matched' as const, result: cached }
      }
      return { video_id: id, status: 'pending' as const }
    })

    setQueue(initial)
  }, [])

  // Sync feedItems from queue matched results, preserving injected MP4s
  useEffect(() => {
    setFeedItems(prev => {
      const matchedFromQueue = queue
        .filter(q => q.status === 'matched' && q.result)
        .map(q => q.result!)

      // On first populate (no existing items), just use queue results
      if (prev.length === 0) return matchedFromQueue

      // Merge: keep injected items at their positions, replace non-injected with queue order
      const result: FeedItem[] = []
      let qIdx = 0
      for (let i = 0; i < prev.length; i++) {
        if (prev[i].isInjected) {
          result.push(prev[i])
        } else if (qIdx < matchedFromQueue.length) {
          result.push(matchedFromQueue[qIdx++])
        }
      }
      // Append any new matched items (from a new batch)
      while (qIdx < matchedFromQueue.length) {
        result.push(matchedFromQueue[qIdx++])
      }

      return result
    })
  }, [queue])

  const addVideos = useCallback((videoIds: string[]) => {
    setQueue(prev => {
      const existingIds = new Set(prev.map(q => q.video_id))
      const newItems: QueueItem[] = videoIds
        .filter(id => !existingIds.has(id))
        .map(id => ({ video_id: id, status: 'pending' }))
      return [...prev, ...newItems]
    })
  }, [])

  const clearQueue = useCallback(() => {
    setQueue([])
    setFeedItems([])
  }, [])

  const processQueue = useCallback(async () => {
    if (isProcessing) return
    setIsProcessing(true)

    try {
      setQueue(prev => prev.map(item =>
        item.status === 'pending' ? { ...item, status: 'processing' } : item
      ))

      const pendingIds = queueRef.current
        .filter(q => q.status === 'pending' || q.status === 'processing')
        .map(q => q.video_id)
        .slice(0, BATCH_SIZE)

      if (pendingIds.length === 0) {
        setIsProcessing(false)
        return
      }

      const res = await fetch(`${API_URL}/shorts/feed?video_ids=${pendingIds.join(',')}`)

      if (!res.ok) {
        throw new Error('Failed to fetch feed')
      }

      const results: FeedItem[] = await res.json()
      const resultsMap = new Map(results.map(r => [r.youtube.video_id, r]))

      setQueue(prev => {
        const next = prev.map(item => {
          if (pendingIds.includes(item.video_id)) {
            const result = resultsMap.get(item.video_id)
            if (result) {
              return { ...item, status: 'matched' as const, result }
            }
            if (item.status === 'matched' && item.result) {
              return item
            }
            return { ...item, status: 'failed' as const, error: 'No match found', result: undefined }
          }
          return item
        })

        // Persist matched results to sessionStorage (exclude injected)
        const allMatched = next
          .filter(q => q.status === 'matched' && q.result)
          .map(q => q.result!)
        saveFeedResults(allMatched)

        return next
      })
    } catch (err) {
      setQueue(prev => prev.map(item => {
        if (item.status === 'processing') {
          return { ...item, status: 'failed', error: String(err) }
        }
        return item
      }))
    } finally {
      setIsProcessing(false)
    }
  }, [isProcessing])

  const insertMp4 = useCallback((
    currentIndex: number,
    keywords: string[],
    market: KalshiMarket,
    betSide: 'YES' | 'NO'
  ) => {
    const entry = findVisualizationVideo(keywords)
    if (!entry || entry.source.type !== 'mp4') return

    const injectedItem: FeedItem = {
      id: `injected-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      youtube: { video_id: '', title: '', thumbnail: '', channel: '' },
      video: { type: 'mp4', url: entry.source.url, title: entry.label },
      kalshi: [market],
      isInjected: true,
      injectedByBetSide: betSide,
    }

    const offset = 3 + Math.floor(Math.random() * 3) // 3, 4, or 5

    setFeedItems(prev => {
      const insertIdx = Math.min(currentIndex + offset, prev.length)
      const next = [...prev]
      next.splice(insertIdx, 0, injectedItem)
      return next
    })
  }, [])

  const stats = useMemo(() => ({
    total: queue.length,
    pending: queue.filter(q => q.status === 'pending').length,
    processing: queue.filter(q => q.status === 'processing').length,
    matched: queue.filter(q => q.status === 'matched').length,
    failed: queue.filter(q => q.status === 'failed').length,
  }), [queue])

  const feedError = useMemo(() => {
    const failed = queue.find(q => q.status === 'failed' && q.error)
    return failed?.error ?? null
  }, [queue])

  const retryFailed = useCallback(() => {
    setQueue(prev =>
      prev.map(item =>
        item.status === 'failed'
          ? { ...item, status: 'pending' as const, error: undefined }
          : item
      )
    )
  }, [])

  return {
    queue,
    feedItems,
    stats,
    feedError,
    isProcessing,
    addVideos,
    clearQueue,
    processQueue,
    retryFailed,
    insertMp4,
  }
}
