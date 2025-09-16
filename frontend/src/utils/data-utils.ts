import { ChartDataPoint, CandlestickDataPoint, JSPoint, Pattern, PriceLevel, TrendInfo } from "@/types";

/**
 * 더미 차트 데이터 생성 (라인 차트용)
 */
export function generateDummyChartData(days: number): ChartDataPoint[] {
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
}

/**
 * 더미 캔들스틱 데이터 생성
 */
export function generateDummyCandlestickData(days: number): CandlestickDataPoint[] {
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
}

/**
 * 더미 JS 포인트 생성 (피크와 밸리)
 */
export function generateDummyJSPoints(count: number): JSPoint[] {
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
}

/**
 * 더미 패턴 데이터 생성
 */
export function generateDummyPatterns(): Pattern[] {
  const patterns: Pattern[] = [];
  
  // 샘플 패턴들
  const patternTypes = [
    { type: 'doubleTop', name: '더블 탑', direction: 'bearish' as const },
    { type: 'doubleBottom', name: '더블 바텀', direction: 'bullish' as const },
    { type: 'headAndShoulders', name: '헤드앤숄더', direction: 'bearish' as const },
    { type: 'inverseHeadAndShoulders', name: '역 헤드앤숄더', direction: 'bullish' as const },
    { type: 'triangle', name: '삼각형', direction: 'neutral' as const },
    { type: 'bullishFlag', name: '불리시 플래그', direction: 'bullish' as const }
  ];
  
  // 랜덤 패턴 2-4개 선택
  const count = Math.floor(Math.random() * 3) + 2;
  
  for (let i = 0; i < count; i++) {
    const patternIndex = Math.floor(Math.random() * patternTypes.length);
    const pattern = patternTypes[patternIndex];
    
    patterns.push({
      id: `pattern-${i+1}`,
      name: pattern.name,
      type: pattern.type,
      description: `${pattern.name} 패턴이 감지되었습니다.`,
      confidence: Math.floor(Math.random() * 40) + 60, // 60-100%
      direction: pattern.direction,
      startTime: '2023-03-15',
      endTime: '2023-03-22',
      status: Math.random() > 0.5 ? 'forming' : 'complete'
    });
  }
  
  return patterns;
}

/**
 * 더미 가격 레벨 생성
 */
export function generateDummyPriceLevels(): PriceLevel[] {
  const levels: PriceLevel[] = [];
  const basePrice = 50000;
  
  // 지지선 2-3개
  const supportCount = Math.floor(Math.random() * 2) + 2;
  for (let i = 0; i < supportCount; i++) {
    const supportPrice = basePrice * (0.9 - (i * 0.05));
    levels.push({
      id: `support-${i+1}`,
      type: 'support',
      price: supportPrice,
      strength: Math.floor(Math.random() * 40) + 60, // 60-100%
      description: `지지선 ${i+1}`
    });
  }
  
  // 저항선 2-3개
  const resistanceCount = Math.floor(Math.random() * 2) + 2;
  for (let i = 0; i < resistanceCount; i++) {
    const resistancePrice = basePrice * (1.1 + (i * 0.05));
    levels.push({
      id: `resistance-${i+1}`,
      type: 'resistance',
      price: resistancePrice,
      strength: Math.floor(Math.random() * 40) + 60, // 60-100%
      description: `저항선 ${i+1}`
    });
  }
  
  // 피벗 포인트 1개
  levels.push({
    id: 'pivot-1',
    type: 'pivot',
    price: basePrice * 1.02,
    strength: Math.floor(Math.random() * 40) + 60, // 60-100%
    description: '피벗 포인트'
  });
  
  return levels;
}

/**
 * 더미 추세 정보 생성
 */
export function generateDummyTrendInfo(): TrendInfo {
  const trendTypes: Array<'uptrend' | 'downtrend' | 'sideways' | 'neutral'> = [
    'uptrend', 'downtrend', 'sideways', 'neutral'
  ];
  
  const trend = trendTypes[Math.floor(Math.random() * trendTypes.length)];
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - (Math.floor(Math.random() * 30) + 1));
  const duration = Math.floor((new Date().getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  
  // 샘플 추세 기간 생성
  const trend_periods: Array<{start: string; end: string; type: string}> = [];
  let endDate = new Date();
  
  // 3~5개의 추세 기간 생성
  for (let i = 0; i < 3 + Math.floor(Math.random() * 3); i++) {
    const periodDays = 10 + Math.floor(Math.random() * 20); // 10-30일 기간
    const periodStartDate = new Date(endDate);
    periodStartDate.setDate(periodStartDate.getDate() - periodDays);
    
    // 번갈아가며 다른 추세 타입 할당
    const periodType = trendTypes[i % trendTypes.length];
    
    trend_periods.push({
      start: periodStartDate.toISOString().split('T')[0],
      end: endDate.toISOString().split('T')[0],
      type: periodType
    });
    
    // 다음 기간의 종료일 = 현재 기간의 시작일
    endDate = new Date(periodStartDate);
  }
  
  // 오래된 순으로 정렬
  trend_periods.reverse();
  
  return {
    trend,
    startDate: startDate.toISOString().split('T')[0],
    duration,
    strength: Math.floor(Math.random() * 100),
    trend_periods
  };
} 