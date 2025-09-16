import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

// 간단한 아이콘 컴포넌트 (SVG)
const LiveScannerIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="19" x2="20" y2="19" />
    <polyline points="4 15 8 9 12 11 16 6 20 10" />
  </svg>
);

const TradingRadarIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <circle cx="12" cy="12" r="6"></circle>
    <circle cx="12" cy="12" r="2"></circle>
    <line x1="12" y1="2" x2="12" y2="4"></line>
    <line x1="12" y1="20" x2="12" y2="22"></line>
    <line x1="2" y1="12" x2="4" y2="12"></line>
    <line x1="20" y1="12" x2="22" y2="12"></line>
  </svg>
);

const PatternStrategyIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 3v18h18"></path>
    <path d="M3 12h4l3-6 4 12 3-7 4 1"></path>
  </svg>
);

export default function TradingLabPage() {
  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Trading Lab</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            실시간 차트 분석 및 패턴 스캐닝 도구
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="primary" className="mr-2">베타 기능</Badge>
          <Badge variant="secondary">업데이트: 2023.03.28</Badge>
        </div>
      </div>
      
      {/* 주요 기능 섹션 */}
      <section>
        <h2 className="text-lg font-semibold mb-4">주요 기능</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {/* 라이브 스캐너 카드 */}
          <a href="/trading-lab/live-scanner" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<LiveScannerIcon />}
                  <CardTitle>Live Scanner</CardTitle>
                </div>
                <CardDescription>
                  실시간으로 차트 패턴을 감지하고 트레이딩 기회를 식별합니다. 다양한 시장과 타임프레임에서 작동합니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
          
          {/* 트레이딩 레이더 카드 */}
          <a href="/trading-lab/trading-radar" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<TradingRadarIcon />}
                  <CardTitle>Trading Radar</CardTitle>
                </div>
                <CardDescription>
                  선택한 자산에 대한 고급 차트 분석과 실시간 패턴 추적을 제공합니다. 심층적인 기술적 분석 도구가 포함되어 있습니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
          
          {/* 패턴&전략 분석 카드 */}
          <a href="/trading-lab/pattern-strategy-analyzer" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<PatternStrategyIcon />}
                  <CardTitle>Pattern & Strategy Analysis</CardTitle>
                </div>
                <CardDescription>
                  과거 차트 패턴의 성능을 분석하고 트레이딩 전략을 백테스트하여 최적의 접근법을 찾습니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
        </div>
      </section>
      
      {/* 빠른 시작 가이드 */}
      <section className="bg-neutral-50 dark:bg-neutral-800/50 p-6 rounded-lg border border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-semibold mb-4">빠른 시작 가이드</h2>
        <ol className="list-decimal pl-5 space-y-3 text-neutral-700 dark:text-neutral-300">
          <li>Live Scanner에서 다중 자산의 차트 패턴을 한눈에 모니터링하세요.</li>
          <li>관심 있는 자산을 발견하면 Trading Radar에서 상세 분석을 진행하세요.</li>
          <li>Pattern & Strategy Analysis 도구를 통해 발견한 패턴의 과거 성과를 검증하세요.</li>
          <li>최적화된 전략으로 트레이딩 결정을 내리고 성과를 향상시키세요.</li>
        </ol>
        
        <div className="mt-4">
          <a href="#" className="text-primary hover:underline">
            자세한 사용 가이드 보기
          </a>
        </div>
      </section>
    </div>
  );
} 