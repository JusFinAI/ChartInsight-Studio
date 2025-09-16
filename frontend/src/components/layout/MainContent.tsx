import React from 'react';

interface MainContentProps {
  children: React.ReactNode;
}

export const MainContent = ({ children }: MainContentProps) => {
  return (
    <main className="
      pt-[var(--header-height)]
      md:pl-[var(--sidebar-width)]
      min-h-screen
      w-full
      bg-neutral-100 dark:bg-neutral-900
      transition-colors duration-200
    ">
      <div className="
        max-w-full
        w-full
        mx-auto 
        p-2 
        bg-white dark:bg-neutral-800
        rounded-lg
        shadow-sm
        my-2
      ">
        {children}
      </div>
    </main>
  );
};

export default MainContent; 