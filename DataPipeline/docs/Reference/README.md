# 📖 개발 참조 문서 (Reference)

## 📋 개요

이 폴더는 **DataPipeline 개발 중 지속적으로 참조**해야 하는 기술 문서를 담고 있습니다.

### Archive vs Reference vs Reports

| 구분 | 목적 | 업데이트 주기 | 사용 시점 |
|------|------|---------------|-----------|
| **Reference** | 현재 개발 참조 | 지속적 | 매일 (개발/디버깅 중) |
| **Reports** | 완료된 결과 기록 | 완료 시 1회 | 학습/회고 |
| **Archive** | 과거 기록 보존 | 업데이트 안 함 | 이력 추적 |

---

## ⚡ 빠른 참조

### 🐛 디버깅 중이라면
→ **`debugging_commands.md`**

### 🔌 API 호출 구현 중이라면
→ **`kiwoom_restapi_specs.md`**

### 🗄️ DB 스키마 확인하려면
→ **`debugging_commands.md`** 3절 (Postgres 쿼리)

### 📊 DAG 로그 보려면
→ **`debugging_commands.md`** 6절 (Airflow 로그)

---

## 📚 문서 목록

### 1. debugging_commands.md
**파일명**: `debugging_commands.md`  
**사용 빈도**: ⭐⭐⭐⭐⭐ (매일)  
**목적**: Docker, PostgreSQL, Airflow 디버깅 명령어 레퍼런스

#### 주요 내용

**1. Docker 관리**
- 컨테이너 상태 확인
- 컨테이너 재시작/빌드
- 볼륨 삭제

**2. PostgreSQL 쿼리**
- 환경변수 확인
- `live.stocks` 조회
- `live.daily_analysis_results` 조회
- `live.financial_analysis_results` 조회
- `is_analysis_target` 통계

**3. Airflow CLI**
- DAG 수동 트리거
- DAG run 목록 확인
- 로그 파일 직접 확인
- 스케줄러 로그 확인

**4. 특수 케이스**
- SIMULATION 모드 테스트
- 업종 마스터 DAG 디버깅
- 환경변수 확장 이슈 해결

#### 핵심 명령어 예시

**DAG 트리거 (SIMULATION 모드)**:
```bash
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -lc \
'airflow dags trigger -c "{\"execution_mode\": \"SIMULATION\", \"analysis_date\": \"2025-10-24\"}" dag_daily_batch'
```

**DB 검증 (분석 결과 확인)**:
```bash
docker compose --env-file .env.docker --profile pipeline exec postgres-tradesmart bash -c \
"psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"SELECT stock_code, analysis_date, market_rs_score, financial_grade FROM live.daily_analysis_results WHERE analysis_date = '2025-10-24' LIMIT 10;\""
```

**로그 확인**:
```bash
docker compose --env-file .env.docker --profile pipeline exec airflow-scheduler bash -c \
"tail -n 200 '/opt/airflow/logs/dag_id=dag_daily_batch/run_id=manual__2025-10-24/task_id=calculate_rs_score/attempt=1.log'"
```

#### 사용 시나리오

1. **DAG 실행 후 결과 검증**
   ```
   DAG 트리거 → 실행 상태 확인 → DB 데이터 확인 → 로그 확인
   ```

2. **버그 디버깅**
   ```
   로그 확인 → DB 상태 확인 → 컨테이너 재시작 → 재테스트
   ```

3. **신규 기능 테스트**
   ```
   SIMULATION 모드 트리거 → 로그 실시간 확인 → DB 결과 검증
   ```

#### 업데이트 이력
- **2025-10-31**: Phase 7 완료 후 최신 환경 반영
- **작성 시점**: dag_daily_batch 중심, SIMULATION v7 대응

---

### 2. kiwoom_restapi_specs.md
**파일명**: `kiwoom_restapi_specs.md` (구: `kiwoom_restapi_명세.md`)  
**사용 빈도**: ⭐⭐⭐⭐ (API 개발 시)  
**목적**: Kiwoom REST API 명세서 및 예제 코드

#### 주요 내용

**포함된 API** (6개):

| API ID | 명칭 | 현재 사용 여부 | 사용 위치 |
|--------|------|----------------|-----------|
| `ka10099` | 종목정보 리스트 | ✅ 사용 중 | `data_collector.py` |
| `ka10101` | 업종코드 리스트 | ✅ **사용 중** | `dag_sector_master_update` |
| `ka10083` | 주식 월봉 차트 | ✅ **사용 중** | RS 계산 (`rs_calculator.py`) |
| `ka20008` | 업종 월봉 | ✅ **사용 중** | Sector RS 계산 |
| `ka20007` | 업종 주봉 | 🔜 예정 | 향후 주봉 분석 |
| `ka20006` | 업종 일봉 | 🔜 예정 | 향후 일봉 분석 |

#### 각 API 상세

**1. ka10099 (종목정보 리스트)**
- **용도**: KOSPI/KOSDAQ 전체 종목 목록 수집
- **파라미터**: `mrkt_tp` (0:코스피, 10:코스닥, ...)
- **응답**: 종목코드, 종목명, 상장주식수, 감사의견, 시장코드 등
- **현재 사용**: `dag_initial_loader`, `dag_daily_batch`에서 종목 마스터 동기화

**2. ka10101 (업종코드 리스트)** ⭐
- **용도**: KOSPI/KOSDAQ 업종 목록 수집
- **파라미터**: `mrkt_tp` (0:코스피, 1:코스닥)
- **응답**: 업종코드, 업종명, 시장코드
- **현재 사용**: `dag_sector_master_update`에서 **매주 토요일 02:00 자동 수집**
- **DB 테이블**: `live.sectors`

**3. ka10083 (주식 월봉 차트)** ⭐
- **용도**: 개별 종목의 월봉 데이터 수집 (RS 계산용)
- **파라미터**: 
  - `stk_cd`: 종목코드
  - `base_dt`: 기준일자 (YYYYMMDD)
  - `upd_stkpc_tp`: 수정주가 구분 (1 권장)
- **응답**: 시가/고가/저가/종가, 거래량, 거래대금
- **현재 사용**: `rs_calculator.py`에서 **Market RS 계산 (6개월 데이터)**

**4. ka20008 (업종 월봉)** ⭐
- **용도**: 업종 지수의 월봉 데이터 수집 (Sector RS 계산용)
- **파라미터**:
  - `inds_cd`: 업종코드 (001:종합, 002:대형주, ...)
  - `base_dt`: 기준일자
- **응답**: 업종지수, 시가/고가/저가/종가, 거래량
- **현재 사용**: `rs_calculator.py`에서 **Sector RS 계산 (6개월 데이터)**

**5. ka20007 (업종 주봉)**
- **용도**: 업종 지수의 주봉 데이터
- **현재 상태**: 미사용 (향후 주봉 기반 분석 추가 시 활용)

**6. ka20006 (업종 일봉)**
- **용도**: 업종 지수의 일봉 데이터
- **현재 상태**: 미사용 (향후 일봉 기반 분석 추가 시 활용)

#### 코드 예제 구조

각 API마다 다음 구조로 예제 제공:

```python
import requests
import json

def fn_kaXXXXX(token, data, cont_yn='N', next_key=''):
    # 1. URL 설정
    host = 'https://api.kiwoom.com'  # 실전
    # host = 'https://mockapi.kiwoom.com'  # 모의
    
    # 2. Header 구성
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'kaXXXXX',
    }
    
    # 3. POST 요청
    response = requests.post(url, headers=headers, json=data)
    
    # 4. 응답 출력
    print('Code:', response.status_code)
    print('Body:', response.json())

# 실행 예시
if __name__ == '__main__':
    MY_ACCESS_TOKEN = '사용자 AccessToken'
    params = {...}
    fn_kaXXXXX(token=MY_ACCESS_TOKEN, data=params)
```

#### Request/Response 예시

각 API마다:
- ✅ Request Body 예시
- ✅ Response Body 예시
- ✅ 필드별 설명

#### 사용 시나리오

**1. 신규 종목 수집 API 추가**
```
1. kiwoom_restapi_specs.md에서 ka10099 참조
2. 예제 코드 복사
3. data_collector.py에 통합
4. 테스트
```

**2. 업종 마스터 업데이트 확인**
```
1. ka10101 API 명세 확인
2. dag_sector_master_update 로그 확인
3. 응답 형식과 DB 저장 매핑 검증
```

**3. RS 계산 로직 개선**
```
1. ka10083, ka20008 API 명세 재확인
2. 필드 의미 파악 (pred_pre, trde_tern_rt 등)
3. rs_calculator.py 로직 수정
```

**4. 테마 분석 기능 추가 (과제 10)**
```
1. 테마 관련 API 추가 필요 여부 확인
2. 기존 API 활용 가능성 검토
3. 신규 API 명세 추가
```

#### 중요 참고 사항

**1. 연속 조회 (Pagination)**
- Response Header의 `cont-yn`, `next-key` 확인
- 데이터가 많을 경우 반복 호출 필요
- 예: `fn_ka10099(token, params, cont_yn='Y', next_key='...')`

**2. 실전 vs 모의 투자**
```python
# 실전
host = 'https://api.kiwoom.com'

# 모의
host = 'https://mockapi.kiwoom.com'
```

**3. Access Token 관리**
- `.env.local` / `.env.docker`에 `KIWOOM_ACCESS_TOKEN` 저장
- 환경변수로 안전하게 관리
- 주기적 갱신 필요

**4. API 호출 제한**
- Airflow Pool 활용: `kiwoom_api_pool` (동시 호출 제한)
- Rate Limiting 고려

#### 업데이트 이력
- **2025-10-23**: 초기 작성
- **2025-10-31**: Reference 폴더로 이동, 영문명 변경

---

## 🔄 문서 업데이트 가이드

### debugging_commands.md

**업데이트해야 하는 경우**:
- ✅ 새로운 DAG 추가 시
- ✅ DB 스키마 변경 시
- ✅ Docker 환경 변경 시
- ✅ 자주 사용하는 명령어 발견 시

**업데이트 방법**:
1. 해당 섹션에 명령어 추가
2. 설명, 사용 상황 작성
3. 실행 예시 포함

### kiwoom_restapi_specs.md

**업데이트해야 하는 경우**:
- ✅ 새로운 API 사용 시
- ✅ API 응답 형식 변경 시
- ✅ 사용 중인 API 표시 변경 시

**업데이트 방법**:
1. 새 섹션에 API 명세 추가
2. 예제 코드 작성
3. Request/Response 예시 포함
4. 현재 사용 여부 표시

---

## 🎯 활용 팁

### 신규 개발자

**첫 날 필독**:
1. `debugging_commands.md` 전체 읽기
2. 핵심 명령어 3개 외우기:
   - DAG 트리거
   - DB 조회
   - 로그 확인

**첫 주 실습**:
1. SIMULATION 모드로 DAG 실행
2. DB 결과 직접 확인
3. 로그 파일 읽기

### 경험 있는 개발자

**빠른 참조**:
- 명령어 템플릿 복사 → 파라미터만 수정
- 자주 쓰는 명령어는 alias 등록 추천

**커스터마이징**:
- 개인 노트북에 자주 쓰는 명령어 정리
- 프로젝트별 변형 버전 작성

---

## 📎 관련 문서

### 상위 문서
- **`../DataPipeline_Project_Roadmap.md`** - 프로젝트 전체 로드맵
- **`../README.md`** - 문서 센터

### 구현 문서
- **`../../src/data/data_collector.py`** - Kiwoom API 실제 구현
- **`../../src/analysis/rs_calculator.py`** - RS 계산 로직
- **`../../dags/dag_sector_master_update.py`** - 업종 마스터 DAG

### 완료 보고서
- **`../Reports/RS_SCORE_IMPLEMENTATION_REPORT.md`** - RS 점수 구현 상세
- **`../Reports/DART_API_Optimization_Final_Report_v3.8.md`** - API 최적화 사례

---

## 💡 자주 묻는 질문 (FAQ)

### Q1: 명령어가 실패하는데요?

**A**: 다음 체크리스트 확인:
1. ✅ 컨테이너가 실행 중인가? (`docker compose ps`)
2. ✅ `.env.docker` 파일이 있는가?
3. ✅ 환경변수 확장이 올바른가? (`bash -c` 사용)
4. ✅ 따옴표가 올바른가? (큰따옴표 vs 작은따옴표)

### Q2: 로그가 너무 많아요

**A**: 
- `tail -n 200`을 `-n 50`으로 줄이기
- `grep` 필터 사용: `| grep ERROR`
- 특정 종목만: `WHERE stock_code = '005930'`

### Q3: SIMULATION 모드가 이해가 안 가요

**A**:
- **`../Reports/report_test_simulation_architechture.md`** 읽기
- 테스트 명령어: debugging_commands.md 4절 참조
- Look-Ahead Bias 방지 원리 학습

### Q4: API 토큰은 어디서 가져오나요?

**A**:
- Kiwoom 개발자 사이트에서 발급
- `.env.local` / `.env.docker`에 `KIWOOM_ACCESS_TOKEN` 저장
- **절대 코드에 하드코딩 금지!**

---

**문서 작성일**: 2025-10-31  
**작성자**: cursor.ai Documentation Manager  
**버전**: 1.0

