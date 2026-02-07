'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { Iphone } from '@/components/ui/iphone'
import Feed, { FeedRef } from '@/components/Feed'
import { KalshiMarket } from '@/types'
import { useVideoQueue } from '@/hooks/useVideoQueue'
const BgWrapper = ({ children, className = '' }: { children: ReactNode, className?: string }) => (
  <div className={`relative min-h-screen overflow-hidden ${className}`} style={{ backgroundColor: '#1a2520' }}>
    {/* Background image layer — light blur for cartoony texture */}
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: "url('/bg.png')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        filter: 'blur(2px)',
        opacity: 0.7,
        transform: 'scale(1.02)',
      }}
    />
    {/* Light overlay to soften slightly */}
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(ellipse at 50% 40%, rgba(16,185,129,0.05) 0%, transparent 70%)',
        pointerEvents: 'none',
      }}
    />
    {/* Content */}
    <div className={`relative z-10 h-screen flex items-center justify-center ${className}`}>
      {children}
    </div>
  </div>
)

export default function Home() {
  const { feedItems, stats, isProcessing, processQueue } = useVideoQueue()
  const [currentMarket, setCurrentMarket] = useState<KalshiMarket | undefined>(undefined)
  const [imgError, setImgError] = useState(false)
  const feedRef = useRef<FeedRef>(null)

  useEffect(() => {
    if (stats.pending > 0 && !isProcessing) {
      processQueue()
    }
  }, [stats.pending, isProcessing, processQueue])

  const handleBet = (side: 'YES' | 'NO') => {
    console.log(`Bet placed: ${side} on ${currentMarket?.ticker}`)
  }

  const handleCurrentItemChange = useCallback((item: { kalshi?: KalshiMarket }) => {
    setCurrentMarket(item.kalshi)
    setImgError(false)
  }, [])

  const progress = stats.total > 0 ? ((stats.matched + stats.failed) / stats.total) * 100 : 0

  if (stats.total === 0) {
    return (
      <BgWrapper className="flex items-center justify-center">
        <div className="text-white/80 text-xl font-medium">No videos in queue</div>
      </BgWrapper>
    )
  }

  if (isProcessing || stats.pending > 0 || stats.processing > 0) {
    return (
      <BgWrapper className="flex items-center justify-center">
        <div 
          className="flex flex-col items-center gap-6 p-8 rounded-3xl min-w-[320px]"
          style={{
            background: 'rgba(255, 255, 255, 0.05)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          }}
        >
          <div className="text-white text-xl font-medium">Processing Videos</div>
          <div className="w-full rounded-full h-2 overflow-hidden" style={{ background: 'rgba(255,255,255,0.1)' }}>
            <div 
              className="h-full transition-all duration-300 ease-out"
              style={{ 
                width: `${progress}%`,
                background: 'linear-gradient(to right, #6366f1, #a855f7)'
              }}
            />
          </div>
          <div className="flex gap-4 text-sm text-white/50">
            <span>{stats.matched} matched</span>
            <span>{stats.processing} processing</span>
            <span>{stats.pending} pending</span>
            {stats.failed > 0 && <span className="text-red-400">{stats.failed} failed</span>}
          </div>
        </div>
      </BgWrapper>
    )
  }

  if (feedItems.length === 0) {
    return (
      <BgWrapper className="flex items-center justify-center">
        <div className="text-white/80 text-xl font-medium">No bets available</div>
      </BgWrapper>
    )
  }

  return (
    <BgWrapper>
      <div className="relative max-h-screen" style={{ filter: 'drop-shadow(0 20px 60px rgba(0,0,0,0.5))' }}>
        <Iphone className="w-[380px] max-h-screen" frameColor="#1a1a1a">
          <Feed ref={feedRef} items={feedItems} onCurrentItemChange={handleCurrentItemChange} />
        </Iphone>
        
        {currentMarket && (
          <div 
            className="absolute left-full top-1/2 -translate-y-1/2 ml-6 w-[320px] rounded-2xl p-4"
            style={{
              background: 'rgba(20, 30, 25, 0.88)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(16, 185, 129, 0.1)',
            }}
          >
            <div className="flex items-start gap-3 mb-3">
              {currentMarket.image_url && !imgError ? (
                <img
                  src={currentMarket.image_url}
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
              <p className="text-white/90 text-xs leading-snug flex-1 line-clamp-2 min-h-[2.5em]">
                {currentMarket.question}
              </p>
            </div>

            <div className="flex items-center justify-between text-xs">
              <a
                href={`https://kalshi.com/events/${currentMarket.event_ticker || currentMarket.ticker}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-white/50 hover:text-white transition-colors"
              >
                View on Kalshi
                <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                  <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                </svg>
              </a>
              <div className="flex gap-2">
                <button
                  className="px-3 py-1 text-xs glass-btn-yes"
                  onClick={() => handleBet('YES')}
                >
                  Yes
                </button>
                <button
                  className="px-3 py-1 text-xs glass-btn-no"
                  onClick={() => handleBet('NO')}
                >
                  No
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </BgWrapper>
  )
}
