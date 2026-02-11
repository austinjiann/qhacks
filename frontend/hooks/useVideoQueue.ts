'use client'

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { collection, query, where, onSnapshot } from 'firebase/firestore'
import { db } from '@/lib/firebase'
import { FeedItem, KalshiMarket } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10
const PREFETCH_THRESHOLD = 15
const QUEUE_MAX = 25

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

      setFeedItems(prev => [...prev, ...results])
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

  // Real-time Firestore listener for generated videos
  useEffect(() => {
    const q = query(
      collection(db, 'generated_videos'),
      where('consumed', '==', false),
    )

    const unsubscribe = onSnapshot(q, (snapshot) => {
      for (const change of snapshot.docChanges()) {
        if (change.type === 'added') {
          const video = change.doc.data()
          const jobId = change.doc.id

          console.log(`[pipeline] 10. Firestore snapshot: new video — job_id=${jobId}, url=${video.video_url}`)

          const injectedItem: FeedItem = {
            id: `generated-${jobId}`,
            youtube: { video_id: '', title: video.title || '', thumbnail: '', channel: '' },
            video: { type: 'mp4', url: video.video_url, title: video.title },
            kalshi: video.kalshi || [],
            isInjected: true,
            injectedByTradeSide: video.trade_side || undefined,
          }

          setFeedItems(prev => {
            if (prev.some(item => item.id === injectedItem.id)) {
              console.log(`[pipeline] ↳ Already in feed, skipping`)
              return prev
            }
            console.log(`[pipeline] 11. Video injected at front of feed!`)
            return [injectedItem, ...prev]
          })

          // Mark as consumed via backend
          fetch(`${API_URL}/pool/generated/${jobId}/consume`, { method: 'POST' }).catch(() => {})
        }
      }
    }, (error) => {
      console.error('[pipeline] Firestore listener error:', error)
    })

    return () => unsubscribe()
  }, [])

  const requestVideoGeneration = useCallback(async (
    market: KalshiMarket,
    tradeSide: 'YES' | 'NO'
  ) => {
    console.log(`[pipeline] 3. POST /jobs/create — title="${market.question}", side=${tradeSide}`)
    try {
      const res = await fetch(`${API_URL}/jobs/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: market.question,
          outcome: `${tradeSide} - ${market.question}`,
          original_trade_link: `https://kalshi.com/events/${market.event_ticker || market.ticker}`,
          source_image_url: market.image_url || undefined,
          kalshi: [market],
          trade_side: tradeSide,
        }),
      })
      if (!res.ok) {
        console.error(`[pipeline] ✗ /jobs/create failed with status ${res.status}`)
        throw new Error('Failed to queue video generation')
      }
      const data = await res.json()
      console.log(`[pipeline] 4. Job created — job_id=${data.job_id}`)
      return data.job_id as string
    } catch (err) {
      console.error('[pipeline] ✗ Video generation request failed:', err)
      return null
    }
  }, [])

  const retryFailed = useCallback(() => {
    setFeedError(null)
    fetchBatch(BATCH_SIZE)
  }, [fetchBatch])

  const removeItem = useCallback((itemId: string) => {
    setFeedItems(prev => prev.filter(i => i.id !== itemId))
  }, [])

  const clearQueue = useCallback(() => {
    setFeedItems([])
    seenVideoIds.current.clear()
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
    removeItem,
    requestMore,
    setCurrentIndex,
  }
}
