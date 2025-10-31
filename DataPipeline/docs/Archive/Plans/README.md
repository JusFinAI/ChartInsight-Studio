# 📋 Archive - 계획서 및 중간 문서

## 개요

이 폴더는 **Phase 5-7 기간에 작성된 계획서 및 중간 검토 문서**를 보관합니다.

이 문서들은 최종 보고서가 작성되기 전의 "작업 과정"을 담고 있으며, 실제 구현 결과와 다를 수 있습니다.

---

## ⚠️ 중요 안내

### 이 문서들의 성격

✅ **학습 및 참조용으로만 사용하세요**
- 문제 접근 과정 학습
- 계획 → 실행 → 변경 과정 추적
- 중간 검토 및 의사결정 기록

⛔ **현재 프로젝트 상태를 반영하지 않습니다**
- **최신 정보**는 **`../../DataPipeline_Project_Roadmap.md`** 참조
- **최종 결과**는 **`../../Reports/`** 참조

---

## 📚 보관 문서 목록

### 1. RS_SCORE_IMPLEMENTATION_PLAN.md
**작성일**: 2025-10-21  
**성격**: Phase 5 계획서

#### 주요 내용
- RS 점수 계산 기능 구현 계획
- `sectors` 테이블 및 `stocks.sector_code` 추가 계획
- Fuzzy Matching 도입 계획

#### 최종 결과 문서
→ **`../../Reports/RS_SCORE_IMPLEMENTATION_REPORT.md`**

---

### 2. SIMULATION 모드 아키텍처 동기화 계획서.md
**작성일**: 2025-10-31  
**성격**: Phase 7 계획서 (v7 아키텍처)

#### 주요 내용
- SIMULATION v7 아키텍처 계획
- 단일 책임 원칙(SRP) 적용 방향
- DB 스냅샷 전략
- Parquet 제거 계획

#### 특징
- **가장 최신 계획서** (2025-10-31)
- 현재 구현된 v7 아키텍처의 설계 문서
- Phase 7 완료 후에도 참조 가치 높음

#### 최종 결과 문서
→ **`../../Reports/report_test_simulation_architechture.md`**

---

### 3. SIMULATION_아키텍처_근본적_재검토_보고서.md
**작성일**: 2025-10-28  
**성격**: 중간 검토 문서

#### 주요 내용
- SIMULATION v6 아키텍처 문제점 분석
- 근본적 재설계 필요성 검토
- v7로의 전환 근거

#### 역할
- v6 → v7 전환 배경 이해
- 아키텍처 의사결정 과정 학습

#### 관련 문서
- **후속**: `SIMULATION 모드 아키텍처 동기화 계획서.md` (v7 계획)
- **결과**: `../../Reports/report_test_simulation_architechture.md` (v7 완성)

---

### 4. p2_dag_scheduling_stability_report.md
**작성일**: 2025-10-31  
**성격**: 문제 해결 과정 기록

#### 주요 내용
- P2 스케줄링 문제 상세 분석
- 과거 실행 자동 트리거 문제
- `start_date` 동적 설정 해결 과정

#### 특징
- 문제 발견 → 분석 → 해결 전체 과정 기록
- 복잡한 guard 로직 vs 간단한 해결책 비교

#### 최종 결과 문서
→ **`../../Reports/report_과거실행자동트리거.md`**

---

## 🔄 계획서 vs 보고서 비교

| 문서 유형 | 작성 시점 | 목적 | 정확도 |
|-----------|-----------|------|--------|
| **계획서** (Plans) | 작업 **전** | 구현 방향 제시 | 실제 결과와 다를 수 있음 |
| **보고서** (Reports) | 작업 **후** | 완성된 결과 기록 | 실제 구현 내용 정확 반영 |

### 예시: RS Score 구현

```
📋 RS_SCORE_IMPLEMENTATION_PLAN.md (계획서)
   "Fuzzy Matching을 도입할 예정입니다"
   
   ↓ (구현 중 변경 발생 가능)
   
📊 RS_SCORE_IMPLEMENTATION_REPORT.md (보고서)
   "Fuzzy Matching을 적용했으며, 90% 이상 매칭되었습니다"
   "단, 10% 미만은 수동 매핑이 필요합니다"
```

---

## 📊 Phase별 문서 매핑

### Phase 5: RS 점수 계산
- **계획**: `RS_SCORE_IMPLEMENTATION_PLAN.md` (이 폴더)
- **보고서**: `../../Reports/RS_SCORE_IMPLEMENTATION_REPORT.md`

### Phase 6: DART API 최적화
- **계획**: 별도 계획서 없음 (문제 발견 후 즉시 해결)
- **보고서**: `../../Reports/DART_API_Optimization_Final_Report_v3.8.md`

### Phase 7: SIMULATION v7 아키텍처
- **v6 검토**: `SIMULATION_아키텍처_근본적_재검토_보고서.md` (이 폴더)
- **v7 계획**: `SIMULATION 모드 아키텍처 동기화 계획서.md` (이 폴더)
- **통합 테스트**: `../../Reports/report_test_simulation_architechture.md`
- **P2 문제 해결**: `p2_dag_scheduling_stability_report.md` (이 폴더)
  - **최종 보고서**: `../../Reports/report_과거실행자동트리거.md`

---

## 🎓 이 문서들에서 배울 수 있는 것

### 1. 계획 수립 방법론
- 문제 정의 → 목표 설정 → 구현 방법 → 검증 계획
- 단계별 접근 방법

### 2. 아키텍처 의사결정 과정
- `SIMULATION_아키텍처_근본적_재검토_보고서.md`에서 학습
- v6의 한계 인식 → v7로의 전환 결정 과정

### 3. 문제 해결 과정
- `p2_dag_scheduling_stability_report.md`에서 학습
- 복잡한 해결책 vs 단순한 해결책 비교
- 실용적 접근 방법

### 4. 계획과 실제의 차이
- 계획서와 보고서를 비교하며 학습
- 왜 변경되었는지 이해
- 유연한 개발 프로세스 체득

---

## 📎 활용 시나리오

### 시나리오 1: RS Score 구현 과정 전체 학습
```
1. RS_SCORE_IMPLEMENTATION_PLAN.md (계획 이해)
   ↓
2. ../../Reports/RS_SCORE_IMPLEMENTATION_REPORT.md (결과 확인)
   ↓
3. ../../DataPipeline_Project_Roadmap.md Phase 5 (요약 정리)
```

### 시나리오 2: SIMULATION v7 전환 배경 이해
```
1. SIMULATION_아키텍처_근본적_재검토_보고서.md (v6 문제점)
   ↓
2. SIMULATION 모드 아키텍처 동기화 계획서.md (v7 계획)
   ↓
3. ../../Reports/report_test_simulation_architechture.md (v7 완성)
```

### 시나리오 3: P2 스케줄링 문제 해결 과정
```
1. p2_dag_scheduling_stability_report.md (상세 분석)
   ↓
2. ../../Reports/report_과거실행자동트리거.md (최종 해결)
```

---

## 💡 읽는 순서 추천

### 입문자
1. **`SIMULATION 모드 아키텍처 동기화 계획서.md`** 먼저 읽기
   - 최신 문서이며 가장 체계적
   - v7 아키텍처의 설계 철학 이해
2. **`../../Reports/`의 해당 보고서**로 실제 결과 확인

### 개발자
1. 관심 Phase의 **계획서** 먼저 읽기
2. **보고서**에서 실제 구현 결과 확인
3. **차이점 분석**을 통한 실전 학습

### 아키텍트
1. **`SIMULATION_아키텍처_근본적_재검토_보고서.md`** 정독
   - 아키텍처 의사결정 과정의 모범 사례
2. **v7 계획서**에서 설계 원칙 학습
3. **보고서**에서 검증 방법 확인

---

## 🔍 키워드 인덱스

### 아키텍처 관련
- **SRP (단일 책임 원칙)**: `SIMULATION 모드 아키텍처 동기화 계획서.md`
- **DB 스냅샷**: `SIMULATION 모드 아키텍처 동기화 계획서.md`
- **v6 → v7 전환**: `SIMULATION_아키텍처_근본적_재검토_보고서.md`

### 구현 전략
- **Fuzzy Matching**: `RS_SCORE_IMPLEMENTATION_PLAN.md`
- **Parquet 제거**: `SIMULATION 모드 아키텍처 동기화 계획서.md`
- **동적 start_date**: `p2_dag_scheduling_stability_report.md`

### 문제 해결
- **스케줄링 안정화**: `p2_dag_scheduling_stability_report.md`
- **Look-Ahead Bias**: `SIMULATION 모드 아키텍처 동기화 계획서.md`

---

## 📊 문서 신선도 지표

| 문서 | 작성일 | 신선도 | 참조 우선순위 |
|------|--------|--------|---------------|
| `SIMULATION 모드 아키텍처 동기화 계획서.md` | 2025-10-31 | ⭐⭐⭐⭐⭐ | **최우선** (현재 아키텍처) |
| `p2_dag_scheduling_stability_report.md` | 2025-10-31 | ⭐⭐⭐⭐⭐ | **최우선** (최신 해결) |
| `SIMULATION_아키텍처_근본적_재검토_보고서.md` | 2025-10-28 | ⭐⭐⭐ | 중간 (v7 배경 이해용) |
| `RS_SCORE_IMPLEMENTATION_PLAN.md` | 2025-10-21 | ⭐⭐ | 보통 (Phase 5 계획) |

---

## 📎 관련 문서 링크

### 상위 문서
- **`../../DataPipeline_Project_Roadmap.md`** - 전체 로드맵

### 최종 보고서
- **`../../Reports/README.md`** - 보고서 모음 센터
- **`../../Reports/RS_SCORE_IMPLEMENTATION_REPORT.md`**
- **`../../Reports/DART_API_Optimization_Final_Report_v3.8.md`**
- **`../../Reports/report_test_simulation_architechture.md`**
- **`../../Reports/report_과거실행자동트리거.md`**

### 과거 기록
- **`../Phase1-4/README.md`** - Phase 1-4 보관 문서

---

**문서 작성일**: 2025-10-31  
**작성자**: cursor.ai Documentation Manager  
**버전**: 1.0

