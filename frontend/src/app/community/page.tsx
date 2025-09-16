import React from 'react';
import { Badge } from '@/components/ui/Badge';

// 커뮤니티 게시물 인터페이스
interface CommunityPost {
  id: number;
  title: string;
  excerpt: string;
  author: string;
  authorAvatar?: string;
  date: string;
  category: string;
  tags: string[];
  commentsCount: number;
  likesCount: number;
  viewsCount: number;
}

export default function CommunityPage() {
  // 인기 토픽 데이터
  const popularTopics = [
    "차트 분석", "기술적 분석", "트레이딩 전략", "시장 전망", 
    "리스크 관리", "패턴 식별", "알고리즘 트레이딩", "심리적 요소"
  ];
  
  // 최신 게시물 데이터
  const latestPosts: CommunityPost[] = [
    {
      id: 1,
      title: "일본 엔화 가치 하락의 기술적 분석",
      excerpt: "최근 달러/엔 환율 차트에서 나타나는 특이 패턴과 미래 가격 예측에 대한 논의",
      author: "경제전문가",
      date: "2023-08-15",
      category: "기술적 분석",
      tags: ["환율", "엔화", "달러", "기술적분석"],
      commentsCount: 24,
      likesCount: 58,
      viewsCount: 412
    },
    {
      id: 2,
      title: "MACD와 RSI 조합을 활용한 전략 공유",
      excerpt: "두 인기 지표의 시그널 조합을 통해 허위 신호를 줄이는 개인 트레이딩 전략 소개",
      author: "전략마스터",
      date: "2023-08-12",
      category: "트레이딩 전략",
      tags: ["MACD", "RSI", "지표조합", "전략"],
      commentsCount: 31,
      likesCount: 76,
      viewsCount: 532
    },
    {
      id: 3,
      title: "바람직한 리스크 관리 계획 수립 방법",
      excerpt: "트레이더가 자신의 트레이딩 스타일에 맞는 리스크 관리 계획을 수립하는 방법 논의",
      author: "리스크전문가",
      date: "2023-08-10",
      category: "리스크 관리",
      tags: ["리스크관리", "자본관리", "손절매", "포지션사이징"],
      commentsCount: 19,
      likesCount: 47,
      viewsCount: 378
    },
    {
      id: 4,
      title: "인공지능 기반 패턴 인식 도구 리뷰",
      excerpt: "최신 AI 기반 차트 패턴 인식 도구들의 정확도 및 사용성 비교 분석",
      author: "테크리뷰어",
      date: "2023-08-08",
      category: "도구 리뷰",
      tags: ["AI", "패턴인식", "도구", "소프트웨어"],
      commentsCount: 15,
      likesCount: 39,
      viewsCount: 287
    },
    {
      id: 5,
      title: "8월 주요 경제 지표 발표와 시장 영향 분석",
      excerpt: "이번 달 발표될 주요 경제 지표와 이들이 금융 시장에 미칠 잠재적 영향에 대한 고찰",
      author: "마켓워처",
      date: "2023-08-05",
      category: "시장 전망",
      tags: ["경제지표", "시장영향", "전망", "분석"],
      commentsCount: 27,
      likesCount: 62,
      viewsCount: 456
    }
  ];
  
  // 인기 토론 데이터
  const hotDiscussions: CommunityPost[] = [
    {
      id: 6,
      title: "현재 시장 환경에서 가격 행동 분석의 효과",
      excerpt: "고변동성 시장에서 전통적인 가격 행동 분석 방법의 유효성에 대한 토론",
      author: "분석가A",
      date: "2023-08-13",
      category: "토론",
      tags: ["가격행동", "변동성", "시장환경"],
      commentsCount: 48,
      likesCount: 92,
      viewsCount: 723
    },
    {
      id: 7,
      title: "알고리즘 트레이딩 vs 수동 트레이딩: 어떤 접근법이 더 효과적인가?",
      excerpt: "다양한 시장 상황에서 알고리즘 트레이딩과 수동 트레이딩의 장단점 비교",
      author: "비교분석가",
      date: "2023-08-11",
      category: "토론",
      tags: ["알고리즘", "수동트레이딩", "비교", "효율성"],
      commentsCount: 63,
      likesCount: 87,
      viewsCount: 812
    },
    {
      id: 8,
      title: "차트 패턴이 실제로 효과가 있는가? 데이터 기반 검증",
      excerpt: "주요 차트 패턴의 실제 성공률을 10년간의 시장 데이터로 검증한 결과 공유",
      author: "데이터사이언티스트",
      date: "2023-08-07",
      category: "연구",
      tags: ["차트패턴", "백테스팅", "데이터분석", "검증"],
      commentsCount: 52,
      likesCount: 104,
      viewsCount: 936
    }
  ];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-title font-bold mb-2">커뮤니티</h1>
        <p className="text-body text-neutral-600 dark:text-neutral-400">
          트레이더들과 아이디어를 교환하고 지식을 공유하세요
        </p>
      </div>
      
      {/* 상단 통계 및 버튼 */}
      <div className="flex flex-col md:flex-row justify-between items-center mb-8">
        <div className="flex space-x-6 mb-4 md:mb-0">
          <div className="text-center">
            <div className="text-2xl font-bold text-primary">12.5K+</div>
            <div className="text-sm text-neutral-600 dark:text-neutral-400">회원</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-secondary">8.7K+</div>
            <div className="text-sm text-neutral-600 dark:text-neutral-400">토론</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-special">42.3K+</div>
            <div className="text-sm text-neutral-600 dark:text-neutral-400">게시물</div>
          </div>
        </div>
        
        <div className="flex space-x-3">
          <button className="bg-primary hover:bg-primary/90 text-white py-2 px-6 rounded-md">
            새 토론 시작
          </button>
          <button className="bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700 py-2 px-6 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-700">
            최신 활동
          </button>
        </div>
      </div>
      
      {/* 인기 토픽 */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-4">인기 토픽</h2>
        <div className="flex flex-wrap gap-2">
          {popularTopics.map(topic => (
            <a
              key={topic}
              href={`/community/topics/${encodeURIComponent(topic)}`}
              className="bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 px-4 py-2 rounded-full border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
            >
              {topic}
            </a>
          ))}
        </div>
      </div>
      
      {/* 최신 게시물 및 인기 토론 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* 최신 게시물 */}
        <div className="lg:col-span-2">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">최신 게시물</h2>
            <a href="/community/posts" className="text-primary hover:underline text-sm font-medium">
              모두 보기
            </a>
          </div>
          
          <div className="space-y-6">
            {latestPosts.map(post => (
              <div 
                key={post.id} 
                className="bg-white dark:bg-neutral-800 rounded-lg p-5 border border-neutral-200 dark:border-neutral-700 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between mb-3">
                  <Badge variant="primary">{post.category}</Badge>
                  <span className="text-sm text-neutral-500 dark:text-neutral-400">
                    {new Date(post.date).toLocaleDateString('ko-KR', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </span>
                </div>
                
                <h3 className="font-semibold text-lg mb-2">
                  <a href={`/community/posts/${post.id}`} className="hover:text-primary transition-colors">
                    {post.title}
                  </a>
                </h3>
                
                <p className="text-neutral-600 dark:text-neutral-400 text-sm mb-4">
                  {post.excerpt}
                </p>
                
                <div className="flex flex-wrap gap-1 mb-4">
                  {post.tags.map(tag => (
                    <a
                      key={tag}
                      href={`/community/tags/${tag}`}
                      className="text-xs bg-neutral-100 dark:bg-neutral-700 text-neutral-700 dark:text-neutral-300 px-2 py-1 rounded-md hover:bg-neutral-200 dark:hover:bg-neutral-600 transition-colors"
                    >
                      #{tag}
                    </a>
                  ))}
                </div>
                
                <div className="flex justify-between items-center">
                  <div className="flex items-center">
                    <div className="w-6 h-6 rounded-full bg-neutral-300 dark:bg-neutral-600 flex items-center justify-center text-xs mr-2">
                      {post.author.charAt(0)}
                    </div>
                    <span className="text-sm font-medium">{post.author}</span>
                  </div>
                  
                  <div className="flex space-x-4 text-neutral-500 dark:text-neutral-400 text-sm">
                    <span className="flex items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-1.008c-.428.303-.805.625-1.298.882l-1.757.585A.5.5 0 012 17.118V15.6c0-.251.154-.437.354-.544A6.975 6.975 0 010 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                      </svg>
                      {post.commentsCount}
                    </span>
                    <span className="flex items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                      </svg>
                      {post.likesCount}
                    </span>
                    <span className="flex items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                        <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                      </svg>
                      {post.viewsCount}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* 인기 토론 및 활동 */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700 overflow-hidden mb-6">
            <div className="bg-neutral-50 dark:bg-neutral-800/50 px-5 py-3 border-b border-neutral-200 dark:border-neutral-700">
              <h2 className="font-semibold">인기 토론</h2>
            </div>
            
            <div className="divide-y divide-neutral-200 dark:divide-neutral-700">
              {hotDiscussions.map(discussion => (
                <div key={discussion.id} className="p-4 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors">
                  <h3 className="font-medium mb-2">
                    <a href={`/community/discussions/${discussion.id}`} className="hover:text-primary transition-colors">
                      {discussion.title}
                    </a>
                  </h3>
                  
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-neutral-500 dark:text-neutral-400">
                      {discussion.author} · {discussion.commentsCount}개 댓글
                    </span>
                    <Badge 
                      variant={
                        discussion.category === "토론" ? "secondary" : 
                        discussion.category === "연구" ? "primary" : 
                        "primary"
                      }
                    >
                      {discussion.category}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="bg-neutral-50 dark:bg-neutral-800/50 px-4 py-3 text-center">
              <a href="/community/discussions" className="text-primary hover:underline text-sm font-medium">
                모든 토론 보기
              </a>
            </div>
          </div>
          
          {/* 커뮤니티 가입 안내 */}
          <div className="bg-gradient-to-r from-primary/10 to-secondary/10 dark:from-primary/20 dark:to-secondary/20 rounded-lg p-5">
            <h2 className="font-semibold mb-3">ChartInsight 커뮤니티에 가입하세요</h2>
            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-4">
              전 세계 트레이더들과 소통하고, 전략을 공유하며, 함께 성장하세요.
            </p>
            
            <ul className="text-sm text-neutral-600 dark:text-neutral-400 mb-4 space-y-2">
              <li className="flex items-center">
                <svg className="h-4 w-4 text-primary mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                실시간 시장 분석 토론
              </li>
              <li className="flex items-center">
                <svg className="h-4 w-4 text-primary mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                전문가의 차트 분석 리뷰
              </li>
              <li className="flex items-center">
                <svg className="h-4 w-4 text-primary mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                독점 교육 자료 접근
              </li>
            </ul>
            
            <button className="w-full bg-primary hover:bg-primary/90 text-white py-2 rounded-md">
              지금 가입하기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 