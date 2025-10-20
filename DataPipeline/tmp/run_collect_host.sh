#!/bin/bash
# =============================================================================
# 스크립트: run_collect_host.sh
# 
# 목적: 
#   이 스크립트는 Airflow DAG (dag_daily_batch)를 SIMULATION 모드로 트리거하고,
#   실행 완료 상태를 폴링하며, 태스크 상태와 로그를 수집하고, XCom 값을 덤프하며,
#   시뮬레이션 데이터베이스에서 결과를 확인합니다.
#   실제 데이터에 영향을 주지 않고 일일 주식 분석 파이프라인을 디버깅하고 테스트하기 위해 설계되었습니다 (execution_mode: SIMULATION).
# 
# 사용법:
#   chmod +x run_collect_host.sh
#   ./run_collect_host.sh
# 
# 요구사항:
#   - Docker Compose의 pipeline 프로파일이 실행 중 (Airflow + Postgres).
#   - JSON 파싱을 위한 jq가 설치되어 있어야 함 (컨테이너 또는 호스트).
#   - Airflow DAG: dag_daily_batch가 /opt/airflow/dags/에 존재해야 함.
# 
# 섹션:
#   1. 설정: RUN_ID 생성 및 DAG 트리거.
#   2. 폴링: DAG 실행 완료까지 최대 2분 대기.
#   3. 태스크 상태 및 로그: 주요 태스크의 상태와 최근 로그 가져오기.
#   4. XCom 덤프: 태스크 간 데이터 쿼리.
#   5. DB 확인: simulation.daily_analysis_results 테이블 결과 검증.
# 
# 노트:
#   - 비중요 오류 시 스크립트 실패 방지를 위해 '|| true' 사용.
#   - SIMULATION 모드: 실제 데이터 업데이트 없음; 모의 함수 사용.
#   - analysis_date를 '2025-10-01'로 고정하여 재현 가능한 테스트.
#   - 로그는 /opt/airflow/logs/에서 가져옴 (최대 400줄).
#   - DB 쿼리는 analysis_date의 UTC/KST 시간대를 표시.
# 
# 문제 해결:
#   - 폴링 실패 시: Airflow 스케줄러 로그 확인.
#   - XCom 없음: 태스크가 XCom.push()로 값을 반환하는지 확인.
#   - DB 비어 있음: load_final_results 태스크 성공 확인.
# 
# 작성자: Grok AI가 주석 추가 지원 (원본 스크립트 기반).
# 날짜: 2025-10-13
# =============================================================================

set -euo pipefail  # 엄격 모드 활성화: 오류 시 종료 (-e), 정의되지 않은 변수 오류 (-u), 파이프 실패 (-o pipefail)

# 섹션 1: 고유 RUN_ID 생성 및 SIMULATION 모드로 DAG 트리거
RUN_ID="manual__$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"  # 수동 실행을 위한 UTC 타임스탬프 기반 RUN_ID 생성
echo "Triggering DAG run: $RUN_ID (SIMULATION)"  # 시작 RUN_ID 안내 메시지 출력

# 스케줄러 컨테이너의 Airflow CLI를 통해 DAG 트리거
# --run-id: 추적을 위한 사용자 정의 ID
# --conf: JSON 설정으로 execution_mode=SIMULATION (모의 데이터, API 호출 없음) 및 고정 analysis_date
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags trigger dag_daily_batch --run-id \"$RUN_ID\" --conf '{\"execution_mode\":\"SIMULATION\",\"analysis_date\":\"2025-10-01\"}' || true"

# 섹션 2: DAG 실행 완료 폴링 (60회 반복, 2초 간격 ~ 최대 2분 대기)
echo "Polling for run state..."  # 폴링 시작 안내
for i in $(seq 1 60); do  # 1부터 60까지 반복 (seq: 숫자 시퀀스 생성)
  # Airflow CLI와 jq를 사용해 특정 run의 상태 가져오기 (JSON 파싱)
  # airflow dags list-runs: DAG의 run 목록; --output json으로 기계 판독 가능
  # jq: run_id로 필터링하고 .state 추출 (예: queued, running, success, failed)
  STATE=$(docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow dags list-runs -d dag_daily_batch --output json | jq -r --arg r '$RUN_ID' '.[] | select(.run_id==\$r) | .state'" 2>/dev/null || true)
  echo "[$i] STATE=$STATE"  # 진행 상황을 위한 현재 폴링 횟수와 상태 출력
  if [ "$STATE" = "success" ] || [ "$STATE" = "failed" ]; then  # 실행 완료 (success 또는 failed) 확인
    break  # 조기 루프 종료
  fi
  sleep 2  # 폴링 간 2초 대기 (스케줄러 과부하 방지)
done

# 섹션 3: 주요 태스크의 상태 및 로그 수집 (디버깅 중심)
echo "--- TASK STATES ---"  # 태스크 상태 출력 헤더
# 이 특정 DAG run의 모든 태스크 상태 나열
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "airflow tasks states-for-dag-run dag_daily_batch $RUN_ID" || true

echo "--- LOG: filter_analysis_targets ---"  # 필터링 태스크 로그 (DAG의 Task 3)
# 이 태스크의 첫 번째 시도 로그 파일의 최근 400줄 가져오기
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 400 \"/opt/airflow/logs/dag_id=dag_daily_batch/run_id=$RUN_ID/task_id=filter_analysis_targets/attempt=1.log\"" || true

echo "--- LOG: calculate_rs_score ---"  # RS 점수 계산 로그 (calculate_core_metrics 그룹의 하위 태스크)
# RS 점수 태스크 로그 가져오기 (TaskGroup 접두사 주의: calculate_core_metrics.calculate_rs_score)
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 400 \"/opt/airflow/logs/dag_id=dag_daily_batch/run_id=$RUN_ID/task_id=calculate_core_metrics.calculate_rs_score/attempt=1.log\"" || true

echo "--- LOG: calculate_financial_grade ---"  # 재무 등급 계산 로그 (calculate_core_metrics의 하위 태스크)
# 재무 등급 태스크 로그 가져오기
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 400 \"/opt/airflow/logs/dag_id=dag_daily_batch/run_id=$RUN_ID/task_id=calculate_core_metrics.calculate_financial_grade/attempt=1.log\"" || true

echo "--- LOG: load_final_results ---"  # 최종 결과 DB 로딩 로그 (Task 6)
# DB upsert 태스크 로그 가져오기
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "tail -n 400 \"/opt/airflow/logs/dag_id=dag_daily_batch/run_id=$RUN_ID/task_id=load_final_results/attempt=1.log\"" || true

# 섹션 4: Airflow 메타데이터 DB에서 XCom 값 덤프 (태스크 간 통신 데이터)
echo "--- XCOM DUMP (container) ---"  # XCom 추출 헤더
# 이 run의 XCom을 쿼리하기 위한 인라인 Python 스크립트
# SQLAlchemy 세션을 사용해 DagRun과 관련 XCom 가져오기
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc "python3 - <<'PY'
from airflow.utils.session import create_session
from airflow.models import DagRun, XCom
dag_id='dag_daily_batch'
run_id='$RUN_ID'
with create_session() as session:
    dr = session.query(DagRun).filter(DagRun.dag_id==dag_id, DagRun.run_id==run_id).one_or_none()
    print('DagRun found:', bool(dr))
    if not dr:
        raise SystemExit(0)
    xcoms = session.query(XCom).filter(XCom.dag_id==dag_id, XCom.execution_date==dr.execution_date).all()
    print('Found', len(xcoms), 'xcoms')
    for x in xcoms:
        print('\\nTASK:', x.task_id, 'KEY:', x.key)
        try:
            print('VALUE repr:', repr(x.value)[:1000])  # 출력 제한: 처음 1000자
        except Exception as e:
            print('VALUE read error:', e)
PY" || true

# 섹션 5: 시뮬레이션 데이터베이스 결과 검증 (Postgres 쿼리)
echo "--- DB check: simulation.daily_analysis_results (recent 1 hour) ---"  # DB 검증 헤더
# psql을 통해 simulation 스키마의 daily_analysis_results 테이블 쿼리
# 주요 컬럼 선택 및 시간대 변환 (UTC → Asia/Seoul)과 최근 데이터 필터링
docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -lc "psql -U tradesmart_db -d tradesmart_db -c \"SELECT analysis_date AT TIME ZONE 'UTC' as ad_utc, (analysis_date AT TIME ZONE 'Asia/Seoul') as ad_kst, stock_code, market_rs_score, sector_rs_score, financial_grade FROM simulation.daily_analysis_results WHERE analysis_date >= now() - interval '1 hour' ORDER BY stock_code\""

echo "Done."  # 최종 완료 메시지


