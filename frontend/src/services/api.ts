import axios from 'axios';
import { Time } from 'lightweight-charts';

// 로깅 유틸리티
const logger = {
  info: (message: string, data?: any) => {
    console.log(`%c[INFO] ${message}`, 'color: #03a9f4', data ? data : '');
  },
  success: (message: string, data?: any) => {
    console.log(`%c[SUCCESS] ${message}`, 'color: #4caf50', data ? data : '');
  },
  warn: (message: string, data?: any) => {
    console.warn(`%c[WARN] ${message}`, 'color: #ff9800', data ? data : '');
  },
  error: (message: string, error?: any) => {
    console.error(`%c[ERROR] ${message}`, 'color: #f44336', error ? error : '');
  }
};

// API 베이스 URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// 기본 라인 차트 데이터 타입
export interface ChartDataPoint {
  time: string | Time;
  value: number;
}

// 캔들스틱 차트 데이터 타입
export interface CandlestickDataPoint {
  time: string | Time;
  open: number;
  high: number;
  low: number;
  close: number;
}

// JS 포인트 타입 (피크와 밸리)
export interface JSPoint {
  time: string | Time;
  value: number;
  type: 'peak' | 'valley';
}

// 패턴 타입
export interface Pattern {
  id: string;
  name: string;
  description: string;
  confidence: number;
  startTime: string;
  endTime: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  status: 'forming' | 'completed';
  completion: number;
}

// 주요 가격 레벨
export interface PriceLevel {
  id?: string;
  value: number;
  type: 'support' | 'resistance' | 'pivot';
  strength: number;
  description?: string;
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

// 시장 데이터 인터페이스
export interface MarketData {
  change_24h: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
}

// 통합 Trading Radar 데이터 인터페이스
export interface TradingRadarData {
  symbol: string;
  chart_data: ChartDataPoint[] | CandlestickDataPoint[];
  js_points: {
    peaks: JSPoint[];
    valleys: JSPoint[];
    secondary_peaks: JSPoint[];
    secondary_valleys: JSPoint[];
  };
  trend_periods: {
    start: string;
    end: string;
    type: string;
  }[];
  price_levels: PriceLevel[];
  trend_info: TrendInfo;
}

// --- Full analysis response types ---
export interface ExtremumPoint {
  type: string;
  index: number;
  value: number;
  actual_date: string;
  detected_date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
}

export interface TrendPeriod {
  start: string;
  end: string;
  type: string;
}

export interface DetectedPattern {
  date: string;
  price: number;
  pattern_type: string;
  meta: Record<string, any>;
}

export interface FullAnalysisData {
  trend_periods: TrendPeriod[];
  zigzag_points: ExtremumPoint[];
  patterns: DetectedPattern[];
}

// 한국 주식 타겟 심볼(백엔드 DB 기반) 가져오기
export interface KrTargetSymbolOption {
  value: string; // 6자리 코드
  label: string; // 종목명
}

export async function fetchKrTargetSymbols(limit: number = 30): Promise<KrTargetSymbolOption[]> {
  try {
    logger.info(`KR 타겟 심볼 요청 (limit=${limit})`);
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/symbols/kr-targets`, {
      params: { limit }
    });
    const symbols = response.data?.symbols as KrTargetSymbolOption[] | undefined;
    if (!symbols || !Array.isArray(symbols)) {
      throw new Error('유효하지 않은 KR 타겟 응답');
    }
    logger.success(`KR 타겟 심볼 받음: ${symbols.length}개`);
    return symbols;
  } catch (error) {
    logger.error('KR 타겟 심볼 가져오기 실패', error);
    return [];
  }
}

// 차트 데이터 가져오기
export async function fetchChartData(symbol: string, timeframe: string, chartType: string, period: string = "1y"): Promise<ChartDataPoint[] | CandlestickDataPoint[]> {
  try {
    logger.info(`차트 데이터 요청: ${symbol}, ${timeframe}, ${chartType}, 기간: ${period}`);
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/chart-data`, {
      params: { symbol, timeframe, chart_type: chartType, period }
    });
    
    // 데이터 유효성 검사
    if (!response.data || !Array.isArray(response.data)) {
      throw new Error("유효하지 않은 응답 데이터");
    }
    
    // 중복된 시간 값 확인
    const timeSet = new Set<string>();
    const duplicates: string[] = [];
    
    response.data.forEach((item: any) => {
      if (timeSet.has(String(item.time))) {
        duplicates.push(String(item.time));
      } else {
        timeSet.add(String(item.time));
      }
    });
    
    if (duplicates.length > 0) {
      logger.warn(`중복된 시간 값 발견: ${duplicates.length}개 (첫 5개: ${duplicates.slice(0, 5).join(', ')})`);
    }
    
    // 데이터 양이 너무 적은지 확인
    const isMinuteTimeframe = /^\d+[m]$/.test(timeframe);
    const expectedMinDataPoints = isMinuteTimeframe ? 30 : 10; // 분봉은 최소 30개, 다른 것은 최소 10개
    
    if (response.data.length < expectedMinDataPoints) {
      logger.warn(`데이터가 너무 적습니다: ${response.data.length}개. 최소 ${expectedMinDataPoints}개 필요.`);
      throw new Error(`데이터가 부족합니다. ${response.data.length}개 데이터 포인트를 받았지만, 분석을 위해 최소 ${expectedMinDataPoints}개가 필요합니다.`);
    }
    
    logger.success(`차트 데이터 받음: ${response.data.length}개 항목`, [timeframe, period]);
    return response.data;
  } catch (error) {
    logger.error(`차트 데이터 가져오기 실패: ${error}`, error);
    
    // 사용자에게 표시할 오류 메시지 생성
    let errorMessage = "데이터를 불러오는 데 실패했습니다.";
    
    if (axios.isAxiosError(error) && error.response) {
      // 서버 응답이 있는 경우
      errorMessage = `서버 오류 (${error.response.status}): ${error.response.data?.detail || error.message}`;
    } else if (error instanceof Error) {
      // 일반 JS 오류
      errorMessage = error.message;
    }
    
    // 더미 데이터를 반환하지 않고 오류를 throw
    throw new Error(errorMessage);
  }
}

// JS 포인트 가져오기
export const fetchJSPoints = async (
  symbol: string, 
  timeframe: string,
  period: string = '1y'
): Promise<JSPoint[]> => {
  try {
    logger.info(`JS 포인트 요청: ${symbol}, ${timeframe}, 기간: ${period}`);
    
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/js-points`, {
      params: { symbol, timeframe, period }
    });
    
    logger.success(`JS 포인트 받음: ${response.data.length}개 항목`, response.data.slice(0, 2));
    
    return response.data;
  } catch (error) {
    logger.error('JS 포인트 가져오기 실패', error);
    
    // 오류 메시지 생성
    let errorMessage = "JS 포인트를 불러오는 데 실패했습니다.";
    
    if (axios.isAxiosError(error) && error.response) {
      errorMessage = `서버 오류 (${error.response.status}): ${error.response.data?.detail || error.message}`;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    // 더미 데이터를 반환하지 않고 오류를 throw
    throw new Error(errorMessage);
  }
};

// 패턴 가져오기
export const fetchPatterns = async (
  symbol: string, 
  timeframe: string,
  period: string = '1y'
): Promise<Pattern[]> => {
  try {
    logger.info(`패턴 요청: ${symbol}, ${timeframe}, 기간: ${period}`);
    
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/patterns`, {
      params: { symbol, timeframe, period }
    });
    
    logger.success(`패턴 받음: ${response.data.length}개 항목`, response.data.slice(0, 2));
    
    return response.data;
  } catch (error) {
    logger.error('패턴 가져오기 실패', error);
    
    // 오류 발생 시 더미 데이터 생성
    return generateDummyPatterns();
  }
};

// 가격 레벨 가져오기
export const fetchPriceLevels = async (
  symbol: string, 
  timeframe: string,
  period: string = '1y'
): Promise<PriceLevel[]> => {
  try {
    logger.info(`가격 레벨 요청: ${symbol}, ${timeframe}, 기간: ${period}`);
    
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/price-levels`, {
      params: { symbol, timeframe, period }
    });
    
    logger.success(`가격 레벨 받음: ${response.data.length}개 항목`, response.data.slice(0, 2));
    
    return response.data;
  } catch (error) {
    // 오류 타입 확인 및 세부 정보 로깅
    if (axios.isAxiosError(error) && error.response) {
      logger.error(`가격 레벨 가져오기 실패 (${period} 기간): HTTP 상태 코드 ${error.response.status}`, error);
      if (error.response.data) {
        logger.error(`응답 데이터: ${JSON.stringify(error.response.data)}`);
      }
    } else {
      logger.error(`가격 레벨 가져오기 실패 (${period} 기간): ${error}`, error);
    }
    
    // 오류 발생 시 더미 데이터 생성
    return generateDummyPriceLevels();
  }
};

// (fetchTrendInfo removed — endpoint deprecated; use trading-radar-data or analyze)

// 시장 데이터 가져오기
export const fetchMarketData = async (symbol: string): Promise<MarketData> => {
  try {
    logger.info(`시장 데이터 요청: ${symbol}`);
    
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/market-data`, {
      params: { symbol }
    });
    
    logger.success(`시장 데이터 받음: ${JSON.stringify(response.data)}`);
    return response.data;
  } catch (error) {
    logger.error('시장 데이터 가져오기 실패', error);
    
    // 오류 발생 시 더미 데이터 생성
    return {
      change_24h: 0,
      volume_24h: 0,
      high_24h: 0,
      low_24h: 0
    };
  }
};

// 통합 Trading Radar 데이터 가져오기
export async function fetchTradingRadarData(
  symbol: string, 
  timeframe: string,
  chartType: string, 
  period: string = "1y"
): Promise<TradingRadarData> {
  try {
    logger.info(`Trading Radar 데이터 요청: ${symbol}, ${timeframe}, ${chartType}, 기간: ${period}`);
    
    const response = await axios.get(`${API_URL}/api/v1/pattern-analysis/trading-radar-data`, {
      params: { symbol, timeframe, chart_type: chartType, period }
    });
    
    // 응답 검증
    if (!response.data) {
      throw new Error("유효하지 않은 응답 데이터");
    }
    
    // 차트 데이터 형식 확인
    if (!Array.isArray(response.data.chart_data)) {
      logger.warn("차트 데이터가 배열 형식이 아닙니다.");
      throw new Error("서버에서 유효한 차트 데이터를 받지 못했습니다.");
    }
    
    // 데이터 양이 너무 적은지 확인
    const isMinuteTimeframe = /^\d+[m]$/.test(timeframe);
    const expectedMinDataPoints = isMinuteTimeframe ? 30 : 10; // 분봉은 최소 30개, 다른 것은 최소 10개
    
    if (response.data.chart_data.length < expectedMinDataPoints) {
      logger.warn(`차트 데이터가 너무 적습니다: ${response.data.chart_data.length}개. 최소 ${expectedMinDataPoints}개 필요.`);
      throw new Error(`데이터가 부족합니다. ${response.data.chart_data.length}개 데이터 포인트를 받았지만, 분석을 위해 최소 ${expectedMinDataPoints}개가 필요합니다.`);
    }
    
    // JS 포인트 데이터 형식 확인
    if (!response.data.js_points || typeof response.data.js_points !== 'object') {
      logger.warn("JS 포인트 데이터가 객체 형식이 아닙니다.");
      response.data.js_points = { peaks: [], valleys: [], secondary_peaks: [], secondary_valleys: [] };
    }
    
    logger.success(`Trading Radar 데이터 받음: 차트 ${response.data.chart_data.length}개 항목, JS 포인트 ${
      (response.data.js_points.peaks?.length || 0) + 
      (response.data.js_points.valleys?.length || 0)}개`);
    
    return response.data;
  } catch (error) {
    logger.error(`Trading Radar 데이터 가져오기 실패: ${error}`, error);
    
         // 백엔드 연결 실패 시 더미 데이터로 대체
    logger.warn('백엔드 API 연결 실패. 더미 데이터로 대체합니다.');
     
    const dummyChartData = generateDummyCandlestickData(100);
    const dummyJSPointsArray = generateDummyJSPoints(100);
    const dummyPatterns = generateDummyPatterns();
    const dummyPriceLevels = generateDummyPriceLevels();
    const dummyTrendInfo = generateDummyTrendInfo();
     
     // JSPoints를 올바른 형식으로 변환
    const peaks = dummyJSPointsArray.filter(point => point.type === 'peak');
    const valleys = dummyJSPointsArray.filter(point => point.type === 'valley');
     
    return {
      symbol: symbol,
      chart_data: dummyChartData,
      js_points: {
        peaks,
        valleys,
        secondary_peaks: [],
        secondary_valleys: []
      },
      trend_periods: [],
      price_levels: dummyPriceLevels,
      trend_info: dummyTrendInfo
    };
  }
}

// 전체 분석 리포트 관련 API는 deprecated 되어 프론트에서 직접 호출하지 않습니다.
// 관련 엔드포인트는 백엔드에서 제거되었으므로 이 함수는 더 이상 제공하지 않습니다.

// ------------------------
// 더미 데이터 생성 함수 (백업 솔루션용)
// ------------------------

// 더미 차트 데이터 생성 (라인 차트용)
export const generateDummyChartData = (days: number): ChartDataPoint[] => {
  const data: ChartDataPoint[] = [];
  const today = new Date();
  let price = 50000 + Math.random() * 10000;
  
  for (let i = 0; i < days; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() - (days - i));
    
    // 랜덤 가격 변동 (-3% ~ +3%)
    const change = (Math.random() * 6 - 3) / 100;
    price = price * (1 + change);
    
    data.push({
      time: date.toISOString().split('T')[0],
      value: price
    });
  }
  
  return data;
};

// 더미 캔들스틱 데이터 생성
export const generateDummyCandlestickData = (days: number): CandlestickDataPoint[] => {
  const data: CandlestickDataPoint[] = [];
  const today = new Date();
  let basePrice = 50000 + Math.random() * 10000;
  
  for (let i = 0; i < days; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() - (days - i));
    
    // 랜덤 가격 변동 (-3% ~ +3%)
    const change = (Math.random() * 6 - 3) / 100;
    basePrice = basePrice * (1 + change);
    
    // 랜덤한 OHLC 값 생성
    const volatility = basePrice * 0.02; // 2% 변동성
    const open = basePrice;
    const close = basePrice * (1 + (Math.random() * 0.04 - 0.02)); // -2% ~ +2%
    const high = Math.max(open, close) + (Math.random() * volatility);
    const low = Math.min(open, close) - (Math.random() * volatility);
    
    data.push({
      time: date.toISOString().split('T')[0],
      open,
      high,
      low,
      close
    });
  }
  
  return data;
};

// 더미 JS 포인트 생성 (피크와 밸리)
export const generateDummyJSPoints = (count: number): JSPoint[] => {
  const points: JSPoint[] = [];
  const chartData = generateDummyChartData(30);
  
  // 데이터에서 일부를 피크와 밸리로 선택
  for (let i = 0; i < count; i++) {
    const idx = Math.floor(Math.random() * chartData.length);
    const point = chartData[idx];
    
    points.push({
      time: point.time,
      value: point.value,
      type: i % 2 === 0 ? 'peak' : 'valley'
    });
  }
  
  return points.sort((a, b) => {
    // 날짜 문자열 비교
    if (typeof a.time === 'string' && typeof b.time === 'string') {
      return new Date(a.time).getTime() - new Date(b.time).getTime();
    }
    // 숫자 타임스탬프 비교
    return Number(a.time) - Number(b.time);
  });
};

// 더미 패턴 생성
export const generateDummyPatterns = (): Pattern[] => {
  logger.warn('더미 패턴 생성');
  
  const patternTypes = [
    { name: '이중 바닥', direction: 'bullish', description: '상승 반전 패턴' },
    { name: '이중 천장', direction: 'bearish', description: '하락 반전 패턴' },
    { name: '삼각형 수렴', direction: 'neutral', description: '추세 지속 또는 반전 패턴' },
    { name: '헤드앤숄더', direction: 'bearish', description: '하락 반전 패턴' },
    { name: '역 헤드앤숄더', direction: 'bullish', description: '상승 반전 패턴' },
  ];
  
  // 1-3개의 패턴 랜덤 생성
  const patternCount = Math.floor(Math.random() * 3) + 1;
  const patterns: Pattern[] = [];
  
  for (let i = 0; i < patternCount; i++) {
    const patternType = patternTypes[Math.floor(Math.random() * patternTypes.length)];
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - (Math.floor(Math.random() * 20) + 5));
    
    const completion = Math.random() * 100;
    const status = completion >= 100 ? 'completed' : 'forming';
    
    patterns.push({
      id: `pattern-${i+1}`,
      name: patternType.name,
      description: patternType.description,
      confidence: Math.random() * 100,
      startTime: startDate.toISOString().split('T')[0],
      endTime: today.toISOString().split('T')[0],
      direction: patternType.direction as 'bullish' | 'bearish' | 'neutral',
      status: status as 'forming' | 'completed',
      completion: completion > 100 ? 100 : Math.round(completion),
    });
  }
  
  logger.info(`더미 패턴 생성 완료: ${patterns.length}개 항목`);
  return patterns;
};

// 더미 가격 레벨 생성
export const generateDummyPriceLevels = (): PriceLevel[] => {
  logger.warn('더미 가격 레벨 생성');
  
  const basePrice = 50000 + Math.random() * 10000;
  const levels: PriceLevel[] = [];
  
  // 지지선 2개
  for (let i = 0; i < 2; i++) {
    const supportPrice = basePrice * (0.9 - (i * 0.05));
    levels.push({
      id: `support-${i+1}`,
      value: supportPrice,
      type: 'support',
      strength: Math.random() * 100,
      description: `강력한 지지선 (${i+1})`,
    });
  }
  
  // 저항선 2개
  for (let i = 0; i < 2; i++) {
    const resistancePrice = basePrice * (1.1 + (i * 0.05));
    levels.push({
      id: `resistance-${i+1}`,
      value: resistancePrice,
      type: 'resistance',
      strength: Math.random() * 100,
      description: `주요 저항선 (${i+1})`,
    });
  }
  
  return levels;
};

// 더미 추세 정보 생성
export const generateDummyTrendInfo = (): TrendInfo => {
  logger.warn('더미 추세 정보 생성');
  
  const trendOptions: ('uptrend' | 'downtrend' | 'sideways' | 'neutral')[] = ['uptrend', 'downtrend', 'sideways', 'neutral'];
  const trend = trendOptions[Math.floor(Math.random() * 4)];
  const startDate = new Date().toISOString().split('T')[0];
  const duration = Math.floor(Math.random() * 30) + 1;
  const strength = Math.random() * 100;
  
  return {
    trend,
    startDate,
    duration,
    strength,
  };
};

// 분봉 더미 차트 데이터 생성 (라인 차트용)
export const generateMinuteChartData = (timeframe: string, period: string): ChartDataPoint[] => {
  logger.warn(`분봉 더미 데이터 생성: ${timeframe}, 기간: ${period}`);
  const data: ChartDataPoint[] = [];
  
  // 기간에 따른 데이터 포인트 수 계산
  const minutesInTimeframe = getMinutesFromTimeframe(timeframe);
  const daysInPeriod = getDaysFromPeriod(period);
  const tradingHoursPerDay = 8; // 하루 8시간 거래 시간 가정
  const pointsPerDay = (tradingHoursPerDay * 60) / minutesInTimeframe;
  const totalPoints = Math.min(daysInPeriod * pointsPerDay, 1000); // 최대 1000개로 제한
  
  const now = new Date();
  let basePrice = 50000 + Math.random() * 10000;
  
  // 현재 시간부터 역순으로 데이터 생성
  for (let i = 0; i < totalPoints; i++) {
    // 시간 계산 (현재 시간에서 i * 분봉단위 만큼 이전)
    // 각 타임스탬프가 고유하도록 정확히 계산
    const timestamp = Math.floor(now.getTime() / 1000) - (i * minutesInTimeframe * 60);
    
    // 랜덤 가격 변동 (더 작은 변동성)
    const change = (Math.random() * 0.6 - 0.3) / 100; // -0.3% ~ +0.3%
    basePrice = basePrice * (1 + change);
    
    data.push({
      time: timestamp as any, // Time 타입으로 변환
      value: basePrice
    });
  }
  
  // 시간순 정렬 (오래된 순으로)
  return data.sort((a, b) => {
    return Number(a.time) - Number(b.time);
  });
};

// 분봉 더미 캔들스틱 데이터 생성
export const generateMinuteCandlestickData = (timeframe: string, period: string): CandlestickDataPoint[] => {
  logger.warn(`분봉 더미 캔들스틱 데이터 생성: ${timeframe}, 기간: ${period}`);
  const data: CandlestickDataPoint[] = [];
  
  // 기간에 따른 데이터 포인트 수 계산
  const minutesInTimeframe = getMinutesFromTimeframe(timeframe);
  const daysInPeriod = getDaysFromPeriod(period);
  const tradingHoursPerDay = 8; // 하루 8시간 거래 시간 가정
  const pointsPerDay = (tradingHoursPerDay * 60) / minutesInTimeframe;
  const totalPoints = Math.min(daysInPeriod * pointsPerDay, 1000); // 최대 1000개로 제한
  
  const now = new Date();
  let basePrice = 50000 + Math.random() * 10000;
  
  // 현재 시간부터 역순으로 데이터 생성
  for (let i = 0; i < totalPoints; i++) {
    // 시간 계산 - 각 캔들이 고유한 타임스탬프를 갖도록 함
    const timestamp = Math.floor(now.getTime() / 1000) - (i * minutesInTimeframe * 60);
    
    // 랜덤 가격 변동 (-0.5% ~ +0.5%, 분봉에 적합한 더 작은 변동성)
    const change = (Math.random() * 1 - 0.5) / 100;
    basePrice = basePrice * (1 + change);
    
    // 캔들스틱 데이터 생성
    const volatility = basePrice * 0.005; // 0.5% 변동성
    const open = basePrice;
    const close = basePrice * (1 + (Math.random() * 0.01 - 0.005)); // -0.5% ~ +0.5%
    const high = Math.max(open, close) + (Math.random() * volatility);
    const low = Math.min(open, close) - (Math.random() * volatility);
    
    data.push({
      time: timestamp as any, // Time 타입으로 변환
      open,
      high,
      low,
      close
    });
  }
  
  // 시간순 정렬 (오래된 순으로)
  return data.sort((a, b) => {
    return Number(a.time) - Number(b.time);
  });
};

// timeframe 문자열에서 분 단위 추출 (예: '30m' -> 30, '1h' -> 60)
function getMinutesFromTimeframe(timeframe: string): number {
  const match = timeframe.match(/^(\d+)([mh])$/);
  if (!match) return 60; // 기본값 1시간
  
  const [, valueStr, unit] = match;
  const value = parseInt(valueStr, 10);
  
  return unit === 'h' ? value * 60 : value;
}

// period 문자열에서 일 단위 추출 (예: '7d' -> 7, '2mo' -> 60, '1y' -> 365)
function getDaysFromPeriod(period: string): number {
  const match = period.match(/^(\d+)([dmo])([so])?$/);
  if (!match) return 30; // 기본값 30일
  
  const [, valueStr, unit] = match;
  const value = parseInt(valueStr, 10);
  
  switch (unit) {
    case 'd': return value;
    case 'm': return value * 30;
    case 'y': return value * 365;
    default: return 30;
  }
}