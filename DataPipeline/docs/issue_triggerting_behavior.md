# dag_daily_batch 수동 트리거 시 scheduled run 동시 실행 현상 보고서

작성일: 2025-10-20

## 1) 현상 요약
- Web UI에서 `dag_daily_batch` DAG를 수동으로 트리거(Trigger w/ config)하면,
  동일 시점에 `scheduled__YYYY...` 형식의 자동 스케줄 Run도 함께 시작되어
  동일 DAG이 두 번 실행되는 것처럼 보이는 현상이 관찰됨.

## 2) 재현 절차(실제 플로우)
- 스케줄러 또는 컨테이너 재시작
- Web UI에서 pause 상태의 DAG에 대해 `Trigger w/ config` 실행 (기본으로 `Unpause DAG when triggered` 켜짐)
- 수동 트리거와 Unpause 동작이 동시에 이루어짐 → 스케줄러가 `scheduled__...` Run을 생성

## 3) 조사 근거
- 메타DB(dag_run) 쿼리 결과: 동일 시점에 두 레코드 존재
  - `manual__...` (external_trigger = true)
  - `scheduled__...` (external_trigger = false)
  두 레코드의 start_date가 거의 동일한 시각으로 기록됨.

## 4) 원인(평가)
- 가장 가능성 높은 시나리오: 스케줄러가 재시작 후 backlog/missed run을 생성(또는 DAG이 unpaused되어 스케줄된 run을 즉시 생성)한 시점과 사용자의 수동 트리거가 겹쳐 두 개의 Run이 병행 실행됨.
- UI의 `Unpause DAG when triggered` 기본 on 상태가 촉발 요인으로 작용함.

## 5) 영향
- 현재 관찰에서는 두 Run이 모두 성공으로 종료되었음. 그러나 외부 시스템에 쓰기 작업이 포함된 경우 중복 실행으로 인한 부작용(데이터 중복 등) 위험 존재.

## 6@
### 즉시(운영)
- 컨테이너/스케줄러 재시작 후 30–60초 대기한 뒤 수동 트리거.
- Web UI에서 `Trigger w/ config` 사용 시 `Unpause DAG when triggered` 체크 수동 해제 또는 CLI로 트리거.

### DAG 설정(권장 코드 변경
  ```python
  with DAG(..., catchup=False, max_active_runs=1, schedule_interval=..., start_date=..., ) as dag:
      ...
  ```

### 선택적(강화)
- 수동 트리거가 들어올 때 메타DB를 조회하여 동일 execution_date에 스케줄러 생성 Run이 있으면 수동 실행을 스킵하는 guard 추가(신중 적용).

## 7) 장기 권장
- Web UI 기본 행동을 변경하는 대신 DAG 레벨(설정/코드)과 운영절차로 대응 권장.

## 8) 재발 방지 체크리스트
- [ ] `max_active_runs=1` 적용 여부
- [ ] 운영 문서화: 재시작 후 대기 규칙, UI 트리거 시 Unpause 체크 확인
- [ ] idempotency 검증(특히 외부 쓰기 작업)

## 9) 참고 명령
- 메타DB 최근 runs 조회:
  ```bash
  docker compose --env-file .env.docker --profile pipeline exec postgres-airflow \ 
    bash -lc "psql -U <POSTGRES_USER> -d airflow_meta -c \"SELECT run_id,state,external_trigger,start_date FROM dag_run WHERE dag_id='dag_daily_batch' ORDER BY start_date DESC LIMIT 50;\""
  ```
- CLI로 unpause 없이 트리거:
  ```bash
  docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler \ 
    bash -lc "airflow dags trigger dag_daily_batch --run-id manual__$(date -u +%Y%m%dT%H%M%SZ)"
  ```

---

원하시면 이 문서를 `DataPipeline/docs/` 아래로 이동하거나 저장소 루트에 복제본을 남겨 커밋하겠습니다.


