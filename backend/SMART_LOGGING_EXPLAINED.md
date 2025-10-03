# 스마트 로깅 시스템 설명

## 🎯 핵심 개념

ChartInsight의 로깅 시스템은 **두 가지 종류의 로그**를 구분하여 처리합니다:

1. **알고리즘 로직 로그** - 캔들 데이터 흐름 추적
2. **시스템 로그** - 실행 타이밍 추적

---

## 📊 로그 포맷 비교

### 변경 전 (모든 로그에 실행 시각)

```
2025-10-03 15:58:49 - app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial
2025-10-03 15:58:49 - app.main - INFO - Request started: GET /api/v1/pattern-analysis
```

**문제점:**
- 알고리즘 디버깅 시 `2025-10-03 15:58:49`가 불필요 (캔들 날짜 `[2023-09-25]`가 중요)
- 로그가 길어져서 가독성 저하

### 변경 후 (스마트 포맷)

```
app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial
2025-10-03 15:58:49 - app.main - INFO - Request started: GET /api/v1/pattern-analysis
```

**개선점:**
- 알고리즘 로그: 실행 시각 제거 → 캔들 흐름에 집중 ✨
- 시스템 로그: 실행 시각 유지 → 타이밍 추적 가능 ✅

---

## 🏗️ 작동 원리

### SmartFormatter 클래스

```python
class SmartFormatter(logging.Formatter):
    """로그 종류에 따라 다른 포맷 적용"""
    
    def format(self, record):
        # 로거 이름 확인
        if 'app.analysis' in record.name:
            # 알고리즘 로그 → 실행 시각 제거
            return "%(name)s - %(levelname)s - %(message)s"
        else:
            # 시스템 로그 → 실행 시각 포함
            return "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 분류 기준

| 로거 이름 패턴 | 로그 종류 | 포맷 |
|---------------|----------|------|
| `app.analysis.*` | 알고리즘 로직 | 모듈명 + 레벨 + 메시지 |
| `app.main` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `app.routers.*` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `app.utils.*` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |
| `root` | 시스템 | 시각 + 모듈명 + 레벨 + 메시지 |

---

## 📝 실제 로그 예시

### 1. 알고리즘 로직 로그 (실행 시각 없음)

```
app.analysis.run_full_analysis - INFO - 데이터 분석 시작: 500 행, 티커=005930
app.analysis.trend - INFO - [2023-08-29] State 0 -> 1 (하락 가설 시작)
app.analysis.trend - INFO - [2023-08-30] State 1(down) -> State 1(up) (방향 전환)
app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial -> Reentry
app.analysis.patterns.pattern_manager - WARNING - add_detector 대체 동작
```

**장점:**
- 캔들 날짜 `[2023-08-29]`, `[2023-08-30]`에 집중
- 불필요한 `2025-10-03 15:58:49` 제거
- 가독성 향상 📈

### 2. 시스템 로그 (실행 시각 포함)

```
2025-10-03 15:57:49 - root - INFO - 로깅 시스템 초기화 완료
2025-10-03 15:58:49 - app.main - INFO - Request 53fce067 started: GET /api/v1/pattern-analysis
2025-10-03 15:58:49 - app.routers.pattern_analysis - INFO - Trading Radar 데이터 요청
2025-10-03 15:58:49 - app.main - INFO - Request 53fce067 completed: 200 - 0.154 sec
```

**장점:**
- API 요청 타이밍 추적 가능
- 시스템 초기화 시간 기록
- 성능 분석 용이 ⏱️

---

## 🎓 왜 이렇게 설계했나요?

### 알고리즘 디버깅 시나리오

**문제 상황:** "2023년 9월 25일에 Double Bottom 패턴이 왜 리셋되었을까?"

**변경 전:**
```
2025-10-03 15:58:49 - app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial
2025-10-03 15:58:49 - app.analysis.trend - INFO - [2023-09-26] State 1(up) -> State 0
2025-10-03 15:58:49 - app.analysis.patterns.base - INFO - [2025-10-03] DB-230922 감지기 리셋
```
→ `2025-10-03 15:58:49`가 반복되어 혼란스러움 😵

**변경 후:**
```
app.analysis.patterns.base - INFO - [2023-09-25] DB-230922 Stage Initial
app.analysis.trend - INFO - [2023-09-26] State 1(up) -> State 0
app.analysis.patterns.base - INFO - [2025-10-03] DB-230922 감지기 리셋
```
→ 캔들 날짜 흐름이 명확하게 보임 ✨

### 시스템 디버깅 시나리오

**문제 상황:** "API 응답이 느려졌는데, 어느 시점부터 느려졌을까?"

```
2025-10-03 15:58:49 - app.main - INFO - Request A started
2025-10-03 15:58:49 - app.main - INFO - Request A completed: 0.154 sec  ← 빠름
2025-10-03 16:05:32 - app.main - INFO - Request B started
2025-10-03 16:05:38 - app.main - INFO - Request B completed: 6.234 sec  ← 느림!
```
→ 실행 시각으로 성능 변화 추적 가능 📊

---

## 🔍 고급 기능 (선택사항)

### 더 세밀한 제어가 필요하면?

`SmartFormatter`를 수정하여 조건을 추가할 수 있습니다:

```python
def format(self, record):
    # 1. 알고리즘 로직 (실행 시각 제거)
    if 'app.analysis' in record.name:
        return self.algorithm_fmt.format(record)
    
    # 2. 데이터 로더 (실행 시각 제거)
    if 'data_loader' in record.name:
        return self.algorithm_fmt.format(record)
    
    # 3. 특정 메시지 패턴 (예: 캔들 날짜 포함)
    if '[20' in record.getMessage():  # [2023-09-25] 같은 패턴
        return self.algorithm_fmt.format(record)
    
    # 4. 나머지는 시스템 로그
    return self.default_fmt.format(record)
```

**하지만 현재 구현으로 충분합니다!** 단순함이 유지보수의 핵심입니다. 🎯

---

## ⚠️ 주의사항

### 1. 알고리즘 로그에서 실행 시각이 필요한 경우

만약 알고리즘 로그에도 실행 시각이 필요한 특별한 경우라면, 메시지에 직접 포함하세요:

```python
from datetime import datetime

logger.info(f"[실행시각: {datetime.now().strftime('%H:%M:%S')}] 분석 완료")
```

### 2. 새 모듈 추가 시

- `app.analysis.*` 하위에 모듈을 추가하면 자동으로 알고리즘 포맷 적용
- 다른 위치에 추가하면 자동으로 시스템 포맷 적용

### 3. 콘솔 출력

콘솔은 여전히 간단한 포맷 사용:
```
INFO - 로그 메시지
```

파일 로그만 스마트 포맷이 적용됩니다.

---

## 📚 참고

### 관련 파일
- `backend/app/utils/logger_config.py` - SmartFormatter 구현
- `backend/LOGGING_GUIDE.md` - 전체 로깅 가이드
- `backend/LOGGING_CHANGES.md` - 변경사항 요약

### Python logging 공식 문서
- [Formatter Objects](https://docs.python.org/3/library/logging.html#formatter-objects)
- [LogRecord attributes](https://docs.python.org/3/library/logging.html#logrecord-attributes)

---

## 🎉 요약

**핵심 아이디어:**
- 알고리즘 로그 = 캔들 날짜 흐름이 중요 → 실행 시각 제거
- 시스템 로그 = 실행 타이밍이 중요 → 실행 시각 유지

**구현 방법:**
- `SmartFormatter` 클래스로 로거 이름 기반 자동 분류
- `app.analysis.*` 모듈은 자동으로 알고리즘 포맷 적용

**효과:**
- 로그 가독성 대폭 향상 📈
- 디버깅 효율 증가 🐛
- 코드 변경 불필요 (자동 적용) ✨

**이것만 기억하세요:**
각 모듈에서 `logger = logging.getLogger(__name__)`만 쓰면, 
나머지는 자동으로 알맞은 포맷이 적용됩니다! 🎯

