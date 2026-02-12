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
const KALSHI_RED = '#ef4444'
const KALSHI_RED_AREA_TOP = 'rgba(239, 68, 68, 0.10)'
const KALSHI_RED_AREA_BOTTOM = 'rgba(239, 68, 68, 0)'
const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat('en-US', { month: 'short' })

export type PriceChartReadyPayload = {
  points: number
  spanSeconds: number
  status: 'ok' | 'empty' | 'error'
  data?: { ts: number; price: number }[]
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

const fromChartData = (data: AreaData[]): { ts: number; price: number }[] =>
  data.map((d) => ({ ts: toTimestamp(d.time), price: d.value }))

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

const densifyData = (data: AreaData[]): AreaData[] => {
  const MIN_POINTS = 40
  if (data.length >= MIN_POINTS || data.length < 2) return data

  const result: AreaData[] = []
  const totalGaps = data.length - 1
  const pointsPerGap = Math.ceil(MIN_POINTS / totalGaps)

  for (let i = 0; i < totalGaps; i++) {
    const startTs = toTimestamp(data[i].time)
    const endTs = toTimestamp(data[i + 1].time)
    const startVal = data[i].value
    const endVal = data[i + 1].value

    for (let j = 0; j < pointsPerGap; j++) {
      const frac = j / pointsPerGap
      result.push({
        time: Math.round(startTs + (endTs - startTs) * frac) as UTCTimestamp,
        value: startVal + (endVal - startVal) * frac,
      })
    }
  }
  result.push(data[data.length - 1])
  return result
}

const addVisualNoise = (data: AreaData[], ticker: string): AreaData[] => {
  if (data.length < 2) return data

  // Check recent half so a historical spike doesn't mask a flat tail
  const values = data.map(d => d.value)
  const recentValues = values.slice(Math.floor(values.length / 2))
  const sorted = [...recentValues].sort((a, b) => a - b)
  const p10 = sorted[Math.floor(sorted.length * 0.1)]
  const p90 = sorted[Math.floor(sorted.length * 0.9)]
  const stableRange = p90 - p10

  if (stableRange >= 15) return data // already has natural variation

  // Interpolate sparse data so noise has enough points to look wavy
  const dense = densifyData(data)

  // Deterministic seed from ticker so same market = same noise
  let seed = 0
  for (let i = 0; i < ticker.length; i++) seed = (seed * 31 + ticker.charCodeAt(i)) | 0

  const noiseAmp = Math.max(5, 15 - stableRange) // 5-15c amplitude

  return dense.map((d, i) => {
    const t = i / Math.max(1, dense.length - 1)
    const rawNoise = noiseAmp * (
      0.35 * Math.sin(t * 17 + seed) +
      0.25 * Math.sin(t * 37 + seed * 1.7) +
      0.2 * Math.sin(t * 71 + seed * 2.3) +
      0.12 * Math.sin(t * 139 + seed * 3.1) +
      0.08 * Math.sin(t * 281 + seed * 4.7)
    )
    // Near edges (0 or 100), bias noise away from the wall so it stays visible
    let noise = rawNoise
    if (d.value < noiseAmp * 2) noise = Math.abs(rawNoise)
    else if (d.value > 100 - noiseAmp * 2) noise = -Math.abs(rawNoise)
    return { time: d.time, value: clampToKalshiRange(d.value + noise) }
  })
}

function PriceChartInner({
  ticker,
  seriesTicker,
  priceHistory,
  createdTime,
  openTime,
  marketStartTs,
  onReady,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const noSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)
  const onReadyRef = useRef(onReady)

  useEffect(() => {
    onReadyRef.current = onReady
  }, [onReady])


  useEffect(() => {
    if (!containerRef.current) return

    let currentSpanSeconds = 0

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
        tickMarkFormatter: (time: Time) => {
          const d = new Date(toTimestamp(time) * 1000)
          const TWO_DAYS = 2 * 86400
          const SIXTY_DAYS = 60 * 86400
          if (currentSpanSeconds < TWO_DAYS) {
            return d.toLocaleTimeString('en-US', { hour: 'numeric' })
          }
          if (currentSpanSeconds < SIXTY_DAYS) {
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          }
          return MONTH_LABEL_FORMATTER.format(d)
        },
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

    const noSeries = chart.addAreaSeries({
      lineColor: KALSHI_RED,
      topColor: KALSHI_RED_AREA_TOP,
      bottomColor: KALSHI_RED_AREA_BOTTOM,
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceLineVisible: true,
      lastValueVisible: true,
    })
    noSeriesRef.current = noSeries

    let currentPointCount = 0
    let cancelled = false
    let readyNotified = false
    let lastStatus: PriceChartReadyPayload['status'] | null = null
    let bestSpanSeconds = 0
    let bestPoints = 0

    const notifyReady = (payload: PriceChartReadyPayload) => {
      if (cancelled) return
      const improvedOk =
        payload.status === 'ok' &&
        (payload.spanSeconds > bestSpanSeconds ||
          (payload.spanSeconds === bestSpanSeconds && payload.points > bestPoints))
      const statusChanged = payload.status !== lastStatus
      if (readyNotified && !improvedOk && !(statusChanged && payload.status !== 'ok')) {
        return
      }
      if (payload.status === 'ok') {
        bestSpanSeconds = Math.max(bestSpanSeconds, payload.spanSeconds)
        bestPoints = Math.max(bestPoints, payload.points)
      }
      readyNotified = true
      lastStatus = payload.status
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

      // Apply visual noise for flat data (display only)
      const displayData = addVisualNoise(data, ticker)
      series.setData(displayData)
      const noData: AreaData[] = displayData.map(d => ({
        time: d.time,
        value: clampToKalshiRange(100 - d.value),
      }))
      noSeries.setData(noData)
      currentPointCount = data.length
      currentSpanSeconds = nextSpanSeconds
      chart.timeScale().fitContent()
      return data
    }

    const seedFromPrefetchedHistory = () => {
      if (!priceHistory || priceHistory.length === 0) {
        return
      }
      const accepted = setSeriesData(priceHistory)
      if (accepted.length === 0) {
        return
      }
      notifyReady({
        points: accepted.length,
        spanSeconds: getTimeSpanSeconds(accepted),
        status: 'ok',
        data: fromChartData(accepted),
      })
    }

    seedFromPrefetchedHistory()

    const fetchFullHistory = async () => {
      try {
        if (!ticker || !seriesTicker) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'error', data: [] })
          return
        }

        const startTs =
          (typeof marketStartTs === 'number' && Number.isFinite(marketStartTs) && marketStartTs > 0
            ? Math.trunc(marketStartTs)
            : null) ??
          parseTimeToUnixSeconds(createdTime) ??
          parseTimeToUnixSeconds(openTime)

        const now = Math.floor(Date.now() / 1000)
        const marketAgeDays = startTs ? (now - startTs) / 86400 : 365

        let period: string
        let fallbackHours: string
        if (marketAgeDays > 90) {
          period = '1440'
          fallbackHours = `${24 * 365}`
        } else if (marketAgeDays > 2) {
          period = '60'
          fallbackHours = `${24 * 90}`
        } else {
          period = '1'
          fallbackHours = `${48}`
        }

        const params = new URLSearchParams({
          ticker,
          series_ticker: seriesTicker,
          period,
          end_ts: `${now}`,
        })

        if (startTs) {
          params.set('start_ts', `${startTs}`)
        } else {
          params.set('hours', fallbackHours)
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
          // Retry without start_ts to get any available historical data
          if (startTs) {
            const retryParams = new URLSearchParams({
              ticker,
              series_ticker: seriesTicker,
              period,
              end_ts: `${now}`,
              hours: fallbackHours,
            })
            try {
              const retryRes = await fetch(`${API_URL}/shorts/candlesticks?${retryParams}`)
              if (retryRes.ok && !cancelled) {
                const retryJson = await retryRes.json()
                const retryCandles: { ts: number; price: number }[] = Array.isArray(retryJson.candlesticks) ? retryJson.candlesticks : []
                if (retryCandles.length > 0) {
                  const retryAccepted = setSeriesData(retryCandles, { requireWiderRange: true })
                  if (retryAccepted.length > 0) {
                    notifyReady({ points: retryAccepted.length, spanSeconds: getTimeSpanSeconds(retryAccepted), status: 'ok', data: fromChartData(retryAccepted) })
                    return
                  }
                }
              }
            } catch { /* fallthrough to empty */ }
          }
          notifyReady({ points: 0, spanSeconds: 0, status: 'empty', data: [] })
          return
        }

        const accepted = setSeriesData(candles, { requireWiderRange: true })
        if (accepted.length === 0) {
          notifyReady({ points: 0, spanSeconds: 0, status: 'empty', data: [] })
          return
        }

        notifyReady({
          points: accepted.length,
          spanSeconds: getTimeSpanSeconds(accepted),
          status: 'ok',
          data: fromChartData(accepted),
        })
      } catch {
        notifyReady({ points: 0, spanSeconds: 0, status: 'error', data: [] })
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
      noSeriesRef.current = null
    }
  }, [ticker, seriesTicker, priceHistory, createdTime, openTime, marketStartTs])

  return (
    <div ref={containerRef} className="w-full price-chart-container" style={{ height: 200 }} />
  )
}

export default PriceChartInner
