<!-- DataPipeline 디버깅 명령 레퍼런스 (현재 환경 버전) -->
# DataPipeline 디버깅 명령 레퍼런스 (dag_daily_batch 중심)

이 문서는 로컬 개발 환경(WSL2 + Docker)에서 DataPipeline을 디버깅할 때 사용한 `docker exec`, `psql`, `airflow` 관련 명령을 정리한 참고 자료입니다. 각 명령은 **명령어**, **설명**, **사용 상황**을 포함합니다. 현재 환경(dag_daily_batch, tradesmart_db, simulation/live 스키마)에 맞춰 업데이트되었습니다. 실패하거나 수정이 필요한 명령도 함께 기재했습니다.

- **주의**: 명령을 실행할 때 환경변수 확장(호스트 vs 컨테이너)과 따옴표 인용을 정확히 해야 합니다. 특히 `docker exec bash -lc "..."`처럼 컨테이너 내부에서 확장되도록 실행하세요. .env.local/.env.docker에서 POSTGRES_TRADESMART_USER=tradesmart_db, 비밀번호=1234 등을 로드하세요.
- **현재 환경**: Airflow DAG=dag_daily_batch (주식 분석 배치), DB=tradesmart_db (스키마: live=실제 데이터, simulation=테스트 모드), 컨테이너 프로파일=pipeline, SIMULATION 모드 테스트 추천.

---

- **파일**: `DataPipeline/docs/debugging_commands.md`

## 1) 컨테이너 상태 확인
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline ps
  ```
- 설명: 실행 중인 컨테이너 목록과 이름/포트 확인. Airflow 관련 컨테이너(예: `airflow-webserver`, `airflow-scheduler`, `postgres-tradesmart`)을 확인할 때 사용. 프로파일 pipeline로 필터링.
- 사용 상황: Docker up 후 컨테이너가 running인지 확인 (예: dag_daily_batch 실행 전).

## 1.1 컨테이너 종료 및 볼륨 삭제
- 명령:
  ```
  docker-compose --env-file .env.docker --profile pipeline down -v
  ```
-설명 : 컨테이너 종료 및 볼륨 삭제

## 1.2 컨테이너 재시작
- 명령:
  ```
  docker-compose --env-file .env.docker --profile pipeline up -d
  ```
-설명 : 컨테이너 재시작



## 2) Postgres: 컨테이너 내부 환경변수 확인
- 명령(성공):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc 'env | grep -i POSTGRES'
  ```
- 설명: 컨테이너 내부에 설정된 DB 사용자·DB명을 확인. `POSTGRES_TRADESMART_USER=tradesmart_db`, `POSTGRES_DB=tradesmart_db` 값을 안전하게 가져올 때 사용. .env.docker에서 로드된 값.
- 사용 상황: DB 연결 실패 시 (예: psql 오류) 변수 확인.

## 3) Postgres: 특정 테이블 백업 (성공)
- 명령(성공):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc 'pg_dump -U "$POSTGRES_TRADESMART_USER" -d "$POSTGRES_DB" -t simulation.daily_analysis_results > /tmp/simulation_daily_analysis_backup.sql'
  docker cp DataPipeline_postgres-tradesmart_1:/tmp/simulation_daily_analysis_backup.sql ./simulation_daily_analysis_backup.sql  # 컨테이너 이름은 docker ps로 확인
  ls -lh ./simulation_daily_analysis_backup.sql
  ```
- 설명: `simulation.daily_analysis_results` 테이블 전체 덤프를 컨테이너 내부에서 생성한 뒤 호스트로 복사하여 백업. 환경변수는 컨테이너 내부에서 확장되도록 작은따옴표/큰따옴표 사용에 주의. live 스키마 테이블(예: live.daily_analysis_results)도 동일하게 적용.
- 사용 상황: DAG 실행 후 분석 결과 백업 (예: RS 스코어 데이터 저장 확인 후).

## 4) Postgres: 쿼리 실행 (컨테이너 내부 환경변수 사용, 성공)
- 명령(성공 예):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc 'psql -U "$POSTGRES_TRADESMART_USER" -d "$POSTGRES_DB" -c "SELECT stock_code, market_rs_score, financial_grade FROM simulation.daily_analysis_results WHERE analysis_date = '\''2025-10-01'\'' ORDER BY stock_code LIMIT 10;"'
  ```
- 설명: 컨테이너 환경변수를 사용하여 안전하게 psql 쿼리를 실행. 외부(호스트)에서 변수를 확장하면 잘못된 사용자로 연결되는 문제가 발생하므로 주의. simulation/live 스키마 테이블(예: daily_analysis_results) 쿼리 예시.
- 사용 상황: DAG(load_final_results) 후 데이터 검증 (예: 주식 코드별 RS/재무 등급 확인, SIMULATION 모드 결과).

## 4.1) Postgres: `live.stocks` 직접 조회 (예제 추가)
- 목적: DAG 실행 후 `live.stocks` 테이블의 상태(`is_active`, `backfill_needed`, `is_analysis_target`)을 빠르게 확인
- 권장 실행 위치: `postgres-tradesmart` 컨테이너 내부 (컨테이너 환경변수 사용 권장)
- 권장 명령(컨테이너 내부에서 env 변수를 확장하도록 실행):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT stock_code, stock_name, is_active, backfill_needed, is_analysis_target FROM live.stocks WHERE stock_code IN (\'005930\', \'000660\') ORDER BY stock_code;"'
  ```
- 설명 및 실행 팁:
  - 반드시 작은따옴표(')로 `bash -lc '...` 블록을 감싸고 내부에서 `"`로 쿼리 문자열을 감싸면 컨테이너 내부에서 환경변수가 안전하게 확장됩니다.
  - 결과 예시: 각 종목의 `is_active`가 `t`(True)인지, `backfill_needed`가 `f`로 업데이트 되었는지, `is_analysis_target` 플래그가 기대대로 설정되었는지 확인할 수 있습니다.
  - 대규모 결과가 나올 경우(수천 행) `ORDER BY ... LIMIT 50` 같은 절을 추가하여 샘플만 확인하세요.

## 5) Airflow CLI: DAG 수동 트리거 (성공)
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc 'airflow dags trigger -c "{\"execution_mode\": \"SIMULATION\", \"analysis_date\": \"2025-10-01\"}" dag_daily_batch'
  ```
- 설명: `dag_daily_batch`를 수동으로 트리거. `-c` 옵션으로 JSON config 전달 (execution_mode=SIMULATION: 모의 테스트, analysis_date: 분석 날짜). run_collect_host.sh 스크립트와 유사.
- 사용 상황: UI 대신 터미널로 배치 DAG 실행 (예: 주식 분석 테스트).

## 6) Airflow: DAG run 목록 확인 (성공)
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags list-runs -d dag_daily_batch | tail -n 50"
  ```
- 설명: DAG 실행 목록과 상태(queued/running/success/failed)를 확인. 최근 50줄로 최신 run 우선.
- 사용 상황: 트리거 후 상태 모니터링 (예: manual__2025-10-13T... run 확인).

## 7) Airflow 로그 파일 직접 확인 (성공)
- 명령(성공):
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "ls -lt '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-13T12:00:00+00:00/task_id=calculate_core_metrics.calculate_rs_score/'"
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 200 '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-13T12:00:00+00:00/task_id=calculate_core_metrics.calculate_rs_score/attempt=1.log'"
  ```
- 설명: Airflow UI에서 로그가 보이지 않을 때 직접 컨테이너 파일 경로에서 로그 파일을 열어 분석. (디렉토리 → 최신 `attempt` 파일 → tail). TaskGroup 태스크(예: calculate_core_metrics.calculate_rs_score) 경로 주의.
- 사용 상황: RS/재무 계산 오류 디버깅 (예: filter_analysis_targets 로그 확인).

추가 예: `sync_stock_master` Task의 최신 run 로그를 바로 출력하려면 다음 명령을 사용하세요.
```
docker compose --env-file /home/jscho/ChartInsight-Studio/.env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 500 '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-16T13:15:40+00:00/task_id=sync_stock_master/attempt=1.log'"
```
사용 예: `dag_daily_batch`를 수동으로 트리거한 후(예: run_id `manual__2025-10-16T13:15:40+00:00`) `sync_stock_master`의 상세 로그를 확인하고자 할 때.

## 8) Airflow 스케줄러 로그 확인
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 200 /opt/airflow/logs/scheduler/$(date +%Y-%m-%d)/dag_daily_batch.py.log"
  ```
- 설명: 스케줄러가 DAG 파일을 처리(파싱/큐잉) 하는 과정의 로그를 확인하여 스케줄러 관련 이슈를 진단. 오늘 날짜로 로그 경로 동적 생성.
- 사용 상황: DAG 파싱 오류나 스케줄 실패 시 (예: dag_daily_batch 스케줄 17:00 실행 안 될 때).

## 9) 실행 중인 파이썬 CLI(로컬/컨테이너)에서 직접 테스트 (실행 예)
- 명령(컨테이너 내):
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "python /opt/airflow/src/analysis/rs_calculator.py --stock_codes '005930,000660' --mode SIMULATION"
  ```
- 설명: DAG가 아니라 로컬 CLI로 직접 스크립트를 실행해 디버깅. API 및 DB 동작을 빠르게 확인할 수 있음. dev_run_datapipeline.sh로 로컬 실행 가능.
- 사용 상황: 개별 모듈 테스트 (예: RS 계산기나 financial_analyzer.py – SIMULATION 모드 추천).

## 10) 문제 사례 (주의할 명령/실패 요약)
- 잘못된 예(실패 원인: 호스트에서 변수 확장됨):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart pg_dump -U "$POSTGRES_TRADESMART_USER" -d "$POSTGRES_DB" -t simulation.daily_analysis_results | gzip > ~/daily_analysis_backup.sql.gz
  ```
- 설명: 이 명령은 호스트 셸이 `"$POSTGRES_TRADESMART_USER"`를 먼저 확장하려고 시도해 `root` 같은 잘못된 사용자로 연결되어 실패했습니다. 위에서 제시한 컨테이너 내부 확장 방식으로 대체해야 합니다. .env.docker 변수(tradesmart_db) 사용 시 주의.
- 사용 상황: 백업/쿼리 시 자주 발생 – bash -lc로 컨테이너 내부 확장.

## 11) 체크리스트(디버깅 루틴)
- 컨테이너 이름 확인: `docker compose --profile pipeline ps`
- 컨테이너 내부 환경확인: `env | grep -i POSTGRES` (docker exec로)
- 로그 파일 위치 확인: `/opt/airflow/logs/dag_id=dag_daily_batch/...`
- Airflow CLI 지원 명령 확인: `airflow dags --help`
- 큰따옴표/작은따옴표로 환경변수 확장 범위 제어 (.env.local/docker 로드 확인)
- SIMULATION 모드 테스트: run_collect_host.sh 실행 후 DB/XCom 확인
- UI 로그인: username=airflow, password=airflow (.env.local 기반)

---

*문서 업데이트 기록*
- 2025-10-13: 환경 업데이트 — dag_daily_batch, simulation/live 스키마, run_collect_host.sh 통합. .env.local/docker 변수 반영.
- 2025-09-16: 최초 생성 (이전 버전 기반).


