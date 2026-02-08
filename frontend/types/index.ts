export interface KalshiMarket {
  ticker: string
  event_ticker?: string
  series_ticker?: string
  question: string
  outcome: string
  created_time?: string
  open_time?: string
  market_start_ts?: number
  yes_price: number
  no_price: number
  volume?: number
  image_url?: string
  price_history?: { ts: number; price: number }[]
}

export interface YouTubeShort {
  video_id: string
  title: string
  thumbnail: string
  channel: string
  channel_thumbnail?: string
}

export type VideoMedia =
  | { type: 'youtube'; data: YouTubeShort }
  | { type: 'mp4'; url: string; title?: string }

export interface FeedItem {
  id: string
  kalshi?: KalshiMarket[]
  youtube: YouTubeShort
  video?: VideoMedia
  isInjected?: boolean
  injectedByBetSide?: 'YES' | 'NO'
}

export interface JobStatus {
  job_id: string
  status: 'waiting' | 'done' | 'error'
  video_url?: string | null
  error: string | null
  original_bet_link?: string | null
}

export interface GeneratedVideo {
  job_id: string
  url: string
  side: 'YES' | 'NO'
  kalshi_ticker: string
}

export type QueueItemStatus = 'pending' | 'processing' | 'matched' | 'failed'

export interface QueueItem {
  video_id: string
  status: QueueItemStatus
  result?: FeedItem
  error?: string
}
