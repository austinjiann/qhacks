'use client'

import { memo } from 'react'
import { FeedItem } from '@/types'

interface ShortCardProps {
  item: FeedItem
}

function ShortCard({ item }: ShortCardProps) {
  console.log('[ShortCard] render', item.youtube.video_id)
  return (
    <div className="short-card">
      <div className="video-container">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${item.youtube.video_id}?autoplay=1&loop=1&mute=1&playlist=${item.youtube.video_id}&controls=1&modestbranding=1&playsinline=1&rel=0`}
          title={item.youtube.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="video-iframe"
          style={{ pointerEvents: 'auto' }}
        />
      </div>

      <div className="short-info">
        <span className="channel-name">@{item.youtube.channel}</span>
        <span className="video-title">{item.youtube.title}</span>
      </div>
    </div>
  )
}

export default memo(ShortCard, (prevProps, nextProps) => {
  return prevProps.item.youtube.video_id === nextProps.item.youtube.video_id
})
