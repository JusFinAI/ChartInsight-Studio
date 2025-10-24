[2 tools called]

요약 먼저 — 세 안(1/2/3)의 기술적 특성·장단점과 관련 코드 위치를 읽어 검토한 뒤, 운영·개발 편의성 관점에서 **3안(동기/플래그 업데이트 단계에서 파라미터 우선 처리)** 을 권장합니다. 아래에 이유와 구체적 구현·테스트 권고를 간결히 정리합니다.

핵심 참고 코드(읽음)
- DAG 파라미터 정의: `dag_daily_batch`의 `target_stock_codes` 파라미터(현재 정의만 존재)
```406:412:DataPipeline/dags/dag_daily_batch.py
        "target_stock_codes": Param(...),
```
- 분석 대상 결정(현재 태스크들이 참조하는 기준): `is_analysis_target == True` 필터
```71:78:DataPipeline/dags/dag_daily_batch.py
stock_codes = {s.stock_code for s in db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()}
```
- 필터 제로 로직(분석 대상 선별): `master_data_manager.update_analysis_target_flags(...)`가 `apply_filter_zero`를 호출해서 `is_analysis_target`를 갱신
```370:373:DataPipeline/src/master_data_manager.py
filtered_stocks_info = apply_filter_zero(stock_info_for_filter)
analysis_target_codes = {s['code'] for s in filtered_stocks_info}
```
- 필터 구현 상세: `apply_filter_zero` (시가총액, 키워드 제외 등)
```5:13:DataPipeline/src/utils/filters.py
# 시가총액 계산 및 키워드/상태 필터 등
```

각 안(요약 + 장단점)

1안) 각 Task가 직접 `params['target_stock_codes']` 확인
- 구현 방식: `_calculate_rs_score`, `_run_technical_analysis`, `_fetch_financial_grades_from_db`, `_fetch_latest_low_frequency_candles` 등 각 Task 시작부에서 params를 확인해 대상 리스트를 결정.
- 장점
  - 매우 명시적: 각 Task가 독립적으로 동작하므로 어떤 Task가 param을 적용하는지 바로 알 수 있음.
  - 세부 제어 가능: Task별로 다른 필터/샘플링 정책 적용 가능.
- 단점
  - 많은 코드 중복(여러 Task 수정 필요) → 리스크·테스트 부담↑
  - 일관성 유지 어려움(한 Task에서는 param 반영, 다른 Task에서는 누락될 위험)
  - 변경 시 모든 Task를 검증해야 하므로 배포 부담 큼

2안) `backfill_needed == False` 필터 사용
- 구현 방식: dag_daily_batch의 대상 조회 쿼리에 `Stock.backfill_needed == False` 조건을 추가.
- 장점
  - 운영 목적(초기 백필 완료 종목만 대상으로 운영)을 명확히 반영
  - DB 상태만으로 대상 제어 가능(간단 쿼리 변경)
- 단점 / 리스크
  - 의미 혼동 가능: `backfill_needed`는 '초기 백필 필요성'을 나타내고, 수동 테스트 선택(임시)과는 다른 용도. 즉 개발/테스트 목적의 일시적 제한에는 부적합.
  - 초기 적재 이력과 무관하게 다른 프로세스가 해당 플래그를 변경할 수 있음(의도치 않은 제외 발생).
  - 이미 DB에 반영된 값(백필 완료 여부)이 없으면 사용 불가; 또한 파라미터로 지정된 '이번 run만' 처리하는 기능 제공하지 않음.

3안) `sync` 또는 `update_analysis_target_flags_task`에서 params 우선 처리 (권장)
- 구현 방식(권장 정책):
  - `_update_analysis_target_flags_task`에서 `params.get('target_stock_codes')`가 있으면 그 리스트를 우선 사용.
  - 안전모드: 전달 리스트를 `update_analysis_target_flags(db, provided_list)`로 전달해서 **필터 제로(apply_filter_zero)를 그대로 적용**(즉, 수동 지정 대상도 필터 조건을 통과해야만 is_analysis_target=True가 되게 함).
  - 선택적 테스트 모드: `force_bypass_filter_zero` 같은 추가 파라미터가 있으면 필터를 건너뛰어 강제 처리(테스트 전용).
- 장점
  - 중앙집중 제어: 한 지점에서 분기하면 downstream 모든 Task가 동일한 대상 집합 사용 → 일관성 보장
  - 최소 변경: Task별 수정 불필요, 변경 범위 작음(주로 `_update_analysis_target_flags_task` 어댑터만 변경)
  - 안전성: 기본적으로 기존 `apply_filter_zero`를 재활용하면 production 규칙(시가총액 등)을 유지하면서도 수동 지정 가능
  - 감사/로깅 용이: 한곳에서 XCom/로그로 사용된 대상 목록과 업데이트 결과를 남기면 추적 쉬움
- 단점
  - `_update_analysis_target_flags_task`가 파라미터 처리 로직을 추가하도록 수정해야 함(작업 필요)
  - 만약 개발자가 “강제 테스트” 목적으로 필터를 우회하고 싶다면 별도 플래그를 제공·관리해야 함(운영 주의 필요)

결론(권장안)
- 개발·검증 목적의 요구(“UI에서 소수 종목 지정 → dag_daily_batch 전체에 적용하여 빠른 테스트”)에는 **3안(동기/플래그 업데이트 단계에서 우선 처리, 안전모드로 필터 적용)** 이 가장 합리적입니다.
  - 이유: 최소 변경으로 전체 파이프라인 대상 집합을 제어할 수 있고, 기존 필터 로직을 유지해 production 안전성을 훼손하지 않음. 또한 로그/요약(XCom) 남기는 지점이 중앙에 있어 검증·추적이 쉬움.
- 운영용(영구적 정책)으로는 2안(`backfill_needed` 기반 운영 필터)를 보조적으로 사용하되, 의미를 명확히 문서화하고 `backfill_needed`의 현재 사용처 전역 검토 후 도입 권장.

구체적 구현 권고(3안 안전모드, 최소 변경)
- 변경 위치: `dag_daily_batch`의 `_update_analysis_target_flags_task` (현재 이 Task가 `sync_stock_master`의 XCom을 받아 `update_analysis_target_flags` 호출)
  - 코드 훅: `all_active_codes = ti.xcom_pull(task_ids='sync_stock_master')` 부분에 params 우선 로직 추가.
- 입력 검증:
  - strip/중복 제거, 숫자 형식 체크(6자리) — 미유효 코드는 경고로 스킵.
  - DB 존재 검증: `existing = db.query(Stock.stock_code).filter(Stock.stock_code.in_(validated_codes)).all()` → 미존재 목록 로그.
- 안전 옵션:
  - 기본: `update_analysis_target_flags(db, validated_codes)` 호출(=apply_filter_zero 적용).
  - 테스트 전용: `force_bypass_filter_zero=True`이면 `update_analysis_target_flags` 대신 직접 `Stock.is_analysis_target`을 배치 업데이트(로그 매우 상세히 남김).
- 출력/검증:
  - Task는 `return {"used_codes": [...], "updated_count": N, "skipped_invalid": [...], "missing_in_db": [...]}` 형태로 요약을 반환 → PythonOperator가 XCom으로 저장.
  - 이후 `load_final_results` 로그/DB를 통해 전체 파이프라인 정상 동작 확인.

테스트 계획(간단)
1. 로컬(또는 컨테이너)에서 DAG를 `target_stock_codes`로 2~3개 지정해 수동 트리거.  
2. `_update_analysis_target_flags_task` 로그에서 사용된 코드 목록과 `update_count` 확인.  
3. downstream 태스크들의 처리 대상 수(로그/XCom)와 `live.daily_analysis_results`에 결과가 올라오는지 확인.  
4. `force_bypass_filter_zero` (옵션) 테스트로 필터 우회 동작 확인(관리자 전용).

