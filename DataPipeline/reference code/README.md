# 키움증권 REST API 예제 코드

이 폴더에는 키움증권 REST API를 사용하여 주식 데이터를 조회하는 다양한 예제 코드가 포함되어 있습니다.

## 설치 방법

1. 필요한 패키지 설치
```
pip install -r requirements.txt
```

2. settings.yaml 파일 설정
- `environment`: `paper`(모의투자) 또는 `real`(실전투자) 선택
- API 키 및 시크릿 키 설정 (발급 받은 키를 입력하세요)

## 예제 파일 설명

1. **OAuth.py**: 접근 토큰 발급
   - 사용 예: `python OAuth.py`

2. **getStockCodelist.py**: 종목 코드 목록 조회
   - 사용 예: `python getStockCodelist.py`

3. **getStockDailyChart.py**: 주식 일봉 차트 조회
   - 사용 예: `python getStockDailyChart.py`

4. **getStockWeeklyChart.py**: 주식 주봉 차트 조회
   - 사용 예: `python getStockWeeklyChart.py`

5. **getStockMinuteChart.py**: 주식 분봉 차트 조회
   - 사용 예: `python getStockMinuteChart.py`

## 파라미터 수정 방법

각 예제 파일의 메인 실행 구간에서 다음 설정을 수정할 수 있습니다:

```python
# getStockDailyChart.py 예시
params = {
    'stk_cd': '005930',      # 종목코드 (삼성전자)
    'base_dt': get_today(),  # 기준일자
    'upd_stkpc_tp': '1',     # 수정주가구분 (1: 수정주가)
}
```

## 주의사항

1. API 호출 시 과도한 요청은 제한될 수 있습니다.
2. 실전투자 환경에서 테스트할 경우 주의하세요.
3. 토큰은 일정 시간 후 만료되며, 필요시 재발급 받아야 합니다. 