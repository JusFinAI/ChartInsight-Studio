# chart_pattern_analyzer_kiwoom_db → Backend 이식 및 리팩토링 보고서

이 문서는 `chart_pattern_analyzer_kiwoom_db` 프로젝트에서 수행한 리팩토링 작업과, 메인 `backend` 프로젝트로 안전하게 이식하기 위해 진행한 절차, 마주친 문제와 해결 방법, 그리고 남은 과제를 초보 개발자가 이해하기 쉽도록 친절하게 정리한 보고서입니다.

작성자: AI 어시스턴트
작성일: 2025년 9월 11일
대상 경로: `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db`

요약:
- 목표: v3 코드를 메인 backend로 포팅하기 전에, 불필요한 의존성과 모듈 레벨 부작용을 제거하고, 로깅·데이터 로더·엔진 진입점을 명확히 분리하여 안전한 이식이 가능하도록 준비했습니다.
- 핵심 변경: 시각화/다운로드 의존 제거, 데이터 로더 표준화, 엔진 진입점 정리, 모듈 임포트 시 부작용 제거.

1) 왜 이 작업을 했는가 (목적)
- 원래 v3는 연구/실험용으로 개발되어 모듈 임포트 시 로그 파일 생성, Plotly 렌더링 초기화 등 부작용이 있었습니다.
- 운영 환경의 backend에 그대로 복사하면 서비스 시작 시 예상치 못한 파일 생성이나 네트워크 호출이 실행될 수 있어, 먼저 import-safe 하게 정리해야 합니다.

2) 주요 리팩토링 항목(무엇을 바꿨는가)
- 데이터 로더(`data_loader.py`):
  - 역할을 `DB 세션 -> pandas.DataFrame`으로 명확히 분리하고 `tz='Asia/Seoul'` 기본 처리 로직을 고정했습니다.
  - 백엔드의 CRUD 인터페이스(`app.crud.get_candles`)와 호환되도록 import 경로를 조정했습니다.
- 엔진(`run_full_analysis_impl.py` → `engine_impl.py`로 포팅 준비):
  - 시각화 및 외부 다운로드(yfinance 등) 코드 제거.
  - 모듈 레벨에서 logger 설정을 제거하고 `logging.getLogger(__name__)`으로 대체.
  - 분석 엔진의 외부 사이드이펙트를 제거하여 함수 호출만으로 동작하게 수정.
- 런처/데모(`main_dashboard.py`):
  - `.env` 또는 sys.path 관련 중복 초기화 제거.
  - 엔진 호출을 내부에서 직접 수행하지 않고 명확한 런처 함수 제공.
- 로깅:
  - v3에 있던 `configure_logger(...)`와 모듈 레벨 핸들러 등록을 제거.
  - 메인 backend의 중앙 로거 정책(`backend/app/utils/logger_config.py`)에 맞춰 작동하도록 문서화.

3) 적용 방법(어떻게 이식했는가 — 단계별 가이드)
1. 리포지터리 내부의 v3 모듈을 복사(`backend/_temp_integration/...` 유지)
2. 모듈 레벨의 `configure_logger` 호출 제거 또는 `if __name__ == '__main__'`로 제한
3. `run_full_analysis_impl.py`의 시각화와 외부 네트워크 의존 제거
4. `data_loader.py`를 `backend/app/services/data_loader.py`로 옮기고 `from app.crud import get_candles` 형태로 적절히 수정
5. `engine_impl.py`로 복사 후 import 경로와 로거만 백엔드 표준에 맞게 조정
6. backend의 startup 루틴에서 중앙 로거를 등록하고 서비스가 시작될 때만 핸들러를 추가

4) 마주친 문제와 해결(문제·원인·해결)
- 문제: Plotly에서 부수 요소(ZigZag, Peaks/Valleys)가 캔들 x축과 일치하지 않음
  - 원인: 일부 trace가 epoch seconds(초)로, 다른 trace가 ms 또는 ISO 문자열로 전달되어 x축 타입 혼합 발생
  - 해결: 모든 x 값을 epoch ms로 normalize하고 Plotly xaxis를 `type: 'date'`로 고정
- 문제: Secondary Peaks/Valleys가 UI의 토글과 무관하게 표시됨
  - 원인: 프론트엔드의 초기화 시 js_points의 상태와 toggle 상태 mismatch 또는 캐시 문제
  - 해결: 프론트엔드에서 `js_points`를 `peaks/valleys/...`로 분리하고, 토글이 바뀔 때마다 `setJSPoints`를 통해 plot 데이터 재계산을 보장
- 문제: 모듈 임포트 시 로그 파일 생성(부작용)
  - 원인: 모듈 레벨에서 `configure_logger(...)` 호출 및 핸들러 등록
  - 해결: 모듈은 `logging.getLogger(__name__)`만 사용하도록 변경, 애플리케이션 startup에서만 핸들러 등록

5) 검증 및 테스트 체크리스트 (초보자용 실행 가이드)
- 단위 검증
  1. `pytest`로 엔진·데이터로더의 단위 테스트 실행
  2. `data_loader.load_candles_from_db(...)`가 UTC→Asia/Seoul 변환을 올바르게 수행하는지 확인
- 통합 검증
  1. backend를 로컬에서 실행하고 FastAPI 엔드포인트를 통해 분석 흐름 호출
  2. `run_full_analysis_impl`(이식본)을 독립적으로 실행해 예외/부작용이 없는지 확인
- UI 검증
  1. Trading Radar에서 피크/밸리 토글을 켜고 끌 때 콘솔 로그로 `jsPoints` 갯수와 `showJSPoints` 값을 확인
  2. Plotly 차트에서 피크/밸리 표시가 정상인지, 넥라인·밴드가 데이터 범위 밖으로 튀지 않는지 확인

6) 남은 과제(우선순위 포함)
- P0
  - 메인 backend에 실제로 복사해 작은 통합 테스트(엔드포인트 호출 → 분석 → DB 업데이트)를 수행
  - 모듈 임포트 시 부작용이 전혀 없는지 CI에서 확인하는 검사 추가
- P1
  - 엔진의 핵심 알고리즘(TrendDetector, Peak/Valley detection)의 단위 테스트 보강
  - 성능 테스트: 대량의 차트 데이터(1분봉 다수)에 대해 분석 시간이 허용 범위인지 측정
- P2
  - 분석 결과 캐시 전략 설계(초당/분 단위 데이터 유입에 따른 캐시 invalidation)
  - 모니터링(로그·메트릭) 대시보드 구축

7) 코드 스니펫(중요 변경 예시)
- 모듈 레벨 로거 제거 전:
```python
from .logger_config import configure_logger
logger = configure_logger(__name__, log_file_prefix="chart_pattern_analyzer_v3", logs_dir=MODULE_LOGS_DIR, level=logging.INFO)
```

- 변경 후 (import-safe):
```python
import logging
logger = logging.getLogger(__name__)
# 앱 startup 시 핸들러를 등록합니다.
```

8) 초보자를 위한 팁 (작은 실수 방지용)
- 절대 모듈 임포트 시 네트워크 호출이나 파일 생성이 일어나지 않도록 하세요. 테스트에서는 `python -c "import your_module"`로 빠르게 확인할 수 있습니다.
- Plotly에서 x축이 섞여서 이상하게 보이면, 모든 x 값을 숫자(밀리초 epoch)로 일관되게 바꿔보세요.
- 토글이 동작하지 않으면 프론트에서 상태(state)가 올바르게 내려가는지(콘솔 로그 확인), 그리고 차트 컴포넌트에서 그 prop을 받아서 조건부로 그리는지 확인하세요.

9) 참고자료 및 관련 파일
- `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db/`
- `backend/app/analysis/engine_impl.py` (이식 후 위치)
- `backend/app/services/data_loader.py`
- `frontend/src/app/trading-lab/trading-radar/page.tsx` (토글 로직)
- `frontend/src/components/ui/Chart.tsx` (Plotly 렌더링 로직)

10) 결론
- 이번 리팩토링은 연구용 코드를 운영 backend로 안전하게 옮기기 위한 필수 사전 작업입니다. 핵심은 "임포트 안전성"과 "부작용 제거"이며, 이를 지키면 배포·운영 시 예기치 않은 동작을 크게 줄일 수 있습니다.

원하시면 이 문서를 repo 루트에 `backend_migration_report.md`로 추가하겠습니다. 추가로 각 변경 파일의 PR 설명 템플릿이나 코드 리뷰 체크리스트를 만들어 드릴까요?


