'use client';

import './globals.css';
import { useState } from 'react';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';
import MainContent from '@/components/layout/MainContent';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  return (
    <html lang="ko">
      <head>
        <title>ChartInsight Studio</title>
        <meta name="description" content="트레이딩 및 차트 분석 플랫폼" />
      </head>
      <body>
        <div className="flex min-h-screen">
          <Header onMenuToggle={toggleSidebar} />
          <Sidebar isOpen={isSidebarOpen} onClose={closeSidebar} />
          <MainContent>
            {children}
          </MainContent>
        </div>
      </body>
    </html>
  );
}
