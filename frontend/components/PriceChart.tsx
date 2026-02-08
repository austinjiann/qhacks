'use client'

import { useEffect, useRef } from 'react'
import {
  createChart,
  type AreaData,
  type IChartApi,
  type ISeriesApi,
  type Time,
  ColorType,
  type UTCTimestamp,
} from 'lightweight-charts'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const KALSHI_GREEN = '#00d084'
const KALSHI_AREA_TOP = 'rgba(0, 208, 132, 0.15)'
const KALSHI_AREA_BOTTOM = 'rgba(0, 208, 132, 0)'
const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat('en-US', { month: 'short' })

export type PriceChartReadyPayload = {
  points: number
  spanSeconds: number
  status: 'ok' | 'empty' | 'error'
}

interface PriceChartProps {
  ticker: string
  seriesTicker: string
  priceHistory?: { ts: number; price: number }[]
  createdTime?: string
  openTime?: string
  marketStartTs?: number
  onReady?: (ticker: string, payload: PriceChartReadyPayload) => void
}

const clampToKalshiRange = (value: number): number => Math.min(100, Math.max(0, value))

const formatCents = (value: number): string => {
  const rounded = Math.round(value * 100) / 100
  return Number.isInteger(rounded) ? `${rounded.toFixed(0)}c` : `${rounded.toFixed(2)}c`
}

const parseTimeToUnixSeconds = (value?: string): number | null => {
  if (!value || typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed) return null

  if (/^\d+$/.test(trimmed)) {
    const numeric = Number(trimmed)
    if (!Number.isFinite(numeric) || numeric <= 0) return null
    return numeric > 10_000_000_000 ? Math.trunc(numeric / 1000) : Math.trunc(numeric)
  }

  const normalizedFraction = trimmed.replace(
    /(\.\d{3})\d+(?=Z|[+-]\d{2}:\d{2}$)/,
    '$1'
  )
  const parsedMs = Date.parse(normalizedFraction)
  if (Number.isNaN(parsedMs)) return null
  return Math.trunc(parsedMs / 1000)
}

const toTimestamp = (time: Time): number => {
  if (typeof time === 'number') return time
  if (typeof time === 'string') {
    const parsedMs = Date.parse(time)
    return Number.isNaN(parsedMs) ? 0 : Math.trunc(parsedMs / 1000)
  }
  return Date.UTC(time.year, time.month - 1, time.day) / 1000
}

const getTimeSpanSeconds = (data: AreaData[]): number => {
  if (data.length < 2) return 0
  return Math.max(0, toTimestamp(data[data.length - 1].time) - toTimestamp(data[0].time))
}

const toChartData = (points: { ts: number; price: number }[] = []): AreaData[] => {
  const byTimestamp = new Map<number, number>()

  for (const point of points) {
    if (!Number.isFinite(point.ts) || !Number.isFinite(point.price)) continue
    const ts = point.ts > 10_000_000_000 ? Math.trunc(point.ts / 1000) : Math.trunc(point.ts)
    byTimestamp.set(ts, clampToKalshiRange(point.price))
  }

  return Array.from(byTimestamp.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([ts, price]) => ({
      time: ts as UTCTimestamp,
      value: price,
    }))
}

function PriceChartInner({
  ticker,
  seriesTicker,
  createdTime,
  openTime,
  marketStartTs,
  onReady,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const onReadyRef = useRef(onReady)

  useEffect(() => {
    onReadyRef.current = onReady
  }, [onReady])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 200,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.35)',
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: 'rgba(255, 255, 255, 0.08)', style: 1 },
      },
      rightPriceScale: {
        borderVisible: false,
        autoScale: true,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: false,
        secondsVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
        tickMarkFormatter: (time: Time) =>
          MONTH_LABEL_FORMATTER.format(new Date(toTimestamp(time) * 1000)),
      },
      crosshair: {
        horzLine: {
          visible: true,
          labelVisible: true,
          style: 3,
          color: 'rgba(255, 255, 255, 0.3)',
        },
        vertLine: {
          visible: true,
          labelVisible: true,
          style: 3,
          color: 'rgba(255, 255, 255, 0.3)',
        },
      },
      handleScroll: false,
      handleScale: false,
      localization: {
        priceFormatter: (price: number) => formatCents(price),
      },
    })

    chartRef.current = chart

    const series = chart.addAreaSeries({
      lineColor: KALSHI_GREEN,
      topColor: KALSHI_AREA_TOP,
      bottomColor: KALSHI_AREA_BOTTOM,
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceLineVisible: true,
      lastValueVisible: true,
    })

    seriesRef.current = series

    let currentPointCount = 0
    let currentSpanSeconds = 0
    let cancelled = false
    let readyNotified = false

    const notifyReady = (payload: PriceChartReadyPayload) => {
      if (readyNotified || cancelled) return
      readyNotified = true
      onReadyRef.current?.(ticker, payload)
    }

    const setSeriesData = (
      points: { ts: number; price: number }[],
      opts: { requireWiderRange?: boolean } = {}
    ): AreaData[] => {
      const data = toChartData(points)
      if (data.length === 0) return []

      const nextSpanSeconds = getTimeSpanSeconds(data)
      if (opts.requireWiderRange) {
        const widerRange = nextSpanSeconds > currentSpanSeconds
        const denserSameRange = nextSpanSeconds === currentSpanSeconds && data.length > currentPointCount
        if (!widerRange && !denserSameRange) {
          return []
        }
      }

      series.setData(data)
      chart.timeScale().fitContent()
      currentPointCount = data.length
      currentSpanSeconds = nextSpanSeconds
      return data
    }

    const fetchFullHistory = async () => {
      try {
        if (!ticker || !seriesTicker) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'error' })
          return
        }

        const startTs =
          (typeof marketStartTs === 'number' && Number.isFinite(marketStartTs) && marketStartTs > 0
            ? Math.trunc(marketStartTs)
            : null) ??
          parseTimeToUnixSeconds(createdTime) ??
          parseTimeToUnixSeconds(openTime)

        const params = new URLSearchParams({
          ticker,
          series_ticker: seriesTicker,
          period: '1440',
          end_ts: `${Math.floor(Date.now() / 1000)}`,
        })

        if (startTs) {
          params.set('start_ts', `${startTs}`)
        } else {
          params.set('hours', `${24 * 365}`)
        }

        const res = await fetch(`${API_URL}/shorts/candlesticks?${params}`)
        if (!res.ok || cancelled) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'error' })
          return
        }

        const json = await res.json()
        const candles: { ts: number; price: number }[] = Array.isArray(json.candlesticks)
          ? json.candlesticks
          : []

        if (cancelled) return
        if (candles.length === 0) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'empty' })
          return
        }

        const accepted = setSeriesData(candles, { requireWiderRange: true })
        if (accepted.length === 0) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'empty' })
          return
        }

        notifyReady({
          points: accepted.length,
          spanSeconds: getTimeSpanSeconds(accepted),
          status: 'ok',
        })
      } catch {
        notifyReady({ points: 0, spanSeconds: 0, status: 'error' })
      }
    }
    fetchFullHistory()

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      cancelled = true
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [ticker, seriesTicker, createdTime, openTime, marketStartTs])

  return <div ref={containerRef} className="w-full price-chart-container" style={{ height: 200 }} />
}

export default PriceChartInner
