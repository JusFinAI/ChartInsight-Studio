'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function PatternStrategyAnalyzerPage() {
  // 백테스트 결과 데이터
  const backtestResults = [
    { 
      name: '이중 바닥 전략', 
      winRate: 68, 
      totalTrades: 124, 
      profitFactor: 1.8, 
      avgReturn: 2.3, 
      maxDrawdown: 12.5 
    },
    { 
      name: '삼각 브레이크아웃 전략', 
      winRate: 72, 
      totalTrades: 87, 
      profitFactor: 2.1, 
      avgReturn: 2.8, 
      maxDrawdown: 15.2 
    },
    { 
      name: '볼린저밴드 반전 전략', 
      winRate: 54, 
      totalTrades: 215, 
      profitFactor: 1.5, 
      avgReturn: 1.7, 
      maxDrawdown: 9.8 
    }
  ];

  // 최근 분석 데이터
  const recentAnalyses = [
    { 
      title: 'BTCUSDT 일간 차트의 삼각수렴 패턴 성공률', 
      date: '2023-03-27', 
      type: '패턴 분석',
      result: '72% 성공률'
    },
    { 
      title: 'AAPL 주가의 패턴 기반 백테스트 결과', 
      date: '2023-03-25', 
      type: '백테스트',
      result: '연간 수익률 18.5%'
    },
    { 
      title: '외환 시장에서의 브레이크아웃 패턴 통계', 
      date: '2023-03-22', 
      type: '시장 분석',
      result: '55% 정확도'
    }
  ];

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Pattern & Strategy Analysis</h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Historical chart pattern performance analysis and trading strategy validation
        </p>
      </div>

      {/* 주요 기능 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card 
          title="Pattern Performance Analysis" 
          description="Analyze the success rate and profitability of chart patterns in various market environments."
          href="/trading-lab/pattern-strategy-analyzer/pattern-performance"
        />
        
        <Card 
          title="Strategy Backtesting" 
          description="Validate historical performance of pattern-based trading strategies."
          href="/trading-lab/pattern-strategy-analyzer/strategy-backtest"
        />
        
        <Card 
          title="Performance Comparison" 
          description="Compare performance of various patterns and strategies to find the optimal approach."
          href="/trading-lab/pattern-strategy-analyzer/performance-comparison"
        />
      </div>

      {/* 백테스트 결과 */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">최근 백테스트 결과</h2>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-neutral-50 dark:bg-neutral-900">
                <th className="px-4 py-3 text-left text-sm font-semibold">전략 이름</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">승률</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">거래 수</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">수익 팩터</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">평균 수익률</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">최대 낙폭</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-700">
              {backtestResults.map((result, index) => (
                <tr key={index} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/80">
                  <td className="px-4 py-3 text-sm font-medium">{result.name}</td>
                  <td className="px-4 py-3 text-sm">
                    <Badge variant={result.winRate > 65 ? 'primary' : result.winRate > 50 ? 'secondary' : 'warning'}>
                      {result.winRate}%
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm">{result.totalTrades}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={result.profitFactor > 1.7 ? 'text-secondary' : 'text-neutral-700 dark:text-neutral-300'}>
                      {result.profitFactor.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">{result.avgReturn}%</td>
                  <td className="px-4 py-3 text-sm">{result.maxDrawdown}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="mt-4 flex justify-end">
          <Button variant="ghost">
            모든 백테스트 결과 보기
          </Button>
        </div>
      </div>

      {/* 분석 도구 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* 왼쪽: 백테스트 설정 */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
            <h2 className="text-xl font-semibold mb-4">새 분석 시작</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  분석 유형
                </label>
                <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
                  <option>패턴 성공률 분석</option>
                  <option>전략 백테스트</option>
                  <option>시장 환경 분석</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  자산 선택
                </label>
                <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
                  <option>BTCUSDT</option>
                  <option>ETHUSDT</option>
                  <option>AAPL</option>
                  <option>SPY</option>
                  <option>EURUSD</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  타임프레임
                </label>
                <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
                  <option>15분</option>
                  <option>1시간</option>
                  <option>4시간</option>
                  <option>1일</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  날짜 범위
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <input type="date" className="p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800" defaultValue="2023-01-01" />
                  <input type="date" className="p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800" defaultValue="2023-03-28" />
                </div>
              </div>
              
              <div className="pt-4">
                <Button variant="primary" className="w-full">
                  분석 시작
                </Button>
              </div>
            </div>
          </div>
        </div>
        
        {/* 오른쪽: 최근 분석 및 성능 차트 */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">최근 분석</h2>
            
            <div className="space-y-4">
              {recentAnalyses.map((analysis, index) => (
                <div key={index} className="flex justify-between items-center border-b last:border-0 pb-3">
                  <div>
                    <h3 className="font-medium">{analysis.title}</h3>
                    <div className="flex items-center mt-1">
                      <span className="text-xs text-neutral-600 dark:text-neutral-400 mr-2">{analysis.date}</span>
                      <Badge variant="secondary" className="text-xs">{analysis.type}</Badge>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium">{analysis.result}</div>
                    <Button variant="ghost" className="text-xs p-0 h-auto mt-1">결과 보기</Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* 성능 차트 */}
          <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
            <h2 className="text-xl font-semibold mb-4">패턴 성능 비교</h2>
            
            <div className="w-full h-[300px] bg-neutral-100 dark:bg-neutral-700 rounded-lg flex items-center justify-center mb-4">
              <div className="text-center">
                <h3 className="text-lg font-medium mb-2">차트 시각화 영역</h3>
                <p className="text-neutral-600 dark:text-neutral-400">실제 구현 시 차트 라이브러리 통합</p>
              </div>
            </div>
            
            <div className="flex flex-wrap gap-2">
              <Badge variant="primary" className="cursor-pointer">이중 바닥</Badge>
                              <Badge variant="secondary" className="cursor-pointer">삼각수렴</Badge>
                <Badge variant="secondary" className="cursor-pointer">헤드앤숄더</Badge>
                <Badge variant="secondary" className="cursor-pointer">브레이크아웃</Badge>
                <Badge variant="secondary" className="cursor-pointer">+ 다른 패턴</Badge>
            </div>
          </div>
        </div>
      </div>
      
      {/* 통계 및 인사이트 */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 p-6">
        <h2 className="text-xl font-semibold mb-4">패턴 인사이트</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-lg font-medium mb-3">시장 환경별 패턴 성공률</h3>
            <ul className="space-y-2">
              <li className="flex justify-between items-center">
                <span>상승장에서의 불리시 패턴</span>
                <Badge variant="primary">78% 성공</Badge>
              </li>
              <li className="flex justify-between items-center">
                <span>하락장에서의 베리시 패턴</span>
                <Badge variant="primary">65% 성공</Badge>
              </li>
              <li className="flex justify-between items-center">
                <span>변동성이 높은 시장에서의 브레이크아웃</span>
                <Badge variant="secondary">52% 성공</Badge>
              </li>
              <li className="flex justify-between items-center">
                <span>저변동성 시장에서의 연속 패턴</span>
                <Badge variant="primary">81% 성공</Badge>
              </li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-lg font-medium mb-3">최적화 인사이트</h3>
            <div className="space-y-4 text-neutral-600 dark:text-neutral-400">
              <p>
                <span className="font-medium text-neutral-900 dark:text-white">이중 바닥 패턴:</span> RSI가 30 이하에서 형성될 때 성공률이 82%로 상승
              </p>
              <p>
                <span className="font-medium text-neutral-900 dark:text-white">삼각수렴 패턴:</span> 거래량이 감소하다가 브레이크아웃 시 급증할 때 성공률 74%
              </p>
              <p>
                <span className="font-medium text-neutral-900 dark:text-white">플래그 패턴:</span> 2:1 위험 대비 보상 비율로 목표가 설정 시 최적의 결과
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 