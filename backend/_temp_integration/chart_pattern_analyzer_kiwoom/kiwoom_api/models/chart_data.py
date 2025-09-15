import pandas as pd
import os
from ..core.config import config
# from src.utils.common_helpers import ensure_directory_exists  # 임시 주석 처리


class ChartData:
    """주식 차트 데이터 모델"""
    
    def __init__(self, chart_type, output_dir=None):
        """
        ChartData 객체 초기화
        
        Args:
            chart_type (str): 차트 유형 ('daily', 'minute', 'weekly')
            output_dir (str, optional): CSV 파일 저장 기본 경로. 기본값은 None.
        """
        self.chart_type = chart_type
        self.data = []
        self.preprocessing_required = False
        self.output_dir = output_dir
    
    def append(self, items):
        """
        차트 데이터 항목 추가
        
        Args:
            items (list): 차트 데이터 항목 리스트
        """
        if items:
            self.data.extend(items)
    
    def to_dataframe(self):
        """
        차트 데이터를 pandas DataFrame으로 변환
        
        Returns:
            DataFrame: 차트 데이터 DataFrame
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[DEBUG] to_dataframe 호출됨! chart_type={self.chart_type}")
        logger.info(f"[DEBUG] self.data 개수: {len(self.data) if self.data else 0}")
        logger.info(f"[DEBUG] preprocessing_required: {self.preprocessing_required}")
        
        if not self.data:
            logger.info("[DEBUG] 데이터가 없어서 빈 DataFrame 반환")
            return pd.DataFrame()
        
        # 데이터프레임 생성
        df = pd.DataFrame(self.data)
        logger.info(f"[DEBUG] DataFrame 생성 완료: {len(df)}행, 컬럼={list(df.columns)}")
        
        # 전처리가 필요한 경우 (일봉 데이터)
        if self.preprocessing_required:
            logger.info("[DEBUG] 전처리 실행 중...")
            return self._preprocess_data(df)
        else:
            logger.info("[DEBUG] 전처리 없이 원본 DataFrame 반환")
        
        return df
    
    def save_csv(self, stock_code, base_date=None):
        """
        차트 데이터를 CSV 파일로 저장
        
        Args:
            stock_code (str): 종목 코드
            base_date (str, optional): 기준 일자(YYYYMMDD)
            
        Returns:
            str: 저장된 CSV 파일 경로
        """
        if not self.data:
            print("저장할 데이터가 없습니다.")
            return None
        
        # 디렉토리 준비
        if self.output_dir:
            current_output_dir = self.output_dir
        else:
            current_output_dir = os.path.join('output', self.chart_type)
        
        os.makedirs(current_output_dir, exist_ok=True)  # ensure_directory_exists 대체
        
        # 데이터프레임 변환
        df = self.to_dataframe()
        
        # 파일 이름 구성
        period_str = ""
        if isinstance(df.index, pd.DatetimeIndex):
            if not df.empty:
                start_date_dt = df.index.min()
                end_date_dt = df.index.max()
                start_date = start_date_dt.strftime('%Y%m%d')
                end_date = end_date_dt.strftime('%Y%m%d')
                period_str = f"{start_date}_{end_date}"
        elif 'Date' in df.columns:
            if not df.empty and pd.api.types.is_datetime64_any_dtype(df['Date']):
                start_date_dt = df['Date'].min()
                end_date_dt = df['Date'].max()
                start_date = start_date_dt.strftime('%Y%m%d')
                end_date = end_date_dt.strftime('%Y%m%d')
                period_str = f"{start_date}_{end_date}"
            elif not df.empty:
                try:
                    # df_temp_sorted = df.sort_values('Date')  # 정렬 제거
                    # start_date = df_temp_sorted['Date'].iloc[0]
                    # end_date = df_temp_sorted['Date'].iloc[-1]
                    
                    # 정렬 없이 min/max로 날짜 범위 구하기
                    start_date = df['Date'].min()
                    end_date = df['Date'].max()
                    
                    if len(start_date) == 8 and start_date.isdigit() and len(end_date) == 8 and end_date.isdigit():
                        period_str = f"{start_date}_{end_date}"
                    else:
                        print(f"경고: 파일명 생성을 위한 Date 컬럼('{start_date}', '{end_date}')이 YYYYMMDD 형식이 아닙니다.")
                except Exception as e:
                    print(f"경고: 파일명 생성을 위한 Date 컬럼 처리 중 오류: {e}")        
        elif base_date:
            period_str = base_date
        
        # 종목 코드 추가
        if 'symbol' not in df.columns:
            df['symbol'] = stock_code
        
        # 파일명 구성
        filename_prefix = ""
        if self.chart_type == 'minute':
            filename_prefix = "min_"
        elif self.chart_type == 'daily':
            filename_prefix = 'day_'
        elif self.chart_type == 'weekly':
            filename_prefix = 'week_'
        else:
            filename_prefix = f"{self.chart_type}_"

        filename = f"{filename_prefix}{stock_code}"
        if period_str:
            filename += f"_{period_str}"
        filename += ".csv"
        
        filepath = os.path.join(current_output_dir, filename)
        
        # 원본 데이터 저장 (전처리 전 데이터)
        original_df = pd.DataFrame(self.data)
        original_filepath = os.path.join(current_output_dir, f"{filename.replace('.csv', '_original.csv')}")
        original_df.to_csv(original_filepath, index=False, encoding='utf-8-sig')
        print(f"원본 데이터가 저장되었습니다: {original_filepath}")
        
        # 전처리된 데이터 저장
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"전처리된 데이터가 저장되었습니다: {filepath}")
        
        return filepath
    
    def _preprocess_data(self, df):
        """
        차트 데이터 전처리
        
        Args:
            df (DataFrame): 차트 데이터 DataFrame
            
        Returns:
            DataFrame: 전처리된 차트 데이터 DataFrame
        """
        print(f"[DEBUG] _preprocess_data 함수 호출됨! chart_type={self.chart_type}")
        print(f"[DEBUG] 입력 DataFrame 정보: {len(df)}행, 컬럼={list(df.columns)}")
        
        if df.empty:
            print("[DEBUG] 빈 DataFrame이므로 그대로 반환")
            return df
        
        # 1. 데이터 복사
        df_processed = df.copy()
        
        # 컬럼 목록 확인
        print(f"원본 데이터 컬럼: {', '.join(df_processed.columns)}")
        print(f"[DEBUG] DataFrame 첫 3행:\n{df_processed.head(3)}")
        
        # 2. API 컬럼명을 표준 OHLCV 컬럼명으로 매핑
        column_mapping = {
            # 일봉/분봉/주봉 공통 매핑
            'dt': 'date',             # 거래일자
            'open_pric': 'Open',      # 시가
            'high_pric': 'High',      # 고가
            'low_pric': 'Low',        # 저가
            'cur_prc': 'Close',       # 종가/현재가
            'trde_qty': 'Volume',     # 거래량
            'trde_prica': 'Value',    # 거래대금
            
            # 기존 매핑 (참고용)
            'stck_bsop_date': 'date',  # 거래일자
            'stck_oprc': 'Open',       # 시가
            'stck_hgpr': 'High',       # 고가
            'stck_lwpr': 'Low',        # 저가
            'stck_clpr': 'Close',      # 종가
            'acml_vol': 'Volume',      # 거래량
            'acml_tr_pbmn': 'Value',   # 거래대금
            
            # 분봉 데이터 특화 필드 매핑
            'stck_cntg_hour': 'time',  # 체결시간
            'cntg_date': 'date',       # 체결일자
            'cntg_time': 'time',       # 체결시간
            'cntg_price': 'Close',     # 체결가격
            
            # ka10080 API 응답 필드
            'opnprc': 'Open',         # 시가
            'hgprc': 'High',          # 고가
            'lwprc': 'Low',           # 저가
            'clsprc': 'Close',        # 종가
            'acmvol': 'Volume',       # 거래량
            'acmtrpbmn': 'Value',     # 거래대금
            
            # 주봉 데이터 특화 필드
            'upd_rt': 'Change_Rate',  # 등락률
            'pred_close_pric': 'Prev_Close',  # 전일종가
        }
        
        # cntr_tm 필드 처리 (timestamp 형식)
        if 'cntr_tm' in df_processed.columns:
            print("cntr_tm 필드 발견, timestamp 형식 처리")
            # 날짜/시간 분리
            df_processed['date'] = df_processed['cntr_tm'].str[:8]
            df_processed['time'] = df_processed['cntr_tm'].str[8:14]
        
        # 필요한 컬럼만 선택하여 이름 변경
        for old_col, new_col in column_mapping.items():
            if old_col in df_processed.columns:
                df_processed[new_col] = df_processed[old_col]
                print(f"컬럼 매핑: {old_col} -> {new_col}")
        
        # 필수 컬럼만 선택
        required_columns = ['date', 'Open', 'High', 'Low', 'Close', 'Volume']
        available_columns = [col for col in required_columns if col in df_processed.columns]
        
        if len(available_columns) < 5:  # 최소 OHLC가 있어야 함
            missing_cols = set(required_columns[:5]) - set(available_columns)
            print(f"경고: 필수 컬럼이 부족합니다. 누락된 컬럼: {', '.join(missing_cols)}")
            
            # 빠진 컬럼이 있는지 확인하고 데이터 추정 시도
            if 'Open' not in df_processed.columns and 'Close' in df_processed.columns:
                df_processed['Open'] = df_processed['Close']
                print("시가(Open) 데이터가 없어 종가(Close)로 대체합니다.")
            
            if 'High' not in df_processed.columns and 'Close' in df_processed.columns:
                df_processed['High'] = df_processed['Close']
                print("고가(High) 데이터가 없어 종가(Close)로 대체합니다.")
                
            if 'Low' not in df_processed.columns and 'Close' in df_processed.columns:
                df_processed['Low'] = df_processed['Close']
                print("저가(Low) 데이터가 없어 종가(Close)로 대체합니다.")
        
        # 'Volume' 컬럼이 없는 경우 0으로 추가
        if 'Volume' not in df_processed.columns:
            df_processed['Volume'] = 0
            print("거래량(Volume) 데이터가 없어 0으로 설정합니다.")
        
        # 'Adj Close' 추가 (수정주가 - 키움에서는 이미 수정주가 적용됨)
        if 'Adj Close' not in df_processed.columns and 'Close' in df_processed.columns:
            df_processed['Adj Close'] = df_processed['Close']
        
        # 3. 데이터 타입 변환
        # 숫자형 컬럼 변환
        numeric_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Change_Rate']
        for col in numeric_columns:
            if col in df_processed.columns:
                # 문자열 값을 숫자로 변환 (콤마 제거)
                if df_processed[col].dtype == 'object':
                    df_processed[col] = df_processed[col].astype(str).str.replace(',', '')
                    # '+', '-' 기호 처리 (Change_Rate 컬럼 등)
                    if col == 'Change_Rate':
                        # %와 +, - 기호 처리
                        df_processed[col] = df_processed[col].str.replace('%', '')
                    else:
                        # 다른 컬럼의 경우 +, - 제거
                        df_processed[col] = df_processed[col].str.replace('+', '').str.replace('-', '')
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
        
        # 4. 날짜 및 시간 형식 처리
        # 분봉 데이터인 경우 (시간 필드가 있음)
        if self.chart_type == 'minute' and 'time' in df_processed.columns:
            print("분봉 데이터를 처리합니다: datetime 인덱스 생성")
            
            # 날짜와 시간 필드가 모두 있는 경우 합쳐서 datetime 인덱스 생성
            if 'date' in df_processed.columns:
                # 디버깅: 원본 분봉 날짜/시간 데이터 확인
                print(f"원본 날짜 데이터 샘플: {df_processed['date'].head().tolist()}")
                print(f"원본 시간 데이터 샘플: {df_processed['time'].head().tolist()}")
                print(f"날짜 데이터 타입: {df_processed['date'].dtype}")
                print(f"시간 데이터 타입: {df_processed['time'].dtype}")
                
                # 날짜+시간 결합 필드 생성
                df_processed['datetime'] = df_processed['date'].astype(str) + df_processed['time'].astype(str)
                print(f"결합된 datetime 샘플: {df_processed['datetime'].head().tolist()}")
                
                # datetime 객체로 변환 (시간 형식 유추)
                try:
                    print(f"🔍 datetime 변환 시도: format='%Y%m%d%H%M%S'")
                    df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='%Y%m%d%H%M%S', errors='coerce')
                    
                    # NaT 개수 확인
                    nat_count = df_processed['datetime'].isna().sum()
                    print(f"🔍 datetime 변환 결과: {len(df_processed) - nat_count}/{len(df_processed)} 성공, NaT={nat_count}개")
                    if nat_count > 0:
                        print(f"🔍 NaT 발생 샘플: {df_processed[df_processed['datetime'].isna()]['datetime'].head().tolist()}")
                    
                    # 한국 시간(KST)로 타임존 설정
                    df_processed['datetime'] = df_processed['datetime'].dt.tz_localize('Asia/Seoul')
                    print("한국 시간(KST) 타임존 설정 완료")
                    print(f"🔍 최종 datetime 샘플: {df_processed['datetime'].head().tolist()}")
                    
                except Exception as e:
                    print(f"날짜+시간 변환 오류: {e}, 다른 형식 시도")
                    try:
                        # 다른 형식 시도
                        print(f"🔍 datetime 변환 시도 (2차): format='%Y%m%d%H%M'")
                        df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='%Y%m%d%H%M', errors='coerce')
                        
                        # NaT 개수 확인
                        nat_count = df_processed['datetime'].isna().sum()
                        print(f"🔍 datetime 변환 결과 (2차): {len(df_processed) - nat_count}/{len(df_processed)} 성공, NaT={nat_count}개")
                        
                        # 한국 시간(KST)로 타임존 설정
                        df_processed['datetime'] = df_processed['datetime'].dt.tz_localize('Asia/Seoul')
                        print("한국 시간(KST) 타임존 설정 완료 (HHMM 형식)")
                        print(f"🔍 최종 datetime 샘플 (2차): {df_processed['datetime'].head().tolist()}")
                        
                    except Exception as e2:
                        print(f"날짜+시간 변환 두 번째 시도 오류: {e2}")
                        print(f"🔍 원본 datetime 문자열 샘플: {df_processed['datetime'].head().tolist()}")
                
                # 인덱스로 설정
                df_processed = df_processed.set_index('datetime')
                
                print(f"datetime 인덱스 생성 완료: {len(df_processed)}행")
            else:
                print("경고: 분봉 데이터에 날짜(date) 필드가 없습니다.")
        # 일봉/주봉 데이터인 경우 (날짜 필드만 있음)
        elif 'date' in df_processed.columns:
            # 디버깅: 원본 날짜 데이터 확인
            print(f"🔍 일봉 원본 날짜 데이터 샘플: {df_processed['date'].head().tolist()}")
            print(f"🔍 일봉 날짜 데이터 타입: {df_processed['date'].dtype}")
            print(f"🔍 일봉 데이터 총 행수: {len(df_processed)}")
            
            # 날짜 형식 변환 (여러 형식 시도)
            try:
                # 1차 시도: YYYYMMDD 형식
                print(f"🔍 일봉 날짜 변환 시도 (1차): format='%Y%m%d'")
                df_processed['date'] = pd.to_datetime(df_processed['date'], format='%Y%m%d', errors='coerce')
                
                # 변환 후 확인
                print(f"🔍 일봉 변환 후 날짜 샘플: {df_processed['date'].head().tolist()}")
                nan_count = df_processed['date'].isna().sum()
                print(f"🔍 일봉 날짜 변환 결과: {len(df_processed) - nan_count}/{len(df_processed)} 성공, NaT={nan_count}개")
                
                if nan_count > 0:
                    print(f"⚠️ 일봉 날짜 변환 실패 샘플: {df_processed[df_processed['date'].isna()]['date'].head().tolist()}")
                    
                    # 2차 시도: 다른 형식들
                    print(f"🔍 일봉 날짜 변환 시도 (2차): infer format")
                    df_processed['date'] = pd.to_datetime(df_processed['date'], infer_datetime_format=True, errors='coerce')
                    
                    nan_count_2 = df_processed['date'].isna().sum()
                    print(f"🔍 일봉 날짜 변환 결과 (2차): {len(df_processed) - nan_count_2}/{len(df_processed)} 성공, NaT={nan_count_2}개")
                    
            except Exception as e:
                print(f"❌ 일봉 날짜 변환 오류: {e}")
                # 마지막 시도: 문자열을 직접 변환
                try:
                    print(f"🔍 일봉 날짜 변환 시도 (최종): 문자열 직접 변환")
                    df_processed['date'] = pd.to_datetime(df_processed['date'].astype(str), errors='coerce')
                    final_nan_count = df_processed['date'].isna().sum()
                    print(f"🔍 일봉 날짜 변환 결과 (최종): {len(df_processed) - final_nan_count}/{len(df_processed)} 성공")
                except Exception as e2:
                    print(f"❌ 일봉 날짜 변환 최종 실패: {e2}")
            
            # 인덱스로 설정
            print(f"🔍 일봉 인덱스 설정 전 날짜 샘플: {df_processed['date'].head().tolist()}")
            df_processed = df_processed.set_index('date')
            print(f"🔍 일봉 인덱스 설정 후 인덱스 샘플: {df_processed.index[:5].tolist()}")
            
            # 인덱스 정렬
            # df_processed = df_processed.sort_index()  # 정렬 제거 - DB 삽입 순서 유지
            
            # 주봉 데이터인 경우 추가 처리
            if self.chart_type == 'weekly':
                print("주봉 데이터를 처리합니다.")
                # 주봉 인덱스 처리 - 주의 마지막 날(금요일)이 아닌 경우 조정 
                # (보통 금요일 종가 기준이지만, 휴장 등으로 다른 날짜일 수 있음)
                try:
                    df_processed.index = df_processed.index.to_period('W').to_timestamp('W')
                    print("주봉 인덱스로 변환 완료")
                except Exception as e:
                    print(f"주봉 인덱스 변환 오류: {e}")
        
        # 5. 필요한 컬럼만 선택 (OHLCV 표준 컬럼)
        standard_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Change_Rate']
        available_standard_columns = [col for col in standard_columns if col in df_processed.columns]
        
        if available_standard_columns:
            # 표준 컬럼만 선택하여 새로운 데이터프레임 생성
            final_df = df_processed[available_standard_columns].copy()
            print(f"표준 OHLCV 컬럼만 선택했습니다: {', '.join(final_df.columns)}")
        else:
            final_df = df_processed
            print("표준 OHLCV 컬럼을 찾을 수 없어 모든 컬럼을 유지합니다.")
        
        # 6. 결측값 처리
        price_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
        available_price_columns = [col for col in price_columns if col in final_df.columns]
        
        if available_price_columns:
            # 앞, 뒤 값으로 결측치 채우기
            final_df[available_price_columns] = final_df[available_price_columns].ffill().bfill()
        
        # 7. 거래량 데이터 처리
        if 'Volume' in final_df.columns:
            # NaN 값을 0으로 대체
            final_df['Volume'] = final_df['Volume'].fillna(0)
            
            # 모든 거래량이 0인지 확인
            if (final_df['Volume'] == 0).all():
                print("경고: 모든 거래량 데이터가 0입니다.")
            else:
                # 0값 거래량 처리 (중간값으로 대체)
                zero_volume_mask = final_df['Volume'] == 0
                zero_volume_count = zero_volume_mask.sum()
                
                if zero_volume_count > 0 and zero_volume_count < len(final_df):
                    # 0이 아닌 값들의 중간값 계산
                    median_volume = final_df.loc[~zero_volume_mask, 'Volume'].median()
                    if not pd.isna(median_volume):
                        print(f"거래량 0값 {zero_volume_count}개를 중간값({median_volume:.0f})으로 대체합니다.")
                        final_df.loc[zero_volume_mask, 'Volume'] = median_volume
        
        # 8. 데이터 반올림 (정수형으로 변환 준비)
        for col in ['Open', 'High', 'Low', 'Close', 'Adj Close']:
            if col in final_df.columns:
                final_df[col] = final_df[col].round(0)
        
        # 9. 최종 결측값 확인 및 처리
        if final_df.isnull().values.any():
            print("경고: 전처리 후에도 결측값이 존재합니다. 추가 처리합니다.")
            final_df = final_df.ffill().bfill()
        
        # 전처리 결과 상태 출력
        print(f"전처리 후 데이터: {len(final_df)}행 x {len(final_df.columns)}열")
        print(f"최종 컬럼: {', '.join(final_df.columns)}")
        
        return final_df 