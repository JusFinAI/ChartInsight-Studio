import React from 'react';
import { Badge } from '@/components/ui/Badge';

interface PatternCard {
  id: number;
  name: string;
  category: string;
  reliability: string;
  description: string;
  direction: '상승' | '하락' | '양방향';
  imageUrl: string;
}

export default function PatternLibraryPage() {
  // 샘플 패턴 데이터
  const patterns: PatternCard[] = [
    {
      id: 1,
      name: '더블 바텀',
      category: '반전',
      reliability: '높음',
      description: '하락 추세가 끝나고 상승 추세로 전환될 가능성을 나타내는 W 형태의 패턴',
      direction: '상승',
      imageUrl: '/patterns/double-bottom.png'
    },
    {
      id: 2,
      name: '헤드 앤 숄더',
      category: '반전',
      reliability: '중간',
      description: '상승 추세가 끝나고 하락 추세로 전환될 가능성을 나타내는 패턴',
      direction: '하락',
      imageUrl: '/patterns/head-and-shoulders.png'
    },
    {
      id: 3,
      name: '삼각 수렴',
      category: '지속',
      reliability: '중간',
      description: '가격 변동성이 줄어들면서 삼각형 모양을 형성하는 패턴으로, 추세 방향으로 브레이크아웃될 가능성이 높음',
      direction: '양방향',
      imageUrl: '/patterns/triangle.png'
    },
    {
      id: 4,
      name: '불 플래그',
      category: '지속',
      reliability: '높음',
      description: '급격한 상승 후 잠시 조정을 받는 패턴으로, 이후 상승 추세가 계속될 가능성이 높음',
      direction: '상승',
      imageUrl: '/patterns/bull-flag.png'
    },
    {
      id: 5,
      name: '디센딩 웨지',
      category: '반전',
      reliability: '중간',
      description: '하락 추세에서 형성되는 쐐기 모양의 패턴으로, 상방 브레이크아웃 가능성이 높음',
      direction: '상승',
      imageUrl: '/patterns/descending-wedge.png'
    },
    {
      id: 6,
      name: '컵 앤 핸들',
      category: '지속',
      reliability: '높음',
      description: '컵 모양과 그 뒤를 따르는 손잡이 모양으로 구성된 패턴으로, 상승 추세의 지속을 의미',
      direction: '상승',
      imageUrl: '/patterns/cup-and-handle.png'
    }
  ];

  // 카테고리별 필터링 기능 (실제로는 상태로 관리 필요)
  const categories = ['모두', '반전', '지속', '브레이크아웃'];
  const directions = ['모두', '상승', '하락', '양방향'];
  const reliabilities = ['모두', '높음', '중간', '낮음'];

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-title font-bold mb-2">Pattern Library</h1>
          <p className="text-body text-neutral-600 dark:text-neutral-400">
            다양한 차트 패턴 정보
          </p>
        </div>
        
        <div className="mt-4 md:mt-0">
          <Badge variant="primary">총 {patterns.length}개의 패턴</Badge>
        </div>
      </div>
      
      {/* 필터 섹션 */}
      <div className="bg-white dark:bg-neutral-800 p-4 rounded-lg shadow-sm border border-neutral-200 dark:border-neutral-700 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              검색
            </label>
            <input 
              type="text" 
              placeholder="패턴 이름 검색..."
              className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              카테고리
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              {categories.map(category => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              방향
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              {directions.map(direction => (
                <option key={direction} value={direction}>{direction}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              신뢰도
            </label>
            <select className="w-full p-2 border border-neutral-300 dark:border-neutral-700 rounded-md bg-white dark:bg-neutral-800">
              {reliabilities.map(reliability => (
                <option key={reliability} value={reliability}>{reliability}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
      
      {/* 패턴 카드 그리드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {patterns.map(pattern => (
          <div key={pattern.id} className="bg-white dark:bg-neutral-800 rounded-lg overflow-hidden border border-neutral-200 dark:border-neutral-700 shadow-sm hover:shadow-md transition-shadow duration-200">
            {/* 이미지 영역 - 이미지가 실제로 없으므로 회색 배경으로 대체 */}
            <div className="bg-neutral-200 dark:bg-neutral-700 h-40 flex items-center justify-center">
              <span className="text-neutral-500 dark:text-neutral-400">
                패턴 차트 이미지
              </span>
            </div>
            
            <div className="p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-lg">{pattern.name}</h3>
                <Badge 
                  variant={pattern.reliability === '높음' ? 'primary' : pattern.reliability === '중간' ? 'secondary' : 'warning'}
                >
                  {pattern.reliability}
                </Badge>
              </div>
              
              <div className="flex space-x-2 mb-3">
                <Badge variant="outline">{pattern.category}</Badge>
                <Badge 
                  variant={pattern.direction === '상승' ? 'success' : pattern.direction === '하락' ? 'warning' : 'secondary'}
                >
                  {pattern.direction}
                </Badge>
              </div>
              
              <p className="text-neutral-600 dark:text-neutral-400 text-sm mb-4">
                {pattern.description}
              </p>
              
              <a href={`/pattern-studio/pattern-library/${pattern.id}`} className="text-primary hover:underline text-sm font-medium">
                상세 정보 보기 →
              </a>
            </div>
          </div>
        ))}
      </div>
      
      {/* 더 보기 버튼 */}
      <div className="flex justify-center">
        <button className="px-6 py-2 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-md text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700">
          더 많은 패턴 보기
        </button>
      </div>
    </div>
  );
} 