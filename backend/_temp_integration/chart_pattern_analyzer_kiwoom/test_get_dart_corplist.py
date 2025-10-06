import dart_fss as dart
import pandas as pd
import os
import re
from datetime import datetime

# DART API 키 설정 (고정값 사용)
DART_API_KEY = "2cae1c66f8f4557528070d84877c183c0cb435cf"

def is_valid_stock_code(stock_code):
    """
    정상적인 종목코드인지 검증합니다.
    - 6자리 숫자만 유효
    - 숫자+문자 혼합(SPAC 등)은 제외
    """
    if not stock_code:
        return False

    str_code = str(stock_code)
    # 정확히 6자리 숫자인지 확인
    return str_code.isdigit() and len(str_code) == 6

def format_stock_code(stock_code):
    """
    종목코드를 6자리 숫자로 변환합니다.
    예: '7490' -> '007490'

    이상한 코드(숫자+문자 혼합)의 경우 제거합니다.
    """
    if not stock_code:
        return ''

    str_stock_code = str(stock_code)

    # 정확히 6자리 숫자인지 확인
    if str_stock_code.isdigit() and len(str_stock_code) == 6:
        return str_stock_code

    # 숫자 부분만 추출 (정규식 사용) - 4자리 숫자 등 변환
    numbers = re.findall(r'\d+', str_stock_code)

    if not numbers:
        return ''

    # 첫 번째 숫자 그룹을 사용
    number_str = numbers[0]

    # 6자리로 맞춤 (숫자만 있는 경우)
    try:
        formatted_code = f"{int(number_str):06d}"
        # 변환 후 다시 검증
        if formatted_code.isdigit() and len(formatted_code) == 6:
            return formatted_code
        else:
            return ''
    except ValueError:
        return ''

def get_dart_corp_list_to_csv():
    """
    DART API에서 상장 기업 목록을 가져와서 CSV 파일로 저장합니다.
    """
    try:
        # --- 1. DART API 키 설정 ---
        print("DART API 키를 설정합니다...")
        dart.set_api_key(api_key=DART_API_KEY)
        print("✅ DART API 키 설정 완료")

        # --- 2. DART에서 상장 기업 목록 필터링 ---
        print("DART에서 전체 기업 목록을 조회합니다...")
        corp_list = dart.get_corp_list()

        print("상장된 기업 목록만 필터링합니다...")
        listed_corps = [corp for corp in corp_list if corp.stock_code]

        print(f"✅ 총 {len(listed_corps)}개의 상장 기업을 조회했습니다.")

        # --- 3. 데이터 가공 ---
        print("기업 데이터를 가공합니다...")
        valid_data = []
        filtered_count = 0

        for corp in listed_corps:
            formatted_code = format_stock_code(corp.stock_code)

            if formatted_code:  # 유효한 코드만 포함
                valid_data.append({
                    '고유번호': corp.corp_code,
                    '법인명': corp.corp_name,
                    '종목코드': formatted_code,
                    '수정일': corp.modify_date
                })
            else:
                filtered_count += 1

        print(f"✅ 유효한 기업: {len(valid_data)}개")
        if filtered_count > 0:
            print(f"⚠️  이상한 코드 제외: {filtered_count}개")

        data = valid_data

        df = pd.DataFrame(data)
        print(f"✅ 총 {len(df)}개의 상장 기업 정보를 조회했습니다.")

        # --- 4. CSV 파일로 저장 ---
        print("CSV 파일로 저장합니다...")

        # 저장할 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dart_data')
        os.makedirs(output_dir, exist_ok=True)

        # 파일명에 타임스탬프 추가
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'dart_corp_list_{timestamp}.csv'
        csv_path = os.path.join(output_dir, csv_filename)

        # CSV 파일로 저장
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✅ CSV 파일 저장 완료: {csv_path}")

        # 저장된 파일 정보 출력
        print("📋 저장된 파일 정보:")
        print(f"   • 파일명: {csv_filename}")
        print(f"   • 경로: {csv_path}")
        print(f"   • 기업 수: {len(df)}개")
        print(f"   • 컬럼: {', '.join(df.columns.tolist())}")

        print("🎉 모든 작업이 완료되었습니다!")
        print(f"파일이 '{output_dir}' 폴더에 저장되었습니다.")

        return csv_path

    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")
        return None

if __name__ == "__main__":
    print("🚀 DART 상장 기업 목록 수집 프로그램 시작")
    print("="*60)

    csv_path = get_dart_corp_list_to_csv()

    print("\n" + "="*60)
    if csv_path:
        print("✅ 프로그램이 성공적으로 완료되었습니다!")
    else:
        print("❌ 프로그램 실행 중 오류가 발생했습니다.")
        print("\n🔧 해결 방안:")
        print("1. 인터넷 연결을 확인하세요.")
        print("2. DART API 키가 유효한지 확인하세요.")
        print("3. 방화벽이나 네트워크 설정을 확인하세요.")