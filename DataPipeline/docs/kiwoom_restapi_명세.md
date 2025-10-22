
# 1. ka10099 종목정보리스트

```
import requests
import json

# 1.1 종목정보 리스트
def fn_ka10099(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/stkinfo'
	url =  host + endpoint

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

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = '사용자 AccessToken' # 접근토큰

	# 2. 요청 데이터
	params = {
		'mrkt_tp': '0', # 시장구분 0:코스피,10:코스닥,3:ELW,8:ETF,30:K-OTC,50:코넥스,5:신주인수권,4:뮤추얼펀드,6:리츠,9:하이일드
	}

	# 3. API 실행
	fn_ka10099(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10099(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

```
---

Request Body

{
	"mrkt_tp" : "0"
}
---
Response Body

{
	"return_msg":"정상적으로 처리되었습니다",
	"return_code":0,
	"list":
		[
			{
				"code":"005930",
				"name":"삼성전자",
				"listCount":"0000000123759593",
				"auditInfo":"투자주의환기종목",
				"regDay":"20091204",
				"lastPrice":"00000197",
				"state":"관리종목",
				"marketCode":"10",
				"marketName":"코스닥",
				"upName":"",
				"upSizeName":"",
				"companyClassName":"",
				"orderWarning":"0",
				"nxtEnable":"Y"
			},
			{
				"code":"005930",
				"name":"삼성전자",
				"listCount":"0000000136637536",
				"auditInfo":"정상",
				"regDay":"20100423",
				"lastPrice":"00000213",
				"state":"증거금100%",
				"marketCode":"10",
				"marketName":"코스닥",
				"upName":"",
				"upSizeName":"",
				"companyClassName":"외국기업",
				"orderWarning":"0",
				"nxtEnable":"Y"
			},
			{
				"code":"005930",
				"name":"삼성전자",
				"listCount":"0000000080000000",
				"auditInfo":"정상",
				"regDay":"20160818",
				"lastPrice":"00000614",
				"state":"증거금100%",
				"marketCode":"10",
				"marketName":"코스닥",
				"upName":"",
				"upSizeName":"",
				"companyClassName":"외국기업",
				"orderWarning":"0",
				"nxtEnable":"Y"
			},
			{
				"code":"005930",
				"name":"삼성전자",
				"listCount":"0000000141781250",
				"auditInfo":"정상",
				"regDay":"20160630",
				"lastPrice":"00000336",
				"state":"증거금100%",
				"marketCode":"10",
				"marketName":"코스닥",
				"upName":"",
				"upSizeName":"",
				"companyClassName":"외국기업",
				"orderWarning":"0",
				"nxtEnable":"Y"
			},
			{
				"code":"005930",
				"name":"삼성전자",
				"listCount":"0000000067375000",
				"auditInfo":"투자주의환기종목",
				"regDay":"20161025",
				"lastPrice":"00000951",
				"state":"관리종목",
				"marketCode":"10",
				"marketName":"코스닥",
				"upName":"",
				"upSizeName":"",
				"companyClassName":"",
				"orderWarning":"0",
				"nxtEnable":"Y"
			}
		]
}

--- 

```
2. ka10101 업종코드 리스트 

import requests
import json

# 업종코드 리스트
def fn_ka10101(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/stkinfo'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10101', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = '사용자 AccessToken' # 접근토큰

	# 2. 요청 데이터
	params = {
		'mrkt_tp': '0', # 시장구분 0:코스피(거래소),1:코스닥,2:KOSPI200,4:KOSPI100,7:KRX100(통합지수)
	}

	# 3. API 실행
	fn_ka10101(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10101(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')
```

---

Request Body

{
	"mrkt_tp": "0"
}
---
Response Body

{
	"return_msg":"정상적으로 처리되었습니다",
	"list":
		[
			{
				"marketCode":"0",
				"code":"001",
				"name":"종합(KOSPI)",
				"group":"1"
			},
			{
				"marketCode":"0",
				"code":"002",
				"name":"대형주",
				"group":"2"
			},
			{
				"marketCode":"0",
				"code":"003",
				"name":"중형주",
				"group":"3"
			},
			{
				"marketCode":"0",
				"code":"004",
				"name":"소형주",
				"group":"4"
			},
			{
				"marketCode":"0",
				"code":"005",
				"name":"음식료업",
				"group":"5"
			},
			{
				"marketCode":"0",
				"code":"006",
				"name":"섬유의복",
				"group":"6"
			},
			{
				"marketCode":"0",
				"code":"007",
				"name":"종이목재",
				"group":"7"
			},
			{
				"marketCode":"0",
				"code":"008",
				"name":"화학",
				"group":"8"
			},
			{
				"marketCode":"0",
				"code":"009",
				"name":"의약품",
				"group":"9"
			},
			{
				"marketCode":"0",
				"code":"010",
				"name":"비금속광물",
				"group":"10"
			},
			{
				"marketCode":"0",
				"code":"011",
				"name":"철강금속",
				"group":"11"
			}
		],
	"return_code":0
}

---

# 3. ka20008 (업종월봉조회요청) 

```
import requests
import json

# 업종월봉조회요청
def fn_ka20008(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/chart'
	url =  host + endpoint

	# 2. header 데이터
	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka20008', # TR명
	}

	# 3. http POST 요청
	response = requests.post(url, headers=headers, json=data)

	# 4. 응답 상태 코드와 데이터 출력
	print('Code:', response.status_code)
	print('Header:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = '사용자 AccessToken' # 접근토큰

	# 2. 요청 데이터
	params = {
		'inds_cd': '002', # 업종코드 001:종합(KOSPI), 002:대형주, 003:중형주, 004:소형주 101:종합(KOSDAQ), 201:KOSPI200, 302:KOSTAR, 701: KRX100 나머지 ※ 업종코드 참고
		'base_dt': '20250905', # 기준일자 YYYYMMDD
	}

	# 3. API 실행
	fn_ka20008(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka20008(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')
```

---

	Request Body

	{
		"inds_cd" : "002",
		"base_dt" : "20250905"
	}

---
Response Body

{
    "inds_cd": "002",
    "inds_mth_pole_qry": [
        {
            "cur_prc": "405407",
            "trde_qty": "366",
            "dt": "20250917",
            "open_pric": "380658",
            "high_pric": "425533",
            "low_pric": "345789",
            "trde_prica": "61127"
        },
        {
            "cur_prc": "251506",
            "trde_qty": "706969",
            "dt": "20250203",
            "open_pric": "246210",
            "high_pric": "253343",
            "low_pric": "243269",
            "trde_prica": "47770055"
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}

---
# 4. ka10083 (주식월봉차트조회요청) 

```
import requests
import json

# 주식월봉차트조회요청
def fn_ka10083(token, data, cont_yn='N', next_key=''):
	# 1. 요청할 API URL
	#host = 'https://mockapi.kiwoom.com' # 모의투자
	host = 'https://api.kiwoom.com' # 실전투자
	endpoint = '/api/dostk/chart'
	url =  host + endpoint

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
	print('Body:', json.dumps(response.json(), indent=4, ensure_ascii=False))  # JSON 응답을 파싱하여 출력

# 실행 구간
if __name__ == '__main__':
	# 1. 토큰 설정
	MY_ACCESS_TOKEN = '사용자 AccessToken' # 접근토큰

	# 2. 요청 데이터
	params = {
		'stk_cd': '005930', # 종목코드 거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)
		'base_dt': '20250905', # 기준일자 YYYYMMDD
		'upd_stkpc_tp': '1', # 수정주가구분 0 or 1
	}

	# 3. API 실행
	fn_ka10083(token=MY_ACCESS_TOKEN, data=params)

	# next-key, cont-yn 값이 있을 경우
	# fn_ka10083(token=MY_ACCESS_TOKEN, data=params, cont_yn='Y', next_key='nextkey..')

```
---
Request Body

{
	"stk_cd": "005930",
	"base_dt": "20250905",
	"upd_stkpc_tp": "1"
}
---
Response Body

{
    "stk_cd": "005930",
    "stk_mth_pole_chart_qry": [
        {
            "cur_prc": "78900",
            "trde_qty": "215040968",
            "trde_prica": "15774571011618",
            "dt": "20250901",
            "open_pric": "68400",
            "high_pric": "79500",
            "low_pric": "67500",
            "pred_pre": "+9200",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+3.38"
        },
        {
            "cur_prc": "69700",
            "trde_qty": "258905351",
            "trde_prica": "18306059690160",
            "dt": "20250804",
            "open_pric": "69500",
            "high_pric": "72400",
            "low_pric": "68300",
            "pred_pre": "+13600",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+4.37"
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}