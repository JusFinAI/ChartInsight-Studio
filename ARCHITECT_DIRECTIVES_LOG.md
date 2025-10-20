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
- **상태**: 

## 과제 2: 경쟁 상태 해결을 위한 XCom 도입

*목표: 통합 테스트에서 발견된 '경쟁 상태(Race Condition)' 문제, 즉 기존 코드에서 sync_stock_master_task가 XCom을 반환하지 않아, DB commit이 완료되기도 전에 update_analysis_target_flags_task에서 DB를 조회할 수 있는 문제를 해결하여, 파이프라인의 데이터 처리 순서와 시점을 보장한다..*

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


[지침서 3.2 - 최종] 데이터 정규화 및 타입 최적화 (Inspector 피드백 반영)

  1. 전체 목표 (Overall Objective)

  last_price 데이터 누락 버그를 해결함과 동시에, PostgreSQL의 특성을 존중하고 데이터 무결성을 강화하는 방향으로 스키마와 데이터 처리 로직을 전면 개선한다.

  2. 전체 계획 및 맥락 (Overall Plan & Context)

  이 지침서는 지침서 3.1을 대체 및 폐기한다.

  이전 설계는 PostgreSQL의 식별자 처리 방식(소문자 변환)을 고려하지 않아 실무적인 위험이 컸다. Inspector의 권고에 따라, 우리는 DB 스키마는 snake_case를 유지하되, 애플리케이션 레벨에서 '데이터 정규화(Normalization)'의 책임을 명확히 하는
  핵심 변경 사항:
   1. DB 타입 최적화: last_price, list_count를 단순 문자열이 아닌, 계산과 집계에 용이한 Numeric, BigInteger 타입으로 변경하여 데이터의 정확성과 성능을 향상시킨다.
   2. 명시적 데이터 정규화: API로부터 받은 문자열("12,500")을 DB에 저장하기 전에, master_data_manager가 명시적으로 숫자 타입으로 변환하고 정제하는 책임을 갖는다.
   3. 안정적인 스키마 유지: DB 컬럼명은 snake_case를 유지하여 모든 DB 도구 및 개발 환경과의 호환성을 보장한다.

  이 작업을 통해 우리는 버그를 수정할 뿐만 아니라, 훨씬 더 안정적이고, 효율적이며, 전문적인 데이터 파이프라인을 구축하게 된다.

  ---

  상세 구현 지침

  1단계: `database.py` 타입 최적화

  [1-1. 목표] last_price, list_count 컬럼을 숫자 타입으로 변경한다.

  [1-2. 수정 대상] DataPipeline/src/database.py

  [1-3. 지침] Stock 클래스의 컬럼 정의를 아래와 같이 수정하십시오. (컬럼명은 snake_case 유지)

   1 # /DataPipeline/src/database.py
   2 from sqlalchemy import Numeric, BigInteger # BigInteger 임포트 추가
   3
   4 class Stock(Base):
   5     # ...
   6     # String -> Numeric, BigInteger로 타입 변경
   7     last_price = Column(Numeric(12, 2), nullable=True)
   8     list_count = Column(BigInteger, nullable=True)
   9     # ...

  2단계: `master_data_manager.py` 데이터 정규화 로직 구현

  [2-1. 목표] API 응답(문자열)을 DB 스키마(숫자)에 맞게 변환하고, 모든 필드를 빠짐없이 저장하도록 수정한다.

  [2-2. 수정 대상] DataPipeline/src/master_data_manager.py

  [2-3. 지침]

    1     # /DataPipeline/src/master_data_manager.py 상단
    2
    3     def _normalize_price(price_str: str) -> float | None:
    4         """문자열 가격을 안전하게 float으로 변환합니다."""
    5         if not price_str or not isinstance(price_str, str):
    6             return None
    7         try:
    8             return float(price_str.replace(',', ''))
    9         except (ValueError, TypeError):
   10             return None
   11
   12     def _normalize_count(count_str: str) -> int | None:
   13         """문자열 수량을 안전하게 int로 변환합니다."""
   14         if not count_str or not isinstance(count_str, str):
   15             return None
   16         try:
   17             # API 응답의 '0000...' 패딩을 제거하고 정수로 변환
   18             return int(count_str.replace(',', ''))
    1     # _map_api_response_to_stock_model 함수 교체
    2     def _map_api_response_to_stock_model(api_data: Dict) -> Dict:
    3         """API 응답을 DB 스키마에 맞게 매핑하고, 숫자 필드를 정규화합니다."""
    4         return {
    5             'code': api_data.get('code'),
    6             'name': api_data.get('name'),
    7             'marketName': api_data.get('marketName'),
    8             'marketCode': api_data.get('marketCode'),
    9             'listCount': _normalize_count(api_data.get('listCount')), # 정규화
   10             'auditInfo': api_data.get('auditInfo'),
   11             'state': api_data.get('state'),
   12             'lastPrice': _normalize_price(api_data.get('lastPrice')), # 정규화
   13             'regDay': api_data.get('regDay'),
   14             'upName': api_data.get('upName'),
   15             'upSizeName': api_data.get('upSizeName'),
   16             'companyClassName': api_data.get('companyClassName'),
   17             'orderWarning': api_data.get('orderWarning'),
    1     # sync_stock_master_to_db 함수 전체를 교체
    2     def sync_stock_master_to_db(db_session) -> List[str]:
    3         logger.info("외부 API로부터 종목 정보를 조회하여 DB와 동기화합니다.")
    4         api_all = sync_stock_master_data()
    5         api_map = {s['code']: s for s in api_all if s.get('code')}
    6         api_codes = set(api_map.keys())
    7
    8         db_stocks = db_session.query(Stock).all()
    9         db_map = {s.stock_code: s for s in db_stocks}
   10         db_codes = set(db_map.keys())
   11
   12         new_codes = api_codes - db_codes
   13         delisted_codes = db_codes - api_codes
   14         existing_codes = api_codes & db_codes
   15
   16         # 신규 종목 추가
   17         for code in new_codes:
   18             src = api_map.get(code)
   19             if not src: continue
   20             # Stock 모델의 컬럼명과 일치하는 키-값만 필터링
   21             model_data = {k: v for k, v in src.items() if k in Stock.__table__.columns.keys()}
   22             stock_obj = Stock(stock_code=code, **model_data)
   23             db_session.add(stock_obj)
   24
   25         # 상장폐지 종목 처리
   26         for code in delisted_codes:
   27             db_obj = db_map.get(code)
   28             if db_obj and db_obj.is_active:
   29                 db_obj.is_active = False
   30
   31         # 기존 종목 정보 업데이트
   32         for code in existing_codes:
   33             src = api_map.get(code)
   34             db_obj = db_map.get(code)
   35             if not src or not db_obj: continue
   36
   37             # 모든 필드를 API의 최신 정보로 덮어쓰기
   38             for key, value in src.items():
   39                 if hasattr(db_obj, key):
   40                     setattr(db_obj, key, value)
   41
   42             # 재활성화 로직
   43             if not db_obj.is_active:
   44                 db_obj.is_active = True
   45                 db_obj.backfill_needed = True
   46
   47         db_session.commit()
   48         logger.info(f"동기화 완료: 신규={len(new_codes)}, 비활성화={len(delisted_codes)}, 업데이트={len(existing_codes)}")
   49
   50         active_stocks = db_session.query(Stock.stock_code).filter(Stock.is_active == True).all()
   51         return [code for code, in active_stocks]

   4. `update_analysis_target_flags` 함수를 수정하십시오. (DB 컬럼명 사용)

   1     # stock_info_for_filter 생성 부분 수정
   2     stock_info_for_filter = [{
   3         'code': s.stock_code, 'name': s.name, 'state': s.state,
   4         'auditInfo': s.auditInfo, 'lastPrice': s.last_price, 'listCount': s.list_count
   5     } for s in target_stocks]

  3단계: `filters.py` 로직 수정

  [3-1. 목표] apply_filter_zero가 숫자 타입을 직접 사용하도록 수정한다.

  [3-2. 수정 대상] DataPipeline/src/utils/filters.py

  [3-3. 지침] apply_filter_zero 함수 내부의 시가총액 계산 부분을 수정하십시오.

   * 수정 전 (AS-IS):

   1     # ...
   2     last_price = _safe_parse_number(last_price_raw)
   3     list_count = _safe_parse_number(list_count_raw)
   4     # ...
   * 수정 후 (TO-BE):

   1     # ...
   2     # _safe_parse_number 호출 제거, 이미 숫자 타입으로 들어옴
   3     last_price = stock.get('lastPrice')
   4     list_count = stock.get('listCount')
   5
   6     if last_price is None or list_count is None:
   7     # ...

  ---