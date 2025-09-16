'use client';

import React, { useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { JSPoint, ChartDataPoint, CandlestickDataPoint, ExtremumPoint, TrendPeriod, DetectedPattern } from '@/services/api';

// Plotly를 동적으로 import (SSR 이슈 방지)
const Plot = dynamic(
  () => import('react-plotly.js'),
  {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-96">차트 로딩 중...</div>
  }
);

// 로깅 유틸리티
const logger = {
  info: (message: string, data?: any) => {
    console.log(`%c[CHART] ${message}`, 'color: #8e44ad', data ? data : '');
  },
  success: (message: string, data?: any) => {
    console.log(`%c[CHART] ${message}`, 'color: #27ae60', data ? data : '');
  },
  warn: (message: string, data?: any) => {
    console.warn(`%c[CHART] ${message}`, 'color: #f39c12', data ? data : '');
  },
  error: (message: string, error?: any) => {
    console.error(`%c[CHART] ${message}`, 'color: #e74c3c', error ? error : '');
  },
  debug: (message: string, data?: any) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(`%c[CHART:DEBUG] ${message}`, 'color: #3498db', data ? data : '');
    }
  }
};

// 시간 변환 유틸: 다양한 입력을 epoch milliseconds로 정규화
// 반환값: epoch milliseconds (number) 또는 null
const toEpochMs = (t: any): number | null => {
  if (t == null) return null;
  try {
    if (typeof t === 'number') return t < 10_000_000_000 ? t * 1000 : t; // seconds->ms or already ms
    if (typeof t === 'string' && /^\d+$/.test(t)) {
      const n = Number(t);
      return n < 10_000_000_000 ? n * 1000 : n;
    }
    // try parse ISO or other date string
    const dt = new Date(t);
    const ms = Number(dt.getTime());
    return Number.isFinite(ms) ? ms : null;
  } catch (e) {
    if (process.env.NODE_ENV === 'development') console.debug('[CHART] toEpochMs parse error', e, t);
    return null;
  }
};

// 차트 컴포넌트 속성
interface ChartProps {
  data: (ChartDataPoint | CandlestickDataPoint)[];
  jsPoints?: JSPoint[];
  showJSPoints?: boolean;
  showZigZag?: boolean;
  showTrendBackground?: boolean;
  currentTrend?: string;
  height?: number;
  width?: number;
  chartType?: 'line' | 'candlestick';
  onCrosshairMove?: (param: any) => void;
  zigzagPoints?: ExtremumPoint[];
  trendDirection?: 'up' | 'down' | 'neutral';
  trendPeriods?: TrendPeriod[];
  patterns?: DetectedPattern[];
  showPatternNecklines?: boolean;
  timeframe?: string;
  showVolume?: boolean;
}

// 데이터 타입 체크 함수
function isCandlestickData(data: any[]): data is CandlestickDataPoint[] {
  return data.length > 0 && 'open' in data[0] && 'high' in data[0] && 'low' in data[0] && 'close' in data[0];
}

// Chart 컴포넌트
const Chart: React.FC<ChartProps> = ({
  data,
  jsPoints = [],
  showJSPoints = true,
  showZigZag = true,
  showTrendBackground = false,
  currentTrend = 'neutral',
  height = 400,
  width,
  chartType = 'candlestick',
  onCrosshairMove,
  zigzagPoints = [],
  trendDirection = 'neutral',
  trendPeriods = [],
  patterns = [],
  showPatternNecklines = true,
  timeframe = '1d'
  , showVolume = true
}) => {
  // 테마 감지 (다크 모드 여부)
  const isDarkMode = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');

  // Fix Plotly modebar interaction: ensure pointer events enabled and bring to front
  useEffect(() => {
    try {
      const style = document.createElement('style');
      style.id = 'plotly-modebar-fix';
      style.innerHTML = `
        .modebar, .modebar button { pointer-events: auto !important; }
        .modebar-container { z-index: 2000 !important; }
      `;
      document.head.appendChild(style);
      return () => {
        const el = document.getElementById('plotly-modebar-fix');
        if (el && el.parentNode) el.parentNode.removeChild(el);
      };
    } catch (e) {
      // ignore in non-browser environments
    }
  }, []);

  // Plotly 데이터 준비
  const plotData = useMemo(() => {
    const traces: any[] = [];
    
    if (data.length === 0) {
      return traces;
    }

    logger.debug('Chart data processing', { 
      dataLength: data.length, 
      chartType, 
      firstItem: data[0] 
    });

    // 시간값 정규화: toEpochMs 유틸 재사용
    const normalizeTime = toEpochMs;

    // 메인 차트 데이터
    if (chartType === 'candlestick' && isCandlestickData(data)) {
      // 캔들스틱 차트 - DTTB 스타일 색상 및 설정
      const candleData = data as CandlestickDataPoint[];
      traces.push({
        type: 'candlestick',
        x: candleData.map(d => normalizeTime((d as any).time)),
        open: candleData.map(d => d.open),
        high: candleData.map(d => d.high),
        low: candleData.map(d => d.low),
        close: candleData.map(d => d.close),
        name: '가격',
        // DTTB 스타일: 기본 Plotly 색상 사용 (더 선명하고 표준적)
        increasing: { 
          line: { color: '#00ff00' },  // 밝은 녹색 (상승)
          fillcolor: '#00ff00'
        },
        decreasing: { 
          line: { color: '#ff0000' },  // 밝은 빨간색 (하락)
          fillcolor: '#ff0000'
        },
        line: { width: 1 },  // 선 두께 설정
        showlegend: false
      });
      // 거래량(Volume) 트레이스: 데이터에 volume 필드가 있으면 하단에 bar로 표시
      try {
        if (showVolume && candleData.some(d => (d as any).volume !== undefined)) {
          const volumes = candleData.map(d => Number((d as any).volume) || 0);
          // color each bar: green if volume >= previous volume, red otherwise
          const volColors = volumes.map((v, i) => {
            if (i === 0) return isDarkMode ? '#94f9b9' : '#9ae6b4';
            return v >= volumes[i - 1] ? (isDarkMode ? '#22c55e' : '#16a34a') : (isDarkMode ? '#ff7b7b' : '#ef4444');
          });

          traces.push({
            type: 'bar',
            x: candleData.map(d => normalizeTime((d as any).time)),
            y: volumes,
            name: 'Volume',
            marker: { color: volColors },
            yaxis: 'y2',
            hoverinfo: 'x+y',
            opacity: 0.8,
            showlegend: false
          });
        }
      } catch (e) { /* defensive: if volume absent or malformed, skip */ }
    } else {
      // 라인 차트
      const lineData = data as ChartDataPoint[];
      traces.push({
        type: 'scatter',
        mode: 'lines',
        x: lineData.map(d => normalizeTime((d as any).time)),
        y: lineData.map(d => d.value),
        name: '가격',
        line: { color: '#8b5cf6', width: 2 }
      });
    }

    // JS Points (Peak/Valley) 표시
    if (showJSPoints && jsPoints.length > 0) {
      const peaks = jsPoints.filter(point => point.type === 'peak');
      const valleys = jsPoints.filter(point => point.type === 'valley');

      if (peaks.length > 0) {
        traces.push({
          type: 'scatter',
          mode: 'markers+text',  // DTTB 스타일: 텍스트 추가
          x: peaks.map(p => normalizeTime((p as any).time)),
          y: peaks.map(p => p.value * 1.005),  // DTTB 스타일: 위치 조정
          text: peaks.map(() => 'P'),  // DTTB 스타일: 텍스트 표시
          textposition: 'top center',
          textfont: {
            family: 'Arial, sans-serif',
            size: 12,
            color: isDarkMode ? '#e5e7eb' : 'black'
          },
          name: 'Peak',
          marker: {
            symbol: 'triangle-down',
            size: 9,  // 다크 모드 가시성 증대
            color: '#ef4444'
          },
          hoverinfo: 'x+y+name',
          showlegend: false
        });
      }

      if (valleys.length > 0) {
        traces.push({
          type: 'scatter',
          mode: 'markers+text',  // DTTB 스타일: 텍스트 추가
          x: valleys.map(v => normalizeTime((v as any).time)),
          y: valleys.map(v => v.value * 0.995),  // DTTB 스타일: 위치 조정
          text: valleys.map(() => 'V'),  // DTTB 스타일: 텍스트 표시
          textposition: 'bottom center',
          textfont: {
            family: 'Arial, sans-serif',
            size: 12,
            color: isDarkMode ? '#e5e7eb' : 'black'
          },
          name: 'Valley',
          marker: {
            symbol: 'triangle-up',
            size: 9,  // 다크 모드 가시성 증대
            color: '#22c55e'
          },
          hoverinfo: 'x+y+name',
          showlegend: false
        });
      }
    }

    // ZigZag 라인 표시 - 분석 엔드포인트의 extremum 시퀀스 사용
    if (showZigZag && zigzagPoints.length > 1) {
      traces.push({
        type: 'scatter',
        mode: 'lines',
        x: zigzagPoints.map(p => normalizeTime((p as any).actual_date)),
        y: zigzagPoints.map(p => p.value),
        name: 'ZigZag',
        line: { color: isDarkMode ? '#e5e7eb' : '#6b7280', width: 1 },
        hoverinfo: 'skip',
        showlegend: false
      });
    }

    // 패턴 넥라인(구간 내부) 표시
    if (showPatternNecklines && patterns && patterns.length > 0) {
      // debug: log incoming patterns prop
      console.log('[CHART:DEBUG] patterns prop len:', patterns?.length, 'sample:', patterns?.slice(0,3));
      const seen = new Set<string>();
      // Convert various time representations into epoch milliseconds (number) using shared util
      // Returns null if conversion fails.
      const toMs = toEpochMs;

      const pickDate = (d: any) => (d ? (d.date ?? d.actual_date ?? d) : undefined);

      for (const p of patterns) {
        const m: any = p.meta || {};
        const neckline = m?.neckline;
        // Prefer explicit start/end from backend (top-level first, then meta fields)
        const prefStart = (p as any).startTimeEpoch ?? (p as any).startTime ?? m?.startTimeEpoch ?? m?.startTime ?? null;
        const prefEnd = (p as any).endTimeEpoch ?? (p as any).endTime ?? m?.endTimeEpoch ?? m?.endTime ?? null;
        // 1) 구간 계산: 요구사항에 맞춰 HS=V3~종결, IHS=P3~종결, DT=start_peak~종결, DB=start_valley~종결
        let startDate: any = prefStart !== null ? prefStart : p.date;
        if (p.pattern_type === 'HS') {
          startDate = prefStart !== null ? prefStart : (pickDate(m.V3) || pickDate(m.V2) || pickDate(m.P1) || p.date);
        } else if (p.pattern_type === 'IHS') {
          startDate = prefStart !== null ? prefStart : (pickDate(m.P3) || pickDate(m.P2) || pickDate(m.V1) || p.date);
        } else if (p.pattern_type === 'DT') {
          startDate = prefStart !== null ? prefStart : (pickDate(m.start_peak) || p.date);
        } else if (p.pattern_type === 'DB') {
          startDate = prefStart !== null ? prefStart : (pickDate(m.start_valley) || p.date);
        }
        const endDate: any = prefEnd !== null ? prefEnd : p.date;

        const key = `${toMs(startDate)}|${toMs(endDate)}|${Number(neckline ?? -1)}`;
        if (seen.has(key)) continue;
        seen.add(key);

        // 넥라인: 구간 내부에만 얇게 표시(존재할 때)
        if (neckline != null) {
          const neckColor = '#f59e0b';
          traces.push({
            type: 'scatter',
            mode: 'lines',
            x: [toMs(startDate), toMs(endDate)],
            y: [Number(neckline), Number(neckline)],
            name: `${p.pattern_type} Neckline`,
            showlegend: false,
            line: { color: neckColor, width: 1.2, dash: 'dot' },
            hoverinfo: 'x+y+name'
          });
        }
      }
      // debug: patterns processed
      console.log('[CHART:DEBUG] patterns processed, seen count:', seen.size);
      const patternShapes: any[] = [];
      // collect patternShapes for debug logging (will be used by layout section)
      // define clampX here so plotData's scope can use the layout clamping logic
      const dataX_for_clamp = ((): number[] => {
        try {
          if (!Array.isArray(data) || data.length === 0) return [];
          return (data as any[]).map(d => normalizeTime((d as any).time)).filter((x): x is number => typeof x === 'number' && !Number.isNaN(x));
        } catch { return []; }
      })();
      const dataMin_for_clamp = dataX_for_clamp.length ? Math.min(...dataX_for_clamp) : null;
      const dataMax_for_clamp = dataX_for_clamp.length ? Math.max(...dataX_for_clamp) : null;
      const pad_for_clamp = 3 * 24 * 60 * 60 * 1000; // 3 days in ms
      const clampX = (v: any) => {
        if (v == null || typeof v !== 'number' || Number.isNaN(v)) return null;
        if (dataMin_for_clamp == null || dataMax_for_clamp == null) return v;
        return Math.max(dataMin_for_clamp - pad_for_clamp, Math.min(dataMax_for_clamp + pad_for_clamp, v));
      };
      for (const p of patterns) {
        const m: any = p.meta || {};
        const prefStart = (p as any).startTime ?? (p as any).startTimeEpoch ?? m?.startTime ?? m?.startTimeEpoch ?? null;
        const prefEnd = (p as any).endTime ?? (p as any).endTimeEpoch ?? m?.endTime ?? m?.endTimeEpoch ?? null;
        let startDate: any = prefStart !== null ? prefStart : p.date;
        if (p.pattern_type === 'HS') startDate = prefStart !== null ? prefStart : (pickDate(m.V3) || pickDate(m.V2) || pickDate(m.P1) || p.date);
        else if (p.pattern_type === 'IHS') startDate = prefStart !== null ? prefStart : (pickDate(m.P3) || pickDate(m.P2) || pickDate(m.V1) || p.date);
        else if (p.pattern_type === 'DT') startDate = prefStart !== null ? prefStart : (pickDate(m.start_peak) || p.date);
        else if (p.pattern_type === 'DB') startDate = prefStart !== null ? prefStart : (pickDate(m.start_valley) || p.date);
        const endDate: any = prefEnd !== null ? prefEnd : p.date;
        const rawX0 = toMs(startDate);
        const rawX1 = toMs(endDate);
        const cx0 = clampX(rawX0);
        const cx1 = clampX(rawX1);
        if (cx0 != null && cx1 != null && cx0 < cx1) {
          patternShapes.push({ pattern_type: p.pattern_type, x0: cx0, x1: cx1 });
        }
      }
    }

    return traces;
  }, [data, jsPoints, showJSPoints, showZigZag, zigzagPoints, chartType, isDarkMode, patterns, showPatternNecklines]);

  // Plotly 레이아웃 설정 + 추세 배경색
  const layout = useMemo(() => {
    // normalizeTime: return epoch milliseconds (number) or null — use shared util
    const normalizeTime = toEpochMs;

    const shapes: any[] = [];
    const annotations: any[] = [];

    // compute data x-range (ms) for clamping shapes to avoid autoscale expansion
    const dataX = ((): number[] => {
      try {
        if (!Array.isArray(data) || data.length === 0) return [];
        return (data as any[]).map(d => normalizeTime((d as any).time)).filter((x): x is number => typeof x === 'number' && !Number.isNaN(x));
      } catch { return []; }
    })();
    const dataMin = dataX.length ? Math.min(...dataX) : null;
    const dataMax = dataX.length ? Math.max(...dataX) : null;
    const pad = 3 * 24 * 60 * 60 * 1000; // 3 days in ms
    const clampX = (v: any) => {
      if (v == null || typeof v !== 'number' || Number.isNaN(v)) return null;
      if (dataMin == null || dataMax == null) return v;
      return Math.max(dataMin - pad, Math.min(dataMax + pad, v));
    };

    // trend background (unchanged)
    // showTrendBackground should directly reflect the toggle state from parent
    // Note: toggle inversion bug fix: respect showTrendBackground flag as-is
    if (showTrendBackground && trendPeriods && trendPeriods.length > 0) {
      // choose visible but subtle colors for non-dark mode; keep darker tints for dark mode
      const colors: Record<string, string> = isDarkMode
        ? {
            Uptrend: 'rgba(34, 197, 94, 0.25)',
            Downtrend: 'rgba(239, 68, 68, 0.25)',
            Sideways: 'rgba(156, 163, 175, 0.20)'
          }
        : {
            Uptrend: 'rgba(198,239,206,0.35)',
            Downtrend: 'rgba(255,210,213,0.35)',
            Sideways: 'rgba(230,230,230,0.22)'
          };

      const borderColors: Record<string, string> = isDarkMode
        ? {
            Uptrend: 'rgba(34,197,94,0.45)',
            Downtrend: 'rgba(239,68,68,0.45)',
            Sideways: 'rgba(156,163,175,0.35)'
          }
        : {
            Uptrend: 'rgba(34,197,94,0.45)',
            Downtrend: 'rgba(239,68,68,0.45)',
            Sideways: 'rgba(120,120,120,0.20)'
          };

      // determine global y-range to avoid filling over axis/labels
      const dataY = ((): number[] => {
        try {
          if (isCandlestickData(data)) {
            return (data as CandlestickDataPoint[]).flatMap(d => [Number(d.low), Number(d.high)]).filter(n => Number.isFinite(n));
          }
          return (data as ChartDataPoint[]).map(d => Number((d as any).value)).filter(n => Number.isFinite(n));
        } catch { return []; }
      })();
      const yMin = dataY.length ? Math.min(...dataY) * 0.995 : null;
      const yMax = dataY.length ? Math.max(...dataY) * 1.005 : null;

      for (const period of trendPeriods) {
        const rawX0 = normalizeTime((period as any).start);
        const rawX1 = normalizeTime((period as any).end);
        const cx0 = clampX(rawX0);
        const cx1 = clampX(rawX1);
        if (cx0 == null || cx1 == null || cx0 >= cx1) continue;
        const shape: any = {
          type: 'rect', xref: 'x', x0: cx0, x1: cx1,
          fillcolor: colors[(period as any).type] || colors['Sideways'],
          layer: 'below', line: { width: 0 }
        };
        // prefer yref:'y' with actual data extents so background doesn't cover axis labels
        if (yMin != null && yMax != null) {
          shape.yref = 'y';
          shape.y0 = yMin;
          shape.y1 = yMax;
        } else {
          // fallback to paper if data extents unknown
          shape.yref = 'paper';
          shape.y0 = 0;
          shape.y1 = 1;
        }
        shapes.push(shape);
      }
    }

    // Patterns: robust y0/y1 계산 + annotations + optional necklines
    if (showPatternNecklines && patterns && patterns.length > 0 && Array.isArray(data) && data.length > 0) {
      // prepare candleTimes & helper arrays when candlestick
      const isCandle = isCandlestickData(data);
      const candleData = isCandle ? (data as CandlestickDataPoint[]) : undefined;
      // keep index alignment: array of {idx, t}
      const candleTimes = isCandle ? candleData!.map((d, idx) => ({ idx, t: normalizeTime((d as any).time) })) : [] as {idx:number,t:number|null}[];

      // helper to find nearest index if none in interval (returns original candle index)
      const findNearestIndex = (targetMs: number) => {
        if (!candleTimes || candleTimes.length === 0) return -1;
        let best = -1;
        let bestDiff = Infinity;
        for (let i = 0; i < candleTimes.length; i++) {
          const entry = candleTimes[i];
          const t = entry.t;
          if (t == null) continue;
          const diff = Math.abs(t - targetMs);
          if (diff < bestDiff) { bestDiff = diff; best = entry.idx; }
        }
        return best;
      };

      for (const p of patterns) {
        const m: any = p.meta || {};
        const prefStart = (p as any).startTime ?? (p as any).startTimeEpoch ?? null;
        const prefEnd = (p as any).endTime ?? (p as any).endTimeEpoch ?? null;

        let startDate: any = prefStart !== null ? prefStart : p.date;
        if (p.pattern_type === 'HS') startDate = prefStart !== null ? prefStart : (m.V3?.actual_date || m.V2?.actual_date || m.P1?.actual_date || p.date);
        else if (p.pattern_type === 'IHS') startDate = prefStart !== null ? prefStart : (m.P3?.actual_date || m.P2?.actual_date || m.V1?.actual_date || p.date);
        else if (p.pattern_type === 'DT') startDate = prefStart !== null ? prefStart : (m.start_peak?.actual_date || p.date);
        else if (p.pattern_type === 'DB') startDate = prefStart !== null ? prefStart : (m.start_valley?.actual_date || p.date);
        const endDate: any = prefEnd !== null ? prefEnd : p.date;

        const x0 = normalizeTime(startDate);
        const x1 = normalizeTime(endDate);
        // debug: log pref values and normalized
        logger.debug('pattern raw times', { id: (p as any).id, type: p.pattern_type, prefStart, prefEnd, startDate, endDate, x0, x1 });
        if (x0 == null || x1 == null || x0 >= x1) {
          logger.debug('pattern skipped due to invalid x-range', { id: (p as any).id, x0, x1 });
          continue;
        }

        // clamp to data range
        let cx0 = clampX(x0);
        let cx1 = clampX(x1);
        if (cx0 == null || cx1 == null) continue;

        // ensure minimal span
        const minSpanMs = 24 * 60 * 60 * 1000;
        if (cx1 - cx0 < 1) cx1 = cx0 + minSpanMs;
        if (cx1 - cx0 < minSpanMs) {
          const half = (minSpanMs - (cx1 - cx0)) / 2;
          cx0 = Math.max((dataMin || 0), cx0 - half);
          cx1 = Math.min((dataMax || Infinity), cx1 + half);
        }

        // collect candle indices inside interval (preserve original candle indices)
        const indices: number[] = [];
        if (isCandle && candleTimes.length) {
          for (let i = 0; i < candleTimes.length; i++) {
            const entry = candleTimes[i];
            const t = entry.t;
            if (t != null && t >= cx0 && t <= cx1) indices.push(entry.idx);
          }
        }

        // if none found, pick nearest index and expand to neighbor for better y-range
        if (indices.length === 0 && isCandle && candleTimes.length) {
          const nearIdx = findNearestIndex((cx0 + cx1) / 2);
          if (nearIdx >= 0) {
            indices.push(nearIdx);
            if (nearIdx > 0) indices.push(nearIdx - 1);
            if (nearIdx < candleData!.length - 1) indices.push(nearIdx + 1);
          }
        }

        // compute y0/y1 from selected indices
        let y0: number | null = null;
        let y1: number | null = null;
        if (isCandle && indices.length) {
          let minLow = Infinity; let maxHigh = -Infinity;
          for (const idx of indices) {
            const cd = candleData![idx];
            const low = Number(cd.low); const high = Number(cd.high);
            if (low < minLow) minLow = low;
            if (high > maxHigh) maxHigh = high;
          }
          if (minLow !== Infinity && maxHigh !== -Infinity) {
            y0 = minLow * 0.995;
            y1 = maxHigh * 1.005;
          }
        } else if (!isCandle) {
          // line data fallback
          const vals: number[] = [];
          for (const dItem of data as ChartDataPoint[]) {
            const t = normalizeTime((dItem as any).time);
            if (t != null && t >= cx0 && t <= cx1) vals.push(Number((dItem as any).value));
          }
          if (vals.length) { y0 = Math.min(...vals) * 0.995; y1 = Math.max(...vals) * 1.005; }
        }

        if (y0 == null || y1 == null) {
          // fallback to global data extents if available
          const dataY = ((): number[] => {
            try {
              if (isCandle) {
                return (data as CandlestickDataPoint[]).flatMap(d => [Number(d.low), Number(d.high)]).filter(n => Number.isFinite(n));
              }
              return (data as ChartDataPoint[]).map(d => Number((d as any).value)).filter(n => Number.isFinite(n));
            } catch { return []; }
          })();
          if (dataY.length) { y0 = Math.min(...dataY) * 0.995; y1 = Math.max(...dataY) * 1.005; }
          else {
            logger.debug('pattern skipped due to missing y-range', { id: (p as any).id, indicesCount: indices.length });
            continue;
          }
        }

        // Development debug: log pattern -> layout mapping
        logger.debug('pattern layout calc', {
          id: (p as any).id || null,
          type: p.pattern_type,
          startDate: startDate,
          endDate: endDate,
          cx0,
          cx1,
          indicesCount: indices.length,
          y0,
          y1
        });

        // choose fill & border color by pattern type
        const borderColor = p.pattern_type === 'HS' ? '#FF6B8A' : p.pattern_type === 'IHS' ? '#4CAF50' : p.pattern_type === 'DT' ? '#FF4560' : '#00C853';
        const fillColor = p.pattern_type === 'HS' ? 'rgba(255,107,138,0.08)' : p.pattern_type === 'IHS' ? 'rgba(76,175,80,0.08)' : p.pattern_type === 'DT' ? 'rgba(255,69,96,0.06)' : 'rgba(0,200,83,0.06)';

        shapes.push({
          type: 'rect', xref: 'x', yref: 'y', x0: cx0, x1: cx1, y0, y1,
          fillcolor: fillColor, layer: 'above', line: { color: borderColor, width: 1.2 }
        });

        // annotation label at top-center of box
        const mid = cx0 + (cx1 - cx0) / 2;
        annotations.push({
          x: mid, y: y1, xref: 'x', yref: 'y', text: p.pattern_type,
          showarrow: false, font: { family: 'Arial, sans-serif', size: 11, color: '#fff' },
          bordercolor: borderColor, borderwidth: 1.2, borderpad: 4, bgcolor: borderColor, opacity: 0.9, yshift: 8
        });

        // necklines: if explicit neckline value exists, draw dotted line across the interval
        const neckline = m?.neckline;
        if (neckline != null && Number.isFinite(Number(neckline))) {
          shapes.push({
            type: 'line', xref: 'x', yref: 'y', x0: cx0, x1: cx1, y0: Number(neckline), y1: Number(neckline),
            line: { color: '#f59e0b', width: 1.2, dash: 'dot' }, layer: 'above'
          });
        }
      }
    }

    return {
      title: { text: '', font: { size: 16 } },
      // 항상 비거래시간(장외시간)은 숨기도록 기본 설정
      xaxis: {
        title: { text: 'Date' },
        type: 'date' as const,
        rangeslider: { visible: false },
        // rangebreaks as a mutable array
        rangebreaks: ([] as any[]).concat({ bounds: ['15:30', '09:00'] }, { pattern: 'day of week', bounds: ['sat', 'sun'] }),
        // anchor x-axis to y2 so labels appear below the volume bars
        anchor: 'y2' as any,
      },
      // price axis on top portion
      yaxis: { title: { text: 'Price' }, side: 'right' as const, domain: ([] as number[]).concat(0.2, 1.0) },
      // volume axis at bottom (shared x-axis)
      yaxis2: { title: { text: '' }, domain: ([] as number[]).concat(0.0, 0.18), showgrid: false, zeroline: false },
      height: height,
      width: width,
      margin: { l: 50, r: 50, t: 48, b: 84 },
      // Ensure base chart background is neutral so trend-free areas appear white/light-gray
      plot_bgcolor: isDarkMode ? 'transparent' : '#ffffff',
      paper_bgcolor: isDarkMode ? 'transparent' : '#ffffff',
      font: { color: isDarkMode ? '#A1A1AA' : '#6b7280' },
      showlegend: true,
      legend: { orientation: 'h' as const, yanchor: 'top' as const, y: -0.18, xanchor: 'left' as const, x: 0 },
      hovermode: 'x unified' as const,
      dragmode: 'pan' as const,
      shapes,
      annotations,
    } as const;
  }, [height, width, showTrendBackground, trendPeriods, isDarkMode, patterns, showPatternNecklines, data]);

  // Plotly 설정 - DTTB 스타일 적용
  const config = useMemo(() => ({
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: [
      'lasso2d' as const,
      'select2d' as const,
      'autoScale2d' as const,
      'hoverClosestCartesian' as const,
      'hoverCompareCartesian' as const,
      'toggleSpikelines' as const
    ],
    responsive: true,
    // DTTB 스타일: 마우스 휠 줌 활성화
    scrollZoom: true,
    // DTTB 스타일: 추가 기능들
    editable: false  // 편집 기능 비활성화 (안정성)
  }), []);

  logger.debug('Chart render', { 
    tracesCount: plotData.length,
    hasData: data.length > 0,
    chartType,
    // debug: sample x-values for first few traces (if any)
    firstTraceXSample: plotData && plotData.length > 0 && Array.isArray(plotData[0].x) ? plotData[0].x.slice(0,5) : null,
    shapesCount: (layout && Array.isArray((layout as any).shapes)) ? (layout as any).shapes.length : 0,
    shapesSample: (layout && Array.isArray((layout as any).shapes)) ? (layout as any).shapes.slice(0,3).map((s: any) => ({ x0: s.x0, x1: s.x1 })) : []
  });

  return (
    <div className="w-full">
      <Plot
        data={plotData}
        layout={layout}
        config={config}
        style={{ width: '100%', height: `${height}px` }}
        onHover={onCrosshairMove}
      />
    </div>
  );
};

export default Chart; 