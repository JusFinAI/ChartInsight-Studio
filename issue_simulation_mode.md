# 📋 **SIMULATION 모드 재무 데이터 복제 문제 분석 보고서**

## 🔍 **문제 개요**
**`dag_financials_update` DAG의 SIMULATION 모드에서 재무 데이터 스냅샷 복제가 0행으로 실패하는 문제가 발생했습니다.**

## 🐛 **문제 증상**
- SIMULATION 모드 실행 시 "재무 분석 데이터 스냅샷 복제 완료: 0 행" 출력
- 실제 `live.financial_analysis_results` 테이블에는 12개 종목의 데이터가 정상적으로 존재함
- `analysis_date`는 모두 `2025-08-14`로 동일하며, `target_datetime`(`2025-08-16`) 이후임

## 🔬 **진단 과정**

### 1. **기본 확인**
```sql
-- 테이블 존재 여부: ✅ True
-- 전체 행 수: ✅ 12행  
-- 샘플 종목(005930,000660) 행 수: ✅ 2행
```

### 2. **서브쿼리 vs 직접 SQL 비교**
```sql
-- SQLAlchemy 서브쿼리: ❌ 0행 반환
SELECT stock_code, MAX(analysis_date) as max_date
FROM live.financial_analysis_results 
WHERE analysis_date <= '2025-08-16' 
AND stock_code IN ('005930','000660','373220','035420','207940','005380','005490','051910','105560','096770','033780','247540')
GROUP BY stock_code

-- 직접 SQL 실행: ✅ 12행 반환 (동일한 쿼리)
```

### 3. **결과 비교**
```
[INFO] 직접 SQL 실행 결과: 12행
[INFO]   - 033780: 2025-08-14
[INFO]   - 005930: 2025-08-14  
[INFO]   - 105560: 2025-08-14
[INFO]   - 005490: 2025-08-14
[INFO]   - 005380: 2025-08-14
[INFO] 서브쿼리 결과: 0행
```

## 🎯 **문제 원인**
**SQLAlchemy 서브쿼리 구현에 버그가 있습니다.** 동일한 쿼리를:
- **직접 SQL로 실행하면 12행 정상 반환**
- **SQLAlchemy 서브쿼리로 실행하면 0행 반환**

## 💡 **해결 방안**
1. **임시 조치**: 서브쿼리 로직을 제거하고 직접 SQL INSERT 문으로 대체
2. **근본적 해결**: SQLAlchemy 서브쿼리 버그 원인 분석 및 수정

## ⚠️ **현재 상태**
- SIMULATION 모드의 재무 데이터 복제 기능이 완전히 작동하지 않음
- `simulation.financial_analysis_results` 테이블이 비어있어 `dag_daily_batch` SIMULATION 모드 실행 시 재무 데이터 부재 문제 발생

## 🚀 **다음 단계**
1. 서브쿼리 로직을 직접 SQL로 대체하는 코드 수정 실행
2. 수정 후 SIMULATION 모드 재테스트
3. SQLAlchemy 서브쿼리 버그 근본 원인 추가 분석

**이 문제는 SIMULATION 모드 아키텍처의 완전성을 위해 반드시 해결해야 할 critical issue입니다.**