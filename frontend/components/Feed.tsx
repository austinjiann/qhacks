'use client'

import { useEffect, useRef, useImperativeHandle, forwardRef, memo } from 'react'
import { FeedItem } from '@/types'
import ShortCard from './ShortCard'

interface FeedProps {
  items: FeedItem[]
  onCurrentItemChange?: (item: FeedItem) => void
}

export interface FeedRef {
  scrollToNext: () => void
  scrollToPrev: () => void
}

const FeedComponent = forwardRef<FeedRef, FeedProps>(function Feed({ items, onCurrentItemChange }, ref) {
  const containerRef = useRef<HTMLDivElement>(null)
  const activeIndexRef = useRef(0)
  const onCurrentItemChangeRef = useRef(onCurrentItemChange)
  useEffect(() => {
    onCurrentItemChangeRef.current = onCurrentItemChange
  }, [onCurrentItemChange])

  const itemsRef = useRef(items)
  useEffect(() => {
    itemsRef.current = items
  }, [items])

  const scrollTo = (index: number) => {
    console.log('[Feed] scrollTo called', { index, itemsLength: itemsRef.current.length })
    if (!containerRef.current || index < 0 || index >= itemsRef.current.length) {
      console.log('[Feed] scrollTo aborted')
      return
    }
    const container = containerRef.current
    const itemHeight = container.clientHeight
    console.log('[Feed] scrollTo executing', { itemHeight, targetTop: index * itemHeight })
    container.scrollTo({ top: index * itemHeight, behavior: 'smooth' })
    activeIndexRef.current = index
    if (itemsRef.current[index]) {
      onCurrentItemChangeRef.current?.(itemsRef.current[index])
    }
  }

  useImperativeHandle(ref, () => ({
    scrollToNext: () => scrollTo(activeIndexRef.current + 1),
    scrollToPrev: () => scrollTo(activeIndexRef.current - 1),
  }), [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      const scrollTop = container.scrollTop
      const itemHeight = container.clientHeight
      const currentIndex = Math.round(scrollTop / itemHeight)

      if (currentIndex !== activeIndexRef.current && itemsRef.current[currentIndex]) {
        console.log('[Feed] scroll index changed', { from: activeIndexRef.current, to: currentIndex })
        activeIndexRef.current = currentIndex
        onCurrentItemChangeRef.current?.(itemsRef.current[currentIndex])
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (items.length > 0 && onCurrentItemChangeRef.current) {
      onCurrentItemChangeRef.current(items[0])
    }
  }, [items])

  console.log('[Feed] render', { itemsLength: items.length })

  return (
    <div ref={containerRef} className="feed-container">
      {items.map((item) => (
        <ShortCard key={item.youtube.video_id} item={item} />
      ))}
    </div>
  )
})

export default memo(FeedComponent, (prev, next) => {
  return prev.items === next.items && prev.onCurrentItemChange === next.onCurrentItemChange
})
