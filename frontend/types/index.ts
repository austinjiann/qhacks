export interface KalshiMarket {
  ticker: string
  event_ticker?: string
  question: string
  outcome: string
  yes_price: number
  no_price: number
  volume?: number
  image_url?: string
}

export interface YouTubeShort {
  video_id: string
  title: string
  thumbnail: string
  channel: string
}

export interface FeedItem {
  id: string
  kalshi?: KalshiMarket
  youtube: YouTubeShort
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
  needsRefresh?: boolean
}
