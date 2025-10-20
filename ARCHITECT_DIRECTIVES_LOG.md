# 아키텍트 지침서 상세 로그 (Architect's Directives Log)

**문서 목적**: 데이터 파이프라인의 완성도를 높이기 위해, 감독관(Gemini)이 발행하고 개발자(cursor.ai)가 수행한 모든 아키텍처 개선 지침의 이력을 추적하고, 각 작업의 목적, 배경, **핵심 코드 변경 내역** 및 진행 상태를 상세히 기록한다.

---

## 과제 1: Stock 테이블 데이터 정책 통일 및 기반 리팩토링

*목표: 파이프라인의 데이터 기반을 견고하고 일관되게 재설계한다.*

### 지침서 1.1: `Stock` 테이블 스키마 확장

- **목표**: `Stock` 테이블에 `is_analysis_target` boolean 컬럼을 추가한다.
- **핵심 변경 (`DataPipeline/src/database.py`)**:
  ```python
  class Stock(Base):
      # ... 기존 컬럼 ...
      is_analysis_target = Column(Boolean, nullable=False, server_default=expression.false(), default=False, comment='분석 대상 여부 (필터 제로 통과)')
  ```
- **상태**: **완료 (Approved)**

### 지침서 1.2: `dag_initial_loader` 종목 마스터 동기화 로직 통일

- **목표**: `dag_initial_loader`가 자체 필터링 로직 대신, 표준 동기화 함수(`sync_stock_master_to_db`)를 사용하도록 변경한다.
- **핵심 변경 (`DataPipeline/dags/dag_initial_loader.py`)**:
  ```python
  # _run_stock_info_load_task 함수 전체를 아래 내용으로 교체
  def _run_stock_info_load_task(**kwargs):
      # ... logger, db_session ...
      from src.master_data_manager import sync_stock_master_to_db
      sync_stock_master_to_db(db_session)
      # ...
  ```
- **상태**: **완료 (Approved)**

### 지침서 1.3: (폐기됨) '분석 대상 선정' Task 초기 설계

- **상태**: **폐기 (Obsoleted)**. XCom Size Limit 및 DB 세션 관리 위험으로 인해 `지침서 1.4`로 대체.

### 지침서 1.4: '분석 대상 선정' Task 최종 수정안 (CQRS 패턴 적용)

- **목표**: '분석 대상 선정' Task가 DB 상태를 변경하는 '명령'만 수행하고, 후속 Task들은 DB에서 직접 '조회'하도록 아키텍처를 수정한다.
- **핵심 변경 1 (`DataPipeline/src/master_data_manager.py`)**:
  ```python
  # update_analysis_target_flags 함수가 업데이트된 개수(int)만 반환하도록 수정
  def update_analysis_target_flags(db_session) -> int:
      # ... (내부 로직: 필터 적용 및 플래그 업데이트) ...
      db_session.commit() # 또는 rollback
      return update_count
  ```
- **핵심 변경 2 (`DataPipeline/dags/dag_daily_batch.py`)**:
  ```python
  # _update_analysis_target_flags_task는 작은 요약 정보만 XCom으로 반환
  def _update_analysis_target_flags_task(**kwargs):
      # ...
      update_count = update_analysis_target_flags(db)
      return {"status": "completed", "updated_count": update_count}

  # 후속 분석 Task들은 DB에서 직접 대상을 조회
  def _calculate_rs_score(**kwargs):
      db = SessionLocal()
      target_codes_tuples = db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()
      # ...
  ```
- **상태**: **완료 (Approved)**

### 지침서 1.5: 최종 정리 및 일관성 확보

- **목표**: `dag_daily_batch`에서 불필요한 코드와 마지막 남은 비일관성을 제거한다.
- **핵심 변경 (`DataPipeline/dags/dag_daily_batch.py`)**:
  1.  `_fetch_latest_low_frequency_candles` Task도 다른 분석 Task처럼 DB에서 직접 대상을 조회하도록 수정.
  2.  더 이상 사용되지 않는 `_get_managed_stocks_from_db_task` 함수와 `get_managed_stocks_task` Operator를 코드에서 완전히 삭제.
- **상태**: **완료 (Approved)**

---

## 과제 2: 경쟁 상태 해결을 위한 XCom 도입

*목표: 통합 테스트에서 발견된 '경쟁 상태(Race Condition)' 문제를 해결하여, 파이프라인의 데이터 처리 순서와 시점을 보장한다.*

### 지침서 2.1: `sync_stock_master_task` XCom 도입 리팩토링

- **목표**: `sync_stock_master_task`가 '활성 종목 리스트'를 XCom으로 명시적으로 반환하고, `update_analysis_target_flags_task`가 이 XCom을 입력으로 받도록 수정한다.
- **핵심 변경 1 (`DataPipeline/src/master_data_manager.py`)**:
  ```python
  # sync_stock_master_to_db가 활성 종목 코드 리스트를 반환하도록 수정
  def sync_stock_master_to_db(db_session) -> List[str]:
      # ... (DB 동기화) ...
      active_stocks = db_session.query(Stock.stock_code).filter(Stock.is_active == True).all()
      return [code for code, in active_stocks]

  # update_analysis_target_flags는 인자로 종목 리스트를 받도록 수정
  def update_analysis_target_flags(db_session, stock_codes: List[str]) -> int:
      # ...
  ```
- **핵심 변경 2 (`DataPipeline/dags/dag_daily_batch.py`)**:
  ```python
  # _sync_stock_master는 XCom으로 리스트를 반환
  def _sync_stock_master(**kwargs):
      # ...
      active_codes = sync_stock_master_to_db(db)
      return active_codes

  # _update_analysis_target_flags_task는 XCom을 소비
  def _update_analysis_target_flags_task(**kwargs):
      all_active_codes = ti.xcom_pull(task_ids='sync_stock_master')
      # ...
      update_count = update_analysis_target_flags(db, all_active_codes)
      # ...
  ```
- **상태**: **완료 (Completed & Approved)**. 통합 테스트(v3)를 통해 '경쟁 상태' 문제가 해결되었음을 최종 검증 완료.

---

## 과제 3: '필터 제로' 로직 결함 디버깅 및 수정

*목표: 통합 테스트에서 발견된 '필터 제로' 로직의 결함을 수정하여, 분석 대상 종목이 정상적으로 선정되도록 한다.*

### 지침서 3.1: (예정) `apply_filter_zero` 함수 디버깅

- **목표**: `apply_filter_zero` 함수가 모든 종목을 필터링하는 원인을 분석하고, 해결을 위한 첫 번째 지침을 발행한다.
- **배경**: 통합 테스트(v3) 결과, `update_analysis_target_flags_task`가 XCom으로 4191개의 종목 리스트를 정상적으로 수신했음에도 불구하고, `apply_filter_zero` 함수를 거친 후 분석 대상이 0개로 선정되는 로직 결함이 발견되었다.
- **상태**: **신규 (New)**. 다음 단계로 진행할 최우선 과제.

---