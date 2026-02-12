'use client'

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FeedItem } from '@/types'

const YT_BASE_ORIGIN = 'https://www.youtube.com'
const ALLOWED_ORIGINS = new Set<string>([YT_BASE_ORIGIN, 'https://www.youtube-nocookie.com'])

let globalMuted = true
const muteListeners = new Set<(value: boolean) => void>()

const emitMuteChange = () => {
  for (const listener of muteListeners) {
    listener(globalMuted)
  }
}

const subscribeToMute = (listener: (value: boolean) => void) => {
  muteListeners.add(listener)
  return () => { muteListeners.delete(listener) }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ShortCardProps {
  item: FeedItem
  isActive: boolean
  shouldRender?: boolean
  prefetch?: boolean
  onDelete?: (itemId: string) => void
}

function ShortCard({ item, isActive, shouldRender = true, prefetch = false, onDelete }: ShortCardProps) {
  const isMp4 = item.video?.type === 'mp4'

  const videoRef = useRef<HTMLVideoElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const playerReadyRef = useRef(false)
  const activeStateRef = useRef(isActive)
  const listeningTimersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const errorDetectedRef = useRef(false)
  const blockTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const iframeId = useMemo(() => `short-${item.youtube.video_id}`, [item.youtube.video_id])
  const [playerOrigin] = useState(() => (typeof window !== 'undefined' ? window.location.origin : ''))
  const [isMuted, setIsMuted] = useState(globalMuted)

  const iframeSrc = useMemo(() => {
    const originParam = playerOrigin ? `&origin=${encodeURIComponent(playerOrigin)}` : ''
    return (
      `${YT_BASE_ORIGIN}/embed/${item.youtube.video_id}` +
      `?autoplay=1&loop=1&mute=1&playlist=${item.youtube.video_id}` +
      '&controls=0&playsinline=1&rel=0&enablejsapi=1' +
      originParam
    )
  }, [item.youtube.video_id, playerOrigin])

  const postPlayerMessage = useCallback((func: string, args: unknown[] = []) => {
    const iframe = iframeRef.current
    if (!iframe) return
    iframe.contentWindow?.postMessage(JSON.stringify({
      event: 'command',
      func,
      args,
      id: iframeId,
    }), YT_BASE_ORIGIN)
  }, [iframeId])

  const syncPlayback = useCallback((shouldPlay: boolean) => {
    if (!playerReadyRef.current) return
    postPlayerMessage(shouldPlay ? 'playVideo' : 'pauseVideo')
  }, [postPlayerMessage])

  const syncMute = useCallback(() => {
    if (!playerReadyRef.current) return
    postPlayerMessage(globalMuted ? 'mute' : 'unMute')
  }, [postPlayerMessage])

  const toggleMute = useCallback(() => {
    globalMuted = !globalMuted
    emitMuteChange()
    postPlayerMessage(globalMuted ? 'mute' : 'unMute')
  }, [postPlayerMessage])

  const handleVideoBlocked = useCallback(() => {
    if (errorDetectedRef.current) return
    errorDetectedRef.current = true
    console.warn(`[ShortCard] Video blocked/unavailable: ${item.youtube.video_id}`)
    onDelete?.(item.id)
    const videoId = item.youtube.video_id || item.id
    fetch(`${API_URL}/pool/feed/${videoId}/delete`, { method: 'POST' }).catch(() => {})
  }, [item.id, item.youtube.video_id, onDelete])

  useEffect(() => {
    activeStateRef.current = isActive
    if (!shouldRender) return
    syncPlayback(isActive)
    if (isActive) {
      syncMute()
    }
  }, [isActive, shouldRender, syncPlayback, syncMute])

  useEffect(() => {
    const handleMuteChange = (value: boolean) => {
      setIsMuted((prev) => (prev === value ? prev : value))
    }
    return subscribeToMute(handleMuteChange)
  }, [])

  // Sync muted state to MP4 video element
  useEffect(() => {
    if (!isMp4) return
    const video = videoRef.current
    if (!video) return
    video.muted = isMuted
  }, [isMp4, isMuted])

  // MP4 play/pause control
  useEffect(() => {
    if (!isMp4 || !shouldRender) return
    const video = videoRef.current
    if (!video) return
    if (isActive) {
      if (video.paused) {
        video.play().catch(() => {
          // Autoplay blocked (unmuted) — mute and retry
          video.muted = true
          video.play().catch(() => {})
        })
      }
    } else {
      if (!video.paused) {
        video.pause()
      }
    }
  }, [isActive, isMp4, shouldRender])

  useEffect(() => {
    if (typeof window === 'undefined') return

    playerReadyRef.current = false

    const handleMessage = (event: MessageEvent) => {
      if (!ALLOWED_ORIGINS.has(event.origin)) {
        return
      }
      let data: { event?: string; id?: string; info?: { playerState?: number; errorCode?: number } } | null = null
      try {
        data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
      } catch {
        return
      }
      if (data?.event === 'onReady' && data?.id === iframeId) {
        playerReadyRef.current = true
        errorDetectedRef.current = false
        if (blockTimeoutRef.current) { clearTimeout(blockTimeoutRef.current); blockTimeoutRef.current = null }
        syncPlayback(activeStateRef.current)
        if (!globalMuted) {
          postPlayerMessage('unMute')
        }
      }
      // Detect playback errors: 100=not found, 101/150=embed restricted
      if (data?.event === 'onError' && data?.id === iframeId) {
        handleVideoBlocked()
      }
      // When video ends (state 0), restart to prevent end-screen recommendations
      if (data?.event === 'onStateChange' && data?.id === iframeId && data?.info?.playerState === 0) {
        postPlayerMessage('seekTo', [0, true])
        postPlayerMessage('playVideo')
      }
    }

    window.addEventListener('message', handleMessage)
    return () => {
      window.removeEventListener('message', handleMessage)
      listeningTimersRef.current.forEach(clearTimeout)
      listeningTimersRef.current = []
      if (blockTimeoutRef.current) { clearTimeout(blockTimeoutRef.current); blockTimeoutRef.current = null }
      playerReadyRef.current = false
      errorDetectedRef.current = false
    }
  }, [iframeId, syncPlayback, postPlayerMessage, handleVideoBlocked])

  const handleIframeLoad = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    // Clear any previous retry timers
    listeningTimersRef.current.forEach(clearTimeout)
    listeningTimersRef.current = []
    if (blockTimeoutRef.current) { clearTimeout(blockTimeoutRef.current); blockTimeoutRef.current = null }

    const sendListening = () => {
      iframe.contentWindow?.postMessage(JSON.stringify({
        event: 'listening',
        id: iframeId,
      }), YT_BASE_ORIGIN)
    }

    // Send immediately, then retry — YouTube's player script needs time to initialize
    sendListening()
    listeningTimersRef.current.push(
      setTimeout(sendListening, 250),
      setTimeout(sendListening, 750),
      setTimeout(sendListening, 2000),
    )

    // Timeout: if player never becomes ready and card is active, video is likely blocked
    blockTimeoutRef.current = setTimeout(() => {
      if (!playerReadyRef.current && !errorDetectedRef.current && activeStateRef.current) {
        handleVideoBlocked()
      }
    }, 8000)
  }, [iframeId, handleVideoBlocked])

  if (isMp4 && item.video?.type === 'mp4') {
    return (
      <div className="short-card">
        <div className="video-container" style={!shouldRender ? { visibility: 'hidden' } : undefined}>
          <video
            ref={videoRef}
            className="video-iframe"
            src={item.video.url}
            autoPlay={isActive}
            loop
            muted={isMuted}
            playsInline
            preload="auto"
            style={{ pointerEvents: 'auto', objectFit: 'cover' }}
          />
        </div>
        {shouldRender && (
          <button
            onClick={toggleMute}
            style={{
              position: 'absolute',
              bottom: 80,
              right: 12,
              zIndex: 15,
              width: 36,
              height: 36,
              borderRadius: '50%',
              border: 'none',
              background: 'rgba(0, 0, 0, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              pointerEvents: 'auto',
              padding: 0,
            }}
            aria-label={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <line x1="23" y1="9" x2="17" y2="15" />
                <line x1="17" y1="9" x2="23" y2="15" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              </svg>
            )}
          </button>
        )}
        {shouldRender && onDelete && (
          <button
            onClick={() => {
              onDelete(item.id)
              const videoId = item.youtube.video_id || item.id
              fetch(`${API_URL}/pool/feed/${videoId}/delete`, { method: 'POST' }).catch(() => {})
            }}
            style={{
              position: 'absolute',
              bottom: 80,
              left: 12,
              zIndex: 15,
              width: 36,
              height: 36,
              borderRadius: '50%',
              border: 'none',
              background: 'rgba(0, 0, 0, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              pointerEvents: 'auto',
              padding: 0,
            }}
            aria-label="Delete short"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        )}
      </div>
    )
  }

  if (!shouldRender) {
    return (
      <div className="short-card">
        {prefetch && !isMp4 && item.youtube.video_id && (
          <link rel="prefetch" href={iframeSrc} as="document" />
        )}
        <div className="video-container" style={{
          width: '100%',
          height: '100%',
          background: item.youtube.thumbnail
            ? `url(${item.youtube.thumbnail}) center/cover no-repeat #000`
            : '#000',
        }} />
      </div>
    )
  }

  return (
    <div className="short-card">
      <div className="video-container" style={item.youtube.thumbnail ? {
        background: `url(${item.youtube.thumbnail}) center/cover no-repeat #000`,
      } : undefined}>
        <iframe
          ref={iframeRef}
          id={iframeId}
          src={iframeSrc}
          title={item.youtube.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="video-iframe"
          style={{ pointerEvents: 'auto' }}
          loading={isActive ? 'eager' : 'lazy'}
          onLoad={handleIframeLoad}
        />
      </div>

      <button
        onClick={toggleMute}
        style={{
          position: 'absolute',
          bottom: 80,
          right: 12,
          zIndex: 15,
          width: 36,
          height: 36,
          borderRadius: '50%',
          border: 'none',
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          pointerEvents: 'auto',
          padding: 0,
        }}
        aria-label={isMuted ? 'Unmute' : 'Mute'}
      >
        {isMuted ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <line x1="23" y1="9" x2="17" y2="15" />
            <line x1="17" y1="9" x2="23" y2="15" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
        )}
      </button>

      {onDelete && (
        <button
          onClick={() => {
            onDelete(item.id)
            const videoId = item.youtube.video_id || item.id
            fetch(`${API_URL}/pool/feed/${videoId}/delete`, { method: 'POST' }).catch(() => {})
          }}
          style={{
            position: 'absolute',
            bottom: 80,
            left: 12,
            zIndex: 15,
            width: 36,
            height: 36,
            borderRadius: '50%',
            border: 'none',
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            pointerEvents: 'auto',
            padding: 0,
          }}
          aria-label="Delete short"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      )}

    </div>
  )
}

export default memo(ShortCard, (prevProps, nextProps) => {
  return (
    prevProps.item.id === nextProps.item.id &&
    prevProps.isActive === nextProps.isActive &&
    prevProps.shouldRender === nextProps.shouldRender &&
    prevProps.prefetch === nextProps.prefetch &&
    prevProps.onDelete === nextProps.onDelete
  )
})
