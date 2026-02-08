'use client'

import { useState, useCallback } from 'react'
import Image from 'next/image'
import { KalshiMarket } from '@/types'

interface BetPlacementCardProps {
  market: KalshiMarket
  initialSide: 'YES' | 'NO'
  onSubmit: (data: { side: 'YES' | 'NO'; amount: number }) => void
  onClose: () => void
}

export default function BetPlacementCard({ market, initialSide, onSubmit, onClose }: BetPlacementCardProps) {
  const [side, setSide] = useState<'YES' | 'NO'>(initialSide)
  const [amount, setAmount] = useState('')
  const [imgError, setImgError] = useState(false)

  const price = side === 'YES' ? (market.yes_price ?? 50) : (market.no_price ?? 50)
  const payout = amount && Number(amount) > 0 ? (Number(amount) / (price / 100)).toFixed(2) : '0.00'
  const odds = price

  const handleSubmit = useCallback(() => {
    const numAmount = Number(amount)
    if (!numAmount || numAmount <= 0) return
    onSubmit({ side, amount: numAmount })
  }, [amount, side, onSubmit])

  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: 'rgba(30, 30, 30, 0.72)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        {market.image_url && !imgError ? (
          <Image
            src={market.image_url}
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
        <div className="flex-1">
          <p className="text-white/90 text-sm leading-snug line-clamp-2">{market.question}</p>
        </div>
        <button
          onClick={onClose}
          className="text-white/40 hover:text-white/70 transition-colors"
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Yes/No toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setSide('YES')}
          className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
            side === 'YES'
              ? 'bg-emerald-500/30 border-emerald-500/60 text-emerald-300'
              : 'bg-white/[0.05] border-white/10 text-white/40'
          }`}
          style={{ border: '1.5px solid', borderColor: side === 'YES' ? 'rgba(16, 185, 129, 0.6)' : 'rgba(255,255,255,0.1)' }}
        >
          Yes {market.yes_price}¢
        </button>
        <button
          onClick={() => setSide('NO')}
          className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all ${
            side === 'NO'
              ? 'bg-red-500/30 border-red-500/60 text-red-300'
              : 'bg-white/[0.05] border-white/10 text-white/40'
          }`}
          style={{ border: '1.5px solid', borderColor: side === 'NO' ? 'rgba(239, 68, 68, 0.6)' : 'rgba(255,255,255,0.1)' }}
        >
          No {market.no_price}¢
        </button>
      </div>

      {/* Amount input */}
      <div className="mb-4">
        <label className="text-xs text-white/40 uppercase tracking-wider mb-1.5 block">Amount ($)</label>
        <input
          type="number"
          min="1"
          step="1"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Enter amount..."
          className="w-full px-4 py-3 rounded-lg text-white text-sm"
          style={{
            background: 'rgba(255, 255, 255, 0.06)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            outline: 'none',
          }}
        />
      </div>

      {/* Odds + Payout */}
      <div className="flex items-center justify-between text-xs text-white/50 mb-4">
        <span>Odds: <span className="text-white/70 font-medium">{odds}%</span></span>
        <span>Payout: <span className="text-white/70 font-medium">${payout}</span></span>
      </div>

      {/* Place Bet button */}
      <button
        onClick={handleSubmit}
        disabled={!amount || Number(amount) <= 0}
        className="w-full py-3 rounded-xl text-sm font-medium transition-all cursor-pointer"
        style={{
          background: side === 'YES'
            ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
            : 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
          color: '#fff',
          border: 'none',
          opacity: !amount || Number(amount) <= 0 ? 0.4 : 1,
          boxShadow: side === 'YES'
            ? '0 4px 15px rgba(16, 185, 129, 0.4)'
            : '0 4px 15px rgba(239, 68, 68, 0.4)',
        }}
      >
        Place {side} Bet {amount ? `$${amount}` : ''}
      </button>
    </div>
  )
}