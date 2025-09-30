# 🚀 차트 패턴 분석기 로깅 시스템 가이드 (초보자용)

안녕하세요! 이 프로젝트의 로깅 시스템을 초보자도 쉽게 이해할 수 있도록 설명해드릴게요.

## 📋 목차
1. [로깅이 무엇인가요?](#로깅이-무엇인가요)
2. [왜 로깅이 필요할까요?](#왜-로깅이-필요할까요)
3. [이 프로젝트의 로깅 구조](#이-프로젝트의-로깅-구조)
4. [로그 파일 보는 방법](#로그-파일-보는-방법)
5. [로그 레벨 이해하기](#로그-레벨-이해하기)
6. [실제 사용 예시](#실제-사용-예시)
7. [문제 해결 팁](#문제-해결-팁)

## 🔍 로깅이 무엇인가요?

**로깅**은 프로그램이 실행되는 동안 일어나는 일들을 기록하는 일기장 같은 거예요.

```python
# 예를 들어 이런 식으로 사용해요:
logger.info("데이터 분석 시작!")           # "정보"를 기록
logger.warning("이상한 데이터 발견!")       # "주의"사항을 기록
logger.error("데이터베이스 연결 실패!")     # "오류"를 기록
```

## 💡 왜 로깅이 필요할까요?

1. **프로그램 추적**: "내 프로그램이 지금 무엇을 하고 있지?"라고 물을 수 있어요
2. **오류 찾기**: 문제가 생겼을 때 "왜?"라는 답을 찾을 수 있어요
3. **성능 확인**: "얼마나 오래 걸렸지?"라고 확인할 수 있어요
4. **학습 도구**: 초보자가 코드가 어떻게 실행되는지 배울 수 있어요

## 🏗️ 이 프로젝트의 로깅 구조

### 1. 핵심 파일: `logger_config.py`
이 파일이 로깅 시스템의 **중앙 관리자** 역할을 해요.

### 2. 로그 파일들이 저장되는 곳
```
logs/
├── dash_app_db_날짜시간.log          # 웹 대시보드 로그
├── backend_events_날짜시간.log       # 공통 백엔드 로그 (patterns.py, trend.py, run_full_analysis.py)
└── 기타 개별 모듈 로그들...
```

### 3. 각 모듈의 로거들

#### **공통 백엔드 로거 (권장)**
```python
# patterns.py, trend.py, run_full_analysis.py에서 사용
logger = logging.getLogger('backend')  # backend_events.log 파일에 기록됨
```

#### **개별 모듈 로거들**
- **대시보드 로거**: `chartinsight.dashboard` (dash_app_db.log)
- **분석 로거**: `backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis` (개별 로그 파일)

## 📖 로그 파일 보는 방법

### 1. 파일 직접 열기
```bash
# logs 폴더로 이동
cd backend/_temp_integration/chart_pattern_analyzer_kiwoom_db/logs

# 최신 로그 파일 찾기
ls -la *.log

# 로그 파일 내용 보기
tail -f chart_pattern_analysis_20240929_143000.log
```

### 2. 코드에서 로그 확인
프로그램 실행 중에 콘솔(터미널)에서도 로그를 볼 수 있어요:
```
INFO - 데이터 분석 시작: 1000 행
DEBUG - 패턴 인식 중...
WARNING - 이상 데이터 발견: 행 456
```

## 📊 로그 레벨 이해하기

| 레벨 | 숫자 | 언제 사용? | 예시 |
|-------|------|-----------|------|
| **DEBUG** | 10 | 매우 자세한 정보 (개발할 때) | "변수 값: 42" |
| **INFO** | 20 | 일반적인 정보 (기본) | "분석 시작!" |
| **WARNING** | 30 | 주의사항 | "메모리 부족" |
| **ERROR** | 40 | 오류 발생 | "파일 읽기 실패" |
| **CRITICAL** | 50 | 심각한 오류 | "시스템 다운" |

## 💻 실제 사용 예시

### 1. 공통 백엔드 로거 사용법 (권장)
```python
import logging

# 공통 백엔드 로거 사용 (main_dashboard.py에서 이미 설정됨)
logger = logging.getLogger('backend')  # backend_events.log에 기록

# 로그 작성
logger.info("프로그램 시작!")
logger.warning("주의: 데이터가 많아요")
logger.error("오류 발생!")
```

### 2. 개별 모듈 로거 사용법 (필요시)
```python
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import configure_logger

# 개별 로거 설정
logger = configure_logger("my_module", log_file_prefix="my_app", logs_dir="./logs")

# 로그 작성
logger.info("프로그램 시작!")
logger.warning("주의: 데이터가 많아요")
logger.error("오류 발생!")
```

### 2. 동적 레벨 변경
```python
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import set_logger_level

# 더 자세한 로그가 필요할 때
set_logger_level("my_module", logging.DEBUG)
```

### 3. 추가 로그 파일 연결
```python
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import add_file_handler

# 특별한 로그를 별도 파일에 저장
add_file_handler("my_module", "special_logs", "./logs")
```

## 🔧 문제 해결 팁

### Q1: 로그가 안 보여요!
**A**: 로그 레벨을 확인해보세요. DEBUG는 INFO보다 자세한 정보예요.
```python
# 더 자세한 로그 보기
set_logger_level("모듈명", logging.DEBUG)
```

### Q2: 로그 파일이 너무 많아요!
**A**: 오래된 로그 파일을 정리해보세요.
```bash
# 7일 이상 된 로그 삭제
find logs/ -name "*.log" -type f -mtime +7 -delete
```

### Q3: 특정 모듈의 로그만 보고 싶어요!
**A**: 해당 모듈의 로거 이름을 찾아보세요.
```python
# 특정 로거만 DEBUG로 설정
set_logger_level("backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis", logging.DEBUG)
```

## 🎯 실전 팁

1. **개발할 때는 DEBUG**를 사용하세요 - 모든 것을 자세히 볼 수 있어요
2. **운영할 때는 INFO**를 사용하세요 - 중요한 정보만 깔끔하게
3. **오류가 나면 ERROR**를 확인하세요 - 문제의 원인을 찾을 수 있어요
4. **꾸준히 로그를 확인**하세요 - 프로그램이 어떻게 동작하는지 배울 수 있어요

## 📞 도움이 필요하신가요?

로깅 시스템에 대해 더 궁금한 점이 있으시면 언제든지 물어보세요! 초보자도 쉽게 이해할 수 있도록 자세히 설명해드릴게요. 😊

---
*이 문서는 2025년 9월 29일에 작성되었어요*
