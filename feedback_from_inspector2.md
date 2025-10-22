## 🔍 `dag_initial_loader.py` 리팩토링 지침 검수

**감독관님, 제안된 `dag_initial_loader.py` 수정 지침을 꼼꼼히 검토했습니다.**

### ✅ **지침의 강점 (동의하는 부분)**

#### 1. **이중 루프 구조의 타당성** ✅
```python
for code in baseline_codes:
    for timeframe in baseline_timeframes:  # 타임프레임 루프 추가
```

**장점**: 
- 모든 기준 데이터(지수+업종)에 대해 일/주/월봉을 완전히 적재
- 데이터 정합성 확보: RS 계산에 필요한 모든 데이터가 초기부터 존재

#### 2. **로그 메시지 개선** ✅
```python
logger.info("기준 데이터(지수, 업종)의 전체 과거 일/주/월봉 적재를 시작합니다.")
```

**장점**: 작업 범위를 명확히 인지할 수 있도록 로그 개선

#### 3. **에러 로깅 향상** ✅  
```python
logger.error(f"기준 데이터 적재 중 오류: {code} ({timeframe}) - {e}", exc_info=True)
```

**장점**: 오류 발생 시 코드와 타임프레임 정보를 함께 기록하여 디버깅 용이성 향상

### ⚠️ **주의가 필요한 부분 (개선 제안)**

#### 1. **TIMEFRAME_PERIOD_MAP 존재 여부 확인 필요** ⚠️
```python:37
period = TIMEFRAME_PERIOD_MAP.get(timeframe, '5y')
```

**문제점**: 현재 `dag_initial_loader.py`에 `TIMEFRAME_PERIOD_MAP`이 정의되어 있는지 확인 필요

**해결방안**: 
```python
# TIMEFRAME_PERIOD_MAP이 없으면 기본값 사용
if 'TIMEFRAME_PERIOD_MAP' in globals():
    period = TIMEFRAME_PERIOD_MAP.get(timeframe, '10y')
else:
    # 기본 폴백 값
    period = '10y' if timeframe == 'mon' else '5y'
```

#### 2. **API Rate Limiting 부하 증가 우려** ⚠️
**현재**: 1개 코드 × 1타임프레임 = 1회 호출  
**변경후**: 1개 코드 × 3타임프레임 = 3회 호출

**해결방안**: sleep 시간을 0.3초 → 0.5초로 증가하여 API 과부하 방지
```python
time.sleep(0.5)  # API Rate Limiting 보강
```

#### 3. **에러 처리 전략 보강 필요** ⚠️
**현재**: 개별 타임프레임 실패 시 continue만 수행

**해결방안**: 주요 지수(KOSPI, KOSDAQ)는 반드시 성공해야 하므로 에러 카운팅 추가
```python
error_count = 0
for code in baseline_codes:
    for timeframe in baseline_timeframes:
        try:
            # ... 적재 로직 ...
        except Exception as e:
            error_count += 1
            logger.error(f"기준 데이터 적재 중 오류: {code} ({timeframe}) - {e}", exc_info=True)
            continue

if error_count > len(baseline_codes) * len(baseline_timeframes) * 0.3:
    raise ValueError("너무 많은 기준 데이터 적재에 실패했습니다.")
```

### 📋 **cursor.ai 개발자에게 전달할 개선된 지침**

**제목**: `dag_initial_loader.py` 초기 적재 확장 지침 (개선안)

**담당자**: cursor.ai 개발자

**작업 파일**: `/home/jscho/ChartInsight-Studio/DataPipeline/dags/dag_initial_loader.py`

**수정 내용**:
```python
# --- [신규] 2. 기준 데이터(지수, 전체 업종) 과거 일/주/월봉 전체 적재 ---
logger.info("기준 데이터(지수, 업종)의 전체 과거 일/주/월봉 적재를 시작합니다.")
index_codes = ['001', '101']
sector_codes = [s.sector_code for s in db_session.query(Sector.sector_code).all()]
baseline_codes = index_codes + sector_codes

# 처리할 타임프레임 목록 정의
baseline_timeframes = ['d', 'w', 'mon']

error_count = 0
for code in baseline_codes:
    for timeframe in baseline_timeframes:
        try:
            # 타임프레임별 적절한 기간 설정 (TIMEFRAME_PERIOD_MAP 있으면 사용)
            if 'TIMEFRAME_PERIOD_MAP' in globals():
                period = TIMEFRAME_PERIOD_MAP.get(timeframe, '10y')
            else:
                # 기본 폴백 값: 월봉은 10년, 일/주봉은 5년
                period = '10y' if timeframe == 'mon' else '5y'

            load_initial_history(
                stock_code=code,
                timeframe=timeframe, 
                period=period,
                execution_mode=execution_mode
            )
            time.sleep(0.5)  # API Rate Limiting 강화
        except Exception as e:
            error_count += 1
            logger.error(f"기준 데이터 적재 중 오류: {code} ({timeframe}) - {e}", exc_info=True)
            continue

# 에러율이 30% 이상이면 실패로 처리
if error_count > len(baseline_codes) * len(baseline_timeframes) * 0.3:
    raise ValueError(f"너무 많은 기준 데이터 적재에 실패했습니다. (에러: {error_count}개)")

logger.info("기준 데이터 과거 일/주/월봉 적재 완료.")
```

**검증 요청사항**:
1. `TIMEFRAME_PERIOD_MAP` 변수가 현재 파일에 존재하는지 확인
2. API Rate Limiting이 충분한지 모니터링
3. 주요 지수(`001`, `101`)가 반드시 모든 타임프레임에서 성공하는지 확인

### 🎯 **최종 판단**

**감독관님, 기본 지침은 훌륭하지만 위험 요소가 있어 개선안을 제안합니다.**

**동의 여부**: **⚠️ 조건부 동의** (개선안 반영 시 완전 동의)

주요 지수(KOSPI, KOSDAQ)의 초기 적재 실패는 전체 시스템에 치명적이므로, 보다 안전한 구현이 필요합니다. 제안된 개선안으로 진행하면 완벽할 것입니다!