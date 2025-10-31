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
  docker-compose --env-file .env.docker --profile pipeline down 
  ```
-설명 : 컨테이너 종료 

- 명령:
  ```
  docker-compose --env-file .env.docker --profile pipeline down -v
  ```
-설명 : 컨테이너 종료 및 볼륨 삭제

- 옵션: --remove-orphans 옵션을 추가하면, 현재 Compose 파일에 정의되어 있지 않은 컨테이너들도 함께 중지 및 삭제되어, 불필요한 리소스가 남지 않게 됩니다.

- 명령:
  ```
  docker-compose --env-file .env.docker --profile pipeline down --remove-orphans -v
  ```


## 1.2 컨테이너 재시작 및 빌드 (이미지 재생성 포함)
- 명령:
  ```
  docker-compose --env-file .env.docker --profile pipeline up -d
  ```
- 설명: 컨테이너 재시작 (기존 이미지와 빌드 캐시 유지, 코드 변경없이 재시작 용도)

- 명령(이미지 빌드/의존성 업데이트 후 재시작):
  ```
  docker-compose --env-file .env.docker --profile pipeline up -d --build
  ```
- 설명: 컨테이너 시작 전 이미지를 다시 빌드. requirements.txt, Dockerfile 수정 또는 라이브러리, 코드에 변경사항이 있을 때 사용(이미지 최신화).

- 참고: `docker compose` 명령으로도 사용 가능함 (`docker compose ...`로 대체 가능, 버전 2 이상 권장)

- 명령: 재시작 (restart)
```
docker compose --env-file .env.docker --profile pipeline restart airflow-scheduler airflow-webserver
```
- 설명: 컨테이너 재시작



## 2) Postgres: 컨테이너 내부 환경변수 확인
- 명령(성공):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc 'env | grep -i POSTGRES'
  ```
- 설명: 컨테이너 내부에 설정된 DB 사용자·DB명을 확인. `POSTGRES_TRADESMART_USER=tradesmart_db`, `POSTGRES_DB=tradesmart_db` 값을 안전하게 가져올 때 사용. .env.docker에서 로드된 값.
- 사용 상황: DB 연결 실패 시 (예: psql 오류) 변수 확인.

## 3) Postgres: 쿼리 실행 (컨테이너 내부 환경변수 사용, 성공)


**financial_analysis_results 테이블의 전체 컬럼과 타입 조회**:
dag_financials_update 실행 직후 \d 명령으로 live.financial_analysis_results 테이블의 컬럼명과 데이터 타입을 확인합니다.

```bash
docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c '\\d live.financial_analysis_results' | grep -E '^\\s+\\w+'"
```


**financial_analysis_results 테이블의 전체 컬럼 조회**:
: `dag_financials_update` 실행 직후 financial_analysis_results 테이블의 전체 컬럼을 조회하여 모든 데이터가 정상적으로 저장되었는지 확인합니다.

  ```bash
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT * FROM live.financial_analysis_results WHERE stock_code IN ('005930','000660','373220','005380','035420','207940','005490','051910','105560','096770','033780','247540') ORDER BY stock_code, analysis_date DESC;\""
  ```

- **financial_analysis_results 테이블의 특정 컬럼 조회**: 
`dag_financials_update` 실행 직후 특정 종목들의 분석 결과가 `live.financial_analysis_results` 테이블의 stock_code, analysis_date, financial_grade, eps_growth_yoy, eps_annual_growth_avg 컬럼에 정상적으로  저장되었는지 확인합니다..

  ```bash
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT stock_code, analysis_date, financial_grade, eps_growth_yoy, eps_annual_growth_avg FROM live.financial_analysis_results WHERE stock_code IN ('005930','000660','373220','005380','035420','207940','005490','051910','105560','096770','033780','247540') ORDER BY stock_code, analysis_date DESC;\""
  ```


- **목적**: `dag_daily_batch` 전체 실행 후 오늘(예: `2025-10-24`) 생성된 주요 컬럼(`market_rs_score`, `sector_rs_score`, `financial_grade`, 기술적 컬럼 등)이 정상적으로 채워졌는지 빠르게 확인합니다.

  ```bash
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c \
  "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT stock_code, analysis_date, market_rs_score, sector_rs_score, financial_grade, eps_growth_yoy, eps_annual_growth_avg, sma_20_val, rsi_14_val FROM live.daily_analysis_results WHERE analysis_date = '2025-10-24' AND (financial_grade IS NOT NULL OR market_rs_score IS NOT NULL) ORDER BY stock_code LIMIT 500;\""
  ```

- **활용 케이스**:
  - DAG 실행 직후 핵심 분석 컬럼이 제대로 적재되었는지 검증
  - 기술적 지표(`sma_20_val` 등)가 null인 경우 기술 태스크(`run_technical_analysis`)와 비교·추적
  - NaN 또는 비정상적 수치(예: `eps_annual_growth_avg = NaN`)가 있는 종목을 식별하여 원인(데이터 부족/계산 오류)을 조사

- **실행 팁**:
  - `analysis_date` 값은 DAG 실행의 logical_date 또는 params.analysis_date와 일치시켜 사용하세요.
  - 결과가 많으면 `LIMIT`을 적절히 낮춰 샘플만 확인하고, 필요 시 `WHERE stock_code IN (...)`로 범위를 좁히세요.
  - 기술적 컬럼과 XCom(예: `run_technical_analysis`)의 값을 비교하려면 XCom을 decode(`convert_from(value,'UTF8')`)하여 매핑을 확인하세요.


## 3.1) Postgres: `live.stocks` 직접 조회 (예제 추가)
- 목적: DAG 실행 후 `live.stocks` 테이블의 상태(`is_active`, `backfill_needed`, `is_analysis_target`)을 빠르게 확인
- 권장 실행 위치: `postgres-tradesmart` 컨테이너 내부 (컨테이너 환경변수 사용 권장)
- 권장 명령(컨테이너 내부에서 env 변수를 확장하도록 실행):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT stock_code, stock_name, is_active, backfill_needed, is_analysis_target FROM live.stocks WHERE stock_code IN ('005930','000660','373220','005380','035420','207940','005490','051910','105560','096770','033780','247540') ORDER BY stock_code;\""
  ```
- 설명 및 실행 팁:
  - `bash -c`를 사용하고 `\$POSTGRES_USER`처럼 환경변수 앞에 백슬래시를 추가해야 컨테이너 내부에서 정확히 확장됩니다.
  - 결과 예시: 각 종목의 `is_active`가 `t`(True)인지, `backfill_needed`가 `f`로 업데이트 되었는지, `is_analysis_target` 플래그가 기대대로 설정되었는지 확인할 수 있습니다.
  - 대규모 결과가 나올 경우(수천 행) `ORDER BY ... LIMIT 50` 같은 절을 추가하여 샘플만 확인하세요.

## 3.2) Postgres: live.stocks의 is_analysis_target 통계 조회
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT COUNT(*) FILTER (WHERE is_analysis_target) AS true_cnt, COUNT(*) FILTER (WHERE NOT is_analysis_target) AS false_cnt FROM live.stocks;\""
  ```
- 설명: 이 명령어는 컨테이너 내부에서 안전하게 환경변수를 확장하여 PostgreSQL 클라이언트를 실행합니다. 쿼리는 live.stocks 테이블에서 is_analysis_target 컬럼이 참인 행과 거짓인 행의 개수를 각각 집계함으로써 데이터의 상태를 빠르게 확인할 수 있도록 합니다.


## 4) Airflow CLI: DAG 수동 트리거 
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc 'airflow dags trigger -c "{\"execution_mode\": \"SIMULATION\", \"analysis_date\": \"2025-10-01\"}" dag_daily_batch'
  ```
- 설명: `dag_daily_batch`를 수동으로 트리거. `-c` 옵션으로 JSON config 전달 (execution_mode=SIMULATION: 모의 테스트, analysis_date: 분석 날짜). run_collect_host.sh 스크립트와 유사.
- 사용 상황: UI 대신 터미널로 배치 DAG 실행 (예: 주식 분석 테스트).

## 5) Airflow: DAG run 목록 확인 (성공)
- 명령(실행 예시 — 최신 50개 DAG run만 출력):
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags list-runs -d dag_initial_loader | tail -n 50"
  ```

  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags list-runs -d dag_daily_batch | tail -n 50"
  ```
- 설명: 
  - 각각의 명령은 해당 DAG(dag_initial_loader, dag_daily_batch)의 실행 이력을 최신순으로 50개만 출력합니다.
  - 상태(queued/running/success/failed) 및 실행일자(run_date) 등 핵심 정보를 확인할 수 있습니다.
  - 여러 DAG의 실행 상태를 빠르게 비교할 때 위와 같이 각각 따로 명령을 실행하세요.

- 사용 상황: 
  - DAG를 수동 트리거한 후, 실행(run) 결과와 상태를 실시간으로 모니터링할 때 사용합니다.
  - 특정 run_id(예: manual__2025-10-13T12:00:00+00:00)가 성공적으로 실행되었는지, 실패했는지를 신속하게 파악하고자 할 때 활용합니다.


## 6) Airflow 로그 파일 직접 확인 및 분석 방법

- **목적**: Airflow UI에서 로그가 표시되지 않을 때 컨테이너 내부 로그 파일을 직접 확인
- **로그 경로 구조**: `/opt/airflow/logs/dag_id={DAG명}/run_id={실행ID}/task_id={태스크명}/attempt={시도횟수}.log`

### 기본 사용법
- **로그 디렉토리 확인**:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "ls -lt '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-21T11:28:21+09:00/task_id=calculate_core_metrics.calculate_rs_score/'"
  ```

- **로그 내용 확인 (최근 200줄)**:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "tail -n 200 '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-21T11:28:21+09:00/task_id=calculate_core_metrics.calculate_rs_score/attempt=1.log'"
  ```

### 실용적 예시
- **dag_initial_loader 특정 태스크 로그**:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "tail -n 500 '/opt/airflow/logs/dag_id=dag_initial_loader/run_id=manual__2025-10-20T17:20:09+09:00/task_id=stock_info_load_task/attempt=1.log'"
  ```

  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "tail -n 500 '/opt/airflow/logs/dag_id=dag_initial_loader/run_id=manual__2025-10-20T17:20:09+09:00/task_id=initial_load_task/attempt=1.log'"
  ```

### 실행 팁
1. **경로 구성**: `dag_id` → `run_id` → `task_id` → `attempt=N.log` 순으로 구성
2. **최신 attempt 확인**: `ls -lt`로 가장 최근 attempt 파일 확인 후 `tail` 실행
3. **출력 줄 수 조절**: `-n 200`, `-n 500` 등 필요에 따라 조정
4. **TaskGroup 주의**: 긴 task_id(`calculate_core_metrics.calculate_rs_score`)는 경로 복사 추천

### 사용 상황
- Airflow UI 로그 미표시 시 상세 오류 확인
- 커스텀 print/log 메시지 직접 확인
- TaskGroup 내 태스크 로그 확인
- DB 쿼리, 데이터 처리 예외 등 상세 디버깅

## 7) Airflow 스케줄러 로그 확인
- 명령:
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 200 /opt/airflow/logs/scheduler/$(date +%Y-%m-%d)/dag_daily_batch.py.log"
  ```
- 설명: 스케줄러가 DAG 파일을 처리(파싱/큐잉) 하는 과정의 로그를 확인하여 스케줄러 관련 이슈를 진단. 오늘 날짜로 로그 경로 동적 생성.
- 사용 상황: DAG 파싱 오류나 스케줄 실패 시 (예: dag_daily_batch 스케줄 17:00 실행 안 될 때).

## 8) 실행 중인 파이썬 CLI(로컬/컨테이너)에서 직접 테스트 (실행 예)
- 명령(컨테이너 내):
  ```
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "python /opt/airflow/src/analysis/rs_calculator.py --stock_codes '005930,000660' --mode SIMULATION"
  ```
- 설명: DAG가 아니라 로컬 CLI로 직접 스크립트를 실행해 디버깅. API 및 DB 동작을 빠르게 확인할 수 있음. dev_run_datapipeline.sh로 로컬 실행 가능.
- 사용 상황: 개별 모듈 테스트 (예: RS 계산기나 financial_analyzer.py – SIMULATION 모드 추천).

## 9) 문제 사례 (주의할 명령/실패 요약)
- 잘못된 예(실패 원인: 호스트에서 변수 확장됨):
  ```
  docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart pg_dump -U "$POSTGRES_TRADESMART_USER" -d "$POSTGRES_DB" -t simulation.daily_analysis_results | gzip > ~/daily_analysis_backup.sql.gz
  ```
- 설명: 이 명령은 호스트 셸이 `"$POSTGRES_TRADESMART_USER"`를 먼저 확장하려고 시도해 `root` 같은 잘못된 사용자로 연결되어 실패했습니다. 위에서 제시한 컨테이너 내부 확장 방식으로 대체해야 합니다. .env.docker 변수(tradesmart_db) 사용 시 주의.
- 사용 상황: 백업/쿼리 시 자주 발생 – bash -lc로 컨테이너 내부 확장.

## 10) 체크리스트(디버깅 루틴)
- 컨테이너 이름 확인: `docker compose --profile pipeline ps`
- 컨테이너 내부 환경확인: `env | grep -i POSTGRES` (docker exec로)
- 로그 파일 위치 확인: `/opt/airflow/logs/dag_id=dag_daily_batch/...`
- Airflow CLI 지원 명령 확인: `airflow dags --help`
- 큰따옴표/작은따옴표로 환경변수 확장 범위 제어 (.env.local/docker 로드 확인)
- SIMULATION 모드 테스트: run_collect_host.sh 실행 후 DB/XCom 확인
- UI 로그인: username=airflow, password=airflow (.env.local 기반)

## 11) 업종 마스터 DAG 디버깅 (dag_sector_master_update)

### DAG 수동 실행
```bash
# DAG 트리거
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags trigger dag_sector_master_update"

# 태스크 실행 (run_id 확인 후)
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow tasks run dag_sector_master_update update_sector_master_task manual__2025-10-21T07:44:20+00:00 --local"
```

### 데이터 검증
```bash
# sectors 테이블 데이터 개수 확인
docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'SELECT COUNT(*) FROM live.sectors;'"

# 샘플 데이터 확인  
docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c 'SELECT * FROM live.sectors LIMIT 10;'"
```

### 사용 상황
- 업종 마스터 데이터 수집 테스트
- 주간 스케줄 DAG 수동 검증
- API 응답 형식 변경 시 데이터 품질 확인
- Kiwoom API ka10101 호출 결과 검증

### 참고 사항
- 이 DAG는 매주 토요일 오전 2시에 자동 실행됩니다
- 실행 시 live.sectors 테이블에 UPSERT 방식으로 데이터가 저장됩니다
- KOSPI와 KOSDAQ 업종을 모두 수집합니다 (총约 65개)




