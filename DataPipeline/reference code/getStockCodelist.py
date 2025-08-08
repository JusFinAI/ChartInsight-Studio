import requests
import json
import pandas as pd
import os
from datetime import datetime
from config import load_settings
from OAuth import fn_au10001

# 종목 코드 리스트 API 호출 함수 (ka10099)
def fn_ka10099(token, data, host=None, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	if host is None:
		host = 'https://mockapi.kiwoom.com'  # 기본값 모의투자
		
	endpoint = '/api/dostk/stkinfo'
	url = host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10099', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드 및 헤더 일부 출력 (디버깅용, 필요시 주석 해제)
	# print('Code:', response.status_code)
	# print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	
	if response.status_code != 200:
		print(f"API 요청 실패: {response.status_code}")
		print(f"응답 내용: {response.text}")
		return {'list': [], 'next_key': '', 'cont_yn': 'N', 'return_code': response.status_code, 'return_msg': 'API 요청 실패'}

	result = response.json()
	
	# 연속 조회를 위한 헤더 정보 추가
	result['next_key'] = response.headers.get('next-key', '')
	result['cont_yn'] = response.headers.get('cont-yn', 'N')
	
	return result

# CSV 파일로 저장하는 함수
def save_to_csv(data, filename):
	if not data:
		print("저장할 데이터가 없습니다 (CSV).")
		return None
	df = pd.DataFrame(data)
	df.to_csv(filename, encoding='utf-8-sig', index=False)
	print(f"CSV 파일 저장 완료: {filename}")
	return filename

# JSON 파일로 저장하는 함수 ({코드:종목명} 형식)
def save_to_json_dict(data, filename):
	if not data:
		print(f"저장할 데이터가 없습니다 (JSON - {filename}).")
		return None
	
	# 제외할 키 목록
	exclude_keys = ['marketName', 'marketOrigin', 'companyClassName', 'lastPrice', 'listCount']
	
	json_data_dict = {}
	for item in data:
		if item.get('code') and item.get('name'): # 코드와 이름이 있는지 먼저 확인
			# 제외할 키를 뺀 새로운 딕셔너리 생성
			filtered_item_details = {k: v for k, v in item.items() if k not in exclude_keys}
			json_data_dict[item.get('code')] = filtered_item_details
	
	with open(filename, 'w', encoding='utf-8') as f:
		json.dump(json_data_dict, f, ensure_ascii=False, indent=2)
	print(f"JSON 파일 저장 완료: {filename} ({len(json_data_dict)}개 항목)")
	return filename

# 실행 구간
if __name__ == '__main__':
	config = load_settings()
	
	auth_params = {
		'grant_type': 'client_credentials',
		'appkey': config['app_key'],
		'secretkey': config['secret_key'],
	}
	
	token = fn_au10001(data=auth_params, host=config['host'])
	if not token:
		print("토큰 발급 실패. 스크립트를 종료합니다.")
		exit()
		
	print(f"발급받은 토큰으로 종목 코드 리스트를 조회합니다...")

	# 조회할 시장 정의 (코스피: 0, 코스닥: 10)
	# ETF(8)는 이번 요청에서 제외
	markets_to_fetch = [
		{'param_code': '0', 'target_market_code': '0', 'market_label': 'KOSPI'}, # API 요청용 mrkt_tp, 필터링용 marketCode, 파일명/로그용 레이블
		{'param_code': '10', 'target_market_code': '10', 'market_label': 'KOSDAQ'}
	]

	all_stock_items_combined = [] # 모든 시장의 모든 종목을 합쳐서 담을 리스트
	kospi_items_filtered = []
	kosdaq_items_filtered = []

	output_dir = 'output'
	if not os.path.exists(output_dir):
		os.makedirs(output_dir)

	for market_info in markets_to_fetch:
		print(f"--- {market_info['market_label']} 종목 조회 시작 (mrkt_tp: {market_info['param_code']}) ---")
		params = {'mrkt_tp': market_info['param_code']}
		current_market_items_api = [] # 현재 시장 API 호출로 가져온 모든 아이템
		page_count = 0
		
		next_key_val = ''
		cont_yn_val = 'N' # 첫 요청시는 N 또는 빈 값

		while True:
			result = fn_ka10099(token=token, data=params, host=config['host'], 
								cont_yn=cont_yn_val, next_key=next_key_val)
			
			page_count += 1
			
			if 'list' in result and result['list']:
				received_count = len(result['list'])
				print(f"페이지 {page_count} ({market_info['market_label']}) 수신: {received_count}개 항목")
				for item in result['list']:
					# API 응답 내 marketCode를 기준으로 정확히 필터링
					# 또한, code와 name이 유효한지 확인
					if item.get('code') and item.get('name') and item.get('marketCode') == market_info['target_market_code']:
						item['marketOrigin'] = market_info['market_label'] # 출처 시장 정보 추가
						current_market_items_api.append(item)
				
				# 모든 종목을 저장하기 위해 all_stock_items_combined에도 추가 (필터링 된 것만)
				all_stock_items_combined.extend([i for i in current_market_items_api if i not in all_stock_items_combined])


			else: # 'list' 키가 없거나 비어있는 경우
				print(f"페이지 {page_count} ({market_info['market_label']}) 수신: 데이터 없음 또는 API 오류 (return_code: {result.get('return_code')}, msg: {result.get('return_msg')})")


			next_key_val = result.get('next_key', '')
			cont_yn_val = result.get('cont_yn', 'N')

			if cont_yn_val != 'Y' or not next_key_val:
				print(f"--- {market_info['market_label']} 종목 조회 완료 (총 {len(current_market_items_api)}개 필터링) ---")
				break
			
			print(f"연속 데이터 조회 (next_key: {next_key_val})")

		# 시장별로 필터링된 데이터 저장
		if market_info['market_label'] == 'KOSPI':
			kospi_items_filtered.extend(current_market_items_api)
		elif market_info['market_label'] == 'KOSDAQ':
			kosdaq_items_filtered.extend(current_market_items_api)
			
	# 4. 데이터 종합 및 저장
	print(f"=== 최종 데이터 저장 ===")
	print(f"전체 수집된 유효 종목 수 (KOSPI+KOSDAQ, 중복제거 가정): {len(all_stock_items_combined)}")
	
	if all_stock_items_combined:
		today = datetime.now().strftime('%Y%m%d')
		csv_filename = os.path.join(output_dir, f'stock_codes_{today}.csv')
		save_to_csv(all_stock_items_combined, csv_filename)
	else:
		print("CSV로 저장할 전체 종목 데이터가 없습니다.")

	# 코스피 종목 JSON 저장
	if kospi_items_filtered:
		kospi_json_filename = os.path.join(output_dir, 'kospi_code.json')
		save_to_json_dict(kospi_items_filtered, kospi_json_filename)
	else:
		print("저장할 KOSPI 종목 데이터가 없습니다.")

	# 코스닥 종목 JSON 저장
	if kosdaq_items_filtered:
		kosdaq_json_filename = os.path.join(output_dir, 'kosdaq_code.json')
		save_to_json_dict(kosdaq_items_filtered, kosdaq_json_filename)
	else:
		print("저장할 KOSDAQ 종목 데이터가 없습니다.")
		
	print("스크립트 실행 완료.")