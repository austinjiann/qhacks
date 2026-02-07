'use client'

import { useState, useRef, useEffect } from 'react'
import { Iphone } from '@/components/ui/iphone'
import Feed, { FeedRef } from '@/components/Feed'
import { KalshiMarket } from '@/types'
import { useVideoQueue } from '@/hooks/useVideoQueue'

export default function Home() {
  const { feedItems, stats, isProcessing, processQueue } = useVideoQueue()
  const [currentMarket, setCurrentMarket] = useState<KalshiMarket | undefined>(undefined)
  const feedRef = useRef<FeedRef>(null)
  const hasProcessed = useRef(false)

  useEffect(() => {
    if (stats.pending > 0 && !isProcessing && !hasProcessed.current) {
      hasProcessed.current = true
      processQueue()
    }
  }, [stats.pending, isProcessing, processQueue])

  useEffect(() => {
    if (feedItems.length > 0 && feedItems[0]?.kalshi && !currentMarket) {
      setCurrentMarket(feedItems[0].kalshi)
    }
  }, [feedItems, currentMarket])

  const handleBet = (side: 'YES' | 'NO') => {
    console.log(`Bet placed: ${side} on ${currentMarket?.ticker}`)
  }

  const progress = stats.total > 0 ? ((stats.matched + stats.failed) / stats.total) * 100 : 0

  if (stats.total === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#9a9a7f]">
        <div className="text-white text-xl" style={{ fontFamily: "var(--font-playfair), serif" }}>No videos in queue</div>
      </div>
    )
  }

  if (isProcessing || stats.pending > 0 || stats.processing > 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#9a9a7f]">
        <div className="flex flex-col items-center gap-6 p-8 bg-[#1a1a1a] rounded-2xl min-w-[320px]">
          <div className="text-white text-xl" style={{ fontFamily: "var(--font-playfair), serif" }}>
            Processing Videos
          </div>
          <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
            <div 
              className="bg-green-500 h-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex gap-4 text-sm text-gray-400">
            <span>{stats.matched} matched</span>
            <span>{stats.processing} processing</span>
            <span>{stats.pending} pending</span>
            {stats.failed > 0 && <span className="text-red-400">{stats.failed} failed</span>}
          </div>
          <div className="flex flex-wrap gap-2 max-w-[280px]">
            {Array.from({ length: stats.total }).map((_, i) => {
              const status = i < stats.matched ? 'matched' : 
                            i < stats.matched + stats.failed ? 'failed' :
                            i < stats.matched + stats.failed + stats.processing ? 'processing' : 'pending'
              return (
                <div 
                  key={i}
                  className={`w-3 h-3 rounded-full ${
                    status === 'matched' ? 'bg-green-500' :
                    status === 'failed' ? 'bg-red-500' :
                    status === 'processing' ? 'bg-yellow-500 animate-pulse' :
                    'bg-gray-600'
                  }`}
                />
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  if (feedItems.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#9a9a7f]">
        <div className="text-white text-xl" style={{ fontFamily: "var(--font-playfair), serif" }}>No bets available</div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#9a9a7f] p-8 gap-8">
      <Iphone className="max-w-[340px]" frameColor="#2a2a2a">
        <Feed ref={feedRef} items={feedItems} onCurrentItemChange={(item) => setCurrentMarket(item.kalshi)} />
      </Iphone>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <button
            onClick={() => feedRef.current?.scrollToPrev()}
            className="flex items-center justify-center w-12 h-12 bg-[#1a1a1a] rounded-full text-white hover:bg-[#2a2a2a] transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>
            </svg>
          </button>
          <button
            onClick={() => feedRef.current?.scrollToNext()}
            className="flex items-center justify-center w-12 h-12 bg-[#1a1a1a] rounded-full text-white hover:bg-[#2a2a2a] transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
            </svg>
          </button>
        </div>
        
        {currentMarket && (
          <div className="flex flex-col gap-4 p-6 bg-[#1a1a1a] rounded-2xl min-w-[280px] max-w-[320px]" style={{ fontFamily: "var(--font-playfair), serif" }}>
            <div className="text-sm text-gray-400 leading-snug">{currentMarket.question}</div>
            <div className="text-xl font-semibold text-white">{currentMarket.outcome}</div>
            <div className="flex flex-col gap-3">
              <button 
                className="flex justify-between items-center px-5 py-4 bg-green-500 text-white font-bold rounded-xl hover:opacity-90 active:scale-[0.97] transition-all"
                onClick={() => handleBet('YES')}
              >
                <span className="text-base">YES</span>
                <span className="text-xl">{currentMarket.yes_price}¢</span>
              </button>
              <button 
                className="flex justify-between items-center px-5 py-4 bg-red-500 text-white font-bold rounded-xl hover:opacity-90 active:scale-[0.97] transition-all"
                onClick={() => handleBet('NO')}
              >
                <span className="text-base">NO</span>
                <span className="text-xl">{currentMarket.no_price}¢</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
