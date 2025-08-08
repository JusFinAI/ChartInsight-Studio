# ChartInsight Studio API

차트 패턴 분석 및 트레이딩 전략 백테스팅을 위한 FastAPI 기반 백엔드 서비스입니다.

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

## 실행 방법

1. 루트 디렉토리에서 다음 명령어로 서버 실행:
```bash
uvicorn app.main:app --reload
```

서버는 기본적으로 http://localhost:8000 에서 실행됩니다.

## API 문서

API 문서는 다음 URL에서 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 엔드포인트

- `/api/v1/pattern-analysis/analyze`: 차트 패턴 분석 수행
- `/api/v1/pattern-analysis/symbols/popular`: 인기 주식 심볼 목록
- `/api/v1/pattern-analysis/periods`: 사용 가능한 기간 목록
- `/api/v1/pattern-analysis/intervals`: 사용 가능한 간격 목록

## 사용 예시

```python
import requests
import json

# 패턴 분석 요청
response = requests.post(
    "http://localhost:8000/api/v1/pattern-analysis/analyze",
    json={
        "symbol": "AAPL",
        "period": "1y",
        "interval": "1d"
    }
)

# 결과 출력
data = response.json()
print(json.dumps(data, indent=2))
``` 