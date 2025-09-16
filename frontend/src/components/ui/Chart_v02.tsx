'use client';

import React, { useState, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { JSPoint, ChartDataPoint, CandlestickDataPoint, ExtremumPoint, TrendPeriod, DetectedPattern } from '@/services/api';
import { Layout, Config } from 'plotly.js';

const Plot = dynamic(() => import('react-plotly.js'), {
    ssr: false,
  loading: () => <div className="flex items-center justify-center h-full">차트 로딩 중...</div>,
});

const toEpochMs = (t: any): number | null => {
  if (t == null) return null;
  try {
    if (typeof t === 'number') return t < 10_000_000_000 ? t * 1000 : t;
    if (typeof t === 'string' && /^\d+$/.test(t)) {
      const n = Number(t);
      return n < 10_000_000_000 ? n * 1000 : n;
    }
    const dt = new Date(t);
    const ms = dt.getTime();
    return Number.isFinite(ms) ? ms : null;
  } catch (e) {
    return null;
  }
};

interface ChartProps {
  data: (ChartDataPoint | CandlestickDataPoint)[];
  jsPoints?: JSPoint[];
  showJSPoints?: boolean;
  showZigZag?: boolean;
  showTrendBackground?: boolean;
  currentTrend?: 'uptrend' | 'downtrend' | 'sideways' | 'neutral';
  height?: number;
  width?: number;
  chartType?: 'line' | 'candlestick';
  zigzagPoints?: ExtremumPoint[];
  trendPeriods?: TrendPeriod[];
  patterns?: DetectedPattern[];
  showPatternNecklines?: boolean;
  timeframe?: string;
  showVolume?: boolean;
  onHoverDataChange?: (data: { current: any; prev: any } | null) => void;
}

// ▼▼▼▼▼ [마지막 오류 수정] 타입을 명확히 하기 위한 사용자 정의 타입 추가 ▼▼▼▼▼
type CandlestickDataWithMs = CandlestickDataPoint & { __ms: number | null };

function isCandlestickData(d: any[]): d is CandlestickDataWithMs[] {
  return d.length > 0 && 'open' in d[0] && 'high' in d[0] && 'low' in d[0] && 'close' in d[0];
}

const Chart: React.FC<ChartProps> = ({
  data,
  jsPoints = [],
  showJSPoints = true,
  showZigZag = true,
  showTrendBackground = true,
  currentTrend = 'neutral',
  height = 550, // 기본 높이 조정
  width,
  chartType = 'candlestick',
  zigzagPoints = [],
  trendPeriods = [],
  patterns = [],
  showPatternNecklines = true,
  timeframe = '1d',
  showVolume = true,
  onHoverDataChange,
}) => {
  const [isDarkMode, setIsDarkMode] = useState(false);
  useEffect(() => {
    // 1. 현재 테마를 확인하여 초기 상태를 설정하는 함수
    const checkTheme = () => {
      const isDark = document.documentElement.classList.contains('dark');
      setIsDarkMode(isDark);
    };
    checkTheme(); // 컴포넌트가 로드될 때 즉시 실행

    // 2. 테마 변경을 감시하는 '감시자(Observer)' 생성
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        // html 태그의 class 속성이 변경될 때마다 테마를 다시 확인
        if (mutation.attributeName === 'class') {
          checkTheme();
        }
      });
    });

    // 3. 감시자에게 html 태그를 감시하라고 명령
    observer.observe(document.documentElement, { attributes: true });

    // 4. 컴포넌트가 사라질 때 감시를 중지하여 메모리 누수 방지 (중요!)
    return () => observer.disconnect();
  }, []); // 이 useEffect는 처음 한 번만 실행됩니다.

  const isMinuteTimeframe = useMemo(() => timeframe.endsWith('m') || timeframe.endsWith('h'), [timeframe]);

  useEffect(() => {
    try {
      const styleId = 'plotly-modebar-fix';
      if (document.getElementById(styleId)) return;
      const style = document.createElement('style');
      style.id = styleId;
      style.innerHTML = `
      .modebar-container { z-index: 1001 !important; }
      .plotly .main-svg .draglayer, .plotly .main-svg .draglayer * { cursor: crosshair !important; }
    `;
      document.head.appendChild(style);
    } catch (e) {}
  }, []);

  const dateHelpers = useMemo(() => {
    const dateToIndexMap = new Map<number, number>();
    const msToFormattedStringMap = new Map<number, string>();
    const dataWithMs = data.map(d => ({ ...d, __ms: toEpochMs((d as any).time) }));

    dataWithMs.forEach((d, index) => {
      const ms = d.__ms;
      if (ms !== null) {
        dateToIndexMap.set(ms, index);
        if (isMinuteTimeframe) {
          const formatted = new Date(ms).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
          msToFormattedStringMap.set(ms, formatted);
        }
      }
    });

    const sortedTimestamps = Array.from(dateToIndexMap.keys()).sort((a, b) => a - b);
    return { dateToIndexMap, msToFormattedStringMap, sortedTimestamps, dataWithMs };
  }, [data, isMinuteTimeframe]);

  const { dateToIndexMap, msToFormattedStringMap, sortedTimestamps, dataWithMs } = dateHelpers;

  const convertXForLayout = (timeValue: any): number | null => {
    const ms = toEpochMs(timeValue);
    if (ms === null) return null;
    if (isMinuteTimeframe) {
      if (dateToIndexMap.has(ms)) return dateToIndexMap.get(ms)!;
      if (sortedTimestamps.length === 0) return null;
      const closestMs = sortedTimestamps.reduce((prev, curr) => (Math.abs(curr - ms) < Math.abs(prev - ms) ? curr : prev));
      return dateToIndexMap.get(closestMs) ?? null;
    }
    return ms;
  };

  const plotData = useMemo(() => {
    const traces: any[] = [];
    if (data.length === 0) return traces;

    const xValues = dataWithMs.map(d => {
      const ms = d.__ms;
      if (isMinuteTimeframe && ms) return msToFormattedStringMap.get(ms);
      return ms;
    });

    if (chartType === 'candlestick' && isCandlestickData(data)) {
      traces.push({
        type: 'candlestick', x: xValues,
        open: data.map(d => (d as CandlestickDataPoint).open), high: data.map(d => (d as CandlestickDataPoint).high), 
        low: data.map(d => (d as CandlestickDataPoint).low), close: data.map(d => (d as CandlestickDataPoint).close),
        name: '가격', 
        increasing: {
          fillcolor: '#089981',      // 몸통 색상
          line: { 
            color: '#089981', // 꼬리/테두리 색상 (몸통과 동일하게)
            width: 1           // 꼬리 두께
          }
        },
        decreasing: {
          fillcolor: '#F23645',      // 몸통 색상
          line: { 
            color: '#F23645', // 꼬리/테두리 색상 (몸통과 동일하게)
            width: 1           // 꼬리 두께
          }
        },
        showlegend: false,
        hoverinfo: 'none',
      });
      if (showVolume) {
        // 1. 거래량 데이터만 먼저 추출합니다.
        const volumes = data.map(d => Number((d as any).volume) || 0);

        // 2. 
        const colors = {
          increase: 'rgba(8, 153, 129, 0.7)',   // TradingView 녹색 (투명도 70%)
          decrease: 'rgba(242, 54, 69, 0.7)',   // TradingView 적색 (투명도 70%)
          initial: isDarkMode ? 'rgba(107, 114, 128, 0.5)' : 'rgba(156, 163, 175, 0.5)',
        };
        
        // 3. 각 거래량 막대의 색상을 계산하는 로직을 추가합니다.
        const barColors = volumes.map((vol, i) => {
          if (i === 0) return colors.initial; // 첫 번째 막대는 기준이 없으므로 중립색
          return vol >= volumes[i - 1] ? colors.increase : colors.decrease;
        });

        // 4. 계산된 색상 배열을 marker.color에 적용합니다.
          traces.push({
            type: 'bar',
          x: xValues,
            y: volumes,
            name: 'Volume',
          marker: { color: barColors }, // 고정된 색상 대신, 계산된 색상 배열을 전달
            yaxis: 'y2',
          showlegend: false,
          hoverinfo: 'none', 
        });

      }
    }

    const getTraceXValues = (points: any[], timeField: string) => {
      return points.map(p => {
        const ms = toEpochMs(p[timeField]);
        if (ms === null) return null;
        if (isMinuteTimeframe) {
          if (sortedTimestamps.length === 0) return null;
          const closestMs = sortedTimestamps.reduce((prev, curr) => (Math.abs(curr - ms) < Math.abs(prev - ms) ? curr : prev));
          return msToFormattedStringMap.get(closestMs);
        }
        return ms;
      }).filter(x => x != null);
    };

    if (showJSPoints && jsPoints.length > 0) {
      const peaks = jsPoints.filter(point => point.type === 'peak');
      const valleys = jsPoints.filter(point => point.type === 'valley');

      if (peaks.length > 0) {
        traces.push({
          type: 'scatter',
          mode: 'markers', // 'markers+text'에서 'markers'로 변경
          x: getTraceXValues(peaks, 'time'), // 이전에 만든 헬퍼 함수 사용
          y: peaks.map(p => p.value * 1.005),
          name: 'Peak',
          marker: {
            symbol: 'triangle-down',
            size: 8, // 사이즈를 약간 줄여 세련미 추가
            color: '#ef4444'
          },
          hoverinfo: 'none',
          showlegend: false
        });
      }

      if (valleys.length > 0) {
        traces.push({
          type: 'scatter',
          mode: 'markers', // 'markers+text'에서 'markers'로 변경
          x: getTraceXValues(valleys, 'time'), // 이전에 만든 헬퍼 함수 사용
          y: valleys.map(v => v.value * 0.995),
          name: 'Valley',
          marker: {
            symbol: 'triangle-up',
            size: 8, // 사이즈를 약간 줄여 세련미 추가
            color: '#22c55e'
          },
          hoverinfo: 'none',
          showlegend: false
        });
      }
    }

    if (showZigZag && zigzagPoints.length > 1) {
      traces.push({
        type: 'scatter', mode: 'lines', x: getTraceXValues(zigzagPoints, 'actual_date'), y: zigzagPoints.map(p => p.value),
        name: 'ZigZag', line: { color: isDarkMode ? '#e5e7eb' : '#6b7280', width: 1 }, 
        showlegend: false,
        hoverinfo: 'none',
      });
    }

    return traces;
  }, [data, jsPoints, showJSPoints, showZigZag, zigzagPoints, chartType, isDarkMode, isMinuteTimeframe, dateHelpers]);
  
  const layout = useMemo((): Partial<Layout> => {
    const shapes: any[] = [];
    const annotations: any[] = [];

    if (showTrendBackground && trendPeriods && trendPeriods.length > 0) {
      const colors: { [key: string]: string } = { Uptrend: 'rgba(34, 197, 94, 0.1)', Downtrend: 'rgba(239, 68, 68, 0.1)', Sideways: 'rgba(156, 163, 175, 0.1)' };
      for (const period of trendPeriods) {
        const x0 = convertXForLayout((period as any).start);
        const x1 = convertXForLayout((period as any).end);
        if (x0 !== null && x1 !== null) {
          shapes.push({
            type: 'rect', xref: 'x', yref: 'paper', x0, x1, y0: 0, y1: 1,
            fillcolor: colors[(period as any).type] || colors['Sideways'], layer: 'below', line: { width: 0 },
          });
        }
      }
    }

    if (showPatternNecklines && patterns && patterns.length > 0 && Array.isArray(data) && data.length > 0) {


      const candleData = isCandlestickData(dataWithMs) ? dataWithMs : null;

      // 패턴 이름을 축약어로 변환하기 위한 맵(Map) 객체
      const patternAbbrs: { [key: string]: string } = {
        'Head & Shoulders': 'HS',
        'Inverse Head & Shoulders': 'IHS',
        'Double Top': 'DT',
        'Double Bottom': 'DB',
      };


      for (const p of (patterns as any[])) {
        const startMs = toEpochMs(p.startTime ?? p.meta?.P1?.actual_date ?? p.date);
        const endMs = toEpochMs(p.endTime ?? p.date);

        if (startMs === null || endMs === null) continue;

        const x0 = convertXForLayout(startMs);
        const x1 = convertXForLayout(endMs);

        let y0: number | null = null;
        let y1: number | null = null;

        if (candleData) {
          const relevantCandles = candleData.filter(d => d.__ms !== null && d.__ms >= startMs && d.__ms <= endMs);
          if (relevantCandles.length > 0) {
            const minLow = Math.min(...relevantCandles.map(c => c.low));
            const maxHigh = Math.max(...relevantCandles.map(c => c.high));
            const padding = (maxHigh - minLow) * 0.05;
            y0 = minLow - padding;
            y1 = maxHigh + padding;
          }
        }

        if (x0 !== null && x1 !== null && y0 !== null && y1 !== null) {

          // 1. 패턴 타입에 따라 방향성을 명확하게 다시 정의합니다. (데이터 의존성 감소)
          let direction = 'neutral';
          if (['DB', 'IHS', 'Double Bottom', 'Inverse Head & Shoulders'].includes(p.pattern_type) || p.direction === 'bullish') {
            direction = 'bullish';
          } else if (['DT', 'HS', 'Double Top', 'Head & Shoulders'].includes(p.pattern_type) || p.direction === 'bearish') {
            direction = 'bearish';
          }
          // 2. 방향성에 따라 색상과 스타일을 정의합니다.
          const bullishStyle = {
            lineColor: '#22c55e', // 녹색 점선
            fillColor: 'rgba(34, 197, 94, 0.05)',
            labelBgColor: '#22c55e',
          };
          const bearishStyle = {
            lineColor: '#ef4444', // 적색 점선
            fillColor: 'rgba(239, 68, 68, 0.05)',
            labelBgColor: '#ef4444',
          };
          const currentStyle = direction === 'bullish' ? bullishStyle : bearishStyle;

          // 3. 패턴 박스(Shape)를 그립니다.
          shapes.push({
            type: 'rect', xref: 'x', yref: 'y', x0, x1, y0, y1,
            layer: 'above', 
            line: { color: currentStyle.lineColor, width: 1.5, dash: 'dot' },
            fillcolor: currentStyle.fillColor,
          });

          // 4. 패턴 라벨(Annotation)을 그립니다.
          const patternText = patternAbbrs[p.name] || p.pattern_type;

          annotations.push({
            x: isMinuteTimeframe ? (x0 as number) + ((x1 as number) - (x0 as number)) / 2 : new Date(startMs + (endMs - startMs) / 2),
            y: y1, yanchor: 'bottom', xref: 'x', yref: 'y',
            text: `<b>${patternText}</b>`,
            showarrow: false,
            font: { color: 'white', size: 10 },
            bgcolor: currentStyle.labelBgColor,
            bordercolor: 'rgba(255,255,255,0.5)',
            borderwidth: 1,
            borderpad: 2,
            yshift: 5, // 라벨과 박스 사이에 약간의 간격을 줍니다.
          });          

        }

      }
    }
    
    const xaxisSettings: Partial<Layout['xaxis']> = {
      title: { text: '' },
      rangeslider: { visible: false },
      anchor: 'y2' as any,
      gridcolor: isDarkMode ? '#2d3748' : '#e2e8f0',
      ...(isMinuteTimeframe 
          ? { type: 'category', tickfont: { size: 10 }, nticks: 10 } 
          : { type: 'date', rangebreaks: [{ pattern: 'day of week', bounds: ['sat', 'sun'] }] }
      )
    };

    return {
      xaxis: xaxisSettings,
      yaxis: { title: { text: 'Price' }, side: 'right' as const, domain: [0.2, 1.0], gridcolor: isDarkMode ? '#2d3748' : '#e2e8f0', fixedrange: true },
      yaxis2: { title: { text: '' }, domain: [0.0, 0.18], showgrid: false, zeroline: false },
      height: height,
      margin: { l: 20, r: 50, t: 30, b: 50 },
      plot_bgcolor: isDarkMode ? '#1f2937' : '#ffffff', // 기본 플롯 배경색
      paper_bgcolor: isDarkMode ? '#1f2937' : '#ffffff', // 전체 차트 배경색
      font: { color: isDarkMode ? '#A1A1AA' : '#6b7280' },
      showlegend: false,
      hovermode: 'x unified' as const,
      dragmode: 'pan' as const,
      shapes,
      annotations,
    };
  }, [height, width, showTrendBackground, trendPeriods, isDarkMode, patterns, showPatternNecklines, data, timeframe, isMinuteTimeframe, dateHelpers]);

  const config = useMemo((): Partial<Config> => ({
    displayModeBar: true, displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'toggleSpikelines'],
    responsive: true, scrollZoom: true,
  }), []);

  const handleHover = (event: any) => {
    if (!onHoverDataChange) return;
    
    if (event.points && event.points.length > 0) {
      const point = event.points[0];
      const dataIndex = point.pointIndex;
      if (data[dataIndex]) {
        const currentData = data[dataIndex];
        const prevData = dataIndex > 0 ? data[dataIndex - 1] : null;
        onHoverDataChange({ current: currentData, prev: prevData });
      }
    }
  };

  const handleUnhover = () => {
    if (onHoverDataChange) {
      onHoverDataChange(null);
    }
  };

  return (
    <div className="w-full h-full">
      <Plot
        data={plotData}
        layout={layout}
        config={config}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
        onHover={handleHover}
        onUnhover={handleUnhover}
      />
    </div>
  );
};

export default Chart; 