# chart_pattern_analyzer_kiwoom_db 리팩토링과 backend 이식 준비

이 문서는 `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db` 폴더에서 진행한 리팩토링 요약과, 메인 `backend` 프로젝트로 안전하게 이식하기 위한 권장 절차를 주니어 개발자 관점에서 이해하기 쉽게 정리한 가이드입니다. 향후 이식 작업을 단계별로 진행할 때 이 문서를 참조하세요.

- 작성자: AI 어시스턴트
- 대상 리포지터리 경로: `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db`
- 목적: 가독성, 포팅(이식) 용이성, 로그·부작용 최소화

---

1) 배경 및 목표
- 기존 `chart_pattern_analyzer_kiwoom_db_v2`는 개발/실험 용도로 복잡도가 높고 UI(Plotly Dash)와 엔진이 촘촘히 결합되어 있었습니다.
- 목표는 `v3` 폴더를 **건드려도 v2는 손상되지 않도록 복사본을 정리**하고, `run_full_analysis_impl.py`(분석 엔진), `data_loader.py`(DB→DataFrame), `analysis.py`(어댑터), `main_dashboard.py`(데모/런처)로 역할을 분리해 메인 `backend`로 이식 가능한 형태로 만드는 것입니다.

2) v3에서 이미 수행한 주요 리팩토링 요약 (핵심만)
- 데이터 로더(`data_loader.py`)를 만들고 `tz` 인자를 단순화: 기본값을 `'Asia/Seoul'`로 고정하여 한국 주식용으로 일관성 유지.
- `analysis.py`에서 `run_analysis_from_df`로 단일 진입점 정리: DB 조회 래퍼를 제거하고 이미 로드된 DataFrame을 직접 엔진에 넘김.
- `run_full_analysis_impl.py`(엔진): 시각화 의존성(Plotly, yfinance) 제거, 모듈 레벨에서 불필요한 파일/디렉토리 생성 제거, logger 구성을 `logger_config.py` 호출로 통일.
- `main_dashboard.py`(런처): 불필요한 중복 `sys.path`/`.env` 로딩 정리, 데이터 로더 호출 시 `tz='Asia/Seoul'`로 고정, `_run_full_analysis_from_db` 래퍼 제거하고 `run_analysis_from_df` 직접 호출.

3) v3에서 발견된 문제 및 결정사항
- 문제: Plotly에서 보조 요소(ZigZag, Peaks/Valleys)가 메인 캔들 x축 형식과 일치하지 않아 표시 이상 발생.
  - 해결: 모든 trace의 x를 datetime으로 통일하고 xaxis type을 `date`로 설정, tickvals/ticktext를 datetime으로 사용.
- 문제: Secondary Peaks/Valleys가 체크박스 상태와 상관없이 표시되는 현상
  - 분석 결과: 엔진은 Secondary를 실제로 생성했으나 UI는 체크박스 상태를 올바르게 반영하도록 수정돼 있었음. 과거 상태의 캐시/초기화 문제였음.
- 로깅: v3는 독립 실행을 위한 `logger_config.py`를 가짐. 그러나 메인 backend에는 이미 중앙 로거(`backend/app/utils/logger_config.py`)가 있어 이식 시 정책 통일 필요.

4) 메인 backend로 이식할 때 고려할 정책(핵심)
- 원칙: 모듈 임포트 시 부작용(파일 생성, 핸들러 추가)을 절대 발생시키지 않는다.
- 로깅: 운영 환경에서는 중앙 유틸(`backend/app/utils/logger_config.py`)을 표준으로 사용하고, 모듈은 `logging.getLogger(__name__)`만 호출한다.
- 코드 의존성: 엔진 모듈은 시각화/외부 데이터 다운로드 의존을 제거하여 서비스 레이어로 분리한다.

5) 현시점에서의 이식 방안 검토 (권장: 2 → 1 순서)
- 권장 순서 요약: 먼저 v3에서 로그 및 부작용(파일 핸들러/디렉토리 생성)을 정리하고 모듈을 import-safe하게 만든 뒤, `run_full_analysis_impl.py`를 `backend/app/analysis/engine_impl.py`로 복사한다. 그 후 backend의 중앙 로거에 맞춰 최소 수정한다.
- 이유: 안전성(임포트 시 부작용 방지), 운영 적합성(통합 로그), 유지보수성(중앙 정책 준수).
- 구체 단계:
  1. v3에서 모듈 레벨 `configure_logger(...)` 호출 제거(또는 `if __name__ == '__main__'`로 한정).
  2. v3 모듈에서 `logger = logging.getLogger(__name__)` 만 사용하게 정리.
  3. `data_loader.py`를 메인 backend에 맞게 경로/CRUD 호출만 `app.crud`로 바꾸어 복사.
  4. `run_full_analysis_impl.py`를 `backend/app/analysis/engine_impl.py`로 복사하고 import 경로, 불필요 의존 제거, 모듈 로거 변경 반영.
  5. 앱 런처(예: FastAPI startup 또는 `main_dashboard` 런처)에서 필요한 로거들을 `backend.app.utils.get_logger(...)`로 초기화.

6) data_loader.py 이식 방법 (요약)
- 현재 v3 `data_loader.py` 역할: DB 세션 + `get_candles` CRUD를 호출하여 pandas DataFrame을 반환하고 tz를 `Asia/Seoul`로 변환.
- 이식 팁:
  - 복사 위치: `backend/app/services/data_loader.py` (이미 일부 복사됨).
  - 변경사항: 내부 import를 `from app.crud import get_candles` 형태로 맞춤(패키지 상대 경로 사용).
  - 인터페이스: keep function `load_candles_from_db(session, stock_code, timeframe, period=None, limit=None, tz='Asia/Seoul')`.
  - tz 관리: DB는 UTC 저장 규칙을 따르므로 함수 내부에서 `ZoneInfo('UTC')`로 로컬화 후 `.tz_convert(ZoneInfo('Asia/Seoul'))` 하는 방식을 권장.

7) 향후 과제 목록 (우선순위 제안)
 - P0 (즉시 필요)
   1. v3 모듈 레벨 로거 제거(임포트 부작용 제거) — 안전성 필수.
   2. `engine_impl.py` 복사 및 백엔드 import 정리(POC 테스트).
   3. `data_loader.py` 최종 이식 및 DB 세션/CRUD 경로 확인.

 - P1 (테스트/운영 준비)
   4. 메인 backend startup에서 로깅 중앙화( `get_logger` 호출 ) 및 로그 폴더 정책 문서화.
   5. 통합 테스트: main_dashboard의 대시보드 런처(개발용)와 FastAPI(프로덕션) 양쪽에서 엔진 호출 검증.

 - P2 (개선/추가)
   6. 로그 포맷·레벨 정책 문서 작성(운영/개발 분리). 
   7. 엔진의 단위 테스트(TrendDetector/PatternManager 주요 로직)을 작성하여 리팩토링 안전성 보장.

8) 핵심 코드 변경 예시(안전화)
- Before (v3 엔진 모듈 초기부):
  ```python
  from .logger_config import configure_logger
  logger = configure_logger(__name__, log_file_prefix="chart_pattern_analyzer_v3", logs_dir=MODULE_LOGS_DIR, level=logging.INFO)
  ```
- After (import-safe, 백엔드용):
  ```python
  import logging
  logger = logging.getLogger(__name__)
  # 앱 초기화 시 get_logger(...) 또는 setup_logger(...)로 핸들러를 등록합니다.
  ```

9) 디버깅·검증 팁 (참고)
- 이식 전 v3에서 다음을 점검하세요: `logger.handlers` 수, `logger.propagate` 값(False 권장), 로그 파일이 의도된 위치에 생성되는지.
- 복사 후 백엔드에서 앱 시작 루틴에서만 로거를 설정하고, 모듈 단위 테스트를 먼저 돌려 이상 유무를 확인합니다.

10) 문서 활용 계획
- 이 문서를 프로젝트 `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db/` 폴더에 두고, 새 대화(또는 PR)에서 참조하세요. PR 설명에는 "이 문서를 참조해 v3 → backend 이식 절차를 따랐음"을 명시하면 리뷰어가 이해하기 쉽습니다.

---

질문이 더 있으시면, 이 문서를 기준으로 어느 파일을 먼저 패치할지(예: `analysis.py`에서 logger 호출 제거 또는 `engine_impl.py` 생성) 지시해 주세요. 제가 구체적 패치(코드 변경)를 만들어 적용하겠습니다.


