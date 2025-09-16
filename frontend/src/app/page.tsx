import React from 'react';

export default function Home() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-title font-bold mb-2">ChartInsight Studio에 오신 것을 환영합니다</h1>
        <p className="text-body text-neutral-600 dark:text-neutral-400">
          트레이딩 및 차트 분석을 위한 종합 플랫폼입니다.
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
          <h2 className="text-lg font-semibold mb-2">트레이딩 랩</h2>
          <p className="text-neutral-600 dark:text-neutral-400 mb-4">실시간 차트 분석 및 패턴 스캐닝 도구</p>
          <a href="/trading-lab" className="text-primary hover:underline">
            살펴보기 &rarr;
          </a>
        </div>
        
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
          <h2 className="text-lg font-semibold mb-2">패턴 스튜디오</h2>
          <p className="text-neutral-600 dark:text-neutral-400 mb-4">AI 패턴 레이블링 및 패턴 라이브러리</p>
          <a href="/pattern-studio" className="text-primary hover:underline">
            살펴보기 &rarr;
          </a>
        </div>
        
        <div className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
          <h2 className="text-lg font-semibold mb-2">지식 허브</h2>
          <p className="text-neutral-600 dark:text-neutral-400 mb-4">교육 자료 및 콘텐츠 섹션</p>
          <a href="/knowledge-hub" className="text-primary hover:underline">
            살펴보기 &rarr;
          </a>
        </div>
      </div>
    </div>
  );
}
