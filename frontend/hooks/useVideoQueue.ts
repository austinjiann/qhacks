'use client'

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { QueueItem, FeedItem } from '@/types'
import { VIDEO_IDS } from '@/mystery'

const STORAGE_KEY = 'video_queue'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10

type StoredQueueItem = {
  video_id: string
  status: QueueItem['status']
  error?: string
}

function normalizeStoredQueueItem(value: unknown): QueueItem | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const video_id = typeof raw.video_id === 'string' ? raw.video_id.trim() : ''
  if (!video_id) return null

  const statusValue = typeof raw.status === 'string' ? raw.status : 'pending'
  const normalizedStatus: QueueItem['status'] =
    statusValue === 'failed'
      ? 'failed'
      : statusValue === 'processing' || statusValue === 'matched'
        ? 'pending'
        : 'pending'

  const error = typeof raw.error === 'string' && raw.error.trim() ? raw.error : undefined
  return {
    video_id,
    status: normalizedStatus,
    error: normalizedStatus === 'failed' ? error : undefined,
    result: undefined,
  }
}

function toStoredQueue(queue: QueueItem[]): StoredQueueItem[] {
  return queue.map((item) => {
    const normalizedStatus: QueueItem['status'] = item.status === 'failed' ? 'failed' : 'pending'
    return {
      video_id: item.video_id,
      status: normalizedStatus,
      error: normalizedStatus === 'failed' ? item.error : undefined,
    }
  })
}

function loadFromStorage(): QueueItem[] {
  if (typeof window === 'undefined') return []
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    const parsed: unknown = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((entry) => normalizeStoredQueueItem(entry))
      .filter((entry): entry is QueueItem => entry !== null)
  } catch {
    return []
  }
}

function saveToStorage(queue: QueueItem[]) {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(toStoredQueue(queue)))
}

export function useVideoQueue() {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const initializedRef = useRef(false)

  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true
    
    const stored = loadFromStorage()
    if (stored.length > 0) {
      setQueue(stored)
    } else {
      const initial: QueueItem[] = VIDEO_IDS.map(id => ({
        video_id: id,
        status: 'pending',
      }))
      setQueue(initial)
      saveToStorage(initial)
    }
  }, [])

  useEffect(() => {
    if (queue.length > 0) {
      saveToStorage(queue)
    }
  }, [queue])

  const addVideos = useCallback((videoIds: string[]) => {
    setQueue(prev => {
      const existingIds = new Set(prev.map(q => q.video_id))
      const newItems: QueueItem[] = videoIds
        .filter(id => !existingIds.has(id))
        .map(id => ({ video_id: id, status: 'pending' }))
      return [...prev, ...newItems]
    })
  }, [])

  const clearQueue = useCallback(() => {
    setQueue([])
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  const processQueue = useCallback(async () => {
    if (isProcessing) return
    setIsProcessing(true)

    try {
      setQueue(prev => prev.map(item => 
        item.status === 'pending' ? { ...item, status: 'processing' } : item
      ))

      const pendingIds = queue
        .filter(q => q.status === 'pending' || q.status === 'processing')
        .map(q => q.video_id)
        .slice(0, BATCH_SIZE)

      if (pendingIds.length === 0) {
        setIsProcessing(false)
        return
      }

      const res = await fetch(`${API_URL}/shorts/feed?video_ids=${pendingIds.join(',')}`)
      
      if (!res.ok) {
        throw new Error('Failed to fetch feed')
      }

      const results: FeedItem[] = await res.json()
      const resultsMap = new Map(results.map(r => [r.youtube.video_id, r]))

      setQueue(prev => prev.map(item => {
        if (pendingIds.includes(item.video_id)) {
          const result = resultsMap.get(item.video_id)
          if (result) {
            return { ...item, status: 'matched', result }
          }
          if (item.status === 'matched' && item.result) {
            return item
          }
          return { ...item, status: 'failed', error: 'No match found', result: undefined }
        }
        return item
      }))
    } catch (err) {
      setQueue(prev => prev.map(item => {
        if (item.status === 'processing') {
          return { ...item, status: 'failed', error: String(err) }
        }
        return item
      }))
    } finally {
      setIsProcessing(false)
    }
  }, [queue, isProcessing])

  const feedItems = useMemo(() => 
    queue
      .filter(q => q.status === 'matched' && q.result)
      .map(q => q.result!),
    [queue]
  )

  const stats = useMemo(() => ({
    total: queue.length,
    pending: queue.filter(q => q.status === 'pending').length,
    processing: queue.filter(q => q.status === 'processing').length,
    matched: queue.filter(q => q.status === 'matched').length,
    failed: queue.filter(q => q.status === 'failed').length,
  }), [queue])

  const feedError = useMemo(() => {
    const failed = queue.find(q => q.status === 'failed' && q.error)
    return failed?.error ?? null
  }, [queue])

  const retryFailed = useCallback(() => {
    setQueue(prev =>
      prev.map(item =>
        item.status === 'failed'
          ? { ...item, status: 'pending' as const, error: undefined }
          : item
      )
    )
  }, [])

  return {
    queue,
    feedItems,
    stats,
    feedError,
    isProcessing,
    addVideos,
    clearQueue,
    processQueue,
    retryFailed,
  }
}
