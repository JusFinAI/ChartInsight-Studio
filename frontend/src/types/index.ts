// 차트 데이터 포인트 (라인 차트용)
export interface ChartDataPoint {
  time: string | number;
  value: number;
}

// 캔들스틱 데이터 포인트
export interface CandlestickDataPoint {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// JS 포인트 (피크와 밸리)
export interface JSPoint {
  time: string | number;
  value: number;
  type: 'peak' | 'valley';
}

// 패턴 정보
export interface Pattern {
  id?: string;
  name: string;
  type: string;
  description?: string;
  confidence: number;
  direction: 'bullish' | 'bearish' | 'neutral';
  startTime?: string;
  endTime?: string;
  status?: 'forming' | 'complete';
}

// 가격 레벨 정보
export interface PriceLevel {
  id?: string;
  type: 'support' | 'resistance' | 'pivot';
  price: number;
  strength?: number;
  description?: string;
  startTime?: string;
  endTime?: string;
}

// 추세 정보
export interface TrendInfo {
  trend: 'uptrend' | 'downtrend' | 'sideways' | 'neutral';
  startDate: string;
  duration: number;
  strength: number;
  trend_periods?: Array<{
    start: string;
    end: string;
    type: string;
  }>;
}

// 시장 데이터
export interface MarketData {
  change_24h: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
}

// 뉴스 아티클
export interface NewsArticle {
  id: string;
  title: string;
  source: string;
  date: string;
  url: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  content?: string;
  image?: string;
}

// 차트 프로퍼티
export interface ChartProps {
  data: ChartDataPoint[] | CandlestickDataPoint[];
  jsPoints?: JSPoint[];
  showJSPoints?: boolean;
  showZigZag?: boolean;
  showTrendBackground?: boolean;
  currentTrend?: 'uptrend' | 'downtrend' | 'sideways' | 'neutral';
  height?: number;
  width?: number;
  chartType?: 'line' | 'candlestick';
  onCrosshairMove?: (param: any) => void;
  zigzagData?: ChartDataPoint[];
  trendDirection?: 'up' | 'down' | 'neutral';
} 