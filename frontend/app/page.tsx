'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import dynamic from 'next/dynamic'
import { motion, AnimatePresence } from 'framer-motion'
import { Iphone } from '@/components/ui/iphone'
import Feed, { FeedRef } from '@/components/Feed'
import { KalshiMarket } from '@/types'
import { useVideoQueue } from '@/hooks/useVideoQueue'

const CharacterPreview = dynamic(() => import('@/components/CharacterPreview'), { ssr: false })
const PriceChart = dynamic(() => import('@/components/PriceChart'), { ssr: false })

const TIPS = [
  { text: 'Welcome to my office!', animation: 'wave' as const },
  { text: "Today we're gonna scroll and bet on Kalshi.", animation: 'idle' as const },
  { text: 'Scroll through shorts right here.', animation: 'point' as const },
  { text: 'Tap YES or NO to place your bet.', animation: 'point' as const },
  { text: "Let's go!", animation: 'wave' as const },
]

const FEED_TIP = 'Swipe up for the next short'

const easeCubic = [0.22, 1, 0.36, 1] as const

const BgWrapper = ({ children, blurred = true }: { children: ReactNode; blurred?: boolean }) => (
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
  </div>
)

function SpeechBubble({ text }: { text: string }) {
  return (
    <div
      className="relative bg-white/95 text-gray-900 rounded-2xl px-5 py-3 max-w-[280px] text-sm font-medium shadow-lg"
    >
      {text}
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
  const { feedItems, stats, feedError, isProcessing, processQueue, retryFailed, clearQueue } = useVideoQueue()
  const [currentMarkets, setCurrentMarkets] = useState<KalshiMarket[]>([])
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [imgError, setImgError] = useState(false)
  const [graphReadyByTicker, setGraphReadyByTicker] = useState<Record<string, boolean>>({})
  const [stage, setStage] = useState(0) // 0-4 = tutorial, 5 = feed
  const [waitingForFeed, setWaitingForFeed] = useState(false)
  const feedRef = useRef<FeedRef>(null)

  // Start processing immediately in background
  useEffect(() => {
    if (stats.pending > 0 && !isProcessing) {
      processQueue()
    }
  }, [stats.pending, isProcessing, processQueue])

  // Spacebar to advance tutorial stages
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.code === 'Space' && stage < 5) {
        e.preventDefault()
        if (stage === 4) {
          if (feedItems.length > 0) {
            setStage(5)
          } else {
            setWaitingForFeed(true)
          }
        } else {
          setStage(s => s + 1)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [stage, feedItems.length])

  // Auto-transition when feed becomes ready while waiting
  useEffect(() => {
    if (waitingForFeed && feedItems.length > 0) {
      const t = setTimeout(() => setStage(5), 800)
      return () => clearTimeout(t)
    }
  }, [waitingForFeed, feedItems.length])

  const expandedMarket = currentMarkets[selectedIdx] as KalshiMarket | undefined

  const handleBet = (side: 'YES' | 'NO') => {
    console.log(`Bet placed: ${side} on ${expandedMarket?.ticker}`)
  }

  const handleCurrentItemChange = useCallback((item: { kalshi?: KalshiMarket[] }) => {
    setCurrentMarkets(item.kalshi ?? [])
    setSelectedIdx(0)
    setImgError(false)
  }, [])

  const handleChartReady = useCallback((ticker: string) => {
    setGraphReadyByTicker((prev) => (prev[ticker] ? prev : { ...prev, [ticker]: true }))
  }, [])

  const currentAnimation = waitingForFeed && stage === 4 ? 'idle' : (TIPS[stage]?.animation ?? 'idle')
  const currentTipText = waitingForFeed && stage === 4 ? 'Hang tight...' : (TIPS[stage]?.text ?? '')

  // rotationY per stage: point stages face toward phone, others centered
  const currentRotationY = currentAnimation === 'point' ? 0.4 : 0.3
  const isActiveMarketGraphReady = expandedMarket ? !!graphReadyByTicker[expandedMarket.ticker] : false
  const isFeedScrollLocked = !expandedMarket || (expandedMarket.series_ticker ? !isActiveMarketGraphReady : false)

  // --- FEED VIEW (stage 5) ---
  if (stage === 5) {
    return (
      <BgWrapper blurred>
        <motion.div
          className="relative flex items-center max-h-screen w-full -mt-4 sm:-mt-6 ml-[3%] gap-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
        >
          {/* Character — left of phone */}
          <div className="flex-shrink-0 z-20 -mr-2">
            <div className="flex flex-col items-center">
              <div className="relative bg-white/95 text-gray-900 rounded-2xl px-4 py-2 max-w-[220px] text-xs font-medium shadow-lg">
                {FEED_TIP}
                <div
                  className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0"
                  style={{
                    borderLeft: '6px solid transparent',
                    borderRight: '6px solid transparent',
                    borderTop: '6px solid rgba(255,255,255,0.95)',
                  }}
                />
              </div>
              <CharacterPreview animation="idle" rotationY={0.8} />
            </div>
          </div>

          <div className="relative flex-shrink-0" style={{ filter: 'drop-shadow(0 20px 60px rgba(0,0,0,0.5))' }}>
            <Iphone className="w-[380px] max-h-screen" frameColor="#1a1a1a">
              <Feed ref={feedRef} items={feedItems} onCurrentItemChange={handleCurrentItemChange} />
            </Iphone>
            {isFeedScrollLocked && (
              <div className="absolute inset-0 z-30 flex items-start justify-center pointer-events-auto">
                <div className="mt-5 rounded-full bg-black/55 border border-white/15 px-3 py-1 text-xs text-white/80">
                  Syncing Kalshi graph...
                </div>
              </div>
            )}
          </div>

          {currentMarkets.length > 0 && expandedMarket && (
            <motion.div
              className="flex flex-col gap-3 w-[500px] flex-shrink-0"
              initial={{ x: 40, opacity: 0, rotate: 2 }}
              animate={{ x: 0, opacity: 1, rotate: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            >
              {/* Bet card */}
              <div
                className="rounded-2xl p-5"
                style={{
                  background: 'rgba(30, 30, 30, 0.88)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
                }}
              >
                {/* Expanded market */}
                <div className="flex items-start gap-3 mb-3">
                  {expandedMarket.image_url && !imgError ? (
                    <img
                      src={expandedMarket.image_url}
                      alt=""
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
                      onClick={() => handleBet('YES')}
                    >
                      Yes {expandedMarket.yes_price != null && <span className="opacity-70">{expandedMarket.yes_price}¢</span>}
                    </button>
                    <button
                      className="px-4 py-2 text-sm glass-btn-no"
                      onClick={() => handleBet('NO')}
                    >
                      No {expandedMarket.no_price != null && <span className="opacity-70">{expandedMarket.no_price}¢</span>}
                    </button>
                  </div>
                </div>

                {/* Scrollable sub-bet rows */}
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

              {/* Separated chart card */}
              {expandedMarket.series_ticker && (
                <div
                  className="rounded-2xl p-5"
                  style={{
                    background: 'rgba(30, 30, 30, 0.88)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-white/40 uppercase tracking-wider">Yes Price</span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text-white/70 font-medium">{expandedMarket.yes_price}¢</span>
                      {isActiveMarketGraphReady && expandedMarket.price_history && expandedMarket.price_history.length > 1 && (() => {
                        const prices = expandedMarket.price_history!.map(p => p.price)
                        const trending = prices[prices.length - 1] >= prices[0]
                        const diff = prices[prices.length - 1] - prices[0]
                        return (
                          <span className={`text-xs font-medium ${trending ? 'text-emerald-400' : 'text-red-400'}`}>
                            {trending ? '+' : ''}{diff.toFixed(0)}¢ since open
                          </span>
                        )
                      })()}
                    </div>
                  </div>
                  {!isActiveMarketGraphReady && (
                    <div className="mb-2 text-xs text-white/60">Loading full market history...</div>
                  )}
                  <PriceChart
                    key={expandedMarket.ticker}
                    ticker={expandedMarket.ticker}
                    seriesTicker={expandedMarket.series_ticker}
                    priceHistory={expandedMarket.price_history}
                    createdTime={expandedMarket.created_time}
                    openTime={expandedMarket.open_time}
                    marketStartTs={expandedMarket.market_start_ts}
                    onReady={handleChartReady}
                  />
                </div>
              )}
            </motion.div>
          )}
        </motion.div>
      </BgWrapper>
    )
  }

  // --- TUTORIAL VIEW (stages 0-4) ---
  return (
    <BgWrapper blurred={stage >= 2}>
      <div className="relative flex items-center justify-center max-h-screen w-full -mt-4 sm:-mt-6">
        {/* Character + Speech Bubble */}
        <motion.div
          className="z-20"
          animate={{
            x: stage >= 2 ? -340 : 0,
          }}
          transition={{ duration: 0.8, ease: easeCubic }}
          style={{ position: stage >= 2 ? 'absolute' : 'relative' }}
        >
          <div className="relative flex flex-col items-center">
            {/* Speech bubble — positioned near character's head */}
            <div className="relative w-full flex justify-center items-end mt-8 h-[68px]">
              <AnimatePresence mode="wait">
                <motion.div
                  key={`tip-${stage}-${waitingForFeed}`}
                  initial={{ opacity: 0, y: 10, rotate: -2 }}
                  animate={{ opacity: 1, y: 0, rotate: 0 }}
                  exit={{ opacity: 0, y: -8, rotate: 2 }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                >
                  <SpeechBubble text={currentTipText} />
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

        {/* Phone — slides in from below at stage 2 */}
        <AnimatePresence>
          {stage >= 2 && (
            <motion.div
              className="relative flex-shrink-0"
              initial={{ y: 120, opacity: 0, rotate: 3 }}
              animate={{ y: 0, opacity: 1, rotate: 0 }}
              exit={{ y: 120, opacity: 0 }}
              transition={{ duration: 0.7, ease: easeCubic }}
              style={{ filter: 'drop-shadow(0 20px 60px rgba(0,0,0,0.5))' }}
            >
              <Iphone className="w-[380px] max-h-screen" frameColor="#1a1a1a">
                {feedItems.length > 0 ? (
                  <Feed ref={feedRef} items={feedItems} onCurrentItemChange={handleCurrentItemChange} />
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
                )}
              </Iphone>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bet card — slides in from right at stage 3 */}
        <AnimatePresence>
          {stage >= 3 && (
            <motion.div
              className="absolute left-[calc(50%+210px)] w-[320px] rounded-2xl p-3"
              initial={{ x: 40, opacity: 0, rotate: 2 }}
              animate={{ x: 0, opacity: 1, rotate: 0 }}
              exit={{ x: 40, opacity: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              style={{
                background: 'rgba(30, 30, 30, 0.88)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
              }}
            >
              {/* Demo bet card content */}
              <div className="flex items-start gap-3 mb-2">
                {expandedMarket?.image_url && !imgError ? (
                  <img
                    src={expandedMarket.image_url}
                    alt=""
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
      </div>

      {/* Spacebar hint — Framer Motion infinite pulse */}
      <motion.div
        className="absolute bottom-3 left-0 right-0 flex justify-center z-30"
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2, ease: 'easeInOut', repeat: Infinity }}
      >
        <span className="text-white/50 text-sm">
          Press space to continue
        </span>
      </motion.div>
    </BgWrapper>
  )
}

