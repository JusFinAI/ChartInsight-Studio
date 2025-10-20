나 (프로젝트 오너)

@market_sector_rs_calcurator_all_final.py 원래 내가 예제로 만든 코드에서도 zero-filtering이 적용되어 있는데, 자세히 비교해보고 차이점을 정리해 볼래 ?


cursor.ai 

좋습니다 — 두 코드의 Zero-filter(필터 제로) 비교 결과를 간결하게 정리합니다. 핵심 차이점, 실제 동작(영향), 개선 권고를 포함합니다.

중요 코드 참조(원본)
```5:11:DataPipeline/src/utils/filters.py
DEFAULT_FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000,  # 최소 시가총액 (단위: 억 원)
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}
```

```41:44:DataPipeline/src/utils/filters.py
    active_config = config if config is not None else DEFAULT_FILTER_ZERO_CONFIG
    min_market_cap_억 = active_config.get("MIN_MARKET_CAP_KRW", 0)
    exclude_keywords = [k.lower() for k in active_config.get("EXCLUDE_KEYWORDS", [])]
```

```56:64:DataPipeline/src/utils/filters.py
    for stock in stock_list:
        # 1) 키워드 필터 (대소문자 무시)
        name = (stock.get('name') or '')
        state = (stock.get('state') or '')
        audit_info = (stock.get('auditInfo') or stock.get('audit_info') or '')
        combined_text = f"{name} {state} {audit_info}".lower()
        if any(keyword in combined_text for keyword in exclude_keywords):
            continue
```

```81:84:DataPipeline/src/utils/filters.py
            market_cap_억 = (last_price * list_count) / 100_000_000
            if market_cap_억 < min_market_cap_억:
                continue
```

예제 스크립트(원본)
```17:23:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000, 
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}
```

```91:101:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
            # 1-1. 종목명에 포함된 키워드 (ETF, 스팩 등) 필터링
            if any(keyword in name for keyword in FILTER_ZERO_CONFIG["EXCLUDE_KEYWORDS"]):
                continue

            # 1-2. 종목 상태(state)에 포함된 키워드 (관리종목, 증거정지 등) 필터링
            if any(keyword in state_info for keyword in ["관리종목", "거래정지", "증거금100"]):
                continue

            # 1-3. 투자 유의(orderWarning) 상태 필터링 (0: 해당없음 외에는 모두 제외)
            if order_warning != '0':
                continue
```

```103:109:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
            last_price = int(stock.get('lastPrice', '0'))
            list_count = int(stock.get('listCount', '0'))
            market_cap = (last_price * list_count) / 100_000_000
            if market_cap < FILTER_ZERO_CONFIG["MIN_MARKET_CAP_KRW"]: continue
```

```111:127:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
            # 정보 보강(Enrichment): 업종 코드 찾기
            ...
            for code, s_name in target_sector_list.items():
                if s_name in corrected_sector_name or corrected_sector_name in s_name:
                    found_sector_code = code
                    break

            if not found_sector_code and sector_name_from_api:
                mismatch_log = {'stock_code': stock['code'], 'api_sector_name': sector_name_from_api}
                if mismatch_log not in self.mismatched_sectors: self.mismatched_sectors.append(mismatch_log)
                continue # 업종 코드를 못찾으면 분석 대상에서 제외
```

차이점 요약 (핵심)
- 대소문자 처리
  - filters.py: 키워드 비교를 모두 소문자로 변환하여 case-insensitive로 검사 (더 관대함).
  - 예제 스크립트: `any(keyword in name for keyword in ...)` 형태로 대소문자 구분(민감) — 영어 키워드가 소문자일 때 걸리지 않을 수 있음.

- 숫자 파싱(시가총액 계산)
  - filters.py: `_safe_parse_number`로 콤마 포함 문자열, 실수 등을 안전히 파싱(더 견고).
  - 예제 스크립트: `int(stock.get('lastPrice', '0'))`로 바로 파싱 — 콤마 등 포맷이 있으면 실패 가능.

- 추가 필터 조건
  - 예제 스크립트: `orderWarning`(투자유의) 체크로 추가 제외(0이 아니면 제외).
  - filters.py: audit/state 키워드와 시가총액만 검사(별도 orderWarning 체크 없음).

- 업종(섹터) 매칭(Enrichment)
  - 예제 스크립트: 업종 코드 매칭 로직이 포함되어 있으며, 업종 코드를 못 찾으면 그 종목을 제외(더 엄격).
  - filters.py: 업종 매칭/보강은 하지 않음 — 업종 누락 때문에 제외되지 않음(더 관대).

- 구성값 적용 방식
  - filters.py: `DEFAULT_FILTER_ZERO_CONFIG`를 함수 인자로 덮어쓸 수 있어 테스트·구성 변경이 쉬움.
  - 예제 스크립트: `FILTER_ZERO_CONFIG` 전역 상수로 고정(오버라이드 인터페이스 없음).

실무적 영향(어떤 차이를 유발하는가)
- 예제 스크립트가 더 엄격하므로 동일한 원시 API 데이터를 넣으면 예제 스크립트는 더 적은 종목을 통과시킴(특히 업종 매칭 실패·orderWarning·case mismatch·콤마 포함 가격 포맷 등에서 탈락).
- `dag_initial_loader`에서 사용하는 `apply_filter_zero`(filters.py)는 업종 미스매치 때문에 대량 제외를 하지 않으므로 더 많은 종목이 `is_active=True`로 올라갈 가능성(그리고 이후 분석 대상이 넓어짐).
- 숫자 파싱 문제(콤마 등)가 있으면 예제 스크립트에서 예외로 탈락하지만 filters.py는 통과시킬 수 있으므로 결과 차이가 생김.

권고(일치/개선 방안)
1. 목적에 맞게 일관화 선택
   - 분석 대상 기준을 엄격히 하려면 예제 스크립트의 추가 체크(업종 매칭, orderWarning, 정확한 포맷 검증)를 `apply_filter_zero`에 통합.
   - 반대로, 초기 적재(백필)에는 보다 관대해야 한다면 현재 `apply_filter_zero` 유지하고, 업종 기반 RS 분석 전 단계에서 별도의 enrichment+검증(예제 방식)을 추가 실행.

2. 기술적 개선 제안(실행하기 쉬운 우선순위)
   - 예제 스크립트처럼 업종 매칭이 필요하면 `apply_filter_zero`에 optional enrichment 파라미터 추가(섹터 리스트 전달 시 업종 매칭 수행하고 못 찾으면 제외).
   - 예제 스크립트의 `any(keyword in name for keyword in ...)`를 case-insensitive로 바꿔 일관성 확보.
   - 숫자 파싱: 예제 스크립트도 `_safe_parse_number` 방식(콤마·float 처리)으로 교체.
   - `orderWarning` 체크는 정책적 판단이므로 config로 켜/끄기 가능하도록.

3. 운영 권고
   - DAG(특히 `dag_daily_batch`)에선 분석 정확성(업종 매칭 중요) 우선이면, 분석 파이프라인 시작 전에 enrichment 필터링 단계를 더 엄격하게 실행하도록 파이프라인 단계 추가 권장.
   - 로그(업종 매칭 실패 목록)를 주기적으로 검토하여 매핑 테이블(SECTOR_NAME_MAP) 갱신.

원하시면 제가 다음 중 하나를 바로 수행해 드립니다:
- A) DB에서 현재 `live.stocks` 중 업종(upName/upCode) 정보가 비어 있거나 매칭 실패 가능성이 높은 레코드 샘플을 추출해 보여드리기,  
- B) `apply_filter_zero`에 예제 스크립트의 추가 체크(orderWarning, 업종 매칭 옵션 등)를 통합하는 코드 변경 제안서 작성(수정안),  
- C) 두 필터를 동일하게 동작시키기 위한 구체적 패치(코드 수정) 초안 생성.

나 (프로젝트 오너)

내가 의도한 zero-filtering은 ka10099 (종목정보 리스트) API 를 통해 얻은 응답 (Body)에서
시가 총액 기준외에도,

1. 'orderWarning' 이 0 이 아닌경우 필터링 대상
2. 'state', ' auditInfo'에 '"관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100", "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO", "스팩", "선물", "인버스", "리츠" 
등의 키워드가 있다면 필터링 대상 

이거든 .  이러한 설계 기준하에  'market_sector_rs_calcurator_all_final.py' 와 dag_initial_loader의 기준의 부합여부를 정리해줘 


아래에 두 코드의 Zero-filter 동작을 직접 비교·정리했습니다. 핵심 차이점, 실제 영향, 권고를 짧고 명확히 적었습니다.

참고 코드(핵심 발췌)
```56:64:DataPipeline/src/utils/filters.py
for stock in stock_list:
    # 1) 키워드 필터 (대소문자 무시)
    name = (stock.get('name') or '')
    state = (stock.get('state') or '')
    audit_info = (stock.get('auditInfo') or stock.get('audit_info') or '')
    combined_text = f"{name} {state} {audit_info}".lower()
    if any(keyword in combined_text for keyword in exclude_keywords):
        continue
```

```81:84:DataPipeline/src/utils/filters.py
market_cap_억 = (last_price * list_count) / 100_000_000
if market_cap_억 < min_market_cap_억:
    continue
```

```91:101:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
# 1-1. 종목명에 포함된 키워드 (ETF, 스팩 등) 필터링
if any(keyword in name for keyword in FILTER_ZERO_CONFIG["EXCLUDE_KEYWORDS"]):
    continue

# 1-2. 종목 상태(state)에 포함된 키워드 (관리종목, 증거정지 등) 필터링
if any(keyword in state_info for keyword in ["관리종목", "거래정지", "증거금100"]):
    continue

# 1-3. 투자 유의(orderWarning) 상태 필터링 (0: 해당없음 외에는 모두 제외)
if order_warning != '0':
    continue
```

```111:127:backend/_temp_integration/chart_pattern_analyzer_kiwoom/market_sector_rs_calcurator_all_final.py
# 업종 코드 찾기(Enrichment)
for code, s_name in target_sector_list.items():
    if s_name in corrected_sector_name or corrected_sector_name in s_name:
        found_sector_code = code
        break

if not found_sector_code and sector_name_from_api:
    # 업종 코드 못찾으면 분석 대상에서 제외
    continue
```

비교 요약 — 일치 항목
- 둘 다 EXCLUDE_KEYWORDS 기반 종목명/상태 필터와 시가총액(MIN_MARKET_CAP_KRW) 필터를 사용함.  
  → 즉, 기본 취지는 동일 (키워드·시가총액으로 1차 필터링).

차이점(중요)
1. orderWarning 체크
   - market_sector 예제: `orderWarning != '0'`이면 즉시 제외.  
   - filters.py: **orderWarning 체크 없음** → 현재 구현은 이 조건을 적용하지 않음.

2. 업종(섹터) 매칭(Enrichment)
   - market_sector 예제: 업종 코드(매칭)를 반드시 찾아야 통과(못 찾으면 제외).  
   - filters.py: 업종 매칭 로직 없음(업종 누락 때문에 제외되지 않음).

3. 케이스·파싱 견고성
   - filters.py: 비교문을 `.lower()`로 만들어 case-insensitive 처리, `_safe_parse_number`로 콤마·문자열 견고 파싱.  
   - 예제 스크립트: 문자열 비교는 원문 그대로(대소문자 민감 가능), `int()`로 직접 파싱(포맷 이슈 시 실패 가능).

실무적 영향
- 현재 `dag_initial_loader`(apply_filter_zero 사용)는 orderWarning 조건과 업종 검증을 적용하지 않으므로, market_sector 기준보다 더 많은 종목을 통과시켜 `is_active=True`로 올릴 가능성이 큼.  
- 그 결과 일일 파이프라인(`dag_daily_batch`)가 업종 매칭 불충분/월봉 부족 종목까지 분석 시도 → `sector_rs`/일부 `market_rs`가 None으로 많이 나올 수 있음(지금 관찰된 현상과 일치).

권고(우선순위)
1. 정책적으로 원하는 기준이 market_sector 예제(엄격)라면 `apply_filter_zero`에 다음을 추가:
   - `orderWarning` 필터 (exclude if != '0')
   - Optional: 업종(enrichment) 단계 — 섹터 리스트를 받아 업종 매칭 실패시 제외 또는 플래그 처리
   - 숫자 파싱은 `_safe_parse_number` 방식으로 통일
   - 키워드 비교는 case-insensitive로 통일(이미 filters.py는 그렇게 함)

2. 운영 선택지
   - 엄격 적용(권장 if 정확한 RS 필요): `apply_filter_zero` 강화 + `dag_initial_loader`에서 강화된 필터 사용 → `is_active`/분석 대상도 정합성 확보.
   - 관대 적용(권장 if 넓은 백필이 목표): 유지하되, `dag_daily_batch`에서 분석 전 업종 매칭/전처리 검증 단계 추가하여 분석 실패(월봉 없음 등)를 걸러내기.

다음 행동 제안 
- A) DB에서 `orderWarning != '0'`인 레코드 수와 샘플 추출 (현황 파악)  
- B) `apply_filter_zero`에 `orderWarning` 체크와 optional 업종 매칭(플래그 기반)을 추가하는 코드 패치 초안 작성  
- C) `dag_initial_loader`/`dag_daily_batch`에 업종 검증 스텝을 추가하는 설계 초안

