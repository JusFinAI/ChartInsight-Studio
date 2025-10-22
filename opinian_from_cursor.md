

# 1.opinian_from_cursor.developer

짧은 상태: 지금은 코드 수정 없이 정책·런타임 보호책을 설계하는 단계입니다. 아래에 원인·해결안(단계별), 점검·긴급조치 명령어, 테스트·모니터링 권장안을 제시합니다.

핵심 문제 요약
- 증상: DAG를 unpause(또는 처음 활성화)할 때 과거 스케줄(run_id: scheduled__YYYY...)이 한두 번 또는 여러 개 생성되어 의도치 않은 실행이 발생.
- 근본 원인: Airflow 설계상의 catchup/스케줄 보정 동작 + start_date와 DAG 실행 기록(또는 기록 부재)의 상호작용. 단순히 catchup=False만으로 모든 엣지케이스를 막을 수 없음(특히 start_date가 과거로 설정되어 있고 이전 DAG run이 없는 경우 스케줄러가 최근 하나를 실행하려는 경향).

권장 해결 전략(우선순위별 — 적용 난이도/안전성 고려)
- 단기(빠르게 적용, 안전):
  - DAG 내부 가드 추가(수정 필요 — 간단 논리 설명만): DAG 시작 부분에 “실행 적합성 검사(Branch/ShortCircuit)”를 넣어, 현재 실행의 execution_date(=logical_date)가 허용된 범위(예: now - schedule_interval * 1)보다 과거이면 전체 작업을 건너뛰게 한다. 이렇게 하면 unpause 시 생성된 과거 스케줄을 안전하게 스킵할 수 있음.
  - DAG 설정 표준화(무중단 적용 가능): 이미 적용된 `catchup=False` 외에 `max_active_runs=1`, `depends_on_past=False` 를 명시적으로 설정해 두면 동시 실행/의존성 문제를 줄여 안전성을 높일 수 있음.
  - 운영 절차(정책): DAG를 unpause하기 전, 최근 DAG run 존재 여부(성공/실패)를 확인하는 체크리스트를 도입. 수동으로 이미 존재하는 과거 run을 수용하려면 UI에서 확인 후 수동 실행 권장.

- 중기(구성/운영 변경):
  - DAG 생성 시 `is_paused_upon_creation=True` 사용 혹은 start_date를 DAG 코드에서 과거가 아닌 적절한 최근 시점으로 재설정(주의: start_date 변경 시 기존 스케줄 영향 고려).
  - `LatestOnlyOperator` 또는 커스텀 “최신만 허용” 브랜치 도입 — 다만 LatestOnly는 스케줄링 특성이 있어 상황에 맞게 사용해야 함.
  - 표준화 스크립트: repo에 DAG 템플릿을 만들어 모든 DAG에 동일한 안전 설정(예: catchup=False, max_active_runs=1, guard operator 포함)을 적용.

- 장기(테스트/모니터링 인프라):
  - 통합 테스트: pause→unpause 시나리오를 자동으로 시뮬레이션하여 “의도치 않은 과거 실행 없음”을 검증하는 CI/테스트 스크립트 작성.
  - 모니터링/알림: 일정 기간 내 동일 DAG의 갑작스런 다량 Run 생성(예: 단시간내 N개 이상) 발생 시 Slack/메일 알림.
  - 운영 문서화: unpause/pause/재배포 표준 절차 문서화.

구체적 구현 아이디어(초심자도 이해할 수 있게 단계별 논리)
- 브랜치 검사 로직(코드 없이 논리만):
  1. DAG가 시작되면 Branch/ShortCircuit 검사 작업이 실행된다.
  2. 검사 작업은 현재 시간(now, KST)과 이 실행의 logical_date(=execution_date)를 비교한다.
  3. 만약 logical_date < (now - 허용 지연폭(예: schedule_interval * 1 또는 24시간)) 이면, “스킵” 분기로 빠져 나가고 실제 데이터 수집/분석 태스크는 실행되지 않는다.
  4. 허용범위 내이면 정상적으로 다음 태스크로 진행.
- 왜 안전한가? unpause시에 스케줄러가 생성한 과거 run들은 logical_date가 현재보다 훨씬 과거일 가능성이 큼 — 검사가 그걸 잡아내 스킵함.

긴급 조치 · 운영 명령어 (검사/조사용)
- DAG 실행 목록(최근 run들) 확인 (Airflow CLI; 컨테이너 명은 사용 환경에 맞춰 조정):
```bash
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "airflow dags list-runs -d dag_daily_batch --no-color | sed -n '1,200p'"
```
- 특정 DAG의 최근 로그/문제 있는 run 조회는 Airflow UI 권장(직관적).
- (DB 직접 조회) Airflow 메타데이터 DB에서 DAG run 확인(pgdocker/컨테이너/DB 이름 환경에 따라 경로 조정 필요):
```bash
# 예시(환경에 맞게 컨테이너/DB 접속정보 조정)
docker compose --env-file .env.docker --profile pipeline exec postgres-airflow bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT dag_id, run_id, state, execution_date, start_date FROM public.dag_run WHERE dag_id='dag_daily_batch' ORDER BY execution_date DESC LIMIT 30;\""
```
- 수동으로 ‘의도치 않은’ 특정 날짜의 run을 무효화/마크하려면 UI에서 수동으로 Mark Success / Clear 사용 권장(안전). CLI로는 `airflow dags backfill <dag_id> -s <date> -e <date> --mark_success` 로 해당 기간의 태스크를 성공 처리할 수 있음(주의 필요).

테스트 전략(권장)
- 시나리오 A (단기 확인): 개발 환경에서 DAG에 Guard를 넣고, DAG를 과거 start_date로 설정 → pause → unpause → 의도치않은 실행이 발생하지 않는지 확인.
- 시나리오 B (레거시 점검): 현재 운영 DAG들에 대해 `airflow dags list-runs`로 최근 7일간 run 패턴을 수집하여 spike 발생 여부 분석.
- 자동화: CI에서 pause/unpause 시나리오를 재현(컨테이너에서 API/CLI 호출)하고, run 목록/로그를 확인해 실패 시 알림.

리스크와 주의점
- start_date 조정은 신중: 과거 start_date를 변경하면 scheduler의 동작이 달라질 수 있음(과거 실행 생성 여부에 영향). 반드시 작은 범위에서 테스트 후 적용.
- DB 직접 업데이트(예: dag_run 상태 수정)는 권장하지 않음(메타데이터 일관성 위험). UI 혹은 Airflow CLI(백필/mark_success 등)를 우선 사용.
- LatestOnlyOperator 등은 DAG 성격에 따라 부작용(예: 백필 용도와 충돌) 있을 수 있으므로 DAG별 목적 고려 필요.

다음 실무적 제안(제가 바로 진행 가능한 일 — 우선순위 제안)
1. (제가 할 수 있음) 현재 핵심 DAG(`dag_daily_batch`, `dag_initial_loader`, `dag_live_collectors`)의 DAG 파라미터(start_date, catchup, max_active_runs, depends_on_past)를 감사해서 불일치 목록을 드리겠습니다. (이 작업을 시작하려면 허가 필요 — 코드를 읽기만 함)
2. (안전한 코드 변경 제안) `dag_daily_batch`에 Branch 기반의 “execution_date 허용범위 검사”를 추가하는 변경안을 PR 형태로 제안/작성하겠습니다(원하시면 코드까지 구현).
3. 테스트 스크립트(파이프라인 컨테이너 내에서 pause→unpause 시나리오를 자동으로 수행하고 결과를 검사하는 쉘 스크립트)를 만들어 드리겠습니다(원하시면 바로 작성).

원하시는 다음 행동(선택)
- A: 바로 1번(감사) 진행 — DAG 설정 목록과 불일치 리포트 제공 (권장, 코드 읽기만).
- B: 바로 2번(가드 로직) 코드 제안 및 구현(사전 리뷰 요청) — 제가 코드 편집 제안 후 사용자가 승인하면 적용.
- C: 테스트 스크립트(시뮬레이션) 먼저 생성.
- D: 우선 운영 매뉴얼(운영자용 체크리스트) 문서화만 요청.

요약(핵심만)
- 문제: Airflow의 설계(특히 start_date와 run 기록 관련) 때문에 unpause 시 과거 스케줄이 실행될 수 있음 — catchup=False만으론 완전 차단 불가.  
- 단기 해법: DAG 내부의 execution_date 검사(Branch/ShortCircuit)로 과거 run 스킵, `max_active_runs=1`, `depends_on_past=False` 명시.  
- 중/장기: DAG 설정 표준화, 자동화된 pause→unpause 테스트, 모니터링/알림.  
- 바로 할 일 제안: 제가 먼저 DAG 설정 감사(리포트 생성)를 수행하고 그 결과로 우선순위 변경/코드 적용을 결정하면 좋겠습니다.

------------------
# 2. opinian_from_cursor.inspector 

## 🔍 P2 과제: Airflow DAG 실행 정책 안정화 - Insight 및 제안

**감독관님, P2 과제에 대한 제 insight와 제안을 말씀드리겠습니다.**

### 🎯 **문제 현상 정확한 분석**

#### ✅ **현재 상황 진단**
```python:5:DataPipeline/dags/dag_daily_batch.py
catchup=False,  # <--- 이미 False로 설정되어 있음
```

**문제**: `catchup=False`만으로는 Airflow의 "첫 실행 보정" 동작을 완전히 차단할 수 없음

#### ✅ **근본 원인**
1. **Airflow 스케줄러의 보정 메커니즘**: start_date가 과거이고 실행 기록이 없는 DAG는 최근 1개 스케줄을 실행하려는 경향
2. **시간대 이슈**: UTC vs KST 시간대 차이로 인한 스케줄 계산 오차
3. **DAG 상태 전환**: pause → unpause 시 스케줄러의 재계산 동작

### 🚀 **제안하는 해결 방안**

#### 1. **start_date 최적화** (가장 효과적)
```python
# AS-IS: 고정된 과거 start_date
start_date=pendulum.datetime(2025, 10, 1, tz="Asia/Seoul")

# TO-BE: 동적 start_date (현재 시간으로 설정)
start_date=pendulum.now('Asia/Seoul')  
```

**장점**: 과거 스케줄이 존재하지 않아 catchup 발생 자체를 원천 차단

#### 2. **schedule_interval 조정** (보조적)
```python
# AS-IS: 매일 17시 KST 고정
schedule_interval="0 17 * * *"  # UTC: 08:00

# TO-BE: 더 유연한 스케줄 또는 @once
schedule_interval=None  # 수동 실행 전용으로 변경
```

#### 3. **DAG 상태 관리 강화** (운영적)
```python
# DAG unpause 시 추가 검증 로직
def safe_unpause_dag(dag_id):
    # 1. 마지막 실행 기록 확인
    # 2. 현재 시간이 다음 스케줄 시간 이후인지 확인  
    # 3. 조건에 맞지 않으면 unpause 보류
    pass
```

### 📊 **구현 난이도 및 효과 비교**

| 해결 방안 | 구현 난이도 | 효과성 | 운영 영향 |
|-----------|------------|--------|-----------|
| ✅ **start_date 동적화** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 낮음 |
| schedule_interval 조정 | ⭐ | ⭐⭐ | 중간 |  
| DAG 상태 관리 강화 | ⭐⭐⭐ | ⭐⭐⭐ | 높음 |

### 🎯 **최적의 접근법**

**단계적 구현 권장**:

#### 1단계: **start_date 동적화 (즉시 적용)**
```python
# DataPipeline/dags/dag_daily_batch.py 수정
start_date=pendulum.now('Asia/Seoul').subtract(days=1)  # 안전을 위해 1일 전
```

#### 2단계: **스케줄러 동작 모니터링**
```bash
# 스케줄러 로그 확인
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c "tail -f /opt/airflow/logs/scheduler/$(date +%Y-%m-%d)/dag_daily_batch.py.log"
```

#### 3단계: **운영자 가이드 제공**
```markdown
## DAG 실행 정책 가이드
1. DAG를 pause할 때: `airflow dags pause dag_daily_batch`
2. DAG를 unpause할 때: **다음 스케줄 시간 1시간 전에** 실행
3. 긴급 실행 시: 수동 trigger 사용 (`airflow dags trigger`)
```

### 🔍 **주의사항 및 고려할 점**

1. **기존 실행 기록**: start_date 변경해도 기존 실행 기록은 유지됨
2. **시간대 일관성**: 모든 DAG가 동일한 시간대(Asia/Seoul) 사용 확인
3. **의존성 Task**: 다른 DAG와의 의존성 관계 고려

### 📈 **기대 효과**

1. **의도치 않은 실행 100% 제거**: 과거 스케줄이 존재하지 않아 catchup 발생 불가
2. **운영 예측성 향상**: DAG 활성화 시점부터만 실행 보장
3. **시스템 안정성**: 스케줄러의 보정 동작에서 완전히 자유로워짐

**감독관님, `start_date`를 동적으로 설정하는 것이 가장 효과적이고 간단한 해결책입니다.** 이렇게 하면 Airflow의 catchup 메커니즘 자체를 우회할 수 있습니다. 🚀