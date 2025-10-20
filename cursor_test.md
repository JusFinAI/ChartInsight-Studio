$source /home/jscho/ChartInsight-Studio/DataPipeline/.venv/bin/activate && export PYTHONPATH='/home/jscho/ChartInsight-Studio:/home/jscho/ChartInsight-Studio/DataPipeline' && export DATABASE_URL='sqlite:///:memory:' && python -m unittest discover -v DataPipeline/tests

---
[2025-10-14T17:11:06.733+0900] {database.py:40} INFO - DB 연결 시도: sqlite:///:memory:
test_case_insensitive_keyword (test_filters.TestApplyFilterZero.test_case_insensitive_keyword) ... ok
test_comma_in_price (test_filters.TestApplyFilterZero.test_comma_in_price) ... ok
test_config_override_min_market_cap (test_filters.TestApplyFilterZero.test_config_override_min_market_cap) ... ok
test_filter_by_keyword (test_filters.TestApplyFilterZero.test_filter_by_keyword) ... ok
test_market_cap_below_threshold (test_filters.TestApplyFilterZero.test_market_cap_below_threshold) ... ok
test_missing_listcount (test_filters.TestApplyFilterZero.test_missing_listcount) ... ok
test_normal_pass (test_filters.TestApplyFilterZero.test_normal_pass) ... ok
test_01_run_stock_info_load_task (test_initial_loader.TestInitialLoaderTasks.test_01_run_stock_info_load_task)
[Task 1] _run_stock_info_load_task가 필터링과 DB 저장을 올바르게 수행하는지 검증 ... 설정 로드 완료: 환경=real, 호스트=https://api.kiwoom.com
[2025-10-14T17:11:06.828+0900] {dag_initial_loader.py:58} INFO - 📊 'live.stocks' 테이블에 종목 정보 적재 시작 (외부 API -> 필터 제로 -> DB upsert)
[2025-10-14T17:11:06.829+0900] {dag_initial_loader.py:62} INFO - 📊 외부 API로부터 로드된 종목 수: 2개
[2025-10-14T17:11:06.829+0900] {dag_initial_loader.py:63} INFO - 🔎 필터 제로 통과 종목 수: 1개
[2025-10-14T17:11:06.830+0900] {dag_initial_loader.py:95} INFO - 1개의 종목 정보를 DB에 동기화(UPSERT)합니다.
📋 입력받은 설정: {}
자동 모드로 DB에서 백필 대상 2건을 조회하여 실행합니다.

============================================================
🚀 🔥 '자동 모드(백필 대상 조회)'으로 초기 적재 작업을 시작합니다.
'AAA' 백필 완료. backfill_needed=False로 업데이트.
'BBB' 백필 완료. backfill_needed=False로 업데이트.



============================================================
🎯 초기 적재 완료
✅ 성공: 0개
❌ 실패/데이터 없음: 0개
📊 전체: 2개
============================================================

📋 입력받은 설정: {'stock_codes': '005930, 000660'}
수동 모드로 특정 종목에 대해 실행합니다: ['005930', '000660']

============================================================
🚀 🎯 '특정 종목' 모드으로 초기 적재 작업을 시작합니다.
'005930' 백필 완료. backfill_needed=False로 업데이트.
'000660' 백필 완료. backfill_needed=False로 업데이트.

============================================================
🎯 초기 적재 완료
✅ 성공: 0개
❌ 실패/데이터 없음: 0개
📊 전체: 2개
============================================================

ok
test_02_run_initial_load_task_auto_mode (test_initial_loader.TestInitialLoaderTasks.test_02_run_initial_load_task_auto_mode)
[Task 2] _run_initial_load_task의 자동 모드가 정상 동작하는지 검증 ... ok
test_03_run_initial_load_task_manual_mode (test_initial_loader.TestInitialLoaderTasks.test_03_run_initial_load_task_manual_mode)
[Task 2] _run_initial_load_task의 수동 모드가 정상 동작하는지 검증 ... ok
test_get_managed_stocks_from_db (test_master_data_manager.TestMasterDataManager.test_get_managed_stocks_from_db) ... 2025-10-14 17:11:06 KST - INFO - DB에서 관리 중인 종목 코드를 조회합니다.
2025-10-14 17:11:06 KST - INFO - 조회 완료: 2개 종목
ok

----------------------------------------------------------------------
Ran 11 tests in 0.043s

OK

