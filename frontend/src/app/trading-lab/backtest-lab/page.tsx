import React from 'react';
import { Badge } from '@/components/ui/Badge';

export default function BacktestLabPage() {
  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Backtest Lab</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            패턴 기반 전략 검증 도구
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="warning">개발 중</Badge>
        </div>
      </div>
      
      {/* 임시 내용 */}
      <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 mb-6">
        <p className="text-neutral-600 dark:text-neutral-400 mb-4">
          Backtest Lab 페이지는 현재 개발 중입니다. 이 페이지에서는 다음과 같은 기능을 제공할 예정입니다:
        </p>
        
        <ul className="list-disc pl-5 space-y-2 text-neutral-700 dark:text-neutral-300">
          <li>패턴 기반 트레이딩 전략 설정</li>
          <li>다양한 시장 및 시간대에서 전략 백테스팅</li>
          <li>백테스트 결과 시각화 및 분석</li>
          <li>전략 최적화 도구</li>
        </ul>
      </div>
      
      {/* 준비 중 메시지 */}
      <div className="flex items-center justify-center p-12 bg-warning/5 rounded-lg border border-warning/20">
        <div className="text-center">
          <svg className="mx-auto mb-4 text-warning" xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 8v4"></path>
            <path d="M12 16h.01"></path>
          </svg>
          <h3 className="text-lg font-semibold mb-2">준비 중입니다</h3>
          <p className="text-neutral-600 dark:text-neutral-400 max-w-md">
            Backtest Lab은 현재 개발 중이며 곧 사용하실 수 있습니다. 
            완료되면 알림을 받으시려면 아래 버튼을 클릭하세요.
          </p>
          <button className="mt-6 bg-primary hover:bg-primary/90 text-white py-2 px-6 rounded-md">
            완료 시 알림 받기
          </button>
        </div>
      </div>
    </div>
  );
} 