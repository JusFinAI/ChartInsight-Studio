import requests
import json

# 종목정보 리스트
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

    ---

Request Body

{
	"mrkt_tp" : "0"
}

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
