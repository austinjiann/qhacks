'use client'

import { useState, useCallback, useRef, useMemo } from 'react'
import { FeedItem, KalshiMarket } from '@/types'
import { MYSTERY_FEED } from '@/data/mystery'

const BATCH_SIZE = 10

// Module-level so it survives Fast Refresh / remounts
let _lastKnownIndex = 0

export function useVideoQueue(_onGenerationError?: (title: string, error: string) => void) {
  // Serve mystery items in order, cycling when exhausted
  const nextMysteryIdx = useRef(0)

  const getNextBatch = useCallback((count: number): FeedItem[] => {
    const batch: FeedItem[] = []
    for (let i = 0; i < count; i++) {
      const idx = nextMysteryIdx.current % MYSTERY_FEED.length
      // Create unique id per cycle so React keys don't collide
      const cycle = Math.floor(nextMysteryIdx.current / MYSTERY_FEED.length)
      const item = MYSTERY_FEED[idx]
      batch.push({
        ...item,
        id: cycle > 0 ? `${item.id}--cycle-${cycle}` : item.id,
      })
      nextMysteryIdx.current += 1
    }
    return batch
  }, [])

  const [feedItems, setFeedItems] = useState<FeedItem[]>(() => getNextBatch(BATCH_SIZE))
  const [isLoading] = useState(false)
  const [feedError] = useState<string | null>(null)
  const currentIndexRef = useRef(_lastKnownIndex)
  const fetchingMore = useRef(false)

  const setCurrentIndex = useCallback((index: number) => {
    currentIndexRef.current = index
    _lastKnownIndex = index
  }, [])

  // Append more mystery items when user nears end of feed
  const requestMore = useCallback((_currentIndex?: number) => {
    if (fetchingMore.current) return
    fetchingMore.current = true
    const batch = getNextBatch(BATCH_SIZE)
    setFeedItems(prev => [...prev, ...batch])
    fetchingMore.current = false
  }, [getNextBatch])

  // No-op: keep the interface but don't actually generate videos
  const requestVideoGeneration = useCallback(async (
    _market: KalshiMarket,
    _tradeSide: 'YES' | 'NO'
  ) => {
    // Video generation disconnected — animations still play via page.tsx
    return null
  }, [])

  const retryFailed = useCallback(() => {}, [])

  const removeItem = useCallback((itemId: string) => {
    setFeedItems(prev => prev.filter(i => i.id !== itemId))
  }, [])

  const clearQueue = useCallback(() => {
    setFeedItems([])
    nextMysteryIdx.current = 0
  }, [])

  const stats = useMemo(() => ({
    total: feedItems.length,
    pending: 0,
    processing: 0,
    matched: feedItems.length,
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
