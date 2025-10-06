import dart_fss as dart
import pandas as pd
import gspread

def fill_existing_dart_sheet():
    """
    미리 만들어진 'DART 상장 기업 목록' Google Sheet를 찾아 데이터를 채워 넣습니다.
    """
    try:
        # --- 1. DART API 키 설정 ---
        api_key = input("DART API 인증키를 입력하세요: ")
        if not api_key:
            print("API 키가 입력되지 않았습니다. 프로그램을 종료합니다.")
            return
        dart.set_api_key(api_key=api_key)

        # --- 2. DART에서 상장 기업 목록 필터링 ---
        print("DART에서 전체 기업 목록을 조회합니다...")
        corp_list = dart.get_corp_list()
        
        print("상장된 기업 목록만 필터링합니다...")
        listed_corps = [corp for corp in corp_list if corp.stock_code]

        data = [
            {
                '고유번호': corp.corp_code,
                '법인명': corp.corp_name,
                '종목코드': corp.stock_code,
                '수정일': corp.modify_date
            }
            for corp in listed_corps
        ]
        df = pd.DataFrame(data)
        print(f"총 {len(df)}개의 상장 기업 정보를 조회했습니다.")

        # --- 3. Google Sheets에 연결 ---
        print("Google Sheets에 최신 인증 방식으로 연결합니다...")
        client = gspread.service_account(filename='credentials.json')

        # --- 4. 미리 만들어둔 스프레드시트 열기 및 데이터 업로드 ---
        sheet_title = "DART 상장 기업 목록"
        print(f"'{sheet_title}' 시트를 엽니다...")
        
        # '생성(create)' 대신 '열기(open)'를 사용합니다.
        spreadsheet = client.open(sheet_title)
        worksheet = spreadsheet.get_worksheet(0)
        
        # 기존 데이터를 지우고 새로 업로드
        worksheet.clear()
        
        # gspread-dataframe 라이브러리를 직접 사용하는 방식으로 변경
        from gspread_dataframe import set_with_dataframe
        print("DataFrame을 Google Sheet에 업로드합니다...")
        set_with_dataframe(worksheet, df)
        print("업로드가 완료되었습니다.")
        
        print("\n🎉 모든 작업이 완료되었습니다!")
        print(f"Google Drive에서 '{sheet_title}' 문서를 확인해주세요.")
        print(f"시트 URL: {spreadsheet.url}")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    # 라이브러리 설치 확인을 위한 임포트
    try:
        import gspread_dataframe
    except ImportError:
        print("gspread-dataframe 라이브러리가 설치되지 않았습니다.")
        print("터미널에 'pip install gspread-dataframe'을 입력하여 설치해주세요.")
        exit()
        
    fill_existing_dart_sheet()