export interface KalshiMarket {
  ticker: string
  question: string
  outcome: string
  yes_price: number
  no_price: number
  volume?: number
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
  status: 'pending' | 'processing' | 'done' | 'failed'
  error: string | null
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
