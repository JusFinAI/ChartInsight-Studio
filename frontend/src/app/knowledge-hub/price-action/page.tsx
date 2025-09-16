import React from 'react';
import { Badge } from '@/components/ui/Badge';

interface PriceActionArticle {
  id: number;
  title: string;
  description: string;
  level: string;
  readTime: string;
  date: string;
  author: string;
  tags: string[];
  imageUrl?: string;
}

export default function PriceActionPage() {
  // 가격 행동 관련 기사 데이터
  const articles: PriceActionArticle[] = [
    {
      id: 1,
      title: "캔들스틱 패턴의 이해",
      description: "기본 캔들스틱 패턴의 의미와 시장에서 이를 해석하는 방법에 대한 종합 가이드",
      level: "초급",
      readTime: "20분",
      date: "2023-02-15",
      author: "김트레이더",
      tags: ["캔들스틱", "차트패턴", "기초"]
    },
    {
      id: 2,
      title: "트렌드 식별 및 분석 기법",
      description: "시장 트렌드를 정확하게 식별하고 분석하는 방법론과 실전 예제",
      level: "중급",
      readTime: "25분",
      date: "2023-03-10",
      author: "이분석가",
      tags: ["트렌드분석", "시장동향", "추세매매"]
    },
    {
      id: 3,
      title: "지지선과 저항선 트레이딩 전략",
      description: "지지선과 저항선을 활용한 효과적인 진입 및 퇴출 전략 개발",
      level: "중급",
      readTime: "30분",
      date: "2023-04-05",
      author: "박전략가",
      tags: ["지지선", "저항선", "진입전략"]
    },
    {
      id: 4,
      title: "가격 행동과 거래량의 관계",
      description: "거래량이 가격 행동에 미치는 영향과 이를 트레이딩에 활용하는 방법",
      level: "고급",
      readTime: "35분",
      date: "2023-05-20",
      author: "최마스터",
      tags: ["거래량분석", "가격행동", "상관관계"]
    },
    {
      id: 5,
      title: "핀바 패턴을 활용한 반전 신호 포착",
      description: "핀바(Pin Bar) 패턴의 특징과 이를 활용한 시장 반전 신호 포착 전략",
      level: "중급",
      readTime: "22분",
      date: "2023-06-15",
      author: "정반전",
      tags: ["핀바", "반전신호", "패턴트레이딩"]
    },
    {
      id: 6,
      title: "다중 시간대 분석의 중요성",
      description: "여러 시간대 차트를 분석하여 보다 정확한 트레이딩 결정을 내리는 방법",
      level: "고급",
      readTime: "40분",
      date: "2023-07-08",
      author: "한시간",
      tags: ["다중시간대", "차트분석", "분석기법"]
    }
  ];

  // 필터링 옵션 (실제 구현 시에는 상태 관리 필요)
  const levels = ["모든 레벨", "초급", "중급", "고급"];
  const tags = ["모든 태그", "캔들스틱", "트렌드분석", "지지선", "저항선", "거래량분석", "패턴트레이딩"];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-title font-bold mb-2">Price Action</h1>
        <p className="text-body text-neutral-600 dark:text-neutral-400">
          가격 행동 분석에 대한 모든 것
        </p>
      </div>

      {/* 필터링 섹션 */}
      <div className="bg-white dark:bg-neutral-800 rounded-lg p-4 mb-8 border border-neutral-200 dark:border-neutral-700">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-2 text-neutral-700 dark:text-neutral-300">
              난이도
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900">
              {levels.map(level => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium mb-2 text-neutral-700 dark:text-neutral-300">
              태그
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900">
              {tags.map(tag => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium mb-2 text-neutral-700 dark:text-neutral-300">
              정렬 기준
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-900">
              <option value="latest">최신순</option>
              <option value="oldest">오래된순</option>
              <option value="popular">인기순</option>
            </select>
          </div>
        </div>
      </div>

      {/* 소개 섹션 */}
      <div className="bg-gradient-to-r from-primary/10 to-secondary/10 dark:from-primary/20 dark:to-secondary/20 p-6 rounded-lg mb-8">
        <h2 className="font-semibold text-lg mb-3">가격 행동 분석이란?</h2>
        <p className="mb-4">
          가격 행동 분석(Price Action)은 차트 상의 순수한 가격 움직임에 기반한 트레이딩 접근법입니다. 
          지표나 오실레이터에 의존하지 않고, 가격 자체의 움직임을 분석하여 시장 방향을 예측합니다.
        </p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="primary">높은 신뢰성</Badge>
          <Badge variant="secondary">적은 지연</Badge>
          <Badge variant="outline">실시간 분석</Badge>
          <Badge variant="success">다양한 시장 적용</Badge>
        </div>
      </div>

      {/* 콘텐츠 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {articles.map(article => (
          <div key={article.id} className="bg-white dark:bg-neutral-800 rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-700 shadow-sm hover:shadow-md transition-shadow duration-200">
            {/* 이미지 영역 - 이미지가 실제로 없으므로 회색 배경으로 대체 */}
            <div className="bg-neutral-200 dark:bg-neutral-700 h-40 flex items-center justify-center">
              <span className="text-neutral-500 dark:text-neutral-400">
                {article.title} 관련 이미지
              </span>
            </div>
            
            <div className="p-4">
              <div className="flex justify-between items-start mb-2">
                <Badge 
                  variant={
                    article.level === "초급" ? "secondary" : 
                    article.level === "중급" ? "primary" : 
                    "warning"
                  }
                >
                  {article.level}
                </Badge>
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  {article.readTime} 읽기
                </span>
              </div>
              
              <h3 className="font-semibold text-lg mb-2">{article.title}</h3>
              
              <p className="text-neutral-600 dark:text-neutral-400 text-sm mb-4 line-clamp-2">
                {article.description}
              </p>
              
              <div className="flex flex-wrap gap-1 mb-3">
                {article.tags.map(tag => (
                  <span key={tag} className="text-xs bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-1 rounded-md">
                    #{tag}
                  </span>
                ))}
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-sm text-neutral-500 dark:text-neutral-400">
                  By {article.author}
                </span>
                <span className="text-xs text-neutral-500 dark:text-neutral-400">
                  {new Date(article.date).toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 페이지네이션 */}
      <div className="flex justify-center mb-8">
        <nav className="inline-flex rounded-md shadow-sm">
          <a href="#" className="px-3 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-l-md hover:bg-neutral-100 dark:hover:bg-neutral-700">
            이전
          </a>
          <a href="#" className="px-3 py-2 text-sm font-medium text-white bg-primary border border-primary">
            1
          </a>
          <a href="#" className="px-3 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-700">
            2
          </a>
          <a href="#" className="px-3 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-700">
            3
          </a>
          <a href="#" className="px-3 py-2 text-sm font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-600 rounded-r-md hover:bg-neutral-100 dark:hover:bg-neutral-700">
            다음
          </a>
        </nav>
      </div>

      {/* 학습 자료 추천 */}
      <div className="bg-neutral-50 dark:bg-neutral-800/50 p-6 rounded-lg border border-neutral-200 dark:border-neutral-700">
        <h2 className="text-lg font-semibold mb-4">추천 학습 자료</h2>
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 bg-white dark:bg-neutral-800 p-4 rounded-md border border-neutral-200 dark:border-neutral-700">
            <h3 className="font-semibold mb-2">초보자를 위한 가격 행동 가이드</h3>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-3">
              처음 시작하는 트레이더를 위한 가격 행동 분석의 기본 원칙과 가이드라인
            </p>
            <a href="#" className="text-primary hover:underline text-sm font-medium">
              자세히 보기 →
            </a>
          </div>
          <div className="flex-1 bg-white dark:bg-neutral-800 p-4 rounded-md border border-neutral-200 dark:border-neutral-700">
            <h3 className="font-semibold mb-2">가격 행동 마스터 코스</h3>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-3">
              고급 트레이더를 위한 심층적인 가격 행동 분석 및 전략 개발 과정
            </p>
            <a href="#" className="text-primary hover:underline text-sm font-medium">
              자세히 보기 →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
} 