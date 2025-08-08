import requests
import json
import datetime
import pandas as pd
import os
import time as time_module
import re
from .config import config
from .auth import Auth

# 주식분봉차트조회요청
def fn_ka10083(token, data, host=None, cont_yn='N', next_key=''):
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
		'api-id': 'ka10083', # TR명
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

# 업데이트된 분봉 조회 함수 (api-id: ka10080)
def fn_ka10080(token, data, host=None, cont_yn='N', next_key=''):
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
		'api-id': 'ka10080', # TR명 - 틱 범위 기준 분봉
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

# 현재 날짜를 YYYYMMDD 형식으로 변환
def get_today():
	return datetime.datetime.now().strftime('%Y%m%d')

# 현재 시간을 HHMMSS 형식으로 변환
def get_current_time():
	return datetime.datetime.now().strftime('%H%M%S')

# 거래일 여부 확인 함수
def is_trading_day(date_str):
	"""
	주어진 날짜가 거래일인지 확인 (주말 제외)
	
	Args:
		date_str: YYYYMMDD 형식의 날짜 문자열
		
	Returns:
		bool: 거래일이면 True, 주말이면 False
	"""
	date_obj = datetime.datetime.strptime(date_str, '%Y%m%d')
	# 주말 확인 (5: 토요일, 6: 일요일)
	return date_obj.weekday() < 5

# 다음 거래일 찾기
def find_next_trading_day(date_str):
	"""
	주어진 날짜의 다음 거래일을 찾음
	
	Args:
		date_str: YYYYMMDD 형식의 날짜 문자열
		
	Returns:
		str: 다음 거래일 (YYYYMMDD 형식)
	"""
	date_obj = datetime.datetime.strptime(date_str, '%Y%m%d')
	while True:
		date_obj += datetime.timedelta(days=1)
		if date_obj.weekday() < 5:  # 주말이 아닌 경우
			return date_obj.strftime('%Y%m%d')

# 이전 거래일 찾기
def find_previous_trading_day(date_str):
	"""
	주어진 날짜의 이전 거래일을 찾음
	
	Args:
		date_str: YYYYMMDD 형식의 날짜 문자열
		
	Returns:
		str: 이전 거래일 (YYYYMMDD 형식)
	"""
	date_obj = datetime.datetime.strptime(date_str, '%Y%m%d')
	while True:
		date_obj -= datetime.timedelta(days=1)
		if date_obj.weekday() < 5:  # 주말이 아닌 경우
			return date_obj.strftime('%Y%m%d')

# 거래 시간 여부 확인
def is_trading_time(time_str):
	"""
	주어진 시간이 거래 시간(9:00-15:30)인지 확인
	
	Args:
		time_str: HHMMSS 형식의 시간 문자열
		
	Returns:
		bool: 거래 시간이면 True, 아니면 False
	"""
	hour = int(time_str[:2])
	minute = int(time_str[2:4])
	
	# 9:00 이전 또는 15:30 이후이면 거래 시간이 아님
	if hour < 9 or (hour == 15 and minute > 30) or hour > 15:
		return False
	return True

# 가장 가까운 거래 시간 찾기
def find_nearest_trading_time(time_str):
	"""
	주어진 시간에 가장 가까운 거래 시간을 찾음
	
	Args:
		time_str: HHMMSS 형식의 시간 문자열
		
	Returns:
		str: 가장 가까운 거래 시간 (HHMMSS 형식)
	"""
	hour = int(time_str[:2])
	minute = int(time_str[2:4])
	second = int(time_str[4:])
	
	# 시작 시간(9:00) 이전인 경우 시작 시간으로 설정
	if hour < 9:
		return '090000'
	
	# 종료 시간(15:30) 이후인 경우 종료 시간으로 설정
	if hour > 15 or (hour == 15 and minute > 30):
		return '153000'
	
	# 거래 시간 내인 경우 그대로 사용
	return time_str

# 기간 문자열 파싱 함수 (분봉 데이터용)
def parse_period(period_str):
	"""
	기간 문자열을 파싱하여 분 단위로 변환
	
	Args:
		period_str: 기간 문자열 ('1d', '4h', '30m' 등)
		- 'd': 일 (하루 = 390분, 6시간 30분 거래 시간 기준)
		- 'h': 시간
		- 'm': 분
	
	Returns:
		int: 분 단위 기간
	"""
	if not period_str:
		return 390  # 기본값 1일 (거래시간 6시간 30분 = 390분)
		
	# 일(d) 매칭
	day_match = re.search(r'(\d+)d', period_str)
	if day_match:
		days = int(day_match.group(1))
		return days * 390  # 하루 거래시간 6시간 30분 = 390분
	
	# 시간(h) 매칭
	hour_match = re.search(r'(\d+)h', period_str)
	if hour_match:
		hours = int(hour_match.group(1))
		return hours * 60  # 1시간 = 60분
	
	# 분(m) 매칭
	minute_match = re.search(r'(\d+)m', period_str)
	if minute_match:
		minutes = int(minute_match.group(1))
		return minutes
	
	# 숫자만 있는 경우 분으로 취급
	if period_str.isdigit():
		return int(period_str)
	
	# 기본값
	return 390  # 1일 (거래시간 6시간 30분)

# 시작시간 계산 함수
def calculate_start_time(base_date, base_time, period):
	"""
	기준일시와 기간을 기반으로 시작일시 계산
	
	Args:
		base_date: 기준일자 (YYYYMMDD 형식)
		base_time: 기준시간 (HHMMSS 형식)
		period: 기간 문자열 ('1d', '4h', '30m' 등)
	
	Returns:
		tuple: (시작일자(YYYYMMDD), 시작시간(HHMMSS))
	"""
	# 기준일시 파싱
	if not base_time:
		base_time = '153000'  # 기본값: 15시 30분 (장 종료 시간)
		
	# 기준일이 주말인 경우 이전 거래일로 조정
	if not is_trading_day(base_date):
		print(f"기준일({base_date})이 주말입니다. 이전 거래일로 조정합니다.")
		base_date = find_previous_trading_day(base_date)
		print(f"조정된 기준일: {base_date}")
	
	# 기준시간이 거래 시간이 아닌 경우 가장 가까운 거래 시간으로 조정
	if not is_trading_time(base_time):
		print(f"기준시간({base_time})이 거래 시간(9:00-15:30)이 아닙니다. 가장 가까운 거래 시간으로 조정합니다.")
		base_time = find_nearest_trading_time(base_time)
		print(f"조정된 기준시간: {base_time}")
	
	# 기준일시 객체 생성
	base_datetime = datetime.datetime.strptime(f"{base_date}{base_time}", '%Y%m%d%H%M%S')
	
	# 기간을 분 단위로 변환
	minutes = parse_period(period)
	
	# 거래 시간만 고려 (9:00 ~ 15:30)
	trading_minutes_per_day = 6.5 * 60  # 6시간 30분 = 390분
	
	# 전체 거래일 수와 남은 분 계산
	trading_days = minutes // trading_minutes_per_day
	remaining_minutes = minutes % trading_minutes_per_day
	
	# 거래일 역순으로 계산 (주말 제외)
	start_date = base_date
	for _ in range(int(trading_days)):
		start_date = find_previous_trading_day(start_date)
	
	# 시작 시간 계산 (남은 분 적용)
	start_datetime = datetime.datetime.strptime(f"{start_date}{base_time}", '%Y%m%d%H%M%S')
	
	# 남은 분 만큼 시간 조정
	if remaining_minutes > 0:
		start_datetime = start_datetime - datetime.timedelta(minutes=remaining_minutes)
		
		# 거래 시간 이전으로 가면 이전 거래일 15:30으로 조정
		new_date = start_datetime.strftime('%Y%m%d')
		new_time = start_datetime.strftime('%H%M%S')
		
		if new_date == start_date and not is_trading_time(new_time):
			if int(new_time) < 90000:  # 9시 이전
				start_date = find_previous_trading_day(start_date)
				start_time = '153000'  # 15:30
			else:
				start_time = new_time
		else:
			start_date = new_date
			start_time = new_time
	else:
		start_time = base_time
	
	return start_date, start_time

# 날짜 유효성 검사 함수
def validate_date_range(start_date, end_date, start_time=None, end_time=None):
	"""
	시작일시와 종료일시의 유효성을 검사
	
	Args:
		start_date: 시작일 (YYYYMMDD 형식)
		end_date: 종료일 (YYYYMMDD 형식)
		start_time: 시작시간 (HHMMSS 형식, 선택적)
		end_time: 종료시간 (HHMMSS 형식, 선택적)
		
	Returns:
		tuple: (시작일, 종료일, 시작시간, 종료시간, 오류 메시지)
	"""
	try:
		# 기본 시간 설정
		if not start_time:
			start_time = '090000'  # 9시 0분 0초
		if not end_time:
			end_time = '153000'  # 15시 30분 0초
		
		error_msg = None
		warnings = []
		
		# 오늘 날짜 및 현재 시간
		today = get_today()
		now = get_current_time()
		
		# 날짜 및 시간 변환
		start_datetime = datetime.datetime.strptime(f"{start_date}{start_time}", '%Y%m%d%H%M%S')
		end_datetime = datetime.datetime.strptime(f"{end_date}{end_time}", '%Y%m%d%H%M%S')
		now_datetime = datetime.datetime.strptime(f"{today}{now}", '%Y%m%d%H%M%S')
		
		# 종료일이 미래인 경우
		if end_date > today:
			warnings.append(f"경고: 종료일({end_date})이 미래 날짜입니다. 오늘({today})로 조정합니다.")
			end_date = today
		
		# 종료일이 주말인 경우
		if not is_trading_day(end_date):
			prev_trading_day = find_previous_trading_day(end_date)
			warnings.append(f"경고: 종료일({end_date})이 주말입니다. 이전 거래일({prev_trading_day})로 조정합니다.")
			end_date = prev_trading_day
		
		# 종료시간이 거래 시간이 아닌 경우
		if not is_trading_time(end_time):
			nearest_time = find_nearest_trading_time(end_time)
			warnings.append(f"경고: 종료시간({end_time})이 거래 시간(9:00-15:30)이 아닙니다. {nearest_time}으로 조정합니다.")
			end_time = nearest_time
		
		# 오늘이면서 현재 시간보다 미래인 경우
		if end_date == today and end_time > now:
			warnings.append(f"경고: 종료시간({end_time})이 현재 시간({now})보다 미래입니다. 현재 시간으로 조정합니다.")
			end_time = now
		
		# 시작일이 미래인 경우
		if start_date > today:
			warnings.append(f"경고: 시작일({start_date})이 미래 날짜입니다. 오늘({today})로 조정합니다.")
			start_date = today
		
		# 시작일이 주말인 경우
		if not is_trading_day(start_date):
			next_trading_day = find_next_trading_day(start_date)
			warnings.append(f"경고: 시작일({start_date})이 주말입니다. 다음 거래일({next_trading_day})로 조정합니다.")
			start_date = next_trading_day
		
		# 시작시간이 거래 시간이 아닌 경우
		if not is_trading_time(start_time):
			nearest_time = find_nearest_trading_time(start_time)
			warnings.append(f"경고: 시작시간({start_time})이 거래 시간(9:00-15:30)이 아닙니다. {nearest_time}으로 조정합니다.")
			start_time = nearest_time
		
		# 재확인: 날짜 및 시간 업데이트
		start_datetime = datetime.datetime.strptime(f"{start_date}{start_time}", '%Y%m%d%H%M%S')
		end_datetime = datetime.datetime.strptime(f"{end_date}{end_time}", '%Y%m%d%H%M%S')
		
		# 시작일시가 종료일시보다 미래인 경우
		if start_datetime > end_datetime:
			# 하루 전으로 조정
			start_datetime = end_datetime - datetime.timedelta(days=1)
			start_date = start_datetime.strftime('%Y%m%d')
			start_time = start_datetime.strftime('%H%M%S')
			
			# 주말인 경우 이전 거래일로 조정
			if not is_trading_day(start_date):
				start_date = find_previous_trading_day(start_date)
			
			# 거래 시간이 아닌 경우 조정
			if not is_trading_time(start_time):
				start_time = find_nearest_trading_time(start_time)
				
			warnings.append(f"경고: 시작일시가 종료일시보다 미래입니다. {start_date} {start_time}으로 조정합니다.")
		
		# 시작일시가 너무 과거인 경우 (30일 이상)
		max_days_back = 30
		min_date = end_datetime - datetime.timedelta(days=max_days_back)
		if start_datetime < min_date:
			min_date_str = min_date.strftime('%Y%m%d')
			min_time_str = min_date.strftime('%H%M%S')
			
			# 주말인 경우 다음 거래일로 조정
			if not is_trading_day(min_date_str):
				min_date_str = find_next_trading_day(min_date_str)
			
			# 거래 시간이 아닌 경우 조정
			if not is_trading_time(min_time_str):
				min_time_str = find_nearest_trading_time(min_time_str)
				
			warnings.append(f"경고: 시작일시가 너무 과거입니다. {min_date_str} {min_time_str}으로 조정합니다.")
			start_date = min_date_str
			start_time = min_time_str
		
		# 경고 메시지 통합
		if warnings:
			error_msg = "\n".join(warnings)
		
		return start_date, end_date, start_time, end_time, error_msg
	
	except ValueError as e:
		# 날짜 형식이 잘못된 경우
		today = get_today()
		now = get_current_time()
		yesterday = find_previous_trading_day(today)
		return yesterday, today, '090000', '153000', f"날짜 형식이 잘못되었습니다: {e}. 기본값으로 설정합니다."

# 미래 데이터 필터링 함수
def filter_future_data(data_list, date_field='stck_bsop_date', time_field='stck_cntg_hour'):
	"""
	미래 날짜/시간의 데이터를 필터링
	
	Args:
		data_list: 데이터 리스트
		date_field: 날짜 필드명
		time_field: 시간 필드명
		
	Returns:
		list: 미래 날짜/시간이 제외된 데이터 리스트
	"""
	if not data_list:
		return []
		
	today = get_today()
	now = get_current_time()
	filtered_data = []
	
	for item in data_list:
		if date_field in item and time_field in item:
			date = item[date_field]
			time = item[time_field]
			
			# 오늘이면서 현재 시간보다 미래인 경우 필터링
			if date == today and time > now:
				continue
			# 오늘 이후 날짜인 경우 필터링
			elif date > today:
				continue
				
			filtered_data.append(item)
		else:
			# 필드가 없는 경우 포함 (호환성 유지)
			filtered_data.append(item)
	
	return filtered_data

# 키움증권 API 분봉 데이터를 표준 OHLCV 형식으로 전처리
def preprocess_kiwoom_minute_data(df):
	"""
	키움증권 API에서 가져온 분봉 데이터를 표준 OHLCV 형식으로 변환합니다.
	
	변환 내용:
	1. 컬럼명 변경: 키움 API → 표준 OHLCV
	2. 날짜/시간 인덱스 변환
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
		'open_pric': 'Open',      # 시가
		'high_pric': 'High',      # 고가
		'low_pric': 'Low',        # 저가
		'cur_prc': 'Close',       # 종가/현재가
		'trde_qty': 'Volume',     # 거래량
		'date': 'date',           # 날짜
		'time': 'time',           # 시간
	}
	
	# 필요한 컬럼만 선택하여 이름 변경
	for old_col, new_col in column_mapping.items():
		if old_col in df_processed.columns:
			df_processed[new_col] = df_processed[old_col]
	
	# 필수 컬럼만 선택
	required_columns = ['date', 'time', 'Open', 'High', 'Low', 'Close', 'Volume']
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
	
	# 3. 데이터 타입 변환
	# 숫자형 컬럼 변환 - 키움 API는 문자열로 값을 반환하므로 숫자로 변환 필요
	numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
	for col in numeric_columns:
		if col in df_processed.columns:
			# 음수 부호 제거 (키움 API는 종종 음수 기호로 반환함)
			if df_processed[col].dtype == 'object':
				df_processed[col] = df_processed[col].str.replace('-', '', regex=False)
			df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
	
	# 4. 날짜/시간 형식 처리
	if 'date' in df_processed.columns and 'time' in df_processed.columns:
		# 날짜와 시간 결합
		df_processed['datetime'] = df_processed['date'] + df_processed['time']
		
		# datetime 객체로 변환
		df_processed['datetime'] = pd.to_datetime(df_processed['datetime'], format='%Y%m%d%H%M%S', errors='coerce')
		
		# 인덱스로 설정
		df_processed = df_processed.set_index('datetime')
		
		# 인덱스 정렬
		df_processed = df_processed.sort_index()
	
	# 5. 필요한 컬럼만 선택 (OHLCV 표준 컬럼)
	standard_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
	available_standard_columns = [col for col in standard_columns if col in df_processed.columns]
	
	if available_standard_columns:
		# 표준 컬럼만 선택하여 새로운 데이터프레임 생성
		final_df = df_processed[available_standard_columns].copy()
		print(f"표준 OHLCV 컬럼만 선택했습니다: {', '.join(final_df.columns)}")
	else:
		final_df = df_processed
		print("표준 OHLCV 컬럼을 찾을 수 없어 모든 컬럼을 유지합니다.")
	
	# 6. 결측값 처리
	price_columns = ['Open', 'High', 'Low', 'Close']
	available_price_columns = [col for col in price_columns if col in final_df.columns]
	
	if available_price_columns:
		# 앞, 뒤 값으로 결측치 채우기
		final_df[available_price_columns] = final_df[available_price_columns].fillna(method='ffill').fillna(method='bfill')
	
	# 7. 거래량 데이터 처리
	if 'Volume' in final_df.columns:
		# NaN 값을 0으로 대체
		final_df['Volume'] = final_df['Volume'].fillna(0)
	
	# 8. 전처리 결과 상태 출력
	print(f"전처리 후 데이터: {len(final_df)}행 x {len(final_df.columns)}열")
	print(f"최종 컬럼: {', '.join(final_df.columns)}")
	
	return final_df

# CSV 파일로 저장하는 함수 (분봉 데이터용)
def save_minute_data_to_csv(data, filename, code=None, preprocess=True):
	"""
	분봉 데이터를 CSV 파일로 저장
	
	Args:
		data: 저장할 데이터 (리스트 또는 데이터프레임)
		filename: 저장할 파일명
		code: 종목코드 (선택적)
		preprocess: 전처리 수행 여부
	
	Returns:
		tuple: (저장된 파일명, 데이터프레임)
	"""
	# 데이터가 없으면 종료
	if not data:
		print("저장할 데이터가 없습니다.")
		return None, None
	
	# 디렉토리 생성
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	
	# 데이터프레임 변환
	df = pd.DataFrame(data) if not isinstance(data, pd.DataFrame) else data
	
	# 원본 형식 파일 저장
	original_filename = filename.replace('.csv', '_raw.csv')
	df.to_csv(original_filename, encoding='utf-8-sig', index=False)
	print(f"원본 형식 CSV 파일 저장 완료: {original_filename}")
	
	# 전처리 수행
	if preprocess:
		processed_df = preprocess_kiwoom_minute_data(df)
		
		# 종목코드 컬럼 추가
		if code and 'symbol' not in processed_df.columns:
			processed_df['symbol'] = code
		
		# 전처리된 파일 저장
		processed_df.to_csv(filename, encoding='utf-8-sig')
		print(f"전처리된 CSV 파일 저장 완료: {filename}")
		
		return filename, processed_df
	else:
		# 날짜/시간 컬럼 기준으로 정렬
		if 'date' in df.columns and 'time' in df.columns:
			df.sort_values(['date', 'time'], inplace=True)
		
		# 종목코드 컬럼 추가
		if code and 'symbol' not in df.columns:
			df['symbol'] = code
		
		# 파일 저장
		df.to_csv(filename, encoding='utf-8-sig', index=False)
		print(f"CSV 파일 저장 완료: {filename}")
		
		return filename, df

# 특정 기간의 분봉 데이터 조회 및 저장
def get_minute_chart(stock_code, period=None, base_date=None, base_time=None, 
                     time_interval='1', modified_price_type='1'):
    """특정 기간의 분봉 데이터를 조회하고 저장하는 함수
    
    Args:
        stock_code (str): 종목코드 (예: '005930')
        period (str): 조회 기간 (예: '1d', '4h', '30m')
            - 'd': 일 (하루 = 390분, 6시간 30분 거래 시간 기준)
            - 'h': 시간
            - 'm': 분
        base_date (str, optional): 기준 일자 (YYYYMMDD). 기본값은 오늘.
        base_time (str, optional): 기준 시간 (HHMMSS). 기본값은 현재 시간.
        time_interval (str): 시간 간격 (1: 1분, 3: 3분, 5: 5분, 10: 10분, 30: 30분, 60: 60분).
        modified_price_type (str): 수정주가구분 (0: 원주가, 1: 수정주가). 기본값은 '1'.
    
    Returns:
        DataFrame: 조회된 분봉 데이터
    """
    # 설정은 이미 import 시점에 로드됨
    
    # 기준일자 및 시간 설정
    if not base_date:
        base_date = get_today()
    if not base_time:
        base_time = get_current_time()
    
    # 시작일시 계산 (기간 기준)
    if period:
        start_date, start_time = calculate_start_time(base_date, base_time, period)
    else:
        # 기본값: 1일
        start_date, start_time = calculate_start_time(base_date, base_time, '1d')
    
    # 날짜/시간 유효성 검사
    start_date, base_date, start_time, base_time, error_msg = validate_date_range(
        start_date, base_date, start_time, base_time)
    
    if error_msg:
        print(f"경고: {error_msg}")
    
    print(f"{stock_code} 종목의 {start_date} {start_time} 부터 {base_date} {base_time} 까지의 {time_interval}분봉 데이터를 조회합니다.")
    
    # 1. 액세스 토큰 발급
    auth = Auth()
    token = auth.get_token()
    print(f"토큰이 발급되었습니다.\n")
    
    # 2. 요청 데이터 - ka10080 API용 파라미터
    params = {
        'stk_cd': stock_code,      # 종목코드
        'tic_scope': time_interval,  # 틱범위 (1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분)
        'upd_stkpc_tp': modified_price_type, # 수정주가구분
    }
    
    # 3. API 실행 - 연속 조회를 위한 while문 사용
    all_data = []               # 모든 분봉 데이터를 담을 리스트
    page_count = 0              # 페이지 카운트
    max_attempts = 3            # 최대 재시도 횟수
    request_delay = 1           # 요청 간 지연 시간(초)
    
    try:
        # 초기 요청 - 명시적으로 fn_ka10080 호출
        result = fn_ka10080(token=token, data=params, host=config.host)
        
        # 응답 코드 확인
        if result['status_code'] != 200:
            print(f"API 요청 실패: 상태 코드 {result['status_code']}")
            if 'return_code' in result and 'return_msg' in result:
                print(f"응답 코드: {result['return_code']}, 메시지: {result['return_msg']}")
            return None
        
        # 데이터 키 확인 (stk_min_pole_chart_qry: 분봉 조회 API 응답의 데이터 키)
        data_key = 'stk_min_pole_chart_qry'
        
        # 데이터 키가 응답에 없거나 비어있는 경우 처리
        if data_key not in result or not isinstance(result[data_key], list) or len(result[data_key]) == 0:
            print(f"응답에서 데이터를 찾을 수 없습니다. 예상 키: {data_key}")
            print(f"응답 구조: {list(result.keys())}")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return None
            
        print(f"데이터를 찾았습니다. 키: {data_key}")
        
        # 첫 번째 결과 처리 및 기간 필터링
        processed_data = []
        
        # 응답 데이터 확인
        if result[data_key]:
            first_item = result[data_key][0]
            print("첫 번째 항목 구조: ", json.dumps(first_item, indent=2, ensure_ascii=False))
            
            # cntr_tm 필드 확인 (거래일시 필드)
            if 'cntr_tm' in first_item:
                print("cntr_tm 필드를 이용하여 데이터 처리 중...")
                for item in result[data_key]:
                    if 'cntr_tm' in item:
                        timestamp = item['cntr_tm']
                        
                        # 14자리인 경우 (YYYYMMDDHHMMSS)
                        if len(timestamp) == 14:
                            date = timestamp[:8]      # YYYYMMDD
                            time_str = timestamp[8:14]    # HHMMSS
                            
                            # 기간 외 데이터 필터링 - 시작일시 이전 또는 종료일시 이후 데이터는 제외
                            if date < start_date or (date == start_date and time_str < start_time):
                                continue
                                
                            if date > base_date or (date == base_date and time_str > base_time):
                                continue
                                
                            # 미래 데이터 필터링
                            today = get_today()
                            now = get_current_time()
                            
                            if date > today or (date == today and time_str > now):
                                continue
                                
                            # 프로세스된 데이터에 날짜 및 시간 필드 추가
                            item_copy = item.copy()
                            item_copy['date'] = date
                            item_copy['time'] = time_str
                            processed_data.append(item_copy)
            else:
                    print("오류: API 응답에서 cntr_tm 필드를 찾을 수 없습니다. 데이터 형식이 변경되었을 수 있습니다.")
        
        all_data.extend(processed_data)
        page_count += 1
        print(f"페이지 {page_count} 수신: {len(processed_data)}개 분봉 데이터 (전체: {len(all_data)}개)")
        
        # 첫 번째 분봉 데이터 출력
        if all_data:
            print("\n첫 번째 분봉 데이터:")
            print(json.dumps(all_data[0], indent=2, ensure_ascii=False))
        
        # 연속 조회 처리
        attempt = 0
        while (result['cont_yn'] == 'Y' and    # 연속 데이터가 있고
               result['next_key'] and          # 다음 키가 있고
               attempt < max_attempts):        # 최대 시도 횟수를 넘지 않았을 때
            
            # API 요청 제한 방지를 위한 지연
            time_module.sleep(request_delay)
            
            # 연속 조회 요청
            print(f"\n연속 데이터가 있습니다. 추가 데이터를 조회합니다...")
            try:
                result = fn_ka10080(
                    token=token, 
                    data=params, 
                    host=config.host, 
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
                        time_module.sleep(wait_time)
                    continue
                
                # 시도 횟수 초기화
                attempt = 0
                
                # 데이터 키 확인 및 처리
                if data_key in result and isinstance(result[data_key], list):
                    page_processed_data = []
                    
                    # ka10080 API 응답 처리
                    for item in result[data_key]:
                        if 'cntr_tm' in item:
                            timestamp = item['cntr_tm']
                            
                            # 14자리인 경우 (YYYYMMDDHHMMSS)
                            if len(timestamp) == 14:
                                date = timestamp[:8]      # YYYYMMDD
                                time_str = timestamp[8:14]    # HHMMSS
                                
                                # 기간 외 데이터 필터링
                                if date < start_date or (date == start_date and time_str < start_time):
                                    continue
                                    
                                if date > base_date or (date == base_date and time_str > base_time):
                                    continue
                                    
                                # 미래 데이터 필터링
                                today = get_today()
                                now = get_current_time()
                                
                                if date > today or (date == today and time_str > now):
                                    continue
                                    
                                # 프로세스된 데이터에 날짜 및 시간 필드 추가
                                item_copy = item.copy()
                                item_copy['date'] = date
                                item_copy['time'] = time_str
                                page_processed_data.append(item_copy)
                    
                    # 데이터 추가
                    all_data.extend(page_processed_data)
                    page_count += 1
                    print(f"페이지 {page_count} 수신: {len(page_processed_data)}개 분봉 데이터 (전체: {len(all_data)}개)")
                    
                    # 데이터가 더 이상 없는 경우
                    if len(page_processed_data) == 0:
                        print("더 이상 조회할 데이터가 없습니다.")
                        break
                    
                    # 모든 데이터를 가져왔는지 확인
                    if not result['cont_yn'] == 'Y' or not result['next_key']:
                        print("모든 데이터를 가져왔습니다.")
                        break
                else:
                    # 데이터 키가 없는 경우
                    print(f"연속 조회 응답에서 데이터 키({data_key})를 찾을 수 없습니다.")
                    print(f"응답 구조: {list(result.keys())}")
                    break
                    
            except Exception as e:
                print(f"연속 조회 중 오류 발생: {e}")
                attempt += 1
                if attempt >= max_attempts:
                    print(f"최대 재시도 횟수를 초과했습니다. 지금까지 수집된 데이터로 진행합니다.")
                    break
        
        # 4. 데이터 저장 및 반환
        if all_data:
            # 날짜/시간 필드 확인 및 처리
            if 'date' in all_data[0] and 'time' in all_data[0]:
                # 데이터 정렬 (날짜+시간 오름차순)
                all_data.sort(key=lambda x: (x['date'], x['time']))
                
                # 실제 조회된 데이터의 날짜 범위
                earliest_date = all_data[0]['date']
                earliest_time = all_data[0]['time']
                latest_date = all_data[-1]['date']
                latest_time = all_data[-1]['time']
                
                print(f"실제 조회된 기간: {earliest_date} {earliest_time} ~ {latest_date} {latest_time}")
            else:
                print("날짜 또는 시간 필드를 찾을 수 없습니다.")
                return None
            
            # 디렉토리 생성
            output_dir = 'output'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # 파일명을 일봉 데이터와 통일된 형식으로 생성
            # 형식: min{time_interval}_{stock_code}_{earliest_date}_{latest_date}.csv
            filename = os.path.join(output_dir, f'min{time_interval}_{stock_code}_{earliest_date}_{latest_date}.csv')
            original_filename = filename.replace('.csv', '_raw.csv')
            
            # 데이터 저장 - 전처리 적용
            saved_file, df = save_minute_data_to_csv(all_data, filename, code=stock_code, preprocess=True)
            
            if saved_file:
                print(f"\n{stock_code} 종목의 {time_interval}분봉 데이터가 저장되었습니다:")
                print(f"  - 전처리 데이터: {saved_file}")
                print(f"  - 원본 데이터: {saved_file.replace('.csv', '_raw.csv')}")
                
                # 데이터 반환
                return df
            else:
                print(f"{stock_code} 종목의 분봉 데이터 저장에 실패했습니다.")
        else:
            print(f"{stock_code} 종목의 분봉 데이터가 없습니다.")
        
        return None
    
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
	
	# period = '1d'    # 1일 데이터
	# period = '4h'    # 4시간 데이터
	# period = '30m'   # 30분 데이터
	
	period = '5d'     # 기본값: 1일 데이터
	
	# 분봉 간격 설정
	# time_interval = '1'   # 1분봉
	# time_interval = '3'   # 3분봉
	time_interval = '5'   # 5분봉
	# time_interval = '10'  # 10분봉
	# time_interval = '30'  # 30분봉
	# time_interval = '60'  # 60분봉
	
	# 분봉 데이터 조회 및 저장
	minute_data = get_minute_chart(stock_code, period, time_interval=time_interval)
	
	# 데이터 요약 출력
	if minute_data is not None and not minute_data.empty:
		print("\n=== 데이터 요약 ===")
		print(f"종목코드: {stock_code}")
		print(f"조회 기간: {period}")
		print(f"분봉 간격: {time_interval}분")
		print(f"행 수: {len(minute_data)}")
		print(f"컬럼: {', '.join(minute_data.columns)}")
		
		# 첫 5개 데이터 출력
		print("\n첫 5개 데이터:")
		print(minute_data.head())
