/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 요구사항에 명시된 색상 팔레트
        primary: '#3B82F6', // 파란색 계열
        secondary: '#10B981', // 녹색 계열 (대체 주 테마색)
        warning: '#F97316', // 경고/중요 정보
        special: '#8B5CF6', // 특별 기능
        neutral: {
          900: '#0F172A',
          800: '#1E293B',
          600: '#64748B',
          300: '#CBD5E1', 
          100: '#F1F5F9',
          50: '#FFFFFF',
        }
      },
      spacing: {
        sidebar: '240px',
        header: '64px',
        'header-mobile': '56px',
      },
      fontFamily: {
        sans: ['Inter', 'Roboto', 'sans-serif'],
      },
      fontSize: {
        'title': ['1.5rem', '2rem'], // 24-32px
        'body': ['1rem', '1.5rem'],  // 16px
        'small': ['0.875rem', '1.25rem'], // 14px
      },
      boxShadow: {
        'header': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      },
    },
    screens: {
      xs: '0px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
  },
  plugins: [],
} 