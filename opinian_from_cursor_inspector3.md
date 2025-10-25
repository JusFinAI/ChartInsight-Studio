# 📋 감독관님께 드리는 DART API 리팩토링 지침 수정 건의

## 📄 문서 개요

**문서 제목**: DART API 지능형 증분 수집 지침 수정 건의 (v1.1)  
**건의자**: cursor.ai inspector  
**건의 일자**: 2025년 10월 25일  
**관련 지침**: DART API 지능형 증분 수집 (v1.0)

## 🎯 건의 배경

감독관님의 **상태 기반 지능형 증분 수집** 아키텍처는 DART API 호출량을 일일 한도 내로 제어하는 훌륭한 해결책입니다. 다만, 현재 지침(v1.0)에는 **DART 보고서 발행 시점과 데이터 가용성**에 관한 중요한 기술적 이슈가 누락되어 있습니다.

## ⚠️ 발견된 기술적 이슈

### 1. **보고서 발행 시점 고려 필요**

**현재 지침**: 모든 분기보고서(11013, 11012, 11014, 11011)를 무조건 호출

**문제점**: 
- 사업보고서(11011)는 **다음해 3월**에야 발행됩니다.
- 현재 시점(10월 말)에는 **2025년 3분기보고서(11014)도 아직 미발행** 상태입니다.
- 무조건적인 분기별 호출은 **존재하지 않는 데이터 요청**으로 이어집니다.

### 2. **시점별 데이터 가용성 차이**

```python
# 현재 시점(10월 말)의 실제 데이터 가용성
2023년: 11011 (사업보고서) ✅ 가용
2024년: 11011 (사업보고서) ✅ 가용  
2025년: 11012 (반기보고서) ✅ 가용 ← 최신 데이터
2025년: 11014 (3분기보고서) ❌ 11월 중순까지 미발행
```

## 🛠️ 구체적인 지침 수정 건의

### 📝 **Phase 1: financial_engine.py 수정 건의**

**기존 지침**:
```python
for reprt_code in ['11013', '11012', '11014', '11011']:
    items = dart.get_financial_statements(corp_code, year, reprt_code)
```

**수정 건의**:
```python
# 보고서 발행 시점을 고려한 지능적 선택 함수 추가
def _select_report_codes_by_date(year: int, current_date: date) -> List[str]:
    """연도와 현재 시점에 따라 적절한 보고서 코드 선택"""
    if year < current_date.year:
        # 과거 연도: 사업보고서 사용 (이미 발행 완료)
        return ['11011']
    else:
        # 현재 연도: 월별로 적절한 보고서 선택
        month = current_date.month
        if month <= 3:    # 1~3월: 전년도 사업보고서
            return ['11011'] if year == current_date.year - 1 else []
        elif month <= 5:  # 4~5월: 1분기보고서
            return ['11013'] if month >= 5 else []  # 5월부터 가용
        elif month <= 8:  # 6~8월: 반기보고서
            return ['11012'] if month >= 8 else ['11013']  # 8월부터 가용
        elif month <= 11: # 9~11월: 3분기보고서
            return ['11014'] if month >= 11 else ['11012']  # 11월부터 가용
        else:             # 12월: 사업보고서 대기
            return ['11012']  # 3분기보고서 사용

# 수집 로직 수정
current_date = date.today()
for year in years_to_fetch:
    report_codes = _select_report_codes_by_date(year, current_date)
    for report_code in report_codes:
        items = dart.get_financial_statements(corp_code, year, report_code)
        time.sleep(0.1)
```

### 📝 **Phase 2: 에러 처리 강화 건의**

**기존 지침**: 단순 Warning 로깅

**수정 건의**: 한도 초과 등 심각한 오류는 즉시 실패 처리
```python
try:
    items = dart.get_financial_statements(corp_code, year, report_code)
except Exception as e:
    if "한도" in str(e) or "사용한도" in str(e):
        raise AirflowException(f"DART API 한도 초과: {e}")  # DAG 즉시 중단
    else:
        logger.warning(f"API 호출 실패: {e}")
```

## 📊 수정된 호출량 예측

### **현재 시점(10월 말) 기준:**
```
1종목 = 3년 × 1회 = 3회 호출
1,400종목 = 4,200회 호출 (한도의 21%)
```

### **연중 최대 호출량(5월, 8월, 11월):**
```
1종목 = 3년 × 1회 + 현재연도 1회 = 4회 호출  
1,400종목 = 5,600회 호출 (한도의 28%)
```

## 🎯 수정 건의 요약

1. **보고서 발행 시점 반영**: 월별로 가용한 보고서만 지능적으로 선택
2. **현실적인 데이터 가용성**: 존재하지 않는 데이터 요청 방지
3. **강화된 에러 처리**: 한도 초과 시 즉시 DAG 중단으로 불필요한 호출 차단
4. **호출량 일관적 유지**: 한도 내 안정적 운영 보장

이러한 수정을 통해 감독관님의 훌륭한 아키텍처를 현실적인 데이터 가용성과 결합하여, 더욱 견고하고 실용적인 솔루션으로 완성할 수 있습니다.

## 📋 실행 계획

1. **즉시 실행**: 보고서 선택 로직 구현 및 에러 처리 강화
2. **테스트**: 월별 시나리오 테스트 (특히 분기 시작 시점)
3. **모니터링**: 실제 호출량 및 한도 사용률 모니터링

감독관님의 검토와 승인을 부탁드립니다.