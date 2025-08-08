"""필요한 라이브러리 설치 확인 스크립트"""

def check_library(library_name):
    try:
        __import__(library_name)
        print(f"✅ {library_name} 설치됨")
        
        # 버전 확인 (가능한 경우)
        try:
            lib = __import__(library_name)
            if hasattr(lib, '__version__'):
                print(f"   버전: {lib.__version__}")
            elif hasattr(lib, 'version'):
                print(f"   버전: {lib.version}")
        except:
            pass
            
        return True
    except ImportError:
        print(f"❌ {library_name} 설치되지 않음")
        return False

if __name__ == "__main__":
    print("필요한 라이브러리 설치 확인:\n")
    
    libraries = [
        "fastapi",
        "uvicorn",
        "pandas",
        "numpy",
        "yfinance",
        "pydantic",
        "plotly"
    ]
    
    all_installed = True
    for lib in libraries:
        if not check_library(lib):
            all_installed = False
    
    print("\n결과:")
    if all_installed:
        print("✅ 모든 필요한 라이브러리가 설치되어 있습니다.")
        print("   백엔드 서버를 실행할 수 있습니다: uvicorn app.main:app --reload")
    else:
        print("❌ 일부 라이브러리가 설치되지 않았습니다.")
        print("   다음 명령으로 필요한 라이브러리를 설치하세요: pip install -r requirements.txt") 