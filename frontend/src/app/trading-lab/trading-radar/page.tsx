'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import Chart from '@/components/ui/Chart';


import {
  generateDummyChartData,
  generateDummyCandlestickData,
  generateDummyJSPoints,
  generateDummyPatterns,
  generateDummyPriceLevels,
  generateDummyTrendInfo,
  ChartDataPoint,
  CandlestickDataPoint,
  JSPoint,
  Pattern,
  PriceLevel,
  TrendInfo,
  fetchChartData,
  fetchJSPoints,
  fetchPatterns,
  fetchPriceLevels,
  fetchTradingRadarData,
  fetchKrTargetSymbols,
  // fetchTrendInfo removed (deprecated). FullAnalysisData removed.
} from '@/services/api';

export default function TradingRadarPage() {
  // 상태 관리
  const [symbol, setSymbol] = useState('005930');
  const [category, setCategory] = useState('한국주식');
  const [timeframe, setTimeframe] = useState('1d');
  const [period, setPeriod] = useState('2y');
  const [chartType, setChartType] = useState<'line' | 'candlestick'>('candlestick');
  const [chartData, setChartData] = useState<ChartDataPoint[] | CandlestickDataPoint[]>([]);
  const [jsPoints, setJSPoints] = useState<JSPoint[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [priceLevels, setPriceLevels] = useState<PriceLevel[]>([]);
  const [trendInfo, setTrendInfo] = useState<TrendInfo>({ 
    trend: 'neutral', 
    startDate: '', 
    duration: 0, 
    strength: 0,
    trend_periods: []
  });

  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showJSPoints, setShowJSPoints] = useState(true);
  const [showZigZag, setShowZigZag] = useState(true);
  const [showTrendBackground, setShowTrendBackground] = useState(true);
  const [showHS, setShowHS] = useState(true);
  const [showIHS, setShowIHS] = useState(true);
  const [showDT, setShowDT] = useState(true);
  const [showDB, setShowDB] = useState(true);
  const [analysisData, setAnalysisData] = useState<any | null>(null);
  const [hoverData, setHoverData] = useState<{ current: any; prev: any } | null>(null); 
  const [rawAnalysisData, setRawAnalysisData] = useState<any | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  
  // 차트 컨테이너 참조
  const chartContainerRef = useRef(null);
  const periodSelectRef = useRef<HTMLSelectElement | null>(null);
  
  // 카테고리별 심볼 옵션 (임시: 한국주식 전용으로 제한)
  const categoryOptions = ['한국주식'] as const;
  
  // 카테고리 타입 정의
  type Category = typeof categoryOptions[number];
  
  // 심볼 옵션 인터페이스
  interface SymbolOption {
    value: string;
    label: string;
  }
  
  // 카테고리별 심볼 리스트
  // 카테고리를 한국주식 전용으로 제한했기 때문에 타입을 더 느슨하게 지정합니다.
  const symbolsByCategory: Record<string, SymbolOption[]> = {
    '지수': [
      { value: '^KS11', label: 'KOSPI' },
      { value: '^KQ11', label: 'KOSDAQ' },
      { value: '^GSPC', label: 'S&P 500' },
      { value: '^DJI', label: 'Dow Jones' },
      { value: '^IXIC', label: 'NASDAQ' },
      { value: '^N225', label: 'Nikkei 225' },
      { value: '^HSI', label: 'Hang Seng' },
      { value: '^FTSE', label: 'FTSE 100' },
      { value: '^GDAXI', label: 'DAX' }
    ],
    '한국주식': [],
    '미국주식': [
      { value: 'AAPL', label: 'Apple' },
      { value: 'MSFT', label: 'Microsoft' },
      { value: 'GOOGL', label: 'Alphabet (Google)' },
      { value: 'AMZN', label: 'Amazon' },
      { value: 'META', label: 'Meta (Facebook)' },
      { value: 'NVDA', label: 'NVIDIA' },
      { value: 'TSLA', label: 'Tesla' },
      { value: 'NFLX', label: 'Netflix' },
      { value: 'JPM', label: 'JPMorgan Chase' },
      { value: 'V', label: 'Visa' },
      { value: 'WMT', label: 'Walmart' },
      { value: 'BAC', label: 'Bank of America' },
      { value: 'PG', label: 'Procter & Gamble' },
      { value: 'DIS', label: 'Disney' },
      { value: 'KO', label: 'Coca-Cola' }
    ],
    '해외선물': [
      { value: 'GC=F', label: '금(Gold)' },
      { value: 'SI=F', label: '은(Silver)' },
      { value: 'CL=F', label: '원유(Crude Oil)' },
      { value: 'NG=F', label: '천연가스(Natural Gas)' },
      { value: 'ZC=F', label: '옥수수(Corn)' },
      { value: 'ZW=F', label: '밀(Wheat)' },
      { value: 'NQ=F', label: '나스닥 선물(NASDAQ)' },
      { value: 'ES=F', label: 'S&P 500 선물' },
      { value: 'YM=F', label: '다우 선물(Dow)' }
    ],
    '코인': [
      { value: 'BTC-USD', label: '비트코인(BTC)' },
      { value: 'ETH-USD', label: '이더리움(ETH)' },
      { value: 'XRP-USD', label: '리플(XRP)' },
      { value: 'SOL-USD', label: '솔라나(SOL)' },
      { value: 'ADA-USD', label: '카르다노(ADA)' }
    ]
  };
  
  // 현재 선택된 카테고리의 심볼 옵션
  const [krSymbolOptions, setKrSymbolOptions] = useState<SymbolOption[]>([]);
  const currentSymbolOptions = (category === '한국주식' ? krSymbolOptions : symbolsByCategory[category as Category]) || [];
  
  // 타임프레임 옵션 (백엔드 지원 항목으로 제한)
  const timeframeOptions = [
    { value: '5m', label: '5분' },
    { value: '30m', label: '30분' },
    { value: '1h', label: '1시간' },
    { value: '1d', label: '1일' },
    { value: '1wk', label: '1주' }
  ];
  
  interface PeriodOption {
    label: string;
    value: string;
  }

  // 타임프레임에 따른 최대 기간 및 기본 기간 정의 함수 추가
  const getMaxPeriodForTimeframe = (timeframe: string): string => {
    // 분봉 (1m-30m)
    if (/^\d+m$/.test(timeframe) && parseInt(timeframe) <= 30) {
      return timeframe === '1m' ? '7d' : '60d'; // 1분봉은 최대 7일, 나머지 분봉은 최대 60일
    }
    // 시간봉 (60m, 1h)
    else if (/^\d+h$/.test(timeframe) || ['60m', '90m'].includes(timeframe)) {
      return "730d"; // 시간봉은 최대 730일
    }
    // 일봉 이상 (1d, 1wk, 1mo)
    else {
      return "max"; // 일봉 이상은 최대 데이터
    }
  };

  // 타임프레임에 따른 기간 옵션 함수 수정
  const getPeriodOptions = (currentTimeframe: string) => {
    const maxPeriod = getMaxPeriodForTimeframe(currentTimeframe);
    
    // 분봉 (1m)
    if (currentTimeframe === '1m') {
      return [
        { value: maxPeriod, label: '최대 (7일)' }, // 최대값을 default로 설정
        { value: "5d", label: '5일' },
        { value: "3d", label: '3일' },
        { value: "1d", label: '1일' }
      ];
    }
    // 분봉 (3m-30m)
    else if (/^\d+m$/.test(currentTimeframe) && parseInt(currentTimeframe) <= 30) {
      return [
        { value: maxPeriod, label: '최대 (60일)' }, // 최대값을 default로 설정
        { value: "30d", label: '30일' },
        { value: "14d", label: '14일' },
        { value: "7d", label: '7일' },
        { value: "3d", label: '3일' },
        { value: "1d", label: '1일' }
      ];
    }
    // 시간봉 (60m, 90m, 1h)
    else if (/^\d+h$/.test(currentTimeframe) || ['60m', '90m'].includes(currentTimeframe)) {
      return [
        { value: maxPeriod, label: '최대 (2년)' }, // 최대값을 default로 설정
        { value: "365d", label: '1년' },
        { value: "180d", label: '6개월' },
        { value: "90d", label: '3개월' },
        { value: "30d", label: '1개월' },
        { value: "14d", label: '14일' },
        { value: "7d", label: '7일' }
      ];
    }
    // 일봉 (1d)
    else if (currentTimeframe === '1d') {
      return [
        { value: maxPeriod, label: '최대' }, // 최대값을 default로 설정
        { value: "5y", label: '5년' },
        { value: "2y", label: '2년' },
        { value: "1y", label: '1년' },
        { value: "6mo", label: '6개월' },
        { value: "3mo", label: '3개월' },
        { value: "1mo", label: '1개월' }
      ];
    }
    // 주봉, 월봉 (1wk, 1mo)
    else {
      return [
        { value: maxPeriod, label: '최대' }, // 최대값을 default로 설정
        { value: "10y", label: '10년' },
        { value: "5y", label: '5년' },
        { value: "2y", label: '2년' },
        { value: "1y", label: '1년' }
      ];
    }
  };
  
  // 현재 타임프레임에 대한 기간 옵션
  const periodOptions = getPeriodOptions(timeframe);

  // 타임프레임 변경 핸들러 수정
  const handleTimeframeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newTimeframe = e.target.value;
    setTimeframe(newTimeframe);
    
    // 새 타임프레임에 맞는 최대 기간으로 자동 설정
    const maxPeriod = getMaxPeriodForTimeframe(newTimeframe);
    setPeriod(maxPeriod);
    
    // 로그 출력
    console.log(`타임프레임 변경: ${newTimeframe}, 기간 자동 설정: ${maxPeriod}`);
  };
  
  // Yahoo Finance 심볼 포맷 변환 함수
  const getYahooFinanceSymbol = (selectedSymbol: string, selectedCategory: string) => {
    // 이미 올바른 포맷인 경우 그대로 반환
    if (selectedSymbol.includes('.KS') || selectedSymbol.includes('.KQ') || 
        selectedSymbol.includes('^') || selectedSymbol.includes('-USD') || 
        selectedSymbol.includes('=F')) {
      return selectedSymbol;
    }
    
    // 카테고리에 따라 적절한 접미사 추가
    if (selectedCategory === '한국주식') {
      // DataPipeline/키움증권 API 형식: 6자리 숫자 코드 그대로 사용
      return selectedSymbol;
    } else if (selectedCategory === '지수') {
      // 지수는 앞에 ^ 추가
      return `^${selectedSymbol}`;
    } else if (selectedCategory === '코인') {
      // 코인은 -USD 추가
      return `${selectedSymbol}-USD`;
    } else if (selectedCategory === '해외선물') {
      // 선물은 =F 추가
      return `${selectedSymbol}=F`;
    }
    
    return selectedSymbol;
  };
  
  // 데이터 불러오기 함수를 수정하여 통합 API 사용
  const loadData = async (overridePeriod?: string) => {
    setLoading(true);
    setError('');
    try {
      // Yahoo Finance 심볼 포맷으로 변환
      const yahooSymbol = getYahooFinanceSymbol(symbol, category);
      
      // 새로운 통합 API 호출
      const effectivePeriod = overridePeriod ?? period;
      const radarData = await fetchTradingRadarData(yahooSymbol, timeframe, chartType, effectivePeriod);
      
      // 데이터 개수 유효성 검사
      if (!radarData.chart_data || radarData.chart_data.length === 0) {
        throw new Error(`${timeframe} 타임프레임에 대한 데이터를 찾을 수 없습니다.`);
      }
      
      // 1분봉에 대한 특별 처리
      if (timeframe === '1m' && radarData.chart_data.length < 30) {
        throw new Error(`1분봉 데이터가 부족합니다. 최소 30개의 데이터 포인트가 필요하지만 ${radarData.chart_data.length}개만 찾았습니다.`);
      }
      
      // 가져온 데이터 설정
      setChartData(radarData.chart_data);
      
      // JS 포인트 데이터 변환 및 설정
      const allJSPoints = [
        ...radarData.js_points.peaks,
        ...radarData.js_points.valleys,
        ...radarData.js_points.secondary_peaks,
        ...radarData.js_points.secondary_valleys
      ];
      setJSPoints(allJSPoints);
      
      // 다른 데이터 설정
      setPatterns(await fetchPatterns(yahooSymbol, timeframe, period)); // 패턴은 아직 통합 API에 포함되지 않음
      setPriceLevels(radarData.price_levels);
      
      // trend_info 설정 (trend_periods 확인) + 전체 분석 데이터 로드
      const trendInfoWithPeriods = radarData.trend_info;
      if (!trendInfoWithPeriods.trend_periods && radarData.trend_periods && radarData.trend_periods.length > 0) {
        // trend_info에 trend_periods가 없지만 상위 레벨에 있으면 추가
        trendInfoWithPeriods.trend_periods = radarData.trend_periods;
      }
      setTrendInfo(trendInfoWithPeriods);

      // 전체 분석(추세선/배경색용) 데이터는 통합 API에서 제공되므로
      // 프론트에서 별도 full-report 호출을 제거했습니다.
      // radarData에 전체 분석결과가 포함된 경우 rawAnalysisData로 저장하여
      // 패턴 필터(HS/DT 등) 토글이 동작하도록 합니다.
      setRawAnalysisData(radarData);
      
      // 디버깅
      console.log("추세 기간 데이터:", trendInfoWithPeriods.trend_periods || radarData.trend_periods);
      
      // 데이터 로드 로그
      console.log(`차트 데이터 로드 완료: ${timeframe} 타임프레임, ${radarData.chart_data.length}개 데이터`);
      if (radarData.chart_data.length > 0) {
        console.log(`데이터 범위: ${radarData.chart_data[0].time} ~ ${radarData.chart_data[radarData.chart_data.length-1].time}`);
      }
      
      setLoading(false);
    } catch (err) {
      // 오류 메시지 추출
      const errorMessage = err instanceof Error 
        ? err.message 
        : '데이터를 불러오는 중 오류가 발생했습니다.';
      
      // 특정 오류에 대한 사용자 친화적 메시지
      let userFriendlyMessage = errorMessage;
      
      if (errorMessage.includes('404') || errorMessage.includes('찾을 수 없')) {
        userFriendlyMessage = `${symbol} 심볼에 대한 ${timeframe} 타임프레임 데이터를 찾을 수 없습니다. 다른 심볼이나 타임프레임을 선택해보세요.`;
      } else if (errorMessage.includes('데이터가 부족') || errorMessage.includes('insufficient data')) {
        userFriendlyMessage = `${timeframe} 타임프레임에 대한 데이터가 충분하지 않습니다. 다른 타임프레임이나 더 긴 기간을 선택해보세요.`;
      }
      
      setError(userFriendlyMessage);
      setLoading(false);
      console.error('데이터 불러오기 오류:', err);
    }
  };
  
  // 카테고리 변경 핸들러
  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newCategory = e.target.value as Category;
    setCategory(newCategory);
    
    // 카테고리 변경 시 해당 카테고리의 첫 번째 심볼로 자동 설정
    if (newCategory === '한국주식') {
      if (krSymbolOptions.length > 0) {
        const preferred = krSymbolOptions.find(o => o.value === '005930');
        setSymbol(preferred ? preferred.value : krSymbolOptions[0].value);
      } else {
        // 백엔드 응답 대기 중이면 기존 심볼 유지
      }
    } else if (symbolsByCategory[newCategory] && symbolsByCategory[newCategory].length > 0) {
      setSymbol(symbolsByCategory[newCategory][0].value);
    }
  };
  
  // 심볼 변경 핸들러
  const handleSymbolChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSymbol(e.target.value);
  };
  
  // 기간 변경 핸들러
  const handlePeriodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setPeriod(e.target.value);
  };
  
  // 차트 타입 변경 핸들러
  const handleChartTypeChange = () => {
    setChartType(prevType => prevType === 'candlestick' ? 'line' : 'candlestick');
  };
  
  // 심볼, 타임프레임, 기간 변경 시 자동 데이터 로드를 위한 useEffect
  useEffect(() => {
    // 초기 로드가 완료된 후에만 자동 로드 실행
    if (!isInitialLoad && symbol && timeframe && period) {
      const timer = setTimeout(() => {
        console.log(`자동 데이터 로드: symbol=${symbol}, timeframe=${timeframe}, period=${period}`);
        loadData(period);
      }, 300); // 300ms 디바운싱으로 연속 변경 시 성능 최적화
      
      return () => clearTimeout(timer);
    }
  }, [symbol, timeframe, period, isInitialLoad]);
  
  // 컴포넌트 마운트 시 초기 데이터 로드
  useEffect(() => {
    // 한국 주식 심볼 옵션을 백엔드에서 로드
    (async () => {
      try {
        const list = await fetchKrTargetSymbols(30);
        if (Array.isArray(list) && list.length > 0) {
          const opts = list.map(s => ({ value: s.value, label: s.label }));
          setKrSymbolOptions(opts);
          // 초기 한국주식 기본값 보정
          if (category === '한국주식') {
            const preferred = opts.find(o => o.value === '005930');
            setSymbol(preferred ? preferred.value : (opts[0]?.value || '005930'));
          }
        } else {
          // 백엔드 실패 시 기본값 유지
          setKrSymbolOptions([]);
        }
      } catch (e) {
        setKrSymbolOptions([]);
      } finally {
        await loadData();
        setIsInitialLoad(false); // 초기 로드 완료 표시
      }
    })();
  }, []);

  // 패턴 유형 토글 변경에 따른 필터 재적용
  useEffect(() => {
    if (!rawAnalysisData) return;
    const origLen = Array.isArray(rawAnalysisData.patterns) ? rawAnalysisData.patterns.length : 0;
    const filteredPatterns = (rawAnalysisData.patterns || []).filter((p: any) =>
      (p.pattern_type === 'HS' && showHS) ||
      (p.pattern_type === 'IHS' && showIHS) ||
      (p.pattern_type === 'DT' && showDT) ||
      (p.pattern_type === 'DB' && showDB)
    );
    const filtered = {
      ...rawAnalysisData,
      patterns: filteredPatterns
    } as any; // FullAnalysisData removed, so use 'any' or define a new type if needed
    console.log('[PATTERN DEBUG] raw patterns len:', origLen, 'filtered len:', filteredPatterns.length, 'flags:', { showHS, showIHS, showDT, showDB });
    setAnalysisData(filtered);
  }, [rawAnalysisData, showHS, showIHS, showDT, showDB]);
  
  // 추세에 따른 배경색 클래스
  const getTrendColorClass = () => {
    switch (trendInfo.trend) {
      case 'uptrend':
        return 'bg-green-50 dark:bg-green-950/30';
      case 'downtrend':
        return 'bg-red-50 dark:bg-red-950/30';
      default:
        return 'bg-gray-50 dark:bg-gray-800/30';
    }
  };

  // 추세를 한글로 표시
  const getTrendName = (trend: string) => {
    switch (trend.toLowerCase()) {
      case 'uptrend':
        return '상승 추세';
      case 'downtrend':
        return '하락 추세';
      case 'sideways':
        return '횡보 추세';
      default:
        return '중립';
    }
  };

  // 시작일 표기 포맷 (epoch seconds 또는 문자열 모두 수용, KST 고정)
  const formatStartDateKST = (value: any): string => {
    try {
      if (value === undefined || value === null) return '';
      let date: Date;
      if (typeof value === 'number') {
        date = new Date(value * 1000);
      } else if (typeof value === 'string' && /^\d+$/.test(value)) {
        date = new Date(Number(value) * 1000);
      } else if (typeof value === 'string') {
        // ISO 등 문자열 날짜 처리
        date = new Date(value);
      } else {
        return String(value);
      }
      return date.toLocaleString('ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return String(value);
    }
  };

  // 버튼 토글 핸들러
  const toggleJSPoints = () => {
    // 로그: 토글 이전/이후 상태를 남겨 반전 동작 여부를 진단합니다.
    setShowJSPoints(prev => {
      console.log('[UI:DEBUG] toggleJSPoints prev:', prev, 'next:', !prev);
      return !prev;
    });
  };
  const toggleZigZag = () => setShowZigZag(!showZigZag);
  const toggleTrendBackground = () => setShowTrendBackground(!showTrendBackground);

  // 가격 정보 표시를 위한 함수
  const getLastPrice = () => {
    if (chartData.length === 0) return 'N/A';
    
    const lastItem = chartData[chartData.length - 1];
    const price = 'close' in lastItem ? lastItem.close : (lastItem as ChartDataPoint).value;
    const formatted = Number(price).toLocaleString('ko-KR');
    return `${formatted}원`;
  };

  const handleChartHover = (data: { current: any; prev: any } | null) => {
    if (data && !data.prev) {
      setHoverData(null);
      return;
    }
    setHoverData(data);
  };

  // 현재 선택된 심볼의 레이블 가져오기
  const getCurrentSymbolLabel = () => {
    const found = currentSymbolOptions.find(option => option.value === symbol);
    return found ? found.label : symbol;
  };

  return (
    <div className="p-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">
        {/* 차트 섹션을 더 넓게 3칸으로 확장 */}
        <div className="lg:col-span-3">
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-4 md:p-6 mb-6">
            {/* 새로운 단일 정보 라인 UI */}
            <div className="flex flex-col md:flex-row md:justify-between md:items-center mb-4 gap-4">
              {/* 좌측 정보 영역 */}
              <div className="flex items-center gap-2">
                {hoverData ? (
                  // 마우스 ON 상태
                  <>
                    <span className="font-bold">{getCurrentSymbolLabel()}</span>
                    <span className="text-neutral-400">|</span>
                    <div className={`flex items-center gap-2 text-xs ${
                      hoverData.current.close >= (hoverData.prev?.close || hoverData.current.close) 
                        ? 'text-green-600 dark:text-green-500' 
                        : 'text-red-600 dark:text-red-500'
                    }`}>
                      <span>시 {hoverData.current.open?.toLocaleString()}</span>
                      <span>고 {hoverData.current.high?.toLocaleString()}</span>
                      <span>저 {hoverData.current.low?.toLocaleString()}</span>
                      <span>종 {hoverData.current.close?.toLocaleString()}</span>
                      {hoverData.current.volume && (
                        <span>거래량 {(hoverData.current.volume / 1000000).toFixed(2)}M</span>
                      )}
                      {hoverData.prev && (
                        <span>
                          {hoverData.current.close >= hoverData.prev.close ? '▲' : '▼'}
                          {' '}
                          ({((hoverData.current.close - hoverData.prev.close) / hoverData.prev.close * 100).toFixed(2)}%)
                        </span>
                      )}
                    </div>
                  </>
                ) : (
                  // 마우스 OFF 상태
                  <>
                    <span className="font-bold">{getCurrentSymbolLabel()}</span>
                    {chartData.length > 0 && (() => {
                      const lastCandle = chartData[chartData.length - 1] as CandlestickDataPoint;
                      const prevCandle = chartData.length > 1 ? chartData[chartData.length - 2] as CandlestickDataPoint : null;
                      const changePercent = prevCandle ? ((lastCandle.close - prevCandle.close) / prevCandle.close * 100) : 0;
                      const isPositive = changePercent >= 0;
                      
                      return (
                        <>
                          <span>{lastCandle.close?.toLocaleString()}원</span>
                          {prevCandle && (
                            <span className={isPositive ? 'text-green-600 dark:text-green-500' : 'text-red-600 dark:text-red-500'}>
                              {isPositive ? '▲' : '▼'} ({Math.abs(changePercent).toFixed(2)}%)
                            </span>
                          )}
                          <span className="text-neutral-400">|</span>
                          <span className="text-sm text-neutral-600 dark:text-neutral-400">
                            {getTrendName(trendInfo.trend)}
                          </span>
                        </>
                      );
                    })()}
                  </>
                )}
              </div>
              
              {/* 우측 컨트롤 영역 */}
              <div className="flex flex-wrap items-center gap-2">
                {/* 카테고리 선택 (한국주식으로 고정되어 UI에서는 숨김) */}
                <span className="hidden">{category}</span>
                
                {/* 심볼 선택 */}
                <select 
                  className="bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm"
                  value={symbol}
                  onChange={handleSymbolChange}
                >
                  {currentSymbolOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                
                {/* 타임프레임 선택 */}
                <select 
                  className="bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm"
                  value={timeframe}
                  onChange={handleTimeframeChange}
                >
                  {timeframeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>

                {/* 기간 선택 제거: 모든 데이터를 표시하도록 프론트에서는 고정 */}
              </div>
            </div>
            
            {/* 차트 영역 */}
            <div 
              ref={chartContainerRef}
              className="w-full h-[825px] rounded-lg flex items-center justify-center relative bg-white dark:bg-neutral-800"
            >
              {loading ? (
                <div className="text-center">
                  <p className="text-lg mb-2">데이터 로딩 중...</p>
                  <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
                </div>
              ) : error ? (
                <div className="text-center text-red-500">
                  <p className="text-lg mb-2">오류 발생</p>
                  <p>{error}</p>
                </div>
              ) : (
                <Chart
                  data={chartData}
                  jsPoints={jsPoints}
                  showJSPoints={showJSPoints}
                  showZigZag={showZigZag}
                  showTrendBackground={showTrendBackground}
                  currentTrend={trendInfo?.trend ?? 'neutral'}
                  height={825}
                  chartType={chartType}
                  trendPeriods={analysisData?.trend_periods || trendInfo.trend_periods || []}
                  patterns={analysisData?.patterns || []}
                  showPatternNecklines
                  zigzagPoints={analysisData?.zigzag_points || []}
                  timeframe={timeframe}
                  onHoverDataChange={handleChartHover}
                />
              )}
            </div>
          </div>
          
          {/* 차트 아래에 감지된 패턴 및 주요 가격 레벨 섹션 추가 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 감지된 패턴 섹션 */}
            <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
              <h3 className="text-lg font-semibold mb-4">감지된 패턴</h3>
              
              {patterns.length === 0 ? (
                <p className="text-neutral-500 dark:text-neutral-400">감지된 패턴이 없습니다.</p>
              ) : (
                <div className="space-y-4">
                  {patterns.map((pattern, index) => (
                    <div key={pattern.id || `pattern-${index}`} className="border-b border-neutral-200 dark:border-neutral-700 pb-4 last:border-b-0 last:pb-0">
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-medium text-base">
                            {pattern.name}
                            <Badge 
                              variant={pattern.direction === 'bullish' ? 'primary' : pattern.direction === 'bearish' ? 'warning' : 'secondary'} 
                              className="ml-2"
                            >
                              {pattern.direction === 'bullish' ? '상승' : pattern.direction === 'bearish' ? '하락' : '중립'}
                            </Badge>
                          </h4>
                          <p className="text-sm text-neutral-600 dark:text-neutral-400">{pattern.description}</p>
                          <div className="flex items-center mt-1 text-sm">
                            <span className="text-neutral-500 mr-2">신뢰도:</span>
                            <div className="w-24 h-2 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                              <div 
                                className={`h-full rounded-full ${pattern.confidence > 70 ? 'bg-green-500' : pattern.confidence > 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                style={{ width: `${pattern.confidence}%` }}
                              ></div>
                            </div>
                            <span className="ml-2">{pattern.confidence.toFixed(0)}%</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-sm ${pattern.status === 'forming' ? 'text-yellow-500' : 'text-green-500'}`}>
                            {pattern.status === 'forming' ? '형성 중' : '완료'}
                          </div>
                          <div className="text-xs text-neutral-500 dark:text-neutral-400">
                            {pattern.startTime} ~ {pattern.endTime}
                          </div>
                          {pattern.status === 'forming' && (
                            <div className="mt-1">
                              <div className="text-xs text-neutral-600 dark:text-neutral-400 mb-1">완성률: {pattern.completion}%</div>
                              <div className="w-full h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-primary rounded-full"
                                  style={{ width: `${pattern.completion}%` }}
                                ></div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* 주요 가격 레벨 섹션 */}
            <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
              <h3 className="text-lg font-semibold mb-4">주요 가격 레벨</h3>
              
              {priceLevels.length === 0 ? (
                <p className="text-neutral-500 dark:text-neutral-400">주요 가격 레벨이 없습니다.</p>
              ) : (
                <div className="space-y-4">
                  {priceLevels.map((level, index) => (
                    <div key={level.id || `level-${index}`} className="flex justify-between items-center">
                      <div>
                        <div className="flex items-center">
                          <Badge 
                            variant={level.type === 'support' ? 'primary' : level.type === 'resistance' ? 'warning' : 'secondary'} 
                            className="mr-2"
                          >
                            {level.type === 'support' ? '지지' : level.type === 'resistance' ? '저항' : '피벗'}
                          </Badge>
                          <span className="font-medium">${(level.value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        </div>
                        <p className="text-sm text-neutral-600 dark:text-neutral-400">{level.description || `${level.type === 'support' ? '지지' : '저항'} 레벨`}</p>
                      </div>
                      <div>
                        <div className="flex items-center">
                          <span className="text-xs text-neutral-500 mr-2">강도</span>
                          <div className="w-16 h-1.5 bg-neutral-200 dark:bg-neutral-700 rounded-full overflow-hidden">
                            <div 
                              className={`h-full rounded-full ${(level.strength || 0) > 70 ? 'bg-green-500' : (level.strength || 0) > 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                              style={{ width: `${level.strength || 0}%` }}
                            ></div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* 오른쪽 사이드바를 1칸으로 축소 */}
        <div className="lg:col-span-1 space-y-4">
          {/* 차트 설정 섹션 */}
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
            <h3 className="text-lg font-semibold mb-4">차트 설정</h3>
            
            {/* 차트 타입 메뉴 제거됨 */}
            
            {/* 차트 표시 옵션 */}
            <div>
              <h4 className="font-medium mb-2">표시 옵션</h4>
              <div className="flex flex-col gap-2">
                <label className="flex items-center">
                  <input 
                    type="checkbox" 
                    className="form-checkbox h-4 w-4 text-primary rounded" 
                    checked={showJSPoints} 
                    onChange={toggleJSPoints} 
                  />
                  <span className="ml-2 text-sm">피크/밸리 포인트 표시</span>
                </label>
                <label className="flex items-center">
                  <input 
                    type="checkbox" 
                    className="form-checkbox h-4 w-4 text-primary rounded" 
                    checked={showZigZag} 
                    onChange={toggleZigZag} 
                  />
                  <span className="ml-2 text-sm">추세선 표시</span>
                </label>
                <label className="flex items-center">
                  <input 
                    type="checkbox" 
                    className="form-checkbox h-4 w-4 text-primary rounded" 
                    checked={showTrendBackground} 
                    onChange={toggleTrendBackground} 
                  />
                  <span className="ml-2 text-sm">추세 배경색 표시</span>
                </label>
                {/* 패턴 유형 표시 옵션 */}
                <div className="mt-2">
                  <div className="text-sm font-medium mb-1">패턴 유형 표시</div>
                  <div className="flex flex-col gap-1">
                    <label className="flex items-center">
                      <input type="checkbox" className="form-checkbox h-4 w-4 text-primary rounded" checked={showHS} onChange={() => setShowHS(v=>!v)} />
                      <span className="ml-2 text-sm">Head & Shoulders (HS)</span>
                    </label>
                    <label className="flex items-center">
                      <input type="checkbox" className="form-checkbox h-4 w-4 text-primary rounded" checked={showIHS} onChange={() => setShowIHS(v=>!v)} />
                      <span className="ml-2 text-sm">Inverse H&S (IHS)</span>
                    </label>
                    <label className="flex items-center">
                      <input type="checkbox" className="form-checkbox h-4 w-4 text-primary rounded" checked={showDT} onChange={() => setShowDT(v=>!v)} />
                      <span className="ml-2 text-sm">Double Top (DT)</span>
                    </label>
                    <label className="flex items-center">
                      <input type="checkbox" className="form-checkbox h-4 w-4 text-primary rounded" checked={showDB} onChange={() => setShowDB(v=>!v)} />
                      <span className="ml-2 text-sm">Double Bottom (DB)</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* 알림 설정 섹션 */}
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">알림 설정</h3>
              <Button variant="outline" size="sm">알림 추가</Button>
            </div>
            
            <div className="border border-neutral-200 dark:border-neutral-700 rounded-md p-4 mb-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h4 className="font-medium">패턴 형성 알림</h4>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">패턴이 75% 이상 형성되면 알림</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked />
                  <div className="w-9 h-5 bg-neutral-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs text-neutral-500 mb-1">최소 신뢰도</label>
                  <select className="block w-full bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm" defaultValue="75%">
                    <option key="conf-50" value="50%">50%</option>
                    <option key="conf-60" value="60%">60%</option>
                    <option key="conf-75" value="75%">75%</option>
                    <option key="conf-90" value="90%">90%</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-xs text-neutral-500 mb-1">알림 방법</label>
                  <select className="block w-full bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm" defaultValue="이메일">
                    <option key="noti-app" value="앱 알림">앱 알림</option>
                    <option key="noti-email" value="이메일">이메일</option>
                    <option key="noti-sms" value="SMS">SMS</option>
                  </select>
                </div>
              </div>
            </div>
            
            <div className="border border-neutral-200 dark:border-neutral-700 rounded-md p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h4 className="font-medium">가격 레벨 돌파 알림</h4>
                  <p className="text-sm text-neutral-600 dark:text-neutral-400">주요 지지/저항선 돌파 시 알림</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked />
                  <div className="w-9 h-5 bg-neutral-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="block text-xs text-neutral-500 mb-1">돌파 유형</label>
                  <select className="block w-full bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm" defaultValue="모든 레벨">
                    <option key="break-support" value="지지선만">지지선만</option>
                    <option key="break-resistance" value="저항선만">저항선만</option>
                    <option key="break-all" value="모든 레벨">모든 레벨</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="block text-xs text-neutral-500 mb-1">확인 캔들</label>
                  <select className="block w-full bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-md p-2 text-sm" defaultValue="1개">
                    <option key="candle-none" value="필요 없음">필요 없음</option>
                    <option key="candle-1" value="1개">1개</option>
                    <option key="candle-2" value="2개">2개</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          
          {/* 뉴스 섹션 */}
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
            <h3 className="text-lg font-semibold mb-4">관련 뉴스</h3>
            
            <div className="space-y-4">
              <div key="news-1" className="border-b border-neutral-200 dark:border-neutral-700 pb-4">
                <h4 className="font-medium mb-1">비트코인, 기관 투자자들의 관심 증가로 상승세</h4>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">비트코인이 기관 투자자들의 지속적인 관심으로 인해 강한 상승 모멘텀을 유지하고 있습니다.</p>
                <div className="flex justify-between text-xs text-neutral-500">
                  <span>Bloomberg</span>
                  <span>1시간 전</span>
                </div>
              </div>
              
              <div key="news-2" className="border-b border-neutral-200 dark:border-neutral-700 pb-4">
                <h4 className="font-medium mb-1">SEC, 새로운 암호화폐 규제안 발표 예정</h4>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">미국 증권거래위원회(SEC)가 다음 주 새로운 암호화폐 관련 규제안을 발표할 예정입니다.</p>
                <div className="flex justify-between text-xs text-neutral-500">
                  <span>CoinDesk</span>
                  <span>3시간 전</span>
                </div>
              </div>
              
              <div key="news-3">
                <h4 className="font-medium mb-1">비트코인 채굴 난이도, 사상 최고치 기록</h4>
                <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">비트코인 채굴 난이도가 네트워크 해시레이트 증가로 인해 사상 최고치를 기록했습니다.</p>
                <div className="flex justify-between text-xs text-neutral-500">
                  <span>Cointelegraph</span>
                  <span>5시간 전</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 