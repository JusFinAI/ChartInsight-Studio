import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import sys

def setup_korean_font():
    """
    시스템에 설치된 한글 폰트를 자동으로 탐지하고 설정합니다.
    """
    try:
        # 환경 변수 설정 (matplotlib 백엔드 강제 설정)
        import os
        os.environ['MPLBACKEND'] = 'Agg'

        # 1. 직접 폰트 파일 등록 (가장 확실한 방법)
        font_paths_to_try = [
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
            '/usr/share/fonts/truetype/unfonts-core/UnDinaruBold.ttf',
            '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
            '/usr/share/fonts/truetype/baekmuk/batang.ttf',
        ]

        for font_path in font_paths_to_try:
            if os.path.exists(font_path):
                try:
                    fm.fontManager.addfont(font_path)
                    font_name = font_path.split('/')[-1].split('.')[0]
                    plt.rc('font', family=font_name)
                    print(f"✅ 한글 폰트 등록 및 설정 완료: {font_name}")
                    return True
                except Exception as e:
                    print(f"⚠️ 폰트 등록 실패 ({font_path}): {e}")
                    continue

        # 2. 시스템에 이미 설치된 폰트 검색
        try:
            import subprocess
            result = subprocess.run(['fc-list', ':lang=ko'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                font_lines = result.stdout.strip().split('\n')
                korean_fonts = [line.split(':')[0] for line in font_lines if line.strip()]
                if korean_fonts:
                    font_path = korean_fonts[0]
                    font_name = font_path.split('/')[-1].split('.')[0]
                    plt.rc('font', family=font_name)
                    print(f"✅ 시스템 한글 폰트 설정 완료: {font_name}")
                    return True
        except:
            pass

        # 3. matplotlib에서 폰트 직접 검색
        font_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
        korean_fonts = [f for f in font_list if any(keyword in f.lower() for keyword in [
            'nanum', 'noto', 'malgun', 'unfonts', 'baekmuk', 'gulim', 'batang', 'dotum',
            'han', 'un', 'baekmuk', 'sans', 'serif', 'square'
        ])]

        if korean_fonts:
            font_name = korean_fonts[0].split('/')[-1].split('.')[0]
            plt.rc('font', family=font_name)
            print(f"✅ 검색된 한글 폰트 설정 완료: {font_name}")
            return True

        # 4. 최후의 대안: 영문 폰트로 설정
        plt.rc('font', family='DejaVu Sans')
        print("ℹ️ 한글 폰트를 찾을 수 없어 영문 폰트로 대체합니다.")
        return False

    except Exception as e:
        print(f"⚠️ 폰트 설정 중 오류 발생: {e}")
        plt.rc('font', family='DejaVu Sans')
        return False

def visualize_financial_analysis(file_path: str):
    """
    EPS 분석 결과 CSV 파일을 읽어 3종의 시각화 차트를 생성하고 이미지 파일로 저장합니다.

    Args:
        file_path (str): 분석할 CSV 파일의 전체 경로.
    """
    try:
        # --- 한글 폰트 설정 ---
        font_success = setup_korean_font()
        plt.rcParams['axes.unicode_minus'] = False

        # --- 1. 데이터 로드 ---
        print(f"'{file_path}' 파일을 로드합니다...")
        df = pd.read_csv(file_path)
        print("✅ 파일 로드 성공!")

        # 스크립트 디렉토리 설정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 그래프 파일 저장 디렉토리: {script_dir}")

        # --- 2. 시각화 1: 재무 등급 분포 ---
        grade_counts = df['financial_grade'].value_counts().sort_index()
        plt.figure(figsize=(8, 6))
        bars = plt.bar(grade_counts.index, grade_counts.values, color=['#FF6B6B', '#4ECDC4'])
        plt.title(f'재무 등급 분포 (총 {len(df)}개 기업)', fontsize=16, fontweight='bold')
        plt.ylabel('기업 수', fontsize=12)
        plt.xticks(fontsize=12)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center', fontsize=12, fontweight='bold')
        plt.savefig(f'{script_dir}/grade_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/grade_distribution.png' 생성 완료.")

        # --- 3. 시각화 2: 성장률 분포 히스토그램 ---
        yoy_growth_clipped = df['eps_growth_yoy'].clip(-100, 300)
        annual_growth_clipped = df['eps_annual_growth_avg_3y'].clip(-100, 300)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        ax1.hist(yoy_growth_clipped, bins=40, color='#4ECDC4', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax1.set_title('최근 분기 EPS 성장률(YoY) 분포', fontsize=15, fontweight='bold')
        ax1.set_xlabel('성장률 (%)', fontsize=12)
        ax1.set_ylabel('기업 수', fontsize=12)
        ax1.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax1.legend(fontsize=11)
        ax1.grid(True, linestyle='--', alpha=0.3)

        ax2.hist(annual_growth_clipped, bins=40, color='#FF6B6B', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.set_title('3년 연평균 EPS 성장률 분포', fontsize=15, fontweight='bold')
        ax2.set_xlabel('성장률 (%)', fontsize=12)
        ax2.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax2.legend(fontsize=11)
        ax2.grid(True, linestyle='--', alpha=0.3)

        plt.tight_layout()
        plt.savefig(f'{script_dir}/growth_histograms.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/growth_histograms.png' 생성 완료.")

        # --- 4. 시각화 3: 성장성 사분면 분석 ---
        strict_df = df[df['financial_grade'] == 'Strict']
        loose_df = df[df['financial_grade'] == 'Loose']

        # 데이터가 없으면 건너뜀
        if len(strict_df) == 0 and len(loose_df) == 0:
            print("⚠️ 시각화할 데이터가 없습니다.")
            return

        plt.figure(figsize=(12, 9))

        # Loose 등급 점들
        if len(loose_df) > 0:
            plt.scatter(loose_df['eps_annual_growth_avg_3y'], loose_df['eps_growth_yoy'],
                        alpha=0.6, s=80, label=f'Loose 등급 ({len(loose_df)}개)',
                        color='#4ECDC4', edgecolor='black', linewidth=0.8)

        # Strict 등급 점들 (더 크게 강조)
        if len(strict_df) > 0:
            plt.scatter(strict_df['eps_annual_growth_avg_3y'], strict_df['eps_growth_yoy'],
                        s=200, alpha=0.9, label=f'Strict 등급 ({len(strict_df)}개)',
                        color='#FF6B6B', edgecolor='black', linewidth=2)

        # 기준선들
        plt.axhline(25, color='red', linestyle='-', linewidth=2, alpha=0.8, label='Strict 기준 (25%)')
        plt.axvline(25, color='red', linestyle='-', linewidth=2, alpha=0.8)

        # 사분면 라벨
        plt.text(175, 175, 'I. 지속적 고성장', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(-35, 175, 'II. 최근 실적 급증', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(-35, -50, 'III. 성장 둔화/역성장', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(175, -50, 'IV. 과거 고성장/최근 부진', ha='center', va='center', fontsize=14, fontweight='bold')

        plt.title('EPS 성장성 사분면 분석', fontsize=18, fontweight='bold')
        plt.xlabel('3년 연평균 EPS 성장률 (%)', fontsize=14)
        plt.ylabel('최근 분기 EPS 성장률 (YoY, %)', fontsize=14)
        plt.xlim(-100, 300)
        plt.ylim(-100, 300)
        plt.legend(fontsize=12, loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.4)
        plt.savefig(f'{script_dir}/growth_quadrant_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/growth_quadrant_analysis.png' 생성 완료.")
        
    except FileNotFoundError:
        print(f"❌ 오류: '{file_path}' 파일을 찾을 수 없습니다. 파일 경로를 다시 확인해주세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def find_csv_file():
    """
    현재 디렉토리에서 최신 dart_financial_analysis_results CSV 파일을 자동으로 찾습니다.
    """
    import glob

    # 현재 작업 디렉토리 확인
    current_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"🔍 현재 작업 디렉토리: {current_dir}")
    print(f"🔍 스크립트 디렉토리: {script_dir}")

    # 다양한 경로에서 CSV 파일들 찾기
    search_paths = [
        current_dir,      # 현재 작업 디렉토리
        script_dir,       # 스크립트가 위치한 디렉토리
        os.path.join(script_dir, ".."),  # 상위 디렉토리
    ]

    all_csv_files = []
    for search_path in search_paths:
        pattern = os.path.join(search_path, "dart_financial_analysis_results_*.csv")
        files = glob.glob(pattern)
        all_csv_files.extend(files)
        print(f"🔍 경로 '{search_path}'에서 찾은 파일들: {files}")

    if all_csv_files:
        # 가장 최근 파일 선택
        latest_file = max(all_csv_files, key=os.path.getctime)
        print(f"✅ 최신 CSV 파일 발견: {latest_file}")
        return latest_file
    else:
        print("❌ CSV 파일을 찾을 수 없습니다.")
        print("🔍 다음 위치들을 확인해보세요:")
        print("  - 현재 디렉토리에 dart_financial_analysis_results_YYYYMMDD.csv 파일이 있는지")
        print("  - test_dartapi_financials_all.py가 성공적으로 실행되었는지")
        print("  - 파일명이 'dart_financial_analysis_results_'로 시작하는지 확인")
        return None

if __name__ == '__main__':
    print("="*80)
    print("🚀 EPS 분석 결과 시각화 시작")
    print("="*80)

    # 파일 경로 자동 탐지 또는 수동 설정
    csv_file_path = find_csv_file()

    if not csv_file_path:
        print("\n📝 파일 경로를 수동으로 설정하려면 아래 주석을 해제하고 경로를 입력하세요:")
        print("# csv_file_path = '/path/to/your/dart_financial_analysis_results_YYYYMMDD.csv'")
        print("# visualize_financial_analysis(csv_file_path)")
        print("\n또는 최신 파일이 생성될 때까지 기다려주세요.")
    else:
        visualize_financial_analysis(csv_file_path)

    print("\n" + "="*80)
    print("✅ 시각화 완료! 생성된 파일들:")
    print(f"  • {script_dir}/grade_distribution.png")
    print(f"  • {script_dir}/growth_histograms.png")
    print(f"  • {script_dir}/growth_quadrant_analysis.png")
    print("="*80)