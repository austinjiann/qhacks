'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import dynamic from 'next/dynamic'
import Image from 'next/image'
import { motion, AnimatePresence } from 'framer-motion'
import { Iphone } from '@/components/ui/iphone'
import Feed, { FeedRef } from '@/components/Feed'
import { KalshiMarket } from '@/types'
import { useVideoQueue } from '@/hooks/useVideoQueue'
import PriceChart, { type PriceChartReadyPayload } from '@/components/PriceChart'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const MAX_PREFETCH_CONCURRENCY = 3

const toUnixSeconds = (value?: string | number | null): number | null => {
  if (value == null) return null
  if (typeof value === 'number') {
    if (!Number.isFinite(value) || value <= 0) return null
    return value > 10_000_000_000 ? Math.trunc(value / 1000) : Math.trunc(value)
  }
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed) return null
  if (/^\d+$/.test(trimmed)) {
    const numeric = Number(trimmed)
    if (!Number.isFinite(numeric) || numeric <= 0) return null
    return numeric > 10_000_000_000 ? Math.trunc(numeric / 1000) : Math.trunc(numeric)
  }
  const normalizedFraction = trimmed.replace(
    /(\.\d{3})\d+(?=Z|[+-]\d{2}:\d{2}$)/,
    '$1'
  )
  const parsedMs = Date.parse(normalizedFraction)
  if (Number.isNaN(parsedMs) || parsedMs <= 0) return null
  return Math.trunc(parsedMs / 1000)
}

const resolveMarketStartTs = (market: KalshiMarket): number | null => {
  if (
    typeof market.market_start_ts === 'number' &&
    Number.isFinite(market.market_start_ts) &&
    market.market_start_ts > 0
  ) {
    return Math.trunc(market.market_start_ts)
  }
  return toUnixSeconds(market.created_time) ?? toUnixSeconds(market.open_time)
}

const CharacterPreview = dynamic(() => import('@/components/CharacterPreview'), { ssr: false })

const TIPS = [
  { text: 'Welcome to Kalship!', animation: 'wave' as const },
  { text: "Today we're gonna scroll and trade on Kalshi.", animation: 'idle' as const },
  { text: 'Scroll through shorts right here.', animation: 'point' as const },
  { text: 'Tap YES or NO to place a trade!', animation: 'point' as const },
  { text: "Let's go!", animation: 'wave' as const },
]

const FEED_TIP = 'Swipe up for the next short'
const SPEECH_BUBBLE_OFFSET_PX = 48

const easeCubic = [0.22, 1, 0.36, 1] as const

const BgWrapper = ({
  children,
  blurred = true,
}: {
  children: ReactNode
  blurred?: boolean
}) => (
  <div className="relative min-h-screen overflow-hidden">
    {/* Background layer — blur controlled by prop with CSS transition */}
    <div
      className="absolute inset-0"
      style={{
        backgroundImage: 'url(/office-bg.jpeg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        filter: blurred ? 'blur(6px)' : 'blur(0px)',
        transform: blurred ? 'scale(1.08)' : 'scale(1.02)',
        transition: 'filter 1s ease, transform 1s ease',
      }}
    />
    {/* Extra blur overlay for blurred state */}
    <div
      className="absolute inset-0"
      style={{
        backgroundImage: 'url(/office-bg.jpeg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        filter: 'blur(6px)',
        transform: 'scale(1.08)',
        opacity: blurred ? 1 : 0,
        transition: 'opacity 1s ease',
        maskImage: 'radial-gradient(ellipse 50% 50% at center, transparent 0%, black 70%)',
        WebkitMaskImage: 'radial-gradient(ellipse 50% 50% at center, transparent 0%, black 70%)',
      }}
    />
    <div className="relative z-10 h-screen flex items-center justify-center">
      {children}
    </div>
    <div
      className="fixed z-20 pointer-events-none select-none"
      style={{
        top: '1.5rem',
        left: '1.5rem',
      }}
    >
      <Image
        src="/kalship-logo-white.png"
        alt="Kalship logo"
        width={220}
        height={72}
        priority
        className="h-auto w-[min(12vw,220px)] min-w-[150px]"
        style={{ filter: 'drop-shadow(0 0 10px rgba(74, 201, 151, 0.62)) drop-shadow(0 0 22px rgba(74, 201, 151, 0.38))' }}
      />
    </div>
  </div>
)

function SpeechBubble({ text, children, large }: { text?: string; children?: ReactNode; large?: boolean }) {
  return (
    <div
      className={`relative bg-white/95 text-gray-900 rounded-2xl font-medium ${
        large ? 'px-10 py-6 max-w-[520px] text-xl leading-relaxed' : 'px-6 py-4 max-w-[300px] text-sm'
      }`}
      style={{ boxShadow: '0 4px 24px rgba(0,0,0,0.25), 0 1px 4px rgba(0,0,0,0.1)', border: '1px solid rgba(0,0,0,0.12)' }}
    >
      {children ?? text}
      {/* Triangle pointer at bottom-center */}
      <div
        className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0"
        style={{
          borderLeft: '8px solid transparent',
          borderRight: '8px solid transparent',
          borderTop: '8px solid rgba(255,255,255,0.95)',
        }}
      />
    </div>
  )
}

export default function Home() {
  const [tradeConfirmation, setTradeConfirmation] = useState<{ side: 'YES' | 'NO'; message: string } | null>(null)
  const handleGenerationError = useCallback((title: string, error: string) => {
    console.error(`[generation] Failed: ${title} — ${error}`)
    setTradeConfirmation({
      side: 'NO',
      message: `Video generation failed — try a different trade!`,
    })
  }, [])
  const { feedItems, feedError, isProcessing, retryFailed, clearQueue, requestVideoGeneration, removeItem, requestMore, setCurrentIndex } = useVideoQueue(handleGenerationError)
  const currentIndexRef = useRef(0)
  const [currentMarkets, setCurrentMarkets] = useState<KalshiMarket[]>([])
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [imgError, setImgError] = useState(false)
  const [historyByTicker, setHistoryByTicker] = useState<Record<string, { ts: number; price: number }[]>>({})
  const [historyLoadingByTicker, setHistoryLoadingByTicker] = useState<Record<string, boolean>>({})
  const [chartStatusByTicker, setChartStatusByTicker] = useState<Record<string, PriceChartReadyPayload['status']>>({})
  const [stage, setStage] = useState(0) // 0-4 = tutorial, 5 = feed
  const [waitingForFeed, setWaitingForFeed] = useState(false)
  const feedRef = useRef<FeedRef>(null)
  const historyFetchInFlight = useRef<Set<string>>(new Set())
  const historyByTickerRef = useRef(historyByTicker)
  const isFeed = stage === 5
  const [currentIsInjected, setCurrentIsInjected] = useState(false)
  const [showTradeInput, setShowTradeInput] = useState<{ side: 'YES' | 'NO' } | null>(null)
  const [tradeAmount, setTradeAmount] = useState('')
  const [adviceLoading, setAdviceLoading] = useState(false)
  const [adviceText, setAdviceText] = useState<string | null>(null)

  // Keep ref in sync with state
  useEffect(() => {
    historyByTickerRef.current = historyByTicker
  }, [historyByTicker])

  // Hydrate historyByTicker from sessionStorage on mount
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('history_cache')
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          setHistoryByTicker(parsed)
        }
      }
    } catch { /* ignore */ }
  }, [])

  const updateHistoryCache = useCallback((ticker: string, data?: { ts: number; price: number }[]) => {
    setHistoryByTicker((prev) => {
      const hasExisting = Object.prototype.hasOwnProperty.call(prev, ticker)
      const sanitized = Array.isArray(data) ? data : []
      if (sanitized.length === 0) {
        if (hasExisting) {
          return prev
        }
        const next = { ...prev, [ticker]: [] }
        try { sessionStorage.setItem('history_cache', JSON.stringify(next)) } catch { /* quota */ }
        return next
      }
      if (hasExisting && (prev[ticker]?.length ?? 0) >= sanitized.length) {
        return prev
      }
      const next = { ...prev, [ticker]: sanitized }
      try { sessionStorage.setItem('history_cache', JSON.stringify(next)) } catch { /* quota */ }
      return next
    })
  }, [])

  const prefetchMarkets = useMemo(() => {
    const deduped: Record<string, KalshiMarket & { series_ticker: string }> = {}
    for (const item of feedItems) {
      const market = item.kalshi?.[0]
      if (!market || !market.series_ticker || !market.ticker) continue
      if (!deduped[market.ticker]) {
        deduped[market.ticker] = market as KalshiMarket & { series_ticker: string }
      }
    }
    return Object.values(deduped)
  }, [feedItems])

  const allMarkets = useMemo(() => {
    const deduped: Record<string, KalshiMarket & { series_ticker: string }> = {}
    for (const item of feedItems) {
      for (const market of item.kalshi ?? []) {
        if (!market || !market.series_ticker || !market.ticker) continue
        if (!deduped[market.ticker]) {
          deduped[market.ticker] = market as KalshiMarket & { series_ticker: string }
        }
      }
    }
    return Object.values(deduped)
  }, [feedItems])

  const { readyCount: readyMarketCount, totalCount: totalMarketCount } = useMemo(() => {
    const total = prefetchMarkets.length
    let ready = 0
    for (const market of prefetchMarkets) {
      const hasCached = Object.prototype.hasOwnProperty.call(historyByTicker, market.ticker)
      const hasPrefilled = Array.isArray(market.price_history) && market.price_history.length > 0
      if (hasCached || hasPrefilled) {
        ready += 1
      }
    }
    return { readyCount: ready, totalCount: total }
  }, [prefetchMarkets, historyByTicker])

  const chartsReady = totalMarketCount === 0 || readyMarketCount === totalMarketCount

  useEffect(() => {
    if (prefetchMarkets.length === 0) return
    for (const market of prefetchMarkets) {
      if (Array.isArray(market.price_history) && market.price_history.length > 0) {
        updateHistoryCache(market.ticker, market.price_history)
      }
    }
  }, [prefetchMarkets, updateHistoryCache])

  const schedulePrefetch = useCallback(
    (markets: (KalshiMarket & { series_ticker: string })[]) => {
      let cancelled = false
      if (markets.length === 0) return () => {}
      const inFlightSet = historyFetchInFlight.current
      const marketsToFetch = markets.filter((market) => {
        if (!market.ticker || !market.series_ticker) return false
        if (Object.prototype.hasOwnProperty.call(historyByTickerRef.current, market.ticker)) return false
        if (Array.isArray(market.price_history) && market.price_history.length > 0) return false
        if (inFlightSet.has(market.ticker)) return false
        return true
      })
      if (marketsToFetch.length === 0) return () => {}

      const queuedTickers = marketsToFetch.map((market) => market.ticker)
      queuedTickers.forEach((ticker) => {
        inFlightSet.add(ticker)
        setHistoryLoadingByTicker((prev) => (prev[ticker] ? prev : { ...prev, [ticker]: true }))
      })
      const startedTickers = new Set<string>()

      const fetchHistory = async (market: KalshiMarket & { series_ticker: string }) => {
        startedTickers.add(market.ticker)
        try {
          const params = new URLSearchParams({
            ticker: market.ticker,
            series_ticker: market.series_ticker,
            period: '60',
            end_ts: `${Math.floor(Date.now() / 1000)}`,
          })
          const startTs = resolveMarketStartTs(market)
          if (startTs) {
            params.set('start_ts', `${startTs}`)
          } else {
            params.set('hours', `${24 * 30}`)
          }
          const response = await fetch(`${API_URL}/shorts/candlesticks?${params.toString()}`)
          if (!response.ok || cancelled) {
            if (!cancelled) updateHistoryCache(market.ticker, [])
            return
          }
          const json = await response.json()
          const candles: { ts: number; price: number }[] = Array.isArray(json.candlesticks)
            ? json.candlesticks
            : []
          if (cancelled) return
          updateHistoryCache(market.ticker, candles)
        } catch (err) {
          console.error(`[prefetch] Failed to load ${market.ticker}`, err)
          if (!cancelled) {
            updateHistoryCache(market.ticker, [])
          }
        } finally {
          inFlightSet.delete(market.ticker)
          setHistoryLoadingByTicker((prev) => {
            if (!prev[market.ticker]) return prev
            const next = { ...prev }
            delete next[market.ticker]
            return next
          })
        }
      }

      const runBatches = async () => {
        const concurrency = Math.min(MAX_PREFETCH_CONCURRENCY, marketsToFetch.length)
        for (let i = 0; i < marketsToFetch.length && !cancelled; i += concurrency) {
          const batch = marketsToFetch.slice(i, i + concurrency)
          await Promise.all(batch.map((market) => fetchHistory(market)))
        }
      }
      runBatches()

      return () => {
        cancelled = true
        for (const ticker of queuedTickers) {
          if (!startedTickers.has(ticker)) {
            inFlightSet.delete(ticker)
            setHistoryLoadingByTicker((prev) => {
              if (!prev[ticker]) return prev
              const next = { ...prev }
              delete next[ticker]
              return next
            })
          }
        }
      }
    },
    [updateHistoryCache]
  )

  useEffect(() => schedulePrefetch(prefetchMarkets), [prefetchMarkets, schedulePrefetch])


  useEffect(() => {
    if (!isFeed || currentMarkets.length === 0) return
    const typed = currentMarkets.filter(
      (market): market is KalshiMarket & { series_ticker: string } =>
        Boolean(market.series_ticker && market.ticker)
    )
    if (typed.length === 0) return
    return schedulePrefetch(typed)
  }, [isFeed, currentMarkets, schedulePrefetch])

  useEffect(() => {
    if (!isFeed || allMarkets.length === 0) return
    return schedulePrefetch(allMarkets)
  }, [isFeed, allMarkets, schedulePrefetch])

  const canEnterFeed = feedItems.length > 0 && chartsReady

  // Spacebar to advance tutorial stages
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'Space' && stage < 5) {
        e.preventDefault()
        if (stage === 4) {
          if (canEnterFeed) {
            setStage(5)
            setWaitingForFeed(false)
          } else {
            setWaitingForFeed(true)
          }
        } else {
          setStage((s) => s + 1)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [stage, canEnterFeed])

  // Auto-transition when feed + graphs become ready while waiting
  useEffect(() => {
    if (waitingForFeed && canEnterFeed) {
      const t = setTimeout(() => {
        setStage(5)
        setWaitingForFeed(false)
      }, 800)
      return () => clearTimeout(t)
    }
  }, [waitingForFeed, canEnterFeed])

  const expandedMarket = currentMarkets[selectedIdx] as KalshiMarket | undefined
  const historyEntryExists = expandedMarket
    ? Object.prototype.hasOwnProperty.call(historyByTicker, expandedMarket.ticker)
    : false
  const resolvedPriceHistory = expandedMarket
    ? historyEntryExists
      ? historyByTicker[expandedMarket.ticker]
      : expandedMarket.price_history
    : undefined
  const chartStatus = expandedMarket ? chartStatusByTicker[expandedMarket.ticker] : undefined
  const graphStatus: 'ready' | 'loading' | 'empty' = (() => {
    if (!expandedMarket) return 'ready'
    // PriceChart has definitively reported its status
    if (chartStatus === 'ok') return 'ready'
    if (chartStatus === 'empty') return 'empty'
    if (chartStatus === 'error') {
      return resolvedPriceHistory && resolvedPriceHistory.length > 0 ? 'ready' : 'empty'
    }
    // chartStatus undefined — PriceChart hasn't reported yet
    // If we have seed data, PriceChart will render it on the next frame
    if (resolvedPriceHistory && resolvedPriceHistory.length > 0) return 'ready'
    // Prefetch completed but returned nothing — no data exists for this market
    if (historyEntryExists) return 'empty'
    // Still waiting for any data
    return 'loading'
  })()

  const handleTrade = useCallback((side: 'YES' | 'NO') => {
    if (!expandedMarket) return
    console.log(`[pipeline] 1. Trade button pressed: ${side} on ${expandedMarket.ticker}`)

    if (currentIsInjected) {
      console.log('[pipeline] ↳ Injected reel — showing trade input instead of generating video')
      setShowTradeInput({ side })
      setTradeAmount('')
      return
    }

    console.log('[pipeline] 2. Requesting video generation...')
    requestVideoGeneration(expandedMarket, side)

    setTradeConfirmation({
      side,
      message: `You traded ${side}! Your video is being generated!`,
    })
  }, [expandedMarket, requestVideoGeneration, currentIsInjected])

  const handleCurrentItemChange = useCallback((item: { kalshi?: KalshiMarket[]; youtube?: { title?: string }; isInjected?: boolean }, index: number) => {
    currentIndexRef.current = index
    setCurrentIndex(index)
    const markets = item.kalshi ?? []
    setCurrentMarkets(markets)

    // Try to pick the most relevant market based on video title
    let bestIdx = 0
    if (markets.length > 1 && item.youtube?.title) {
      const titleWords = item.youtube.title.toLowerCase().split(/\s+/)
      let bestScore = 0
      for (let i = 0; i < markets.length; i++) {
        const qWords = markets[i].question.toLowerCase().split(/\s+/)
        const score = titleWords.filter(w => w.length > 2 && qWords.includes(w)).length
        if (score > bestScore) {
          bestScore = score
          bestIdx = i
        }
      }
      // No match found — pick random instead of defaulting to 0
      if (bestScore === 0) {
        bestIdx = Math.floor(Math.random() * markets.length)
      }
    }
    setSelectedIdx(bestIdx)

    setImgError(false)
    setCurrentIsInjected(!!item.isInjected)
  }, [setCurrentIndex])

  const handleChartReady = useCallback(
    (ticker: string, payload?: PriceChartReadyPayload) => {
      if (!payload) return
      setChartStatusByTicker((prev) => (prev[ticker] === payload.status ? prev : { ...prev, [ticker]: payload.status }))
      if (payload.status === 'ok' && payload.data && payload.data.length > 0) {
        updateHistoryCache(ticker, payload.data)
      } else if (payload.status === 'empty') {
        updateHistoryCache(ticker, [])
      }
    },
    [updateHistoryCache, setChartStatusByTicker]
  )

  const dismissTradeInput = useCallback(() => {
    setShowTradeInput(null)
    setTradeAmount('')
  }, [])

  const submitTradeAdvice = useCallback(async () => {
    if (!expandedMarket || !showTradeInput || !tradeAmount) return
    const amount = parseFloat(tradeAmount)
    if (isNaN(amount) || amount <= 0) return
    setAdviceLoading(true)
    try {
      const res = await fetch(`${API_URL}/shorts/advice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: expandedMarket.question,
          side: showTradeInput.side,
          amount,
          yes_price: expandedMarket.yes_price ?? 50,
          no_price: expandedMarket.no_price ?? 50,
        }),
      })
      const data = await res.json()
      setAdviceText(data.advice || 'No advice available right now.')
    } catch {
      setAdviceText('Hmm, I couldn\'t get advice right now. Try again!')
    } finally {
      setAdviceLoading(false)
      setShowTradeInput(null)
      setTradeAmount('')
    }
  }, [expandedMarket, showTradeInput, tradeAmount])

  const dismissAdvice = useCallback(() => {
    setAdviceText(null)
  }, [])

  // Escape key dismisses overlays
  useEffect(() => {
    if (!showTradeInput && !adviceText) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (adviceText) dismissAdvice()
        else if (showTradeInput) dismissTradeInput()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [showTradeInput, dismissTradeInput, adviceText, dismissAdvice])

  // Auto-dismiss trade confirmation after 3 seconds
  useEffect(() => {
    if (!tradeConfirmation) return
    const t = setTimeout(() => setTradeConfirmation(null), 3000)
    return () => clearTimeout(t)
  }, [tradeConfirmation])

  const currentAnimation = waitingForFeed && stage === 4 ? 'idle' : isFeed ? 'idle' : (TIPS[stage]?.animation ?? 'idle')
  const waitingMessage = feedItems.length === 0 ? 'Loading shorts...' : 'Hang tight...'
  const currentTipText = isFeed ? FEED_TIP : (waitingForFeed && stage === 4 ? waitingMessage : (TIPS[stage]?.text ?? ''))

  const overlayActive = !!tradeConfirmation || !!showTradeInput || !!adviceText

  // rotationY per stage: point stages face toward phone, feed faces phone more
  const currentRotationY = isFeed ? 0.8 : (currentAnimation === 'point' ? 0.4 : 0.3)

  // Phone content shared by both tutorial and feed views
  const phoneContent = feedItems.length > 0 ? (
    <Feed ref={feedRef} items={feedItems} onCurrentItemChange={handleCurrentItemChange} onNearEnd={(idx) => requestMore(idx)} onDelete={removeItem} paused={overlayActive} />
  ) : (
    <div className="flex flex-col items-center justify-center h-full bg-black gap-3 p-4">
      <div className="text-white/30 text-sm">
        {isProcessing ? 'Loading shorts...' : feedError ? 'Error loading feed' : 'No shorts loaded'}
      </div>
      {feedError && (
        <div className="text-red-400/80 text-xs text-center max-w-[260px]">
          {feedError.includes('fetch') || feedError.includes('Failed to fetch')
            ? 'Backend was unreachable.'
            : feedError}
        </div>
      )}
      {!isProcessing && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={retryFailed}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-white/15 text-white hover:bg-white/25 transition-colors"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={clearQueue}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-white/10 text-white/60 hover:bg-white/15 hover:text-white/80 transition-colors"
          >
            Reset
          </button>
        </div>
      )}
    </div>
  )

  return (
    <BgWrapper blurred={stage >= 2}>
      <div
        className="relative flex items-center justify-center max-h-screen w-full -mt-4 sm:-mt-6 gap-10"
        style={{ fontFamily: 'var(--font-playfair), serif' }}
      >
        {/* Character + speech bubble — hidden in feed view */}
        <AnimatePresence>
          {!isFeed && (
            <motion.div
              key="character"
              className="z-20 flex-shrink-0"
              animate={{
                x: stage >= 2 ? -480 : 0,
              }}
              exit={{ opacity: 0, x: -540 }}
              transition={{ duration: 0.8, ease: easeCubic }}
              style={{
                position: stage >= 2 ? 'absolute' : 'relative',
              }}
            >
              <div className="relative flex flex-col items-center">
                <div className="relative w-full flex justify-center items-end mt-40 h-[68px]">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={`tip-${stage}-${waitingForFeed}`}
                      initial={{ opacity: 0, y: SPEECH_BUBBLE_OFFSET_PX + 10, rotate: -2 }}
                      animate={{ opacity: 1, y: SPEECH_BUBBLE_OFFSET_PX, rotate: 0 }}
                      exit={{ opacity: 0, y: SPEECH_BUBBLE_OFFSET_PX - 8, rotate: 2 }}
                      transition={{ duration: 0.35, ease: 'easeOut' }}
                    >
                      {stage === 0 && !waitingForFeed ? (
                        <SpeechBubble large>
                          <span className="inline-flex items-center">
                            <span>Welcome to</span>
                            <Image
                              src="/kalship-text.png"
                              alt="Kalship"
                              width={200}
                              height={66}
                              className="inline-block"
                              style={{ height: '1em', width: 'auto', marginLeft: '0.4em', verticalAlign: 'middle', transform: 'translateY(0.1em)' }}
                            />
                          </span>
                        </SpeechBubble>
                      ) : (
                        <SpeechBubble text={currentTipText} large={stage < 2} />
                      )}
                    </motion.div>
                  </AnimatePresence>
                </div>
                <CharacterPreview
                  animation={currentAnimation}
                  size={{ width: 500, height: 600 }}
                  rotationY={currentRotationY}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Persistent phone — mounts at stage 2, never unmounts */}
        <AnimatePresence>
          {stage >= 2 && (
            <motion.div
              key="phone"
              className="relative flex-shrink-0"
              initial={{ y: 120, opacity: 0, rotate: 3 }}
              animate={overlayActive
                ? { y: 40, opacity: 0.1, rotate: 0, scale: 0.95 }
                : { y: 0, opacity: 1, rotate: 0, scale: 1 }
              }
              transition={{ duration: 0.7, ease: easeCubic }}
              style={{
                filter: 'drop-shadow(0 20px 60px rgba(0,0,0,0.5))',
                pointerEvents: overlayActive ? 'none' : 'auto',
              }}
            >
              <Iphone className="w-[380px] max-h-screen" frameColor="#1a1a1a">
                {phoneContent}
              </Iphone>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tutorial trade card preview — stages 3-4 only */}
        <AnimatePresence>
          {!isFeed && stage >= 3 && (
            <motion.div
              key="tutorial-trade"
              className="absolute left-[calc(50%+240px)] w-[360px] rounded-2xl p-3"
              initial={{ x: 40, opacity: 0, rotate: 2 }}
              animate={{ x: 0, opacity: 1, rotate: 0 }}
              exit={{ x: 40, opacity: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              style={{
                background: 'rgba(30, 30, 30, 0.72)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
              }}
            >
              <div className="flex items-start gap-3 mb-2">
                {expandedMarket?.image_url && !imgError ? (
                  <Image
                    src={expandedMarket.image_url}
                    alt=""
                    width={40}
                    height={40}
                    unoptimized
                    className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                    onError={() => setImgError(true)}
                  />
                ) : (
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: 'rgba(16, 185, 129, 0.2)' }}
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-emerald-400">
                      <path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/>
                    </svg>
                  </div>
                )}
                <p className="text-white/90 text-xs leading-snug flex-1 line-clamp-2">
                  {expandedMarket?.question ?? 'Will this event happen by end of month?'}
                </p>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-white/50">View on Kalshi</span>
                <div className="flex gap-2">
                  <button className="px-3 py-1 text-xs glass-btn-yes">
                    Yes {expandedMarket?.yes_price != null && <span className="opacity-70">{expandedMarket.yes_price}¢</span>}
                  </button>
                  <button className="px-3 py-1 text-xs glass-btn-no">
                    No {expandedMarket?.no_price != null && <span className="opacity-70">{expandedMarket.no_price}¢</span>}
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Feed trade card + chart — stage 5 */}
        <AnimatePresence>
          {isFeed && currentMarkets.length > 0 && expandedMarket && (
            <motion.div
              key="feed-trade"
              className="flex flex-col gap-3 w-[640px] flex-shrink-0"
              initial={{ x: 40, opacity: 0, rotate: 2 }}
              animate={overlayActive
                ? { x: 80, opacity: 0, rotate: 0 }
                : { x: 0, opacity: 1, rotate: 0 }
              }
              exit={{ x: 40, opacity: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              style={{ pointerEvents: overlayActive ? 'none' : 'auto' }}
            >
              <div
                className="rounded-2xl p-5"
                style={{
                  background: 'rgba(30, 30, 30, 0.72)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
                }}
              >
                <div className="flex items-start gap-3 mb-3">
                  {expandedMarket.image_url && !imgError ? (
                    <Image
                      src={expandedMarket.image_url}
                      alt=""
                      width={48}
                      height={48}
                      unoptimized
                      className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
                      onError={() => setImgError(true)}
                    />
                  ) : (
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(16, 185, 129, 0.2)' }}
                    >
                      <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-emerald-400">
                        <path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/>
                      </svg>
                    </div>
                  )}
                  <p className="text-white/90 text-sm leading-snug flex-1 line-clamp-2">
                    {expandedMarket.question}
                  </p>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <a
                    href={`https://kalshi.com/events/${expandedMarket.event_ticker || expandedMarket.ticker}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-white/50 hover:text-white transition-colors"
                  >
                    View on Kalshi
                    <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5">
                      <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                    </svg>
                  </a>
                  <div className="flex gap-2">
                    <button
                      className="px-4 py-2 text-sm glass-btn-yes"
                      onClick={() => handleTrade('YES')}
                    >
                      Yes {expandedMarket.yes_price != null && <span className="opacity-70">{expandedMarket.yes_price}¢</span>}
                    </button>
                    <button
                      className="px-4 py-2 text-sm glass-btn-no"
                      onClick={() => handleTrade('NO')}
                    >
                      No {expandedMarket.no_price != null && <span className="opacity-70">{expandedMarket.no_price}¢</span>}
                    </button>
                  </div>
                </div>

                {currentMarkets.length > 1 && (
                  <div className="mt-3 pt-3 border-t border-white/10 flex flex-col gap-1 max-h-[280px] overflow-y-auto scrollbar-thin">
                    {currentMarkets.map((m, i) => (
                      <button
                        key={m.ticker}
                        onClick={() => { setSelectedIdx(i); setImgError(false) }}
                        className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-left transition-colors"
                        style={{
                          background: i === selectedIdx ? 'rgba(255,255,255,0.1)' : 'transparent',
                        }}
                      >
                        <span className="text-white/80 text-sm line-clamp-1 flex-1 mr-2">
                          {m.question}
                        </span>
                        <span className="text-emerald-400 text-sm font-medium flex-shrink-0">
                          {m.yes_price}¢
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {expandedMarket.series_ticker && (
                <div
                  className="rounded-2xl p-5"
                  style={{
                    background: 'rgba(30, 30, 30, 0.72)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-white/40 uppercase tracking-wider">Yes</span>
                        <span className="text-sm text-emerald-400 font-medium">{expandedMarket.yes_price}¢</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-white/40 uppercase tracking-wider">No</span>
                        <span className="text-sm text-red-400 font-medium">{expandedMarket.no_price}¢</span>
                      </div>
                    </div>
                    {resolvedPriceHistory && resolvedPriceHistory.length > 1 && (() => {
                      const prices = resolvedPriceHistory.map((p) => p.price).filter((v) => Number.isFinite(v))
                      if (prices.length < 2) return null
                      const trending = prices[prices.length - 1] >= prices[0]
                      const diff = prices[prices.length - 1] - prices[0]
                      if (!Number.isFinite(diff)) return null
                      return (
                        <span className={`text-xs font-medium ${trending ? 'text-emerald-400' : 'text-red-400'}`}>
                          {trending ? '+' : ''}{diff.toFixed(0)}¢ since open
                        </span>
                      )
                    })()}
                  </div>
                  <div className="relative">
                    {graphStatus === 'loading' && (
                      <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm rounded-xl pointer-events-none">
                        <div className="flex items-center gap-2 text-xs text-white/85">
                          <span className="inline-block w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                          Loading market history…
                        </div>
                      </div>
                    )}
                    <PriceChart
                      key={expandedMarket.ticker}
                      ticker={expandedMarket.ticker}
                      seriesTicker={expandedMarket.series_ticker}
                      priceHistory={resolvedPriceHistory}
                      createdTime={expandedMarket.created_time}
                      openTime={expandedMarket.open_time}
                      marketStartTs={expandedMarket.market_start_ts}
                      onReady={handleChartReady}
                    />
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Trade confirmation overlay */}
        <AnimatePresence>
          {tradeConfirmation && (
            <>
            <motion.div
              key="trade-backdrop"
              className="fixed inset-0 z-40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              style={{ background: 'rgba(0, 0, 0, 0.6)' }}
            />
            <motion.div
              key="trade-confirmation"
              className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="flex flex-col items-center">
                <motion.div
                  initial={{ opacity: 0, y: 20, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.5, delay: 0.15, ease: easeCubic }}
                >
                  <SpeechBubble text={tradeConfirmation.message} large />
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 40 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  transition={{ duration: 0.5, ease: easeCubic }}
                >
                  <CharacterPreview
                    animation="wave"
                    size={{ width: 500, height: 600 }}
                    rotationY={0.3}
                  />
                </motion.div>
              </div>
            </motion.div>
            </>
          )}
        </AnimatePresence>

        {/* Trade amount input overlay (AI reels only) */}
        <AnimatePresence>
          {showTradeInput && (
            <>
              <motion.div
                key="trade-input-backdrop"
                className="fixed inset-0 z-40"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                style={{ background: 'rgba(0, 0, 0, 0.6)' }}
                onClick={dismissTradeInput}
              />
              <motion.div
                key="trade-input-modal"
                className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <motion.div
                  className="pointer-events-auto flex flex-col items-center gap-5"
                  initial={{ opacity: 0, y: 30, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.4, ease: easeCubic }}
                >
                  <div
                    className="rounded-2xl p-6 w-[400px]"
                    style={{
                      background: 'rgba(30, 30, 30, 0.92)',
                      backdropFilter: 'blur(20px)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                      fontFamily: 'var(--font-playfair), serif',
                    }}
                  >
                    {/* Market question */}
                    <div className="flex items-start gap-3 mb-4">
                      {expandedMarket?.image_url && !imgError ? (
                        <Image
                          src={expandedMarket.image_url}
                          alt=""
                          width={40}
                          height={40}
                          unoptimized
                          className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
                          onError={() => setImgError(true)}
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(16, 185, 129, 0.2)' }}>
                          <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-emerald-400"><path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/></svg>
                        </div>
                      )}
                      <div className="flex-1">
                        <p className="text-white/90 text-sm leading-snug line-clamp-2">{expandedMarket?.question}</p>
                        <p className="text-emerald-400 text-xs mt-0.5">
                          Buy {showTradeInput.side}
                        </p>
                      </div>
                    </div>

                    {/* YES / NO price pills */}
                    <div className="flex gap-2 mb-4">
                      <div
                        className="flex-1 py-2 rounded-xl text-center text-sm font-medium transition-colors"
                        style={{
                          background: showTradeInput.side === 'YES' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                          border: showTradeInput.side === 'YES' ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid rgba(255,255,255,0.15)',
                          color: showTradeInput.side === 'YES' ? 'rgb(52, 211, 153)' : 'rgba(255,255,255,0.4)',
                        }}
                      >
                        Yes {expandedMarket?.yes_price ?? 50}¢
                      </div>
                      <div
                        className="flex-1 py-2 rounded-xl text-center text-sm font-medium transition-colors"
                        style={{
                          background: showTradeInput.side === 'NO' ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
                          border: showTradeInput.side === 'NO' ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(255,255,255,0.15)',
                          color: showTradeInput.side === 'NO' ? 'rgb(248, 113, 113)' : 'rgba(255,255,255,0.4)',
                        }}
                      >
                        No {expandedMarket?.no_price ?? 50}¢
                      </div>
                    </div>

                    {/* Amount input */}
                    <div
                      className="rounded-xl px-4 py-3 mb-4 flex items-center justify-between"
                      style={{ border: '1px solid rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.05)' }}
                    >
                      <div>
                        <p className="text-white/80 text-sm">Amount</p>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-white/60 text-lg">$</span>
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={tradeAmount}
                          onChange={(e) => setTradeAmount(e.target.value)}
                          placeholder="0"
                          autoFocus
                          className="w-24 bg-transparent text-white text-2xl font-semibold outline-none text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') submitTradeAdvice()
                          }}
                        />
                      </div>
                    </div>

                    {/* Odds & Payout */}
                    {(() => {
                      const price = showTradeInput.side === 'YES'
                        ? (expandedMarket?.yes_price ?? 50)
                        : (expandedMarket?.no_price ?? 50)
                      const amt = parseFloat(tradeAmount) || 0
                      const payout = amt > 0 && price > 0 ? (amt / price) * 100 : 0
                      return (
                        <div className="flex items-center justify-between mb-5">
                          <div>
                            <p className="text-white/40 text-xs">Odds</p>
                            <p className="text-white/80 text-sm font-medium">{price}% chance</p>
                          </div>
                          <div className="text-right">
                            <p className="text-white/40 text-xs">Payout if {showTradeInput.side}</p>
                            <p className="text-emerald-400 text-xl font-semibold">
                              ${payout > 0 ? payout.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}
                            </p>
                          </div>
                        </div>
                      )
                    })()}

                    {/* Actions */}
                    <div className="flex gap-3">
                      <button
                        onClick={dismissTradeInput}
                        className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer bg-white/[0.08] border border-white/15 text-white/50 hover:bg-white/20 hover:text-white/70"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={submitTradeAdvice}
                        disabled={adviceLoading || !tradeAmount || parseFloat(tradeAmount) <= 0}
                        className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/40 hover:border-emerald-500/60 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {adviceLoading ? 'Asking Joe...' : 'Ask Joe'}
                      </button>
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            </>
          )}
        </AnimatePresence>

        {/* Joe's advice overlay */}
        <AnimatePresence>
          {adviceText && (
            <>
              <motion.div
                key="advice-backdrop"
                className="fixed inset-0 z-40"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                style={{ background: 'rgba(0, 0, 0, 0.6)' }}
                onClick={dismissAdvice}
              />
              <motion.div
                key="advice-overlay"
                className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="flex flex-col items-center pointer-events-auto">
                  <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.9 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.5, delay: 0.2, ease: easeCubic }}
                  >
                    <SpeechBubble large>
                      <div className="whitespace-pre-line text-base leading-relaxed">{adviceText}</div>
                    </SpeechBubble>
                  </motion.div>
                  <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 20 }}
                    transition={{ duration: 0.5, ease: easeCubic }}
                  >
                    <CharacterPreview
                      animation="point"
                      size={{ width: 500, height: 600 }}
                      rotationY={0.3}
                    />
                  </motion.div>
                  <motion.div
                    className="relative z-10 -mt-8"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.4, delay: 0.35, ease: easeCubic }}
                  >
                    <button
                      type="button"
                      onClick={() => { dismissAdvice() }}
                      className="px-8 py-3 rounded-xl text-sm font-medium transition-all cursor-pointer bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/40 hover:border-emerald-500/60"
                    >
                      Back to Feed
                    </button>
                  </motion.div>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>

      {/* Spacebar hint — only tutorial stages */}
      {!isFeed && (
        <div
          className="absolute bottom-3 left-0 right-0 flex justify-center z-30"
        >
          <motion.span
            className="text-white/50 text-sm"
            style={{ fontFamily: 'var(--font-playfair), serif' }}
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, ease: 'easeInOut', repeat: Infinity }}
          >
            Press space to continue
          </motion.span>
        </div>
      )}
    </BgWrapper>
  )
}
