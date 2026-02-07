'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { Iphone } from '@/components/ui/iphone'
import Feed, { FeedRef } from '@/components/Feed'
import { KalshiMarket } from '@/types'
import { useVideoQueue } from '@/hooks/useVideoQueue'

const BgWrapper = ({ children, className = '' }: { children: ReactNode, className?: string }) => (
  <div className={`relative min-h-screen overflow-hidden ${className}`}>
    <div 
      className="absolute inset-0 -z-10"
      style={{
        backgroundImage: 'url(/bg.jpeg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        filter: 'blur(4px) brightness(0.5)',
        transform: 'scale(1.02)',
      }}
    />
    {children}
  </div>
)

export default function Home() {
  const { feedItems, stats, isProcessing, processQueue } = useVideoQueue()
  const [currentMarket, setCurrentMarket] = useState<KalshiMarket | undefined>(undefined)
  const [showBetModal, setShowBetModal] = useState(false)
  const feedRef = useRef<FeedRef>(null)

  useEffect(() => {
    if ((stats.pending > 0 || stats.refreshPending > 0) && !isProcessing) {
      processQueue()
    }
  }, [stats.pending, stats.refreshPending, isProcessing, processQueue])

  const handleBet = (side: 'YES' | 'NO') => {
    console.log(`Bet placed: ${side} on ${currentMarket?.ticker}`)
    setShowBetModal(false)
  }

  const handleCurrentItemChange = useCallback((item: { kalshi?: KalshiMarket }) => {
    setCurrentMarket(item.kalshi)
  }, [])

  const progress = stats.total > 0 ? ((stats.matched + stats.failed) / stats.total) * 100 : 0

  if (stats.total === 0) {
    return (
      <BgWrapper className="flex items-center justify-center">
        <div className="text-white/80 text-xl font-medium">No videos in queue</div>
      </BgWrapper>
    )
  }

  if (isProcessing || stats.pending > 0 || stats.processing > 0 || stats.refreshPending > 0) {
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
            {stats.refreshPending > 0 && (
              <span className="text-emerald-300">Refreshing images</span>
            )}
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
    <BgWrapper className="flex items-center justify-center p-8">
      <div className="relative flex items-center gap-4">
        <div className="flex flex-col gap-3 z-10">
          <button
            onClick={() => feedRef.current?.scrollToPrev()}
            className="flex items-center justify-center w-11 h-11 rounded-full text-white/70 hover:text-white transition-all"
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>
            </svg>
          </button>
          <button
            onClick={() => feedRef.current?.scrollToNext()}
            className="flex items-center justify-center w-11 h-11 rounded-full text-white/70 hover:text-white transition-all"
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
              <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
            </svg>
          </button>
        </div>

        <Iphone className="w-[380px]" frameColor="#1a1a1a">
          <Feed ref={feedRef} items={feedItems} onCurrentItemChange={handleCurrentItemChange} />
        </Iphone>
        
        {currentMarket && (
          <button
            onClick={() => setShowBetModal(true)}
            className="flex items-center justify-center w-14 h-14 rounded-full text-white transition-all hover:scale-110"
            style={{
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              boxShadow: '0 4px 20px rgba(16, 185, 129, 0.5)',
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
          </button>
        )}
      </div>

      {showBetModal && currentMarket && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={() => setShowBetModal(false)}
        >
          <div 
            className="absolute inset-0"
            style={{ background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(8px)' }}
          />
          <div 
            className="relative rounded-2xl overflow-hidden w-full max-w-[480px] z-10"
            style={{
              background: 'linear-gradient(135deg, #064e3b 0%, #065f46 50%, #047857 100%)',
              boxShadow: '0 25px 50px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.1)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-start gap-4 mb-6">
                {currentMarket.image_url ? (
                  <img 
                    src={currentMarket.image_url} 
                    alt="" 
                    className="w-12 h-12 rounded-xl object-cover flex-shrink-0"
                  />
                ) : (
                  <div 
                    className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: 'rgba(255,255,255,0.15)' }}
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-emerald-300">
                      <path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/>
                    </svg>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-emerald-100/80 text-base leading-relaxed">
                    {currentMarket.question}
                  </p>
                </div>
                <button
                  onClick={() => setShowBetModal(false)}
                  className="text-emerald-200/50 hover:text-white transition-colors flex-shrink-0"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                  </svg>
                </button>
              </div>

              <div 
                className="rounded-xl p-4 mb-4"
                style={{ background: 'rgba(0,0,0,0.2)' }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-white text-2xl font-bold mb-1">
                      {currentMarket.outcome}
                    </h2>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-emerald-400 font-semibold">NEW</span>
                      {currentMarket.volume && (
                        <span className="text-emerald-200/60">${Math.round(currentMarket.volume / 1000)}k Vol.</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-100/70 text-lg font-medium">
                      {currentMarket.yes_price}%
                    </span>
                    <div className="flex gap-1">
                      <button 
                        className="px-4 py-2 rounded-lg font-bold text-sm transition-all hover:scale-105 active:scale-95"
                        style={{ background: '#22c55e', color: 'white' }}
                        onClick={() => handleBet('YES')}
                      >
                        Yes
                      </button>
                      <button 
                        className="px-4 py-2 rounded-lg font-bold text-sm transition-all hover:scale-105 active:scale-95"
                        style={{ background: '#ef4444', color: 'white' }}
                        onClick={() => handleBet('NO')}
                      >
                        No
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between text-emerald-200/50 text-sm">
                <span>Powered by Kalshi</span>
                <a 
                  href={`https://kalshi.com/events/${currentMarket.event_ticker || currentMarket.ticker}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 hover:text-white transition-colors"
                >
                  <span>View on Kalshi</span>
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                    <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
                  </svg>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </BgWrapper>
  )
}
