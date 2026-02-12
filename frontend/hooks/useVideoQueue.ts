'use client'

import { useState, useCallback, useRef, useMemo, useEffect } from 'react'
import { FeedItem, KalshiMarket } from '@/types'
import { MYSTERY_FEED } from '@/data/mystery'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10

// Deterministic seeded PRNG so the same ticker always gets the same graph
function seededRng(ticker: string): () => number {
  let seed = 0
  for (let i = 0; i < ticker.length; i++) seed = (seed * 31 + ticker.charCodeAt(i)) | 0
  seed = Math.abs(seed) || 1
  return () => {
    seed = (seed * 16807) % 2147483647
    return (seed - 1) / 2147483646
  }
}

function generateSyntheticHistory(ticker: string, yesPrice: number): { ts: number; price: number }[] {
  const rng = seededRng(ticker)
  const now = Math.floor(Date.now() / 1000)
  const points = 200
  const span = 30 * 24 * 3600 // 30 days
  const step = span / points

  const startPrice = Math.max(5, Math.min(95, yesPrice + (rng() - 0.5) * 20))
  const history: { ts: number; price: number }[] = []
  let price = startPrice

  for (let i = 0; i <= points; i++) {
    history.push({ ts: now - span + i * step, price: Math.max(1, Math.min(99, Math.round(price))) })
    const drift = (yesPrice - price) * 0.01
    const noise = (rng() - 0.5) * 3
    price += drift + noise
  }
  history[history.length - 1].price = yesPrice
  return history
}

// Module-level so it survives Fast Refresh / remounts
let _lastKnownIndex = 0

export function useVideoQueue(_onGenerationError?: (title: string, error: string) => void) {
  const nextMysteryIdx = useRef(0)
  // Stores kalshi data from the API so later batches can use it
  const kalshiMapRef = useRef<Map<string, KalshiMarket[]>>(new Map())

  const getNextBatch = useCallback((count: number): FeedItem[] => {
    const batch: FeedItem[] = []
    for (let i = 0; i < count; i++) {
      // Stop at the end — don't cycle
      if (nextMysteryIdx.current >= MYSTERY_FEED.length) break
      const idx = nextMysteryIdx.current
      const item = MYSTERY_FEED[idx]
      // Use API-fetched kalshi data if available, fall back to hardcoded
      const apiKalshi = kalshiMapRef.current.get(item.youtube.video_id)
      const baseKalshi = apiKalshi ?? item.kalshi
      // Pre-fill synthetic price history so charts are ready immediately
      const kalshi = baseKalshi?.length
        ? baseKalshi.map(m => ({
            ...m,
            price_history: m.price_history?.length
              ? m.price_history
              : generateSyntheticHistory(m.ticker, m.yes_price),
          }))
        : undefined
      batch.push({
        ...item,
        id: item.id,
        ...(kalshi ? { kalshi } : {}),
      })
      nextMysteryIdx.current += 1
    }
    return batch
  }, [])

  const [feedItems, setFeedItems] = useState<FeedItem[]>(() => getNextBatch(BATCH_SIZE))
  const [isLoading] = useState(false)
  const [feedError] = useState<string | null>(null)

  // Fetch real Kalshi market data for YouTube videos on mount
  useEffect(() => {
    const videoIds = MYSTERY_FEED
      .map(item => item.youtube.video_id)
      .filter(id => id !== '')
    if (videoIds.length === 0) return

    let cancelled = false
    ;(async () => {
      try {
        const params = new URLSearchParams({
          video_ids: videoIds.join(','),
          limit: '25',
        })
        const res = await fetch(`${API_URL}/shorts/feed?${params}`)
        if (!res.ok || cancelled) return
        const data: { youtube: { video_id: string }; kalshi: KalshiMarket[] }[] = await res.json()

        // Build lookup: video_id → kalshi[]
        const kalshiByVideoId = new Map<string, KalshiMarket[]>()
        for (const item of data) {
          if (item.youtube?.video_id && item.kalshi?.length) {
            kalshiByVideoId.set(item.youtube.video_id, item.kalshi)
          }
        }

        if (cancelled) return

        // Store in ref so future getNextBatch calls can use it
        kalshiMapRef.current = kalshiByVideoId

        // Apply to all current feed items
        setFeedItems(prev =>
          prev.map(fi => {
            const realKalshi = kalshiByVideoId.get(fi.youtube.video_id)
            const kalshi = realKalshi ?? fi.kalshi
            if (!kalshi?.length) return fi
            return {
              ...fi,
              kalshi: kalshi.map(m => ({
                ...m,
                price_history: m.price_history?.length
                  ? m.price_history
                  : generateSyntheticHistory(m.ticker, m.yes_price),
              })),
            }
          })
        )
      } catch {
        // Backend unreachable — still add synthetic price_history so graphs render
        if (!cancelled) {
          setFeedItems(prev =>
            prev.map(fi => {
              if (!fi.kalshi?.length) return fi
              const needsHistory = fi.kalshi.some(m => !m.price_history?.length)
              if (!needsHistory) return fi
              return {
                ...fi,
                kalshi: fi.kalshi.map(m => ({
                  ...m,
                  price_history: m.price_history?.length
                    ? m.price_history
                    : generateSyntheticHistory(m.ticker, m.yes_price),
                })),
              }
            })
          )
        }
      }
    })()

    return () => { cancelled = true }
  }, [])
  const currentIndexRef = useRef(_lastKnownIndex)
  const fetchingMore = useRef(false)

  const setCurrentIndex = useCallback((index: number) => {
    currentIndexRef.current = index
    _lastKnownIndex = index
  }, [])

  // Append more mystery items when user nears end of feed
  const requestMore = useCallback((_currentIndex?: number) => {
    if (fetchingMore.current) return
    if (nextMysteryIdx.current >= MYSTERY_FEED.length) return // exhausted
    fetchingMore.current = true
    const batch = getNextBatch(BATCH_SIZE)
    if (batch.length > 0) {
      setFeedItems(prev => [...prev, ...batch])
    }
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
