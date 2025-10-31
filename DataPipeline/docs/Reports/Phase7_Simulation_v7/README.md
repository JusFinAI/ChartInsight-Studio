# 📊 Phase 7: SIMULATION v7 아키텍처

## 개요

**완료일**: 2025-10-30  
**DataPipeline 버전**: v7.0  
**주요 성과**: 단일 책임 원칙(SRP) 기반 SIMULATION 모드 완성 및 P2 스케줄링 안정화

---

## 🎯 Phase 7의 목표

SIMULATION 모드를 안정적이고 확장 가능한 아키텍처로 완성하여, 과거 시점 데이터 기반 분석 및 테스트를 가능하게 합니다.

---

## 📚 문서

### 1. report_test_simulation_architechture.md

**작성일**: 2025-10-30  
**중요도**: ⭐⭐⭐⭐⭐  
**주제**: SIMULATION v7 아키텍처 End-to-End 테스트

#### 주요 내용

**1. 아키텍처 원칙**
- **단일 책임 원칙(SRP)**: 각 DAG는 하나의 책임만
  - `dag_initial_loader`: 데이터 수집/저장
  - `dag_daily_batch`: 순수 분석
  - `dag_financials_update`: 재무 데이터 수집

**2. SIMULATION 모드 구현**
- **DB 스냅샷 생성**: 과거 시점 데이터 복제
  - `simulation.candles` ← `live.candles`
  - `simulation.financial_analysis_results` ← `live.financial_analysis_results`
- **순수 분석**: `dag_daily_batch`는 데이터 변경 없음
- **자동 감지**: `target_datetime`, `test_stock_codes` 자동 결정
- **Parquet 제거**: DB만 사용하여 단순화

**3. 검증 결과**
- LIVE 모드 초기 적재 성공 (30종목, 2024-01-01 ~ 2024-12-31)
- SIMULATION 스냅샷 생성 검증
- SIMULATION 분석 실행 확인 (2024-09-26)
- 데이터 분리 및 무결성 검증 완료

---

### 2. report_과거실행자동트리거.md

**작성일**: 2025-10-30  
**중요도**: ⭐⭐⭐⭐  
**주제**: P2 DAG 스케줄링 안정성 확보

#### 주요 내용

**1. 문제 정의**
- DAG unpause 시 과거 스케줄 자동 실행
- 의도하지 않은 backfill 발생
- 개발 중 테스트 방해

**2. 근본 원인**
- `start_date`가 과거 (예: 2024-01-01)
- Airflow의 "catchup" 동작
- 스케줄 누락 자동 보충

**3. 해결 방안**
```python
# Before
start_date=datetime(2024, 1, 1)  # ❌ 과거 날짜

# After
start_date=pendulum.now('Asia/Seoul').subtract(hours=1)  # ✅ 최근 날짜
```

**4. 효과**
- unpause 후 과거 실행 없음
- 다음 스케줄부터만 실행
- 개발 환경 안정화

---

### 3. SIMULATION_모드_재무_데이터_복제_문제_분석_보고서.md

**작성일**: 2025-10-28  
**중요도**: ⭐⭐⭐⭐  
**주제**: SIMULATION 재무 데이터 복제 버그 해결

#### 주요 내용

**1. 문제**
- `simulation.financial_analysis_results` 데이터 복제 안 됨
- 재무 분석이 비어있는 상태로 실행

**2. 근본 원인**
- SQLAlchemy subquery의 `session.get_bind()` 버그
- `financial_analysis_results` 테이블만 영향
- `candles` 테이블은 정상 동작

**3. 해결 방안**
```python
# Before: SQLAlchemy ORM (버그)
subquery = session.query(LiveFinancialAnalysisResult).filter(...)
session.execute(insert_stmt.from_select([...], subquery))  # ❌

# After: Raw SQL (안정적)
sql = """
    INSERT INTO simulation.financial_analysis_results
    SELECT * FROM live.financial_analysis_results
    WHERE analysis_date <= :target_date
"""
session.execute(text(sql), {"target_date": target_date})  # ✅
```

**4. 교훈**
- ORM의 한계 인식
- 복잡한 쿼리는 Raw SQL 고려
- 철저한 데이터 검증 필요

**현황 코멘트**: 이 버그는 완전히 해결되었으며, 현재 SIMULATION 모드의 재무 데이터 스냅샷은 정상적으로 작동합니다.

---

## 🏆 주요 성과

### 아키텍처 완성도

```
✅ 단일 책임 원칙(SRP) 완벽 구현
✅ LIVE/SIMULATION 완전 분리
✅ 순수 분석 DAG 구현
✅ 자동 타겟 감지
✅ Parquet 의존성 제거
✅ P2 스케줄링 안정화
```

### 정성적 성과

**🎯 테스트 가능성**
- 과거 시점 데이터로 안전한 테스트
- LIVE 데이터 보호

**🔧 유지보수성**
- 역할 분리로 디버깅 용이
- 독립적 DAG 수정 가능

**📈 확장성**
- 새로운 분석 추가 용이
- 타 DAG 영향 최소화

**⚡ 안정성**
- 스케줄링 문제 해결
- 데이터 무결성 보장

---

## 🔄 Phase 7의 의미

### 아키텍처 성숙도 도약

```
Phase 1-4: 기반 구축        ████████████████████ 100%
Phase 5-6: 기능 추가        ████████████████████ 100%
Phase 7:   아키텍처 완성    ████████████████████ 100% ✨
```

**"작동하는 시스템"에서 "잘 설계된 시스템"으로**:
- SRP 원칙 적용
- 테스트 가능 구조
- 안정적 운영 환경

### SIMULATION 모드의 중요성

**개발 안전망**:
```
개발 → SIMULATION 테스트 → 검증 → LIVE 적용
         ↑
    과거 데이터로 안전하게 테스트
```

**알고리즘 백테스팅**:
- 과거 시점 데이터 분석
- 전략 검증
- 성과 시뮬레이션

---

## 📊 기술적 하이라이트

### 1. DB 스냅샷 아키텍처

```python
# LIVE → SIMULATION 스냅샷 생성
def create_snapshot(session, target_datetime):
    # 1. 기존 데이터 삭제
    session.execute(text("TRUNCATE simulation.candles CASCADE"))
    
    # 2. 과거 시점 데이터 복제
    session.execute(text("""
        INSERT INTO simulation.candles
        SELECT * FROM live.candles
        WHERE candle_date_kst <= :target_date
    """), {"target_date": target_datetime})
    
    # 3. 재무 데이터 복제
    session.execute(text("""
        INSERT INTO simulation.financial_analysis_results
        SELECT * FROM live.financial_analysis_results
        WHERE analysis_date <= :target_date
    """), {"target_date": target_datetime})
```

**장점**:
- DB만 사용 (Parquet 불필요)
- 완전한 데이터 격리
- 빠른 스냅샷 생성

### 2. 순수 분석 DAG

```python
# dag_daily_batch: 읽기만 수행
def analyze_stocks(mode: str):
    # 데이터 읽기
    candles = read_candles(mode)
    financial_data = read_financial_data(mode)
    
    # 분석 수행
    results = perform_analysis(candles, financial_data)
    
    # 결과 저장 (daily_analysis_results 테이블)
    save_results(results)
    
    # ✅ candles, financial_data 변경 없음
```

**핵심**:
- 입력 데이터 불변
- 사이드 이펙트 없음
- 멱등성 보장

### 3. 동적 start_date

```python
# P2 스케줄링 안정화
default_args = {
    'start_date': pendulum.now('Asia/Seoul').subtract(hours=1),
    'catchup': False,
}
```

**효과**:
- 항상 최근 날짜
- 과거 실행 방지
- 의도된 스케줄만 실행

---

## 🎓 학습 포인트

### 1. 단일 책임 원칙(SRP)

**잘못된 설계**:
```
dag_daily_batch:
  - 데이터 수집
  - 데이터 저장
  - 데이터 분석  ❌ 너무 많은 책임
```

**올바른 설계**:
```
dag_initial_loader: 수집/저장
dag_daily_batch: 분석
dag_financials_update: 재무 수집
  ✅ 각자 명확한 책임
```

### 2. SIMULATION의 가치

**프로덕션 보호**:
- LIVE 데이터 절대 수정 안 함
- 실험과 운영 분리

**빠른 검증**:
- 과거 데이터로 즉시 테스트
- 결과 확인 후 LIVE 적용

### 3. Airflow 스케줄링 이해

**start_date의 의미**:
- DAG 실행 가능 시작점
- 과거 날짜 → catchup 발생
- 최근 날짜 → 안정적 스케줄

### 4. ORM vs Raw SQL

**ORM의 장점**:
- 객체 지향적
- 타입 안전

**Raw SQL이 필요한 경우**:
- 복잡한 쿼리
- 대량 데이터 처리
- ORM 버그 회피

---

## 🔗 연관 Phase

### 선행 Phase

**Phase 5-6**: 분석 기능 구현
- RS 점수, 재무 분석
- SIMULATION으로 테스트할 로직 준비

### 후속 Phase

**Phase 8**: Filter Zero 통합
- SRP 기반 필터링 구현
- SIMULATION 모드 활용

---

## 📎 관련 문서

### 상위 문서
- **`../../DataPipeline_Project_Roadmap.md`**: Phase 7 섹션
- **`../../README.md`**: 문서 센터

### 관련 Phase
- **`../Phase5_RS_Score/`**: 분석 기능 (RS)
- **`../Phase6_DART_API/`**: 분석 기능 (재무)
- **`../Phase8_Zero_Filter/`**: SRP 활용

### 참조 문서
- **`../../Reference/debugging_commands.md`**: SIMULATION 테스트

### 계획 문서
- **`../../Archive/Plans/SIMULATION 모드 아키텍처 동기화 계획서.md`**: 초기 계획

---

## 💡 Phase 7 이후

### 확립된 아키텍처
- ✅ SRP 기반 DAG 구조
- ✅ SIMULATION 모드 완성
- ✅ P2 스케줄링 안정화
- ✅ DB 스냅샷 체계

### 다음 단계
1. **Phase 8**: 아키텍처 기반 최적화
2. **Phase 9**: 선택적 데이터 수집
3. **Phase 10**: 테마 분석 통합

---

**Phase 7은 DataPipeline을 "작동하는 시스템"에서 "잘 설계된 시스템"으로 진화시킨 결정적 전환점입니다.**

이제 DataPipeline은:
- ✅ **안전하게 테스트** 가능하며
- ✅ **쉽게 확장** 가능하고
- ✅ **안정적으로 운영**됩니다

Phase 8부터는 이 탄탄한 기반 위에서 성능 최적화와 새로운 기능을 추가합니다. 🏗️

---

**문서 작성일**: 2025-10-31  
**작성자**: cursor.ai Documentation Manager  
**버전**: 1.0

