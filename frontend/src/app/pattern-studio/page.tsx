import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

// 아이콘 컴포넌트
const PatternLibraryIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
    <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
    <path d="M9 12l2 2 4-4"></path>
  </svg>
);

const AIPatternLabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
    <line x1="3" y1="9" x2="21" y2="9"></line>
    <line x1="9" y1="21" x2="9" y2="9"></line>
  </svg>
);

const PatternAnalyticsIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"></line>
    <line x1="12" y1="20" x2="12" y2="4"></line>
    <line x1="6" y1="20" x2="6" y2="14"></line>
    <line x1="2" y1="20" x2="22" y2="20"></line>
  </svg>
);

export default function PatternStudioPage() {
  // 예시 통계 데이터
  const statsData = [
    { title: '등록된 패턴', value: '35+', change: '+3 (이번 달)' },
    { title: 'AI 분석', value: '1,240', change: '+18% (지난 주 대비)' },
    { title: '성공률', value: '72%', change: '+2.5% (지난 달 대비)' },
  ];

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Pattern Studio</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            AI 패턴 레이블링 및 패턴 라이브러리
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="primary" className="mr-2">AI 기능</Badge>
          <Badge variant="secondary">업데이트: 2023.03.28</Badge>
        </div>
      </div>
      
      {/* 통계 섹션 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {statsData.map((stat, index) => (
          <div key={index} className="bg-white dark:bg-neutral-800 p-6 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700">
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-1">{stat.title}</p>
            <div className="flex items-end justify-between">
              <h3 className="text-2xl font-bold text-neutral-900 dark:text-white">{stat.value}</h3>
              <p className={`text-xs ${stat.change.includes('+') ? 'text-secondary' : 'text-warning'}`}>
                {stat.change}
              </p>
            </div>
          </div>
        ))}
      </div>
      
      {/* 주요 기능 섹션 */}
      <section>
        <h2 className="text-lg font-semibold mb-4">주요 기능</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {/* 패턴 라이브러리 카드 */}
          <Card 
            title="Pattern Library" 
            description="차트 패턴의 상세 정보, 예시 이미지 및 성과 통계를 제공하는
            종합 라이브러리입니다."
            href="/pattern-studio/pattern-library"
            icon={<PatternLibraryIcon />}
          />
          
          {/* AI 패턴 랩 카드 */}
          <Card 
            title="AI Pattern Lab" 
            description="인공지능을 활용한 패턴 레이블링 도구로 차트에서 자동으로 패턴을 
            감지하고 분석합니다."
            href="/pattern-studio/ai-pattern-lab"
            icon={<AIPatternLabIcon />}
          />
          
          {/* 패턴 분석 카드 */}
          <Card 
            title="Pattern Analytics" 
            description="다양한 시장 환경에서 패턴의 성과와 신뢰도를 분석하고 시각화합니다."
            href="/pattern-studio/pattern-analytics"
            icon={<PatternAnalyticsIcon />}
          />
        </div>
      </section>
      
      {/* 최근 업데이트 섹션 */}
      <section className="bg-neutral-50 dark:bg-neutral-800/50 p-6 rounded-lg border border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-semibold mb-4">최근 업데이트</h2>
        <ul className="space-y-4">
          <li className="border-l-2 border-primary pl-4 py-1">
            <p className="font-medium">새로운 패턴 추가: Triangle Breakout</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">2023-03-25</p>
          </li>
          <li className="border-l-2 border-primary pl-4 py-1">
            <p className="font-medium">AI 모델 정확도 개선 (v2.1)</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">2023-03-18</p>
          </li>
          <li className="border-l-2 border-primary pl-4 py-1">
            <p className="font-medium">패턴 분석 대시보드 UI 개선</p>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">2023-03-10</p>
          </li>
        </ul>
        
        <div className="mt-4">
          <a href="#" className="text-primary hover:underline">
            모든 업데이트 보기
          </a>
        </div>
      </section>
    </div>
  );
} 