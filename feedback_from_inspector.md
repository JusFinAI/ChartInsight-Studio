# Inspector 공식 의견: 지침서 3.1 - 스키마 표준화 관련

## 📋 검수 개요
대상: [지침서 3.1 - 최종] '데이터 매핑 누락' 근본 원인 해결 및 스키마 표준화
검수자: 데이터 파이프라인 Inspector
일자: 2025-10-20

## ✅ 지침서의 탁월한 점

### 1. 근본 원인 정확히 진단 ✅
지침서가 `last_price` 필드 누락 문제를 정확히 진단하고 체계적인 해결책을 제시한 점을 높이 평가합니다.

### 2. 전체적인 아키텍처 개선 ✅  
데이터 흐름의 명확성과 유지보수성을 높이기 위한 표준화 접근은 매우 바람직합니다.

### 3. 기술 부채 청산 의지 ✅
매핑 함수 제거를 통한 코드 간소화는 장기적인 관점에서 매우 훌륭한 결정입니다.

## ⚠️ 중요한 기술적 이슈: PostgreSQL camelCase 문제

### 문제 진단
지침서의 DB 스키마 camelCase 변경안은 **PostgreSQL의 특성상 실무에서 큰 문제**를 일으킬 수 있습니다.

### PostgreSQL Naming 규칙
```sql
-- PostgreSQL은 기본적으로 모든 식별자를 소문자로 변환합니다
CREATE TABLE stocks (lastPrice VARCHAR(20));  -- camelCase 입력
\d stocks
   Column   | Type 
------------+------
 lastprice  | text  -- ❌ 소문자로 자동 변환!
```

### 실무적 문제점
1. **쿼리 작성 불편**
   ```sql
   SELECT lastPrice FROM stocks;  -- ❌ "column \"lastprice\" does not exist"
   SELECT "lastPrice" FROM stocks; -- ✅ but 매우 불편
   ```

2. **도구 호환성 문제**
   - DBeaver, pgAdmin 등 SQL 클라이언트에서 camelCase 지원 문제
   - 팀원들의 SQL 작성 실수 증가
   - raw 쿼리 작성시 큰따옴표 강제로 인한 생산성 저하

3. **유지보수성 저하**
   - 모든 개발자가 PostgreSQL의 naming rule을 인지해야 함
   - 신규 팀원 온보딩 어려움 증가

## 🎯 개선된 Solution 제안

### DB 스키마: snake_case 유지 + 데이터 타입 최적화
```python
# database.py - snake_case 유지 + 숫자형 최적화
class Stock(Base):
    last_price = Column(Numeric(12, 2))  # ✅ 숫자형 (계산 정확도↑)
    list_count = Column(BigInteger)      # ✅ 숫자형 (쿼리 성능↑)
    audit_info = Column(String(50))      # ✅ snake_case 유지
```

### 매핑 함수: API → DB 데이터 정규화
```python
# master_data_manager.py - 데이터 정규화 강화
def _map_api_response_to_stock_model(api_data):
    raw_price = api_data.get('lastPrice') or api_data.get('last_price')
    raw_count = api_data.get('listCount') or api_data.get('list_count')
    
    return {
        'last_price': _normalize_price(raw_price),  # ✅ "12,500" → 12500.00
        'list_count': _normalize_count(raw_count),  # ✅ "125,000,000" → 125000000
        'audit_info': api_data.get('auditInfo', '')
    }

def _normalize_price(price_str):
    """문자열 가격을 숫자형으로 정규화"""
    if not price_str:
        return None
    # 쉼표 제거, 숫자 변환
    return float(price_str.replace(',', '')) if price_str else None

def _normalize_count(count_str):
    """문자열 수량을 정수형으로 정규화"""
    if not count_str:
        return None
    return int(count_str.replace(',', '')) if count_str else None
```

### Filter 변환: DB → Filter Zero 명확한 책임 분리
```python
# filters.py - DB → Filter Zero 변환 전담
def prepare_for_filter_zero(stock_objects):
    """DB의 snake_case 데이터를 Filter Zero용 camelCase로 변환"""
    return [{
        'lastPrice': float(s.last_price) if s.last_price else 0,
        'listCount': int(s.list_count) if s.list_count else 0,
        'auditInfo': s.audit_info or ''
    } for s in stock_objects]

# update_analysis_target_flags - 명확한 데이터 흐름
stock_info_for_filter = prepare_for_filter_zero(target_stocks)
filtered_stocks_info = apply_filter_zero(stock_info_for_filter)
```

### 이 solution의 장점
1. **PostgreSQL 호환성**: snake_case로 모든 도구/쿼리 문제 해결
2. **데이터 정확성**: 숫자형으로 계산 오류 방지 및 쿼리 성능 향상
3. **Filter Zero 호환성**: camelCase 기대값에 맞게 변환 제공  
4. **유지보수성**: 명확한 책임 분리로 디버깅 용이
5. **점진적 개선**: 기존 코드베이스와의 호환성 유지

## 📋 실행 권장 사항

### 1. 데이터 타입 최적화
- `last_price`: `String` → `Numeric(12, 2)` 전환 (소수점 2자리)
- `list_count`: `String` → `BigInteger` 전환 (대량 정수 처리)

### 2. 매핑 함수 정규화
- API 응답 데이터 정제 로직 추가
- 숫자형 변환 및 형식 통일
- NULL/빈값 방어적 처리

### 3. Filter 변환 책임 분리
- `filters.py`에서 DB → Filter Zero 데이터 변환 전담
- 단일 키(`lastPrice`, `listCount`, `auditInfo`) 사용 보장

### 4. 테스트 체계 강화
- **단위 테스트**: 매핑 함수, 필터 함수 검증
- **통합 테스트**: 동기화 → DB → 필터 전체 흐름 검증
- **샘플 데이터**: 실제 API 응답으로 end-to-end 검증

### 5. 문서화 및 운영
- `docs/`에 쿼리 예제(`psql`), 마이그레이션 절차 추가
- 모니터링 체크리스트 및 롤백 방안 문서화
- 팀원 교육 자료 준비 (PostgreSQL naming rule 등)

## 🔚 결론 및 최종 요약

지침서 3.1의 근본 문제 해결 의지는 매우 훌륭하지만, PostgreSQL의 기술적 특성과 실무 운영 리스크를 고려하여 **다음과 같은 접근을 강력히 권장합니다**:

**"Inspector 권고를 수용하여 `snake_case` 스키마 유지 후 API→DB 매핑을 개선(정규화 포함)하고, `last_price/list_count`는 숫자형 전환을 검토하여 안정성과 계산정확성을 확보하겠습니다."**

이렇게 하면:
- ✅ PostgreSQL 호환성 문제 원천 해결
- ✅ 데이터 계산 정확성 및 쿼리 성능 향상
- ✅ Filter Zero 정상 작동 보장  
- ✅ 기존 코드베이스와의 완전 호환
- ✅ 장기적인 유지보수성 및 운영 안정성 확보

감독관님의 최종 결정을 기다리겠습니다.
