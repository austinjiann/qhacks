'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { QueueItem, FeedItem } from '@/types'

const STORAGE_KEY = 'video_queue'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const BATCH_SIZE = 10

export const HARDCODED_VIDEO_IDS = [
  "vHaPgrSMlI0",
  "HZOkwNsYFdo",
  "w1rbnM6A4AA",
  "_qW6a1A9gb0",
  "3fQhDJlRJYg",
  "LQ8uCvKYu3Y",
]

function loadFromStorage(): QueueItem[] {
  if (typeof window === 'undefined') return []
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveToStorage(queue: QueueItem[]) {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(queue))
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
      const initial: QueueItem[] = HARDCODED_VIDEO_IDS.map(id => ({
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
          return { ...item, status: 'failed', error: 'No match found' }
        }
        return item
      }))
    } catch (err) {
      setQueue(prev => prev.map(item => 
        item.status === 'processing' 
          ? { ...item, status: 'failed', error: String(err) }
          : item
      ))
    } finally {
      setIsProcessing(false)
    }
  }, [queue, isProcessing])

  const feedItems = queue
    .filter(q => q.status === 'matched' && q.result)
    .map(q => q.result!)

  const stats = {
    total: queue.length,
    pending: queue.filter(q => q.status === 'pending').length,
    processing: queue.filter(q => q.status === 'processing').length,
    matched: queue.filter(q => q.status === 'matched').length,
    failed: queue.filter(q => q.status === 'failed').length,
  }

  return {
    queue,
    feedItems,
    stats,
    isProcessing,
    addVideos,
    clearQueue,
    processQueue,
  }
}
