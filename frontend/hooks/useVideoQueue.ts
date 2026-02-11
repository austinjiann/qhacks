'use client'

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { FeedItem, KalshiMarket } from '@/types'

const SESSION_RESULTS_KEY = 'feed_results'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10
const GENERATED_POLL_INTERVAL = 30_000
const PREFETCH_THRESHOLD = 15
const QUEUE_MAX = 25

function saveFeedResults(items: FeedItem[]) {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.setItem(SESSION_RESULTS_KEY, JSON.stringify(items))
  } catch { /* quota exceeded — non-critical */ }
}

function loadFeedResults(): FeedItem[] | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(SESSION_RESULTS_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || parsed.length === 0) return null
    return parsed as FeedItem[]
  } catch {
    return null
  }
}

export function useVideoQueue() {
  const [feedItems, setFeedItems] = useState<FeedItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [feedError, setFeedError] = useState<string | null>(null)
  const initializedRef = useRef(false)
  const seenVideoIds = useRef<Set<string>>(new Set())
  const fetchingMore = useRef(false)
  const currentIndexRef = useRef(0)

  // Load cached results or fetch initial batch on mount
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    const cached = loadFeedResults()
    if (cached && cached.length > 0) {
      setFeedItems(cached)
      for (const item of cached) {
        if (item.youtube?.video_id) seenVideoIds.current.add(item.youtube.video_id)
      }
      return
    }

    // Fetch initial batch
    fetchBatch(BATCH_SIZE)
  }, [])

  const fetchBatch = useCallback(async (count: number) => {
    setIsLoading(true)
    setFeedError(null)
    try {
      const excludeParam = seenVideoIds.current.size > 0
        ? `&exclude=${Array.from(seenVideoIds.current).join(',')}`
        : ''
      const res = await fetch(`${API_URL}/pool/feed?count=${count}${excludeParam}`)
      if (!res.ok) throw new Error('Failed to fetch feed')

      const results: FeedItem[] = await res.json()

      for (const item of results) {
        if (item.youtube?.video_id) seenVideoIds.current.add(item.youtube.video_id)
      }

      setFeedItems(prev => {
        const next = [...prev, ...results]
        // Persist non-injected items
        saveFeedResults(next.filter(i => !i.isInjected))
        return next
      })
    } catch (err) {
      setFeedError(String(err))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const setCurrentIndex = useCallback((index: number) => {
    currentIndexRef.current = index
  }, [])

  // Request more items when user nears end of feed
  const requestMore = useCallback((currentIndex?: number) => {
    if (fetchingMore.current || isLoading) return
    const idx = currentIndex ?? currentIndexRef.current
    const unwatched = feedItems.length - idx
    if (unwatched >= QUEUE_MAX || unwatched > PREFETCH_THRESHOLD) return

    fetchingMore.current = true
    fetchBatch(BATCH_SIZE).finally(() => {
      fetchingMore.current = false
    })
  }, [fetchBatch, isLoading, feedItems.length])

  // Poll for generated videos every 30s
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/pool/generated`)
        if (!res.ok) return
        const videos = await res.json()
        if (!Array.isArray(videos) || videos.length === 0) return

        for (const video of videos) {
          const injectedItem: FeedItem = {
            id: `generated-${video.job_id}`,
            youtube: { video_id: '', title: video.title || '', thumbnail: '', channel: '' },
            video: { type: 'mp4', url: video.video_url, title: video.title },
            kalshi: video.kalshi || [],
            isInjected: true,
            injectedByBetSide: video.bet_side || undefined,
          }

          setFeedItems(prev => {
            // Don't add if already present
            if (prev.some(item => item.id === injectedItem.id)) return prev
            return [injectedItem, ...prev]
          })

          // Mark as consumed
          fetch(`${API_URL}/pool/generated/${video.job_id}/consume`, { method: 'POST' }).catch(() => {})
        }
      } catch { /* ignore polling errors */ }
    }

    const interval = setInterval(poll, GENERATED_POLL_INTERVAL)
    // Run once on mount after a short delay
    const timeout = setTimeout(poll, 3000)
    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [])

  const requestVideoGeneration = useCallback(async (
    market: KalshiMarket,
    betSide: 'YES' | 'NO'
  ) => {
    try {
      const res = await fetch(`${API_URL}/jobs/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: market.question,
          outcome: `${betSide} - ${market.question}`,
          original_bet_link: `https://kalshi.com/events/${market.event_ticker || market.ticker}`,
          source_image_url: market.image_url || undefined,
          kalshi: [market],
          bet_side: betSide,
        }),
      })
      if (!res.ok) throw new Error('Failed to queue video generation')
      const data = await res.json()
      return data.job_id as string
    } catch (err) {
      console.error('Video generation request failed:', err)
      return null
    }
  }, [])

  const retryFailed = useCallback(() => {
    setFeedError(null)
    fetchBatch(BATCH_SIZE)
  }, [fetchBatch])

  const clearQueue = useCallback(() => {
    setFeedItems([])
    seenVideoIds.current.clear()
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem(SESSION_RESULTS_KEY)
    }
  }, [])

  const stats = useMemo(() => ({
    total: feedItems.length,
    pending: 0,
    processing: 0,
    matched: feedItems.filter(i => !i.isInjected).length,
    failed: 0,
  }), [feedItems])

  return {
    feedItems,
    stats,
    feedError,
    isProcessing: isLoading,
    retryFailed,
    clearQueue,
    requestVideoGeneration,
    requestMore,
    setCurrentIndex,
  }
}
