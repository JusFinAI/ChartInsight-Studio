import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

// 아이콘 컴포넌트
const PriceActionIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 9.5V4a2 2 0 0 1 2-2h3.5"></path>
    <path d="M2 14.5V20a2 2 0 0 0 2 2h3.5"></path>
    <path d="M22 9.5V4a2 2 0 0 0-2-2h-3.5"></path>
    <path d="M22 14.5V20a2 2 0 0 1-2 2h-3.5"></path>
    <line x1="7" y1="12" x2="17" y2="12"></line>
  </svg>
);

const AlgorithmTradingIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
    <line x1="8" y1="21" x2="16" y2="21"></line>
    <line x1="12" y1="17" x2="12" y2="21"></line>
    <polyline points="8 11 12 15 16 11"></polyline>
    <line x1="12" y1="9" x2="12" y2="15"></line>
  </svg>
);

const AITradingIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a10 10 0 1 0 10 10H12V2z"></path>
    <path d="M20 2a10 10 0 0 0-10 10V2a10 10 0 0 0 10 10h-8a10 10 0 0 0 0 0v0"></path>
    <path d="M2 12h10V2"></path>
  </svg>
);

const MarketAnalysisIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8" cy="21" r="1"></circle>
    <circle cx="20" cy="21" r="1"></circle>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
  </svg>
);

export default function KnowledgeHubPage() {
  // 추천 콘텐츠 데이터
  const featuredContent = [
    {
      id: 1,
      title: "가격 행동 트레이딩 가이드",
      description: "초보자부터 전문가까지 모든 수준의 트레이더를 위한 가격 행동 분석의 기초",
      category: "Price Action",
      difficulty: "초급",
      author: "John Smith",
      readTime: "15분",
      imageUrl: "/content/price-action-guide.jpg"
    },
    {
      id: 2,
      title: "알고리즘 트레이딩 시작하기",
      description: "프로그래밍 지식 없이도 시작할 수 있는 알고리즘 트레이딩 입문서",
      category: "Algorithm Trading",
      difficulty: "중급",
      author: "Jane Doe",
      readTime: "20분",
      imageUrl: "/content/algo-trading-intro.jpg"
    },
    {
      id: 3,
      title: "AI를 활용한 시장 예측",
      description: "인공지능과 머신러닝이 금융 시장 예측에 어떻게 적용되는지에 대한 분석",
      category: "AI & Trading",
      difficulty: "고급",
      author: "Alex Chen",
      readTime: "25분",
      imageUrl: "/content/ai-market-prediction.jpg"
    }
  ];

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Knowledge Hub</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            교육 자료 및 콘텐츠 섹션
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="secondary">최근 업데이트: 2023.03.28</Badge>
        </div>
      </div>
      
      {/* 추천 콘텐츠 섹션 */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">추천 콘텐츠</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
          {featuredContent.map(content => (
            <div key={content.id} className="bg-white dark:bg-neutral-800 rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-700 shadow-sm hover:shadow-md transition-shadow duration-200">
              {/* 이미지 영역 - 이미지가 실제로 없으므로 회색 배경으로 대체 */}
              <div className="bg-neutral-200 dark:bg-neutral-700 h-40 flex items-center justify-center">
                <span className="text-neutral-500 dark:text-neutral-400">
                  {content.category} 콘텐츠 이미지
                </span>
              </div>
              
              <div className="p-4">
                <div className="flex justify-between items-start mb-2">
                  <Badge 
                    variant={
                      content.category === "Price Action" ? "primary" : 
                      content.category === "Algorithm Trading" ? "secondary" : 
                      "outline"
                    }
                  >
                    {content.category}
                  </Badge>
                  <span className="text-sm text-neutral-500 dark:text-neutral-400">
                    {content.readTime} 읽기
                  </span>
                </div>
                
                <h3 className="font-semibold text-lg mb-2">{content.title}</h3>
                
                <p className="text-neutral-600 dark:text-neutral-400 text-sm mb-4">
                  {content.description}
                </p>
                
                <div className="flex justify-between items-center">
                  <span className="text-sm text-neutral-500 dark:text-neutral-400">
                    작성자: {content.author}
                  </span>
                  <Badge 
                    variant={
                      content.difficulty === "초급" ? "secondary" : 
                      content.difficulty === "중급" ? "primary" : 
                      "warning"
                    }
                  >
                    {content.difficulty}
                  </Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <div className="text-right">
          <a href="#" className="text-primary hover:underline text-sm font-medium">
            모든 추천 콘텐츠 보기 →
          </a>
        </div>
      </section>
      
      {/* 카테고리 섹션 */}
      <section>
        <h2 className="text-lg font-semibold mb-4">지식 카테고리</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <a href="/knowledge-hub/price-action" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<PriceActionIcon />}
                  <CardTitle>Price Action</CardTitle>
                </div>
                <CardDescription>
                  가격 행동 분석의 기초부터 고급 기법까지, 시장의 움직임을 직접 분석하는 방법을 배웁니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
          
          <a href="/knowledge-hub/algorithm-trading" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<AlgorithmTradingIcon />}
                  <CardTitle>Algorithm Trading</CardTitle>
                </div>
                <CardDescription>
                  자동화된 트레이딩 시스템 구축 및 백테스팅 방법론에 대한 가이드라인과 실전 예제를 제공합니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
          
          <a href="/knowledge-hub/ai-trading" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<AITradingIcon />}
                  <CardTitle>AI & Trading</CardTitle>
                </div>
                <CardDescription>
                  인공지능과 머신러닝을 활용한 트레이딩 전략 개발 및 최신 기술 동향을 소개합니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
          
          <a href="/knowledge-hub/market-analysis" className="block transition-transform hover:scale-105">
            <Card className="h-full cursor-pointer">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {<MarketAnalysisIcon />}
                  <CardTitle>Market Analysis</CardTitle>
                </div>
                <CardDescription>
                  펀더멘털 분석과 기술적 분석을 결합한 시장 분석 방법론과 실전 적용 사례를 다룹니다.
                </CardDescription>
              </CardHeader>
            </Card>
          </a>
        </div>
      </section>
      
      {/* 학습 진행 상황 섹션 */}
      <section className="bg-neutral-50 dark:bg-neutral-800/50 p-6 rounded-lg border border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-semibold mb-4">나의 학습 현황</h2>
        <p className="text-neutral-600 dark:text-neutral-400 mb-4">
          로그인하여 자신만의 학습 경로를 만들고 진행 상황을 추적하세요.
        </p>
        
        <button className="bg-primary hover:bg-primary/90 text-white py-2 px-6 rounded-md">
          로그인하기
        </button>
      </section>
    </div>
  );
} 