<!-- Documentation of useful docker/psql/airflow commands used during DataPipeline debugging -->

# DataPipeline 디버깅 명령 레퍼런스

이 문서는 로컬 개발 환경(WSL2 + Docker)에서 DataPipeline을 디버깅할 때 사용한 `docker exec`, `psql`, `airflow` 관련 명령을 정리한 참고 자료입니다. 각 명령은 **명령어**, **설명**, **사용 상황**을 포함합니다. 실패하거나 수정이 필요한 명령도 함께 기재했습니다.

- **주의**: 명령을 실행할 때 환경변수 확장(호스트 vs 컨테이너)과 따옴표 인용을 정확히 해야 합니다. 특히 `docker exec bash -lc "..."`처럼 컨테이너 내부에서 확장되도록 실행하세요.

---

- **파일**: `DataPipeline/docs/debugging_commands.md`

## 1) 컨테이너 상태 확인
- 명령:
```
docker ps
```
- 설명: 실행 중인 컨테이너 목록과 이름/포트 확인. Airflow 관련 컨테이너 이름(예: `airflow-webserver`, `airflow-scheduler`, `postgres-tradesmart`)을 확인할 때 사용.

## 2) Postgres: 컨테이너 내부 환경변수 확인
- 명령(성공):
```
docker exec -it postgres-tradesmart bash -lc 'env | grep -i POSTGRES'
```
- 설명: 컨테이너 내부에 설정된 DB 사용자·DB명을 확인. `POSTGRES_USER`, `POSTGRES_DB` 값을 안전하게 가져올 때 사용.

## 3) Postgres: 특정 테이블 백업 (성공)
- 명령(성공):
```
docker exec -it postgres-tradesmart bash -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t live.candles > /tmp/live_candles_backup.sql'
docker cp postgres-tradesmart:/tmp/live_candles_backup.sql ./live_candles_backup.sql
ls -lh ./live_candles_backup.sql
```
- 설명: `live.candles` 테이블 전체 덤프를 컨테이너 내부에서 생성한 뒤 호스트로 복사하여 백업. 환경변수는 컨테이너 내부에서 확장되도록 작은따옴표/큰따옴표 사용에 주의.

## 4) Postgres: 쿼리 실행 (컨테이너 내부 환경변수 사용, 성공)
- 명령(성공 예):
```
docker exec -it postgres-tradesmart bash -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT stock_code, COUNT(*) FROM live.candles WHERE timeframe = '\''D'\'' GROUP BY stock_code ORDER BY stock_code;"'
```
- 설명: 컨테이너 환경변수를 사용하여 안전하게 psql 쿼리를 실행. 외부(호스트)에서 변수를 확장하면 잘못된 사용자로 연결되는 문제가 발생하므로 주의.

## 5) Airflow CLI: DAG 수동 트리거 (성공)
- 명령:
```
docker exec -it airflow-webserver bash -lc 'airflow dags trigger -c "{\"run_all_targets\": true, \"period\": \"5y\", \"execution_mode\": \"LIVE\"}" dag_initial_loader'
```
- 설명: `dag_initial_loader`를 수동으로 트리거. `-c` 옵션으로 JSON config 전달 가능.

## 6) Airflow: DAG run 목록 확인 (성공)
- 명령:
```
docker exec -it airflow-webserver bash -lc "airflow dags list-runs -d dag_initial_loader | tail -n 50"
```
- 설명: DAG 실행 목록과 상태(failed/success)를 확인.

## 7) Airflow 로그 파일 직접 확인 (성공)
- 명령(성공):
```
docker exec -it airflow-webserver bash -lc "ls -lt '/opt/airflow/logs/dag_id=dag_initial_loader/run_id=manual__2025-09-15T19:34:10+09:00/task_id=initial_load_task'"
docker exec -it airflow-webserver bash -lc "tail -n 200 '/opt/airflow/logs/dag_id=dag_initial_loader/run_id=manual__2025-09-15T19:34:10+09:00/task_id=initial_load_task/attempt=2.log'"
```
- 설명: Airflow UI에서 로그가 보이지 않을 때 직접 컨테이너 파일 경로에서 로그 파일을 열어 분석. (디렉토리 → 최신 `attempt` 파일 → tail)

## 8) Airflow 스케줄러 로그 확인
- 명령:
```
docker exec -it airflow-webserver bash -lc "tail -n 200 /opt/airflow/logs/scheduler/2025-09-15/dag_initial_loader.py.log"
```
- 설명: 스케줄러가 DAG file을 처리(파싱/큐잉) 하는 과정의 로그를 확인하여 스케줄러 관련 이슈를 진단.

## 9) 실행 중인 파이썬 CLI(로컬)에서 직접 테스트 (실행 예)
- 명령:
```
docker exec -it airflow-webserver bash -lc "python /opt/airflow/src/data_collector.py initial 005930 d --period 5y --mode LIVE"
```
- 설명: DAG가 아니라 로컬 CLI로 직접 스크립트를 실행해 디버깅. API 및 DB 동작을 빠르게 확인할 수 있음.

## 10) 문제 사례 (주의할 명령/실패 요약)
- 잘못된 예(실패 원인: 호스트에서 변수 확장됨):
```
docker exec -it postgres-tradesmart pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -n live | gzip > ~/candles_live_backup.sql.gz
```
설명: 이 명령은 호스트 셸이 `"$POSTGRES_USER"`를 먼저 확장하려고 시도해 `root` 같은 잘못된 사용자로 연결되어 실패했습니다. 위에서 제시한 컨테이너 내부 확장 방식으로 대체해야 합니다.

## 11) 체크리스트(디버깅 루틴)
- 컨테이너 이름 확인: `docker ps`
- 컨테이너 내부 환경확인: `env | grep -i POSTGRES`
- 로그 파일 위치 확인: `/opt/airflow/logs/...`
- Airflow CLI가 지원하는 명령인지 확인: `airflow tasks --help`
- 큰따옴표/작은따옴표로 환경변수 확장 범위 제어

---

*문서 업데이트 기록*
- 2025-09-16: 최초 생성 — single-run 디버깅 세션에서 사용된 성공/실패 명령 정리.


