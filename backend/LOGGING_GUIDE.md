# ChartInsight 백엔드 로깅 시스템 가이드

## 📚 개요

이 문서는 ChartInsight 백엔드의 로깅 시스템을 설명합니다.
초보 개발자도 쉽게 이해하고 사용할 수 있도록 단순하고 명확하게 설계되었습니다.

---

## 🎯 로깅 시스템의 목적

로깅은 애플리케이션이 실행되는 동안 무슨 일이 일어나는지 기록하는 것입니다.

**왜 로그가 필요한가요?**
- 🐛 **디버깅**: 에러가 발생했을 때 원인을 찾을 수 있습니다
- 📊 **모니터링**: 시스템이 정상적으로 동작하는지 확인할 수 있습니다
- 📈 **분석**: 사용자 행동 패턴, 성능 병목 등을 분석할 수 있습니다
- 🔍 **감사**: 누가 언제 무엇을 했는지 추적할 수 있습니다

---

## 🏗️ 시스템 구조

### 중앙 집중식 로깅

```
app/main.py (앱 시작 시)
    ↓
setup_logging() 한 번 호출
    ↓
루트 로거 + 파일 핸들러 + 콘솔 핸들러 설정
    ↓
모든 모듈에서 logging.getLogger(__name__) 사용
```

**장점:**
- ✅ 설정이 한 곳에 집중되어 관리가 쉽습니다
- ✅ 모든 로그가 하나의 파일에 기록됩니다
- ✅ 로그 파일이 자동으로 롤오버됩니다 (크기 제한)
- ✅ 코드가 단순하고 이해하기 쉽습니다

---

## 📖 사용법

### 1. 앱 시작 시 (main.py)

```python
# app/main.py
from app.utils.logger_config import setup_logging

# 로깅 시스템 설정 (앱 시작 시 한 번만!)
setup_logging(log_level="INFO")
```

**파라미터 설명:**
- `log_level`: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
- `logs_dir`: 로그 파일 저장 디렉토리 (기본값: 프로젝트 루트/logs)
- `max_bytes`: 로그 파일 최대 크기 (기본값: 10MB)
- `backup_count`: 보관할 백업 파일 개수 (기본값: 5개)

### 2. 각 모듈에서 사용

```python
# app/analysis/trend.py (예시)
import logging

# 모듈명으로 로거 가져오기 (이것만 하면 됩니다!)
logger = logging.getLogger(__name__)

# 로그 남기기
logger.debug("디버깅용 상세 정보")
logger.info("일반 정보 메시지")
logger.warning("경고 메시지")
logger.error("에러 메시지")
logger.critical("치명적 에러")

# 예외 처리 시 스택 트레이스 자동 기록
try:
    # 위험한 작업
    result = 1 / 0
except Exception as e:
    logger.exception("나눗셈 오류 발생")  # 스택 트레이스가 자동으로 로그에 기록됨
```

---

## 📊 로그 레벨 설명

로그 레벨은 메시지의 심각도를 나타냅니다. 숫자가 높을수록 심각합니다.

| 레벨 | 숫자 | 용도 | 예시 |
|------|------|------|------|
| `DEBUG` | 10 | 개발 중 상세 정보 | "변수 x의 값: 42" |
| `INFO` | 20 | 정상 동작 정보 | "사용자 로그인 성공" |
| `WARNING` | 30 | 주의가 필요한 상황 | "캐시 만료됨, 재생성 중" |
| `ERROR` | 40 | 에러 발생 (복구 가능) | "파일을 찾을 수 없음" |
| `CRITICAL` | 50 | 치명적 에러 (복구 불가) | "데이터베이스 연결 실패" |

**예시:**
```python
logger.info("분석 시작: 심볼=005930, 기간=1y")  # 정상 동작
logger.warning("데이터가 부족합니다. 최소 100개 필요, 현재 50개")  # 주의
logger.error("패턴 분석 실패: 잘못된 입력 형식")  # 에러
```

---

## 📁 로그 파일 구조

### 파일 위치
```
ChartInsight-Studio/
└── logs/
    ├── chartinsight_20250103.log       # 오늘 날짜 로그
    ├── chartinsight_20250103.log.1     # 백업 1 (가장 최근)
    ├── chartinsight_20250103.log.2     # 백업 2
    ├── chartinsight_20250103.log.3     # 백업 3
    ├── chartinsight_20250103.log.4     # 백업 4
    └── chartinsight_20250103.log.5     # 백업 5 (가장 오래됨)
```

### 자동 로테이션

로그 파일이 10MB를 초과하면:
1. 현재 파일 → `.1`로 이름 변경
2. 기존 백업들은 숫자가 하나씩 증가 (`.1` → `.2`, `.2` → `.3`, ...)
3. 가장 오래된 백업(`.5`)은 삭제됨
4. 새로운 빈 로그 파일 생성

**장점:**
- 디스크 공간을 효율적으로 사용
- 오래된 로그는 자동으로 정리
- 수동 관리 불필요

---

## 🔍 로그 포맷

### 스마트 포맷팅 (새로운 기능!)

ChartInsight는 **스마트 포맷터**를 사용하여 로그 종류에 따라 다른 포맷을 자동으로 적용합니다.

#### 파일 로그 (스마트 포맷팅 적용)

**알고리즘 로직 로그** (app.analysis.* 모듈):
```
app.analysis.trend - INFO - [2023-08-29] State 0 -> 1 (하락 가설 시작)
app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial
```

**시스템 로그** (app.main, app.routers.* 등):
```
2025-01-03 14:23:45 - app.main - INFO - Request started: GET /api/v1/pattern-analysis
2025-01-03 14:23:45 - app.routers.pattern_analysis - INFO - Trading Radar 데이터 요청
```

**장점:**
- 알고리즘 로그: 실행 시각 제거 → 캔들 날짜 흐름에 집중
- 시스템 로그: 실행 시각 유지 → API 타이밍 추적 가능
- 자동 적용: 코드 변경 없이 작동

#### 콘솔 로그 (터미널)
```
INFO - 분석 시작: 005930, 1y
```

**이유:** 개발 중 터미널에서는 간단하게 표시하여 가독성을 높입니다.

#### 포맷 구분 기준
| 로거 이름 패턴 | 로그 종류 | 포맷 |
|---------------|----------|------|
| `app.analysis.*` | 알고리즘 로직 | 모듈명 + 레벨 + 메시지 |
| `app.main` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `app.routers.*` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `app.utils.*` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `root` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |

---

## 🛠️ 실전 예시

### 예시 1: API 엔드포인트

```python
# app/routers/pattern_analysis.py
import logging

logger = logging.getLogger(__name__)

@router.get("/patterns")
async def get_patterns(symbol: str):
    logger.info(f"패턴 요청: 심볼={symbol}")
    
    try:
        # 데이터 조회
        data = load_data(symbol)
        
        if data is None:
            logger.warning(f"데이터 없음: {symbol}")
            raise HTTPException(status_code=404, detail="데이터 없음")
        
        # 분석 실행
        patterns = analyze(data)
        logger.info(f"패턴 응답: {len(patterns)}개 발견")
        return patterns
        
    except HTTPException:
        raise  # HTTPException은 그대로 전달
    except Exception as e:
        # 예상치 못한 에러는 스택 트레이스와 함께 로그
        logger.exception("패턴 분석 중 예외 발생")
        raise HTTPException(status_code=500, detail="서버 오류")
```

### 예시 2: 분석 엔진

```python
# app/analysis/run_full_analysis.py
import logging

logger = logging.getLogger(__name__)

def run_full_analysis(data, ticker, period):
    logger.info(f"분석 시작: 티커={ticker}, 기간={period}, 데이터={len(data)}행")
    
    if len(data) < 10:
        logger.warning(f"데이터 부족: {len(data)}행 (최소 10행 필요)")
        return {"error": "데이터 부족"}
    
    start_time = time.time()
    
    # 분석 수행
    detector = TrendDetector()
    for i, row in enumerate(data):
        detector.process(row)
        
        # 진행 상황 로그 (너무 자주 찍지 않도록 100개마다)
        if i % 100 == 0:
            logger.debug(f"진행: {i}/{len(data)} ({i/len(data)*100:.1f}%)")
    
    elapsed = time.time() - start_time
    logger.info(f"분석 완료: 소요시간={elapsed:.2f}초")
    
    return results
```

---

## 🐛 디버깅 팁

### 1. 로그 레벨 조정

**개발 중:**
```python
setup_logging(log_level="DEBUG")  # 모든 로그 출력
```

**운영 환경:**
```python
setup_logging(log_level="INFO")   # 중요한 로그만
```

### 2. 로그 확인하기

```bash
# 최신 로그 파일 보기
tail -f logs/chartinsight_20250103.log

# 에러만 필터링
grep ERROR logs/chartinsight_20250103.log

# 특정 모듈 로그만 보기
grep "app.analysis.trend" logs/chartinsight_20250103.log
```

### 3. 예외 처리 모범 사례

```python
# ❌ 나쁜 예
try:
    result = do_something()
except Exception as e:
    logger.error(str(e))  # 스택 트레이스가 없어서 디버깅 어려움

# ✅ 좋은 예
try:
    result = do_something()
except Exception as e:
    logger.exception("작업 실패")  # 스택 트레이스가 자동으로 기록됨
```

---

## ⚠️ 주의사항

### 1. 민감한 정보 로그 금지

```python
# ❌ 절대 안 됨!
logger.info(f"사용자 로그인: password={password}")

# ✅ 안전한 방법
logger.info(f"사용자 로그인: user_id={user_id}")
```

### 2. 과도한 로그 지양

```python
# ❌ 너무 많은 로그
for i in range(10000):
    logger.debug(f"처리 중: {i}")  # 10,000개 로그!

# ✅ 적절한 로그
logger.info("대량 처리 시작: 10,000건")
for i in range(10000):
    if i % 1000 == 0:  # 1,000개마다 한 번만
        logger.debug(f"진행: {i}/10,000")
logger.info("대량 처리 완료")
```

### 3. 로그는 사용자에게 보이지 않습니다

```python
# ❌ 로그를 사용자 메시지로 착각
logger.info("처리 완료되었습니다!")  # 사용자는 못 봄

# ✅ 올바른 방법
logger.info("처리 완료: 결과 반환")
return {"message": "처리 완료되었습니다!"}  # 사용자에게 전달
```

---

## 🔧 문제 해결

### Q1: 로그가 파일에 기록되지 않아요!

**A:** `setup_logging()`이 `main.py`에서 호출되었는지 확인하세요.

```python
# app/main.py
from app.utils.logger_config import setup_logging

setup_logging(log_level="INFO")  # 이게 있어야 합니다!
```

### Q2: 로그 파일이 너무 커져요!

**A:** 로그 레벨을 높이거나 파일 크기 제한을 조정하세요.

```python
setup_logging(
    log_level="WARNING",      # INFO 대신 WARNING 사용
    max_bytes=5*1024*1024,    # 5MB로 줄이기
    backup_count=3            # 백업 3개만 유지
)
```

### Q3: 예전 로그를 보고 싶어요!

**A:** 백업 파일을 확인하세요.

```bash
# 모든 로그 파일 보기
ls -lh logs/

# 백업 파일 내용 보기
cat logs/chartinsight_20250103.log.1
```

---

## 📚 참고 자료

- [Python logging 공식 문서](https://docs.python.org/3/library/logging.html)
- [Python logging 튜토리얼](https://docs.python.org/3/howto/logging.html)
- [로깅 베스트 프랙티스](https://docs.python-guide.org/writing/logging/)

---

## 🎓 학습 포인트

**초보 개발자가 기억해야 할 것:**

1. ✅ `setup_logging()`은 `main.py`에서 한 번만 호출
2. ✅ 각 모듈에서는 `logger = logging.getLogger(__name__)` 사용
3. ✅ 예외 처리 시 `logger.exception()` 사용
4. ✅ 적절한 로그 레벨 선택 (DEBUG < INFO < WARNING < ERROR < CRITICAL)
5. ✅ 민감한 정보는 절대 로그에 남기지 않기

**이것만 기억하면 됩니다!** 🎉

