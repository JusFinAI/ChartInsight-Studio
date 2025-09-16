import React from 'react';
import { Badge } from '@/components/ui/Badge';

export default function LiveScannerPage() {
  // 임시 데이터: 감지된 패턴 목록
  const detectedPatterns = [
    {
      id: 1,
      symbol: 'BTCUSDT',
      pattern: 'Double Bottom',
      timeframe: '1h',
      reliability: '높음',
      direction: '상승',
      detectedAt: '2023-03-28 14:30',
      priceLevel: '57,230'
    },
    {
      id: 2,
      symbol: 'ETHUSDT',
      pattern: 'Bull Flag',
      timeframe: '4h',
      reliability: '중간',
      direction: '상승',
      detectedAt: '2023-03-28 12:15',
      priceLevel: '3,145'
    },
    {
      id: 3,
      symbol: 'AAPL',
      pattern: 'Head and Shoulders',
      timeframe: '1d',
      reliability: '높음',
      direction: '하락',
      detectedAt: '2023-03-28 09:45',
      priceLevel: '175.23'
    },
    {
      id: 4,
      symbol: 'EURUSD',
      pattern: 'Triangle Breakout',
      timeframe: '1h',
      reliability: '중간',
      direction: '상승',
      detectedAt: '2023-03-28 15:00',
      priceLevel: '1.0845'
    }
  ];

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Live Scanner</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            실시간 패턴 감지 및 알림 기능
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="primary" className="mr-2">실시간</Badge>
          <Badge variant="secondary">AI 분석</Badge>
        </div>
      </div>
      
      {/* 필터 섹션 */}
      <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              마켓
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              <option>모든 마켓</option>
              <option>암호화폐</option>
              <option>주식</option>
              <option>외환</option>
              <option>상품</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              시간대
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              <option>모든 시간대</option>
              <option>1분</option>
              <option>5분</option>
              <option>15분</option>
              <option>1시간</option>
              <option>4시간</option>
              <option>1일</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              패턴 유형
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              <option>모든 패턴</option>
              <option>반전 패턴</option>
              <option>지속 패턴</option>
              <option>브레이크아웃 패턴</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              신뢰도
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              <option>모든 신뢰도</option>
              <option>높음</option>
              <option>중간</option>
              <option>낮음</option>
            </select>
          </div>
        </div>
        
        <div className="mt-4 flex justify-end">
          <button className="bg-primary hover:bg-primary/90 text-white py-2 px-4 rounded-md">
            필터 적용
          </button>
        </div>
      </div>
      
      {/* 감지된 패턴 테이블 */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 mb-6 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-neutral-50 dark:bg-neutral-900">
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">심볼</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">패턴</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">시간대</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">신뢰도</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">방향</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">감지 시간</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-neutral-700 dark:text-neutral-300">가격</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-neutral-700 dark:text-neutral-300">액션</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-700">
              {detectedPatterns.map((pattern) => (
                <tr key={pattern.id} className="hover:bg-neutral-50 dark:hover:bg-neutral-800/80">
                  <td className="px-4 py-3 text-sm font-medium">{pattern.symbol}</td>
                  <td className="px-4 py-3 text-sm">{pattern.pattern}</td>
                  <td className="px-4 py-3 text-sm">{pattern.timeframe}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium
                      ${pattern.reliability === '높음' ? 'bg-primary/10 text-primary' : 
                        pattern.reliability === '중간' ? 'bg-warning/10 text-warning' : 
                        'bg-neutral-200 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300'}`}>
                      {pattern.reliability}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`inline-flex items-center
                      ${pattern.direction === '상승' ? 'text-secondary' : 'text-warning'}`}>
                      {pattern.direction === '상승' ? (
                        <svg className="w-4 h-4 mr-1" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M12 5L19 12L12 19M5 12H18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      ) : (
                        <svg className="w-4 h-4 mr-1" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M12 19L5 12L12 5M19 12H6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                      {pattern.direction}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-neutral-600 dark:text-neutral-400">{pattern.detectedAt}</td>
                  <td className="px-4 py-3 text-sm">{pattern.priceLevel}</td>
                  <td className="px-4 py-3 text-sm text-center">
                    <button className="inline-flex items-center justify-center p-1 bg-primary/10 text-primary rounded-md hover:bg-primary/20">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                        <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* 알림 설정 섹션 */}
      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-semibold mb-4">알림 설정</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-base font-medium mb-2">알림 방식</h3>
            <div className="space-y-2">
              <div className="flex items-center">
                <input id="email-alert" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" />
                <label htmlFor="email-alert" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  이메일 알림
                </label>
              </div>
              <div className="flex items-center">
                <input id="browser-alert" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" defaultChecked />
                <label htmlFor="browser-alert" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  브라우저 알림
                </label>
              </div>
              <div className="flex items-center">
                <input id="mobile-alert" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" />
                <label htmlFor="mobile-alert" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  모바일 푸시 알림
                </label>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-base font-medium mb-2">필터링 옵션</h3>
            <div className="space-y-2">
              <div className="flex items-center">
                <input id="high-reliability" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" defaultChecked />
                <label htmlFor="high-reliability" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  높은 신뢰도 패턴만 알림
                </label>
              </div>
              <div className="flex items-center">
                <input id="watchlist-only" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" />
                <label htmlFor="watchlist-only" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  관심 목록 심볼만 알림
                </label>
              </div>
              <div className="flex items-center">
                <input id="specific-patterns" type="checkbox" className="h-4 w-4 text-primary border-neutral-300 focus:ring-primary" />
                <label htmlFor="specific-patterns" className="ml-2 text-sm text-neutral-700 dark:text-neutral-300">
                  특정 패턴만 알림
                </label>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-6">
          <button className="bg-primary hover:bg-primary/90 text-white py-2 px-4 rounded-md">
            알림 설정 저장
          </button>
        </div>
      </div>
    </div>
  );
} 