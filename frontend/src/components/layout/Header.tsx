'use client';

import { useState } from 'react';
import Link from 'next/link';
import ThemeToggle from '@/components/ui/ThemeToggle';

interface HeaderProps {
  onMenuToggle: () => void;
}

export const Header = ({ onMenuToggle }: HeaderProps) => {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  
  // 임시 로그인 상태 (나중에 실제 인증 상태로 대체)
  const isLoggedIn = false;
  
  return (
    <header className="fixed top-0 left-0 right-0 h-[var(--header-height)] bg-neutral-800 text-neutral-100 shadow-header z-50 md:h-[var(--header-height)]">
      <div className="h-full flex items-center justify-between px-4 md:px-6">
        {/* 로고 및 모바일 메뉴 버튼 */}
        <div className="flex items-center">
          {/* 모바일 햄버거 메뉴 */}
          <button 
            className="mr-3 p-2 md:hidden" 
            onClick={onMenuToggle}
            aria-label="메뉴 열기"
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
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          
          {/* 로고 */}
          <Link href="/" className="text-xl font-bold text-white">
            ChartInsight Studio
          </Link>
        </div>
        
        {/* 데스크톱 메인 메뉴 (모바일에서는 숨김) */}
        <nav className="hidden md:flex items-center ml-10 space-x-6">
          <Link href="/trading-lab" className="text-neutral-100 hover:text-white">
            Trading Lab
          </Link>
          <Link href="/pattern-studio" className="text-neutral-100 hover:text-white">
            Pattern Studio
          </Link>
          <Link href="/knowledge-hub" className="text-neutral-100 hover:text-white">
            Knowledge Hub
          </Link>
          <Link href="/community" className="text-neutral-100 hover:text-white">
            Community
          </Link>
        </nav>
        
        {/* 오른쪽 영역: 검색, 테마 토글, 로그인 */}
        <div className="flex items-center space-x-4">
          {/* 검색 버튼 */}
          <button 
            className="p-2 text-neutral-300 hover:text-white"
            aria-label="검색"
          >
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              width="20" 
              height="20" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </button>
          
          {/* 테마 토글 */}
          <ThemeToggle />
          
          {/* 로그인/회원가입 또는 사용자 메뉴 */}
          {isLoggedIn ? (
            <div className="relative">
              <button 
                className="flex items-center space-x-1 p-2 rounded-full hover:bg-neutral-700"
                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                aria-expanded={isUserMenuOpen}
                aria-haspopup="true"
              >
                <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white">
                  사용자
                </div>
              </button>
              
              {/* 드롭다운 메뉴 */}
              {isUserMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-neutral-800 rounded-md shadow-lg py-1 z-50">
                  <Link href="/profile" className="block px-4 py-2 text-sm text-neutral-800 dark:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-700">
                    프로필
                  </Link>
                  <Link href="/settings" className="block px-4 py-2 text-sm text-neutral-800 dark:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-700">
                    설정
                  </Link>
                  <button className="w-full text-left block px-4 py-2 text-sm text-neutral-800 dark:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-700">
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link 
              href="/login" 
              className="bg-primary hover:bg-primary/90 text-white py-2 px-4 rounded text-sm"
            >
              로그인
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header; 