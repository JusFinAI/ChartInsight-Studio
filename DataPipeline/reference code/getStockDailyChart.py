import requests
import json
import datetime
import pandas as pd
import os
import time
import re
from config import load_settings
from OAuth import fn_au10001

# 주식일봉차트조회요청
def fn_ka10081(token, data, host=None, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	if host is None:
		host = 'https://mockapi.kiwoom.com'  # 기본값 모의투자
		
	endpoint = '/api/dostk/chart'
	url = host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10081', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	
	# 응답 결과 반환
	result = response.json()
	
	# 연속 조회를 위한 헤더 정보 추가
	result['next_key'] = response.headers.get('next-key', '')
	result['cont_yn'] = response.headers.get('cont-yn', 'N')
	result['status_code'] = response.status_code
	
	return result

# 기간 문자열 파싱 함수
def parse_period(period_str, trading_days=True):
	"""
	기간 문자열을 파싱하여 일수로 변환
	
	Args:
		period_str: 기간 문자열 ('2y', '3m', '40d' 등)
		trading_days: True면 거래일 기준, False면 달력일 기준으로 계산
	
	거래일 기준 환산:
	- 1년 = 약 252일 (주말 및 공휴일 제외)
	- 1개월 = 약 21일 (주말 제외)
	- 1주 = 5일 (주말 제외)
	
	예:
	- '2y': 2년 (거래일: 504일, 달력일: 730일)
	- '3m': 3개월 (거래일: 63일, 달력일: 90일)
	- '40d': 40일 (거래일: 40일, 달력일: 40일)
	"""
	if not period_str:
		return 252 if trading_days else 365  # 기본값 1년
		
	# 복합 기간 처리 (예: '1y6m')
	total_days = 0
	
	# 년(y) 매칭
	year_match = re.search(r'(\d+)y', period_str)
	if year_match:
		years = int(year_match.group(1))
		total_days += years * (252 if trading_days else 365)
	
	# 월(m) 매칭
	month_match = re.search(r'(\d+)m', period_str)
	if month_match:
		months = int(month_match.group(1))
		total_days += months * (21 if trading_days else 30)
	
	# 주(w) 매칭
	week_match = re.search(r'(\d+)w', period_str)
	if week_match:
		weeks = int(week_match.group(1))
		total_days += weeks * (5 if trading_days else 7)
	
	# 일(d) 매칭
	day_match = re.search(r'(\d+)d', period_str)
	if day_match:
		days = int(day_match.group(1))
		total_days += days
	
	# 숫자만 있는 경우 일수로 취급
	if total_days == 0 and period_str.isdigit():
		total_days = int(period_str)
	
	# 최소 1일
	return max(1, total_days)

# 시작일 계산 함수
def calculate_start_date(end_date, period, trading_days=True):
	"""
	종료일과 기간을 기반으로 시작일 계산
	
	Args:
		end_date: 종료일 (YYYYMMDD 문자열 또는 datetime 객체)
		period: 기간 문자열 ('2y', '3m', '40d' 등)
		trading_days: True면 거래일 기준, False면 달력일 기준으로 계산
	
	Returns:
		YYYYMMDD 형식의 시작일 문자열
	
	예:
	- end_date: '20230401', period: '1y', trading_days=True -> 약 252 거래일 전 날짜
	- end_date: 현재날짜, period: '3m', trading_days=False -> 90일(달력일) 전 날짜
	"""
	# 기간을 일수로 변환 (거래일 또는 달력일 기준)
	days = parse_period(period, trading_days)
	
	# 종료일 파싱
	if isinstance(end_date, str):
		end_date_obj = datetime.datetime.strptime(end_date, '%Y%m%d')
	else:
		end_date_obj = end_date
	
	# 거래일 기준인 경우 보정값 적용 (주말/공휴일을 고려하여 약 1.4배 더 많은 날짜를 뺌)
	if trading_days:
		calendar_days = int(days * 1.4)  # 거래일을 달력일로 대략 변환
	else:
		calendar_days = days
	
	# 시작일 계산 (종료일 - 일수)
	start_date_obj = end_date_obj - datetime.timedelta(days=calendar_days)
	
	# YYYYMMDD 형식으로 반환
	return start_date_obj.strftime('%Y%m%d')

# 날짜 유효성 검사 함수
def validate_date_range(start_date, end_date):
	"""
	시작일과 종료일의 유효성을 검사
	
	Args:
		start_date: 시작일 (YYYYMMDD 형식)
		end_date: 종료일 (YYYYMMDD 형식)
		
	Returns:
		tuple: (시작일, 종료일, 오류 메시지)
			- 유효한 경우: (시작일, 종료일, None)
			- 유효하지 않은 경우: (조정된 시작일, 조정된 종료일, 오류 메시지)
	"""
	try:
		# 날짜 변환
		start_dt = datetime.datetime.strptime(start_date, '%Y%m%d')
		end_dt = datetime.datetime.strptime(end_date, '%Y%m%d')
		today = datetime.datetime.now()
		
		error_msg = None
		
		# 종료일이 오늘보다 미래인 경우
		if end_dt > today:
			end_dt = today
			end_date = today.strftime('%Y%m%d')
			error_msg = f"종료일이 미래 날짜입니다. 오늘({end_date})로 조정합니다."
		
		# 시작일이 종료일보다 미래인 경우
		if start_dt > end_dt:
			start_dt = end_dt - datetime.timedelta(days=365)  # 기본값 1년
			start_date = start_dt.strftime('%Y%m%d')
			error_msg = f"시작일이 종료일보다 미래입니다. 종료일 1년 전({start_date})으로 조정합니다."
		
		# 시작일이 너무 과거인 경우 (예: 20년 이상)
		max_years_back = 20
		min_date = end_dt - datetime.timedelta(days=365 * max_years_back)
		if start_dt < min_date:
			start_dt = min_date
			start_date = start_dt.strftime('%Y%m%d')
			error_msg = f"시작일이 너무 과거입니다. {max_years_back}년 전({start_date})으로 조정합니다."
		
		return start_date, end_date, error_msg
	
	except ValueError as e:
		# 날짜 형식이 잘못된 경우
		today_str = datetime.datetime.now().strftime('%Y%m%d')
		last_year = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y%m%d')
		return last_year, today_str, f"날짜 형식이 잘못되었습니다: {e}. 기본값으로 설정합니다."

# 미래 데이터 필터링 함수
def filter_future_data(data_list, date_field='dt'):
	"""
	미래 날짜의 데이터를 필터링
	
	Args:
		data_list: 데이터 리스트
		date_field: 날짜 필드명
		
	Returns:
		list: 미래 날짜가 제외된 데이터 리스트
	"""
	if not data_list:
		return []
		
	today = datetime.datetime.now().strftime('%Y%m%d')
	filtered_data = []
	
	for item in data_list:
		if date_field in item and item[date_field] <= today:
			filtered_data.append(item)
	
	return filtered_data

# 문자열 날짜를 YYYYMMDD 형식으로 변환
def format_date(date_str):
	"""다양한 형식의 날짜 문자열을 YYYYMMDD 형식으로 변환"""
	if isinstance(date_str, datetime.datetime):
		return date_str.strftime('%Y%m%d')
	
	if len(date_str) == 8 and date_str.isdigit():
		return date_str
	
	try:
		# 하이픈이나 슬래시 포함된 날짜를 파싱
		if '-' in date_str or '/' in date_str:
			date_obj = datetime.datetime.strptime(
				date_str.replace('/', '-'), 
				'%Y-%m-%d' if len(date_str.split('-')[0]) == 4 else '%d-%m-%Y'
			)
		else:
			# 다른 형식 시도
			formats = ['%Y%m%d', '%d%m%Y', '%m%d%Y']
			for fmt in formats:
				try:
					date_obj = datetime.datetime.strptime(date_str, fmt)
					break
				except ValueError:
					continue
			else:
				raise ValueError(f"인식할 수 없는 날짜 형식: {date_str}")
		
		return date_obj.strftime('%Y%m%d')
	except Exception as e:
		print(f"날짜 변환 오류: {e}, 기본값 사용")
		return datetime.datetime.now().strftime('%Y%m%d')

# 현재 날짜를 YYYYMMDD 형식으로 변환
def get_today():
	return datetime.datetime.now().strftime('%Y%m%d')

# 키움증권 API 데이터를 표준 OHLCV 형식으로 전처리
def preprocess_kiwoom_data(df):
	"""
	키움증권 API에서 가져온 일봉 데이터를 표준 OHLCV 형식으로 변환합니다.
	
	변환 내용:
	1. 컬럼명 변경: 키움 API → 표준 OHLCV
	2. 날짜 인덱스 변환
	3. 결측값 처리
	4. 데이터 타입 정리
	"""
	if df.empty:
		print("빈 데이터프레임입니다.")
		return df
	
	# 1. 데이터 복사
	df_processed = df.copy()
	
	# 컬럼 목록 확인
	print(f"원본 데이터 컬럼: {', '.join(df_processed.columns)}")
	
	# 2. 키움 API 컬럼명을 표준 OHLCV 컬럼명으로 매핑
	column_mapping = {
		# 키움증권 API 실제 응답 필드명 → 표준 OHLCV 컬럼명
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
	}
	
	# 필요한 컬럼만 선택하여 이름 변경
	for old_col, new_col in column_mapping.items():
		if old_col in df_processed.columns:
			df_processed[new_col] = df_processed[old_col]
	
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
	numeric_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
	for col in numeric_columns:
		if col in df_processed.columns:
			df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
	
	# 4. 날짜 형식 처리
	if 'date' in df_processed.columns:
		# 날짜 형식 변환
		df_processed['date'] = pd.to_datetime(df_processed['date'], format='%Y%m%d', errors='coerce')
		
		# 인덱스로 설정
		df_processed = df_processed.set_index('date')
		
		# 인덱스 정렬
		df_processed = df_processed.sort_index()
	
	# 5. 필요한 컬럼만 선택 (OHLCV 표준 컬럼)
	standard_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
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
		final_df[available_price_columns] = final_df[available_price_columns].fillna(method='ffill').fillna(method='bfill')
	
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
		final_df = final_df.fillna(method='ffill').fillna(method='bfill')
	
	# 전처리 결과 상태 출력
	print(f"전처리 후 데이터: {len(final_df)}행 x {len(final_df.columns)}열")
	print(f"최종 컬럼: {', '.join(final_df.columns)}")
	
	return final_df

# CSV 파일로 저장하는 함수
def save_to_csv(data, filename, code=None, preprocess=True):
	# 데이터가 없으면 종료
	if not data:
		print("저장할 데이터가 없습니다.")
		return None
		
	# 데이터프레임 변환
	df = pd.DataFrame(data)
	
	# 원본 형식 파일 저장
	original_filename = filename.replace('.csv', '_original.csv')
	df.to_csv(original_filename, encoding='utf-8-sig', index=False)
	print(f"원본 형식 CSV 파일 저장 완료: {original_filename}")
	
	# 전처리 수행
	if preprocess:
		processed_df = preprocess_kiwoom_data(df)
		
		# 종목코드 컬럼 추가
		if code and 'symbol' not in processed_df.columns:
			processed_df['symbol'] = code
		
		# 전처리된 파일 저장
		processed_df.to_csv(filename, encoding='utf-8-sig')
		print(f"전처리된 CSV 파일 저장 완료: {filename}")
		
		return filename, processed_df
	else:
		# 날짜 컬럼 기준으로 정렬 (일봉 데이터는 보통 역순으로 제공)
		if 'dt' in df.columns:
			df.sort_values('dt', inplace=True)
		
		# 종목코드 컬럼 추가
		if code and 'symbol' not in df.columns:
			df['symbol'] = code
		
		# 파일 저장
		df.to_csv(filename, encoding='utf-8-sig', index=False)
		print(f"CSV 파일 저장 완료: {filename}")
		
		return original_filename, df

# 특정 기간의 일봉 데이터 조회 및 저장
def get_daily_chart(stock_code, period=None, end_date=None, trading_days=True):
	"""특정 기간의 일봉 데이터를 조회하고 저장하는 함수
	
	Args:
		stock_code (str): 종목코드 (예: '005930')
		period (str): 조회 기간 (예: '2y', '3m', '40d', '1y6m', '2w')
			- 'Xy': X년
			- 'Xm': X개월
			- 'Xd': X일
			- 'Xw': X주
			- 복합형식 가능 (예: '1y6m')
		end_date (str, optional): 조회 종료일. 기본값은 오늘.
		trading_days (bool): True면 거래일 기준, False면 달력일 기준으로 계산
	
	Returns:
		DataFrame: 조회된 일봉 데이터
	"""
	# 설정 로드
	config = load_settings()
	
	# 종료일 설정 (기본값: 오늘)
	if not end_date:
		end_date = get_today()
	else:
		end_date = format_date(end_date)
	
	# 시작일 계산
	if period:
		start_date = calculate_start_date(end_date, period, trading_days)
	else:
		# 기본 기간: 1년
		start_date = calculate_start_date(end_date, '1y', trading_days)
	
	# 날짜 유효성 검사
	start_date, end_date, error_msg = validate_date_range(start_date, end_date)
	if error_msg:
		print(f"경고: {error_msg}")
	
	print(f"{stock_code} 종목의 {start_date}부터 {end_date}까지의 일봉 데이터를 조회합니다.")
	print(f"조회 기간: {period if period else '1y'} (약 {parse_period(period, trading_days) if period else (252 if trading_days else 365)}일)")
	print(f"계산 기준: {'거래일' if trading_days else '달력일'}")
	
	# 1. 액세스 토큰 발급
	auth_params = {
		'grant_type': 'client_credentials',
		'appkey': config['app_key'],
		'secretkey': config['secret_key'],
	}
	
	token = fn_au10001(data=auth_params, host=config['host'])
	print(f"토큰이 발급되었습니다.\n")
	
	# 2. 요청 데이터 - 명확한 시작일/종료일 지정
	params = {
		'stk_cd': stock_code,          # 종목코드
		'fr_dt': start_date,           # 시작일 (명시적 지정)
		'to_dt': end_date,             # 종료일 (명시적 지정)
		'base_dt': end_date,           # 기준일자 (과거 데이터 조회 시작점)
		'upd_stkpc_tp': '1',           # 수정주가구분 (1: 수정주가)
	}
	
	# 3. API 실행 - 연속 조회를 위한 while문 사용
	all_data = []               # 모든 일봉 데이터를 담을 리스트
	page_count = 0              # 페이지 카운트
	max_attempts = 3            # 최대 재시도 횟수
	request_delay = 1           # 요청 간 지연 시간(초)
	target_period_reached = False  # 목표 기간 도달 여부
	earliest_date = '99991231'  # 가장 이른 날짜 초기화 (비교를 위해 큰 값으로)
	latest_date = '00000000'    # 가장 최근 날짜 초기화 (비교를 위해 작은 값으로)
	
	try:
		# 초기 요청
		result = fn_ka10081(token=token, data=params, host=config['host'])
		
		# 응답 코드 확인
		if result['status_code'] != 200:
			print(f"API 요청 실패: 상태 코드 {result['status_code']}")
			if 'return_code' in result and 'return_msg' in result:
				print(f"응답 코드: {result['return_code']}, 메시지: {result['return_msg']}")
			return None
		
		# 응답 구조 확인
		print(f"\n응답 구조: {list(result.keys())}")
		
		# 데이터 키 찾기
		data_key = None
		possible_keys = ['output2', 'stk_dt_pole_chart_qry', 'chart', 'list']
		for key in possible_keys:
			if key in result and isinstance(result[key], list) and len(result[key]) > 0:
				data_key = key
				print(f"데이터 키를 찾았습니다: {data_key}")
				break
		
		if not data_key:
			print("응답에서 데이터를 찾을 수 없습니다.")
			print(json.dumps(result, indent=2, ensure_ascii=False))
			return None
		
		# 첫 번째 결과 처리 및 기간 체크
		processed_data = []
		for item in result[data_key]:
			# 날짜 필드 이름 확인 (dt 또는 다른 이름)
			date_field = 'dt' if 'dt' in item else 'stck_bsop_date'
			
			if date_field in item:
				date = item[date_field]
				
				# 날짜가 지정된 범위 내에 있는지 확인
				if start_date <= date <= end_date:
					# 날짜 기록
					earliest_date = min(earliest_date, date)
					latest_date = max(latest_date, date)
					processed_data.append(item)
				elif date < start_date:
					# 시작일보다 이전 데이터 발견 시 target_period_reached 설정
					target_period_reached = True
		
		# 미래 데이터 필터링 (모의 API에서 미래 데이터가 포함될 수 있음)
		processed_data = filter_future_data(processed_data, date_field=date_field)
		
		all_data.extend(processed_data)
		page_count += 1
		print(f"페이지 {page_count} 수신: {len(processed_data)}개 일봉 데이터 (전체: {len(all_data)}개)")
		
		# 첫 번째 일봉 데이터 출력
		if all_data:
			print("\n첫 번째 일봉 데이터:")
			print(json.dumps(all_data[0], indent=2, ensure_ascii=False))
		
		# 목표 기간에 도달했는지 확인
		if target_period_reached:
			print(f"목표 기간({start_date}~{end_date})의 데이터 수집을 완료했습니다.")
		
		# 연속 조회 처리
		attempt = 0
		while (not target_period_reached and  # 목표 기간에 도달하지 않았고
			   result['cont_yn'] == 'Y' and    # 연속 데이터가 있고
			   result['next_key'] and          # 다음 키가 있고
			   attempt < max_attempts):        # 최대 시도 횟수를 넘지 않았을 때
			
			# API 요청 제한 방지를 위한 지연
			time.sleep(request_delay)
			
			# 연속 조회 요청
			print(f"\n연속 데이터가 있습니다. 추가 데이터를 조회합니다...")
			try:
				result = fn_ka10081(
					token=token, 
					data=params, 
					host=config['host'], 
					cont_yn='Y', 
					next_key=result['next_key']
				)
				
				# 상태 코드 확인
				if result['status_code'] != 200:
					attempt += 1
					print(f"API 요청 실패: 상태 코드 {result['status_code']}, 시도 {attempt}/{max_attempts}")
					if 'return_code' in result and 'return_msg' in result:
						print(f"응답 코드: {result['return_code']}, 메시지: {result['return_msg']}")
					
					if attempt >= max_attempts:
						print(f"최대 재시도 횟수를 초과했습니다. 지금까지 수집된 데이터로 진행합니다.")
						break
					
					# 요청 제한 초과 시 대기 시간 증가
					if result['status_code'] == 429:
						wait_time = 5 * (attempt + 1)
						print(f"요청 제한에 도달했습니다. {wait_time}초 대기 후 재시도합니다...")
						time.sleep(wait_time)
					continue
				
				# 시도 횟수 초기화
				attempt = 0
				
				# 데이터 키 확인 및 기간 체크
				if data_key in result and isinstance(result[data_key], list):
					page_processed_data = []
					for item in result[data_key]:
						# 날짜 필드 이름 확인
						date_field = 'dt' if 'dt' in item else 'stck_bsop_date'
						
						if date_field in item:
							date = item[date_field]
							
							# 날짜가 지정된 범위 내에 있는지 확인
							if start_date <= date <= end_date:
								# 날짜 기록
								earliest_date = min(earliest_date, date)
								latest_date = max(latest_date, date)
								page_processed_data.append(item)
							elif date < start_date:
								# 시작일보다 이전 데이터 발견 시 target_period_reached 설정
								target_period_reached = True
					
					# 미래 데이터 필터링
					page_processed_data = filter_future_data(page_processed_data, date_field=date_field)
					
					# 기간 내 데이터만 추가
					all_data.extend(page_processed_data)
					page_count += 1
					print(f"페이지 {page_count} 수신: {len(page_processed_data)}개 일봉 데이터 (전체: {len(all_data)}개)")
					
					# 목표 기간에 도달했는지 확인 또는 데이터가 더 이상 없는 경우
					if target_period_reached or len(page_processed_data) == 0:
						print(f"목표 기간({start_date}~{end_date})의 데이터 수집을 완료했습니다.")
						break
					
					# 모든 데이터를 가져왔는지 확인
					if not result['cont_yn'] == 'Y' or not result['next_key']:
						print("모든 데이터를 가져왔습니다.")
						break
				else:
					# 데이터 키가 없는 경우
					print("응답에서 데이터를 찾을 수 없습니다.")
					break
					
			except Exception as e:
				print(f"연속 조회 중 오류 발생: {e}")
				attempt += 1
				if attempt >= max_attempts:
					print(f"최대 재시도 횟수를 초과했습니다. 지금까지 수집된 데이터로 진행합니다.")
					break
		
		# 4. 데이터 검증 및 기간 확인
		print(f"\n전체 일봉 데이터 수: {len(all_data)}")
		
		if len(all_data) > 0:
			# 날짜 필드 확인
			date_field = 'dt' if 'dt' in all_data[0] else 'stck_bsop_date'
			
			# 데이터 정렬 (날짜 오름차순)
			all_data.sort(key=lambda x: x[date_field])
			
			# 실제 조회된 데이터의 날짜 범위
			earliest_date = all_data[0][date_field]
			latest_date = all_data[-1][date_field]
			
			print(f"실제 조회된 기간: {earliest_date} ~ {latest_date}")
			
			# 목표 기간과 실제 기간 비교
			if earliest_date > start_date:
				print(f"경고: 요청한 시작일({start_date})보다 실제 시작일({earliest_date})이 더 최근입니다.")
				print("      이는 해당 기간에 거래 데이터가 없거나 API 제한으로 인한 것일 수 있습니다.")
			
			if latest_date < end_date:
				today = get_today()
				if end_date > today:
					print(f"참고: 종료일({end_date})이 오늘({today})보다 미래이므로 최신 데이터까지만 조회되었습니다.")
				else:
					print(f"경고: 요청한 종료일({end_date})까지 데이터가 조회되지 않았습니다.")
			
			# 디렉토리 생성
			output_dir = 'output'
			if not os.path.exists(output_dir):
				os.makedirs(output_dir)
				
			# 파일명에 종목코드와 기간 추가
			filename = os.path.join(output_dir, f'daily_{stock_code}_{earliest_date}_{latest_date}.csv')
			
			# CSV 저장
			saved_file, df = save_to_csv(all_data, filename, code=stock_code, preprocess=True)
			
			if saved_file:
				print(f"\n{stock_code} 종목의 {earliest_date}~{latest_date} 기간 데이터가 저장되었습니다.")
				# 데이터 검증
				if df.empty:
					print("경고: 저장된 데이터가 비어 있습니다.")
				elif len(df) < 2:
					print("경고: 저장된 데이터가 2개 미만입니다.")
				return df
			else:
				print("데이터 저장에 실패했습니다.")
		else:
			print(f"{stock_code} 종목의 {start_date}~{end_date} 기간에 해당하는 데이터가 없습니다.")
		
	except Exception as e:
		print(f"API 요청 중 오류 발생: {e}")
		import traceback
		traceback.print_exc()
	
	return None

# 실행 구간
if __name__ == '__main__':
	# 종목코드 설정 (삼성전자)
	stock_code = '005930'
	
	# 기간 설정
	# 아래 주석을 해제하고 원하는 기간을 선택하세요
	
	# period = '2y'    # 2년 데이터
	# period = '6m'    # 6개월 데이터
	# period = '30d'   # 30일 데이터
	# period = '1y6m'  # 1년 6개월 데이터
	# period = '2w'    # 2주 데이터
	
	period = '1y'     # 기본값: 1년 데이터
	
	# 거래일 기준 사용 여부
	trading_days = True  # True: 거래일 기준, False: 달력일 기준
	
	# 일봉 데이터 조회 및 저장
	daily_data = get_daily_chart(stock_code, period, trading_days=trading_days)
	
	# 데이터 요약 출력
	if daily_data is not None and not daily_data.empty:
		print("\n=== 데이터 요약 ===")
		print(f"종목코드: {stock_code}")
		print(f"조회 기간: {period} (거래일 기준: {'예' if trading_days else '아니오'})")
		print(f"행 수: {len(daily_data)}")
		print(f"컬럼: {', '.join(daily_data.columns)}")
		
		if isinstance(daily_data.index, pd.DatetimeIndex):
			print(f"기간: {daily_data.index.min().strftime('%Y-%m-%d')} ~ {daily_data.index.max().strftime('%Y-%m-%d')}")
		
		if 'Close' in daily_data.columns:
			print(f"시가: {daily_data['Open'].iloc[-1]}")
			print(f"종가: {daily_data['Close'].iloc[-1]}")
			print(f"최고가: {daily_data['High'].max()}")
			print(f"최저가: {daily_data['Low'].min()}")
			print(f"평균 종가: {daily_data['Close'].mean():.2f}")
		
		if 'Volume' in daily_data.columns:
			print(f"평균 거래량: {daily_data['Volume'].mean():.0f}")
			print(f"최대 거래량: {daily_data['Volume'].max()}")