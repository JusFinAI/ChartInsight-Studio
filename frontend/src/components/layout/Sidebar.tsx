'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface MenuItem {
  title: string;
  path: string;
  icon?: React.ReactNode;
  children?: MenuItem[];
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar = ({ isOpen, onClose }: SidebarProps) => {
  const pathname = usePathname();
  const [expandedMenus, setExpandedMenus] = useState<string[]>([]);
  const [activeMainMenu, setActiveMainMenu] = useState<string | null>(null);
  
  // 주 메뉴 구조 정의
  const mainMenuItems: MenuItem[] = [
    {
      title: 'Trading Lab',
      path: '/trading-lab',
      children: [
        { title: 'Live Scanner', path: '/trading-lab/live-scanner' },
        { title: 'Trading Radar', path: '/trading-lab/trading-radar' },
        { title: 'Pattern & Strategy Analysis', path: '/trading-lab/pattern-strategy-analyzer' },
      ]
    },
    {
      title: 'Pattern Studio',
      path: '/pattern-studio',
      children: [
        { title: 'Pattern Library', path: '/pattern-studio/pattern-library' },
        { title: 'AI Pattern Lab', path: '/pattern-studio/ai-pattern-lab' },
        { title: 'Pattern Analytics', path: '/pattern-studio/pattern-analytics' },
      ]
    },
    {
      title: 'Knowledge Hub',
      path: '/knowledge-hub',
      children: [
        { title: 'Price Action', path: '/knowledge-hub/price-action' },
        { title: 'Algorithm Trading', path: '/knowledge-hub/algorithm-trading' },
        { title: 'AI & Trading', path: '/knowledge-hub/ai-trading' },
        { title: 'Market Analysis', path: '/knowledge-hub/market-analysis' },
      ]
    },
    {
      title: 'Community',
      path: '/community',
      children: [
        { title: 'Trading Ideas', path: '/community/trading-ideas' },
        { title: 'Pattern Analysis', path: '/community/pattern-analysis' },
        { title: 'Q&A', path: '/community/qa' },
        { title: 'Study Groups', path: '/community/study-groups' },
      ]
    }
  ];

  // 현재 활성화된 메인 메뉴 확인 및 설정
  useEffect(() => {
    // 현재 경로에 기반하여 활성화된 메인 메뉴 찾기
    const activeMenu = mainMenuItems.find(item => 
      pathname === item.path || pathname.startsWith(item.path + '/')
    );
    
    if (activeMenu) {
      setActiveMainMenu(activeMenu.path);
      // 해당 메뉴 자동 확장
      if (!expandedMenus.includes(activeMenu.path)) {
        setExpandedMenus(prev => [...prev, activeMenu.path]);
      }
    } else {
      setActiveMainMenu(null);
    }
  }, [pathname]);
  
  // 메뉴 확장/축소 토글 함수
  const toggleMenu = (menuPath: string) => {
    setExpandedMenus((prev) =>
      prev.includes(menuPath)
        ? prev.filter((path) => path !== menuPath)
        : [...prev, menuPath]
    );
  };
  
  // 메뉴가 현재 경로와 일치하는지 확인하는 함수
  const isActive = (path: string) => {
    return pathname === path || pathname.startsWith(path + '/');
  };
  
  // 모바일 사이드바 및 오버레이 효과를 위한 스타일
  const sidebarClasses = `
    fixed left-0 top-0 h-screen w-[var(--sidebar-width)] bg-white dark:bg-neutral-900 shadow-lg z-50
    transform ${isOpen ? 'translate-x-0' : '-translate-x-full'}
    transition-transform duration-300 ease-in-out
    md:translate-x-0 md:mt-[var(--header-height)] md:z-30
  `;
  
  // 모바일 오버레이 클래스
  const overlayClasses = `
    fixed inset-0 bg-black bg-opacity-50 z-40
    ${isOpen ? 'block' : 'hidden'}
    md:hidden
  `;
  
  // 현재 활성화된 메인 메뉴 찾기
  const currentActiveMenu = activeMainMenu 
    ? mainMenuItems.find(item => item.path === activeMainMenu)
    : null;
  
  return (
    <>
      {/* 모바일 오버레이 */}
      <div className={overlayClasses} onClick={onClose} />
      
      {/* 사이드바 본체 */}
      <aside className={sidebarClasses}>
        {/* 모바일에서만 보이는 헤더 부분 */}
        <div className="flex justify-between items-center p-4 h-[var(--header-height)] border-b border-neutral-200 dark:border-neutral-800 md:hidden">
          <h2 className="text-lg font-bold">메뉴</h2>
          <button 
            className="p-2 text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-100"
            onClick={onClose}
            aria-label="메뉴 닫기"
          >
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="24" 
              height="24" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        {/* 메뉴 항목들 */}
        <nav className="p-4 overflow-y-auto h-[calc(100vh-var(--header-height))]">
          {/* 현재 선택된 메인 메뉴 표시 */}
          {currentActiveMenu ? (
            <div className="mb-6">
              <div className="flex items-center mb-4">
                <h2 className="text-lg font-semibold">{currentActiveMenu.title}</h2>
              </div>
              
              {/* 현재 선택된 메인 메뉴의 하위 메뉴만 표시 */}
              <ul className="space-y-1 ml-2 pl-2 border-l-2 border-primary/30">
                {currentActiveMenu.children?.map((subItem) => (
                  <li key={subItem.path}>
                    <Link
                      href={subItem.path}
                      className={`
                        block px-4 py-2 rounded
                        ${isActive(subItem.path) ? 'text-primary font-medium bg-primary/10' : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800'}
                      `}
                      onClick={() => {
                        // 모바일에서 서브메뉴 클릭시 사이드바 닫기
                        if (window.innerWidth < 768) {
                          onClose();
                        }
                      }}
                    >
                      {subItem.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            // 선택된 메인 메뉴가 없을 경우 (홈페이지 등) 모든 메뉴 표시 
            <ul className="space-y-2">
              {mainMenuItems.map((item) => (
                <li key={item.path} className="mb-1">
                  {/* 주 메뉴 항목 */}
                  <Link
                    href={item.path}
                    className={`
                      flex items-center justify-between w-full px-4 py-2 text-left rounded
                      ${isActive(item.path) ? 'bg-primary/10 text-primary dark:bg-primary/20' : 'hover:bg-neutral-100 dark:hover:bg-neutral-800'}
                    `}
                  >
                    <span>{item.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;