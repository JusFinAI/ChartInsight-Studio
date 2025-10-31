# 📊 Phase 5: RS 점수 계산 기능

## 개요

**완료일**: 2025-10-22  
**DataPipeline 버전**: v5.0  
**주요 성과**: Market RS 및 Sector RS 계산 엔진 완성

---

## 🎯 Phase 5의 목표

모든 종목에 대해 **시장 대비 상대강도(Market RS)**와 **업종 대비 상대강도(Sector RS)**를 계산하여, 종목의 상대적 성과를 정량화합니다.

---

## 📚 문서

### RS_SCORE_IMPLEMENTATION_REPORT.md

**작성일**: 2025-10-22  
**중요도**: ⭐⭐⭐⭐⭐

#### 주요 내용

**1. 구현 내용**
- `rs_calculator.py` 모듈 개발
- 월봉 기반 RS 계산 알고리즘
- Market RS: KOSPI/KOSDAQ 대비 상대강도
- Sector RS: 소속 업종 대비 상대강도

**2. 인프라 구축**
- `sectors` 테이블 신설
- `stocks.sector_code` 컬럼 추가
- `dag_sector_master_update` DAG 구현
- Fuzzy Matching 기반 업종 매핑 (90% 이상 성공률)

**3. 검증 결과**
- 전 종목 Market RS 계산 완료
- 90% 이상 종목 Sector RS 계산 완료
- 업종 마스터 데이터 자동 업데이트 체계 확립

---

## 🏆 주요 성과

### 기술적 성과

✅ **RS 계산 엔진 완성**
- 월봉 데이터 기반 정확한 계산
- 시장/업종 대비 이중 평가 체계

✅ **업종 매핑 자동화**
- Fuzzy Matching 알고리즘 적용
- 90% 이상 자동 매핑 성공

✅ **마스터 데이터 관리**
- `dag_sector_master_update` 자동화
- 업종 정보 주기적 동기화

### 비즈니스 가치

- **종목 스크리닝**: RS 점수 기반 강세 종목 선별
- **상대 성과 평가**: 시장 및 업종 대비 객관적 비교
- **데이터 기반 의사결정**: 정량적 지표 제공

---

## 🔄 Phase 5의 의미

### 분석 역량 강화

**Phase 1-4**: 데이터 수집 및 저장
**Phase 5**: 데이터 분석 및 지표 생성 ✨

이제 DataPipeline은 단순한 "데이터 저장소"를 넘어 "분석 엔진"으로 진화했습니다.

### 아키텍처 확장

```
데이터 수집 → 저장 → 분석 → 지표 생성
                          ↑
                    Phase 5에서 추가
```

---

## 📊 기술적 하이라이트

### RS 계산 알고리즘

```python
# 월봉 기반 상대강도 계산
def calculate_rs_score(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    period: int = 12
) -> float:
    # 12개월 누적 수익률 비교
    stock_cum_return = (1 + stock_returns).prod() - 1
    benchmark_cum_return = (1 + benchmark_returns).prod() - 1
    
    # RS = (종목 수익률 - 벤치마크 수익률) * 100
    rs_score = (stock_cum_return - benchmark_cum_return) * 100
    return rs_score
```

### Fuzzy Matching 업종 매핑

```python
from fuzzywuzzy import fuzz

def match_sector(stock_sector: str, sector_list: List[str]) -> str:
    best_match = None
    best_score = 0
    
    for sector in sector_list:
        score = fuzz.ratio(stock_sector, sector)
        if score > best_score:
            best_score = score
            best_match = sector
    
    # 80% 이상 유사도 → 자동 매핑
    if best_score >= 80:
        return best_match
    else:
        return None
```

---

## 🎓 학습 포인트

### 1. 상대강도의 중요성

절대 수익률보다 **상대 수익률**이 중요한 이유:
- 시장 상황(상승/하락장) 독립적 평가
- 종목의 진짜 강점 파악
- 업종 내 상대적 위치 이해

### 2. Fuzzy Matching의 활용

완벽한 문자열 일치가 어려운 경우:
- 유사도 알고리즘 활용
- 임계값 설정 (80%)
- 자동화와 정확도의 균형

### 3. 마스터 데이터 관리

분석 정확도를 위한 기반:
- 업종 정보 최신 상태 유지
- 자동 업데이트 체계 구축
- 데이터 품질 모니터링

---

## 🔗 연관 Phase

### 선행 Phase

**Phase 1-4**: 캔들 데이터 수집 완료
- RS 계산을 위한 가격 데이터 확보

### 후속 Phase

**Phase 6**: DART API 최적화
- 재무 분석 기능 추가

**Phase 7**: SIMULATION v7 아키텍처
- RS 점수를 활용한 종목 선정

**Phase 8**: Filter Zero 통합
- RS 기반 필터링 적용

---

## 📎 관련 문서

### 상위 문서
- **`../../DataPipeline_Project_Roadmap.md`**: Phase 5 섹션
- **`../../README.md`**: 문서 센터

### 후속 Phase
- **`../Phase6_DART_API/`**: 재무 분석 기능
- **`../Phase7_Simulation_v7/`**: SIMULATION 아키텍처
- **`../Phase8_Zero_Filter/`**: 필터링 최적화

### 참조 문서
- **`../../Reference/kiwoom_restapi_specs.md`**: 업종 API 명세

---

## 💡 Phase 5 이후

### 확립된 기능
- ✅ RS 점수 계산 엔진
- ✅ 업종 마스터 관리
- ✅ Fuzzy Matching 매핑

### 다음 단계
1. **Phase 6**: 재무 분석 추가 (ROE, PER 등)
2. **Phase 7**: 분석 결과 활용 (SIMULATION)
3. **Phase 8**: 성능 최적화 (Filter Zero)

---

**Phase 5는 DataPipeline을 "저장소"에서 "분석 엔진"으로 도약시킨 중요한 이정표입니다.** 📊

---

**문서 작성일**: 2025-10-31  
**작성자**: cursor.ai Documentation Manager  
**버전**: 1.0

