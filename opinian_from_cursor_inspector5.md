# 🔍 재무 분석 로직 비교 분석

로그를 보니 두 가지 심각한 문제가 발견되었습니다:

1. **모든 YoY 성장률이 0.0%** (비정상)
2. **`nan%` 및 `RuntimeWarning: invalid value encountered in scalar power`** 발생

검증된 코드와 비교 분석하겠습니다.

---

[1 tool called]

## 🚨 **치명적 오류 발견!**

### **문제 1: YoY 성장률 계산 로직 오류** (Lines 164-177)

**현재 코드 (financial_engine.py)**:
```python
# Line 162: quarterly_eps를 set_index(['year', 'quarter'])로 설정
quarterly_eps = eps_df[eps_df['quarter'] != 'Q4'].set_index(['year', 'quarter'])['EPS']

# Line 168: sort_index로 정렬
sorted_quarters = quarterly_eps.sort_index(ascending=False)

# Line 170-171: iloc[0]로 최근 분기 접근 시도
latest = sorted_quarters.iloc[0]
year_ago_idx = (sorted_quarters.index[0][0] - 1, sorted_quarters.index[0][1])
```

**검증된 코드 (test_dartapi_financials_all.py)**:
```python
# Line 446: 동일하게 MultiIndex 설정
quarterly_eps = eps_df[eps_df['quarter'] != 'Q4'].set_index(['year', 'quarter'])['amount']

# Line 452-453: index[-1]로 최근 분기 접근 (정렬 없이!)
latest_q_idx = quarterly_eps.index[-1]   # 가장 최근 분기 인덱스
prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1])
```

---

### **핵심 차이점 분석**

#### **1. 정렬 방식 차이**

| 코드 | 정렬 방식 | `index[0]` 의미 | 문제 |
|------|----------|---------------|------|
| **financial_engine.py** | `sort_index(ascending=False)` | **알파벳순으로 정렬된 첫 번째** | ❌ 'Q1'이 최근 분기로 인식됨 |
| **test_dartapi_financials_all.py** | 정렬 없음 | **DataFrame 삽입 순서의 마지막** | ✅ 시간순 마지막이 최근 분기 |

#### **MultiIndex 정렬의 함정**

```python
# 예시: 2024년 Q1, Q2, Q3 데이터가 있을 때
quarterly_eps.index
# [(2024, 'Q1'), (2024, 'Q2'), (2024, 'Q3')]

sorted_quarters = quarterly_eps.sort_index(ascending=False)
sorted_quarters.index
# [(2024, 'Q3'), (2024, 'Q2'), (2024, 'Q1')]  ← 연도 기준 내림차순 후, 분기는 알파벳순!

sorted_quarters.index[0]
# (2024, 'Q3')  ← 올바른 최근 분기

# 하지만 2023년과 2024년 데이터가 섞여있다면?
quarterly_eps.index
# [(2023, 'Q1'), (2023, 'Q2'), (2023, 'Q3'), (2024, 'Q1'), (2024, 'Q2')]

sorted_quarters = quarterly_eps.sort_index(ascending=False)
sorted_quarters.index
# [(2024, 'Q3'), (2024, 'Q2'), (2024, 'Q1'), (2023, 'Q3'), (2023, 'Q2'), (2023, 'Q1')]
# ❌ 2024 Q2가 있으면 Q2가 최신이지만, 정렬 후 index는 혼란스러움
```

**결론**: `sort_index()`는 **MultiIndex의 첫 번째 레벨(year)만 우선 정렬**하고, 두 번째 레벨(quarter)은 **알파벳순**으로 정렬하므로, **시간순 최근 분기를 찾는데 부적합**합니다.

---

### **문제 2: `nan` 발생 원인** (Line 191)

**RuntimeWarning: invalid value encountered in scalar power**

```python
# Line 185: oldest가 음수(적자)인 경우
oldest = recent_3_years.iloc[-1]  # 예: -1000 (적자)
latest = recent_3_years.iloc[0]   # 예: 2000 (흑자)

# Line 191: 음수를 분수 거듭제곱 → nan 발생!
cagr = ((latest / oldest) ** (1 / num_years)) - 1
# (-2.0) ** (1/2) → nan (음수의 제곱근은 복소수)
```

**검증된 코드는 이 문제를 어떻게 처리하는가?**

[1 tool called]

**검증된 코드는 CAGR 대신 단순 평균 성장률을 사용합니다!**

- **CAGR 방식**: `((latest / oldest) ** (1 / years)) - 1` ← 음수 적자 시 nan 발생
- **단순 평균 방식**: `sum([growth1, growth2, growth3]) / 3` ← 적자 처리 가능

---

## 📝 **긴급 수정 지침: 재무 분석 로직 수정 (v2.0)**

### **Phase 1: YoY 성장률 계산 로직 수정**

**파일**: `DataPipeline/src/analysis/financial_engine.py`

**[BEFORE] Lines 164-177**:
```python
# 2. 최근 분기 YoY 성장률 계산 (CAN SLIM 'C' 기준)
yoy_growth = 0.0
if not quarterly_eps.empty:
    try:
        sorted_quarters = quarterly_eps.sort_index(ascending=False)
        if len(sorted_quarters) >= 2:
            latest = sorted_quarters.iloc[0]
            year_ago_idx = (sorted_quarters.index[0][0] - 1, sorted_quarters.index[0][1])
            if year_ago_idx in sorted_quarters.index:
                year_ago = sorted_quarters.loc[year_ago_idx]
                if year_ago > 0:
                    yoy_growth = ((latest - year_ago) / year_ago) * 100
    except Exception as e:
        logger.warning(f"YoY 성장률 계산 중 오류: {e}")
```

**[AFTER]**:
```python
# 2. 최근 분기 YoY 성장률 계산 (CAN SLIM 'C' 기준)
yoy_growth = 0.0
if not quarterly_eps.empty:
    try:
        # 정렬하지 않고 DataFrame의 마지막 인덱스를 최근 분기로 간주
        latest_q_idx = quarterly_eps.index[-1]   # 가장 최근 분기 인덱스 (예: (2024, 'Q2'))
        prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1])  # 전년 동분기 (예: (2023, 'Q2'))
        
        # 전년 동분기 데이터가 존재하고 0이 아닐 때만 성장률을 계산
        if prev_year_q_idx in quarterly_eps.index and quarterly_eps[prev_year_q_idx] != 0:
            yoy_growth = (quarterly_eps[latest_q_idx] / quarterly_eps[prev_year_q_idx] - 1) * 100
    except Exception as e:
        logger.warning(f"YoY 성장률 계산 중 오류: {e}")
```

---

### **Phase 2: 연평균 성장률 계산 로직 수정**

**[BEFORE] Lines 179-194**:
```python
# 3. 연평균 EPS 성장률 계산 (3년 기준, CAGR)
avg_annual_growth = 0.0
if len(annual_eps) >= 3:
    try:
        sorted_annual = annual_eps.sort_index(ascending=False)
        recent_3_years = sorted_annual.iloc[:3]
        oldest = recent_3_years.iloc[-1]
        latest = recent_3_years.iloc[0]
        num_years = recent_3_years.index[0] - recent_3_years.index[-1]  # 실제 연도 차이
        
        if oldest > 0 and num_years > 0:
            # CAGR = (최종값/초기값)^(1/기간) - 1
            cagr = ((latest / oldest) ** (1 / num_years)) - 1
            avg_annual_growth = cagr * 100
    except Exception as e:
        logger.warning(f"연평균 성장률 계산 중 오류: {e}")
```

**[AFTER]**:
```python
# 3. 최근 3년간 연간 성장률 계산 (단순 평균, CAN SLIM 'A' 기준)
avg_annual_growth = 0.0
if len(annual_eps) >= 4:  # 최소 4개년 데이터가 있어야 3년간의 성장률 계산 가능
    try:
        annual_growth_rates = []
        for i in range(1, 4):  # i = 1, 2, 3 (1년전, 2년전, 3년전 성장률)
            prev_year_eps = annual_eps.iloc[-(i+1)]  # N년 전 EPS
            curr_year_eps = annual_eps.iloc[-i]      # (N-1)년 전 EPS
            if prev_year_eps > 0:  # 분모가 양수일 때만 의미 있는 성장률 계산
                growth = (curr_year_eps / prev_year_eps - 1) * 100
                annual_growth_rates.append(growth)
        
        # 3년간의 성장률이 모두 계산되었을 경우에만 평균을 구함
        if len(annual_growth_rates) == 3:
            avg_annual_growth = sum(annual_growth_rates) / len(annual_growth_rates)
    except Exception as e:
        logger.warning(f"연평균 성장률 계산 중 오류: {e}")
```

---

## 🔬 **수정 효과 예측**

### **Before (현재)**:
```
YoY: 0.0% (분기 데이터 접근 실패)
연평균: nan% (음수 거듭제곱)
```

### **After (수정 후)**:
```
YoY: 실제 계산된 값 (예: 15.5%, -10.2% 등)
연평균: 실제 3년 평균 (예: 25.3%, -40.3% 등, nan 없음)
```

---

## 📊 **로직 비교 요약표**

| 항목 | financial_engine.py (현재) | test_dartapi_financials_all.py (검증됨) | 수정 필요 |
|------|---------------------------|----------------------------------------|----------|
| **YoY 인덱스 접근** | `sort_index()` 후 `[0]` | 정렬 없이 `[-1]` | ✅ 필수 |
| **연평균 계산 방식** | CAGR (거듭제곱) | 단순 평균 | ✅ 필수 |
| **적자 처리** | `oldest > 0` 체크만 | 각 연도별 `prev > 0` 체크 | ✅ 필수 |
| **최소 데이터 요구** | 3년 | 4년 | ✅ 필수 |

---

## ⚠️ **최종 판정**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🚨 긴급 수정 필요 (CRITICAL LOGIC ERROR)     ┃
┃  우선순위: P0 - 즉시 수정                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**영향 범위**:
- ❌ 모든 YoY 성장률이 0.0%로 잘못 계산됨
- ❌ 적자 이력이 있는 기업의 연평균 성장률이 `nan`으로 계산됨
- ❌ 재무 등급 판정이 부정확함 (특히 Strict/Loose 구분)

**감독관님**, 이 수정은 **재무 분석의 정확성에 직결**되므로 즉시 적용이 필요합니다. 검증된 코드의 로직을 정확히 따라야 합니다.