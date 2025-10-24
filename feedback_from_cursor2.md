## 🔍 감독관 지침 검수 결과

**cursor.ai inspector**로서 감독관의 지침을 꼼꼼히 검토했습니다. [[memory:4423699]] [[memory:3005993]] [[memory:2934118]]

### ✅ 지침 적합성 평가

**지침은 전반적으로 타당합니다:**
1. **목표 명확성**: `dag_live_collectors.py`의 역할을 "장중 분봉 데이터 수집"으로 명확히 한정
2. **수정 범위 적절**: DAG_CONFIGS에서 `daily`, `weekly` 제거 및 관련 코드 단순화
3. **아키텍처 일관성**: `dag_daily_batch`가 저빈도 데이터 처리를 전담하도록 역할 분리

### ⚠️ 발견된 추가 문제점 및 제안사항

하지만 지침에서 다루지 않은 **중요한 기술적 이슈**를 발견했습니다:

#### 1. **타임프레임 매핑 불일치 문제**

```python:50:56:DataPipeline/src/data_collector.py
TIMEFRAME_TO_DB_FORMAT = {
    '5m': 'M5', 
    '30m': 'M30',
    '1h': 'H1',
    'd': 'D',      # 주의: 'd' 형식 사용
    'w': 'W'       # 주의: 'w' 형식 사용
}
```

**문제점**: `data_collector.py`에서는 `'d'`, `'w'` 형식을 기대하지만, `dag_live_collectors.py`에서는 `'5m'`, `'30m'`, `'1h'` 형식만 사용하게 됨

#### 2. **DAG 설명문 업데이트 필요**

현재 DAG description이 여전히 광범위하게 기술됨:
```python:83:83:DataPipeline/dags/dag_live_collectors.py
description='[LIVE 모드 전용] 실시간 증분 데이터 수집 DAG'
```
→ **"장중 분봉 데이터 수집 전용 DAG"**로 명확히 변경 필요

#### 3. **주석 정리 필요**

제거된 기능에 대한 주석이 여전히 존재:
```python:12:13:DataPipeline/dags/dag_live_collectors.py
# 정규화: DAG 레벨에서 'daily'/'weekly'을 collector가 기대하는 'd'/'w'로 변환
```
→ 이 주석은 이제 불필요함

### 💡 감독관에게의 제안

**질문 1: 타임프레임 형식 통일성**
> "`data_collector.py`의 `TIMEFRAME_TO_DB_FORMAT`이 `'d'`, `'w'` 형식을 사용하는데, `dag_live_collectors.py`에서는 `'5m'`, `'30m'`, `'1h'` 형식만 남게 됩니다. 이 형식 불일치를 해결하기 위해 `data_collector.py`의 매핑을 수정할지, 아니면 현재 상태로 유지할지 여부를 확인해 주시겠습니까?"

**질문 2: DAG 태그 정리**
> "`tags=['production', 'incremental'] + config['tags']`에서 `config['tags']`에 이제 `['5min']`, `['30min']`, `['1h']`만 포함됩니다. 기존 `['daily']`, `['weekly']` 태그를 완전히 제거하는 것이 맞는지 확인 부탁드립니다."

**제안 3: 추가 코드 정리**
> "`get_live_collector_targets()` 함수의 docstring에서 'live.stocks 테이블에서 is_active=True인 종목 코드를 조회합니다.'라는 설명이 있는데, 이제 순수 분봉 데이터 수집만 하므로 '장중 분봉 데이터 수집 대상 종목 조회'로 명확히 하는 것이 좋을 것 같습니다."

### 🛠️ 수정 실행 계획

지침에 따라 다음과 같이 수정을 진행하겠습니다:

1. **1단계**: DAG_CONFIGS에서 `'daily'`, `'weekly'` 제거
2. **2단계**: 타임프레임 변환 로직 단순화 (`timeframe: timeframe`)
3. **추가 작업**: 
   - DAG description 업데이트
   - 불필요한 주석 제거
   - docstring 명확화

이 수정들을 진행하기 전에, 감독관님의 위 제안사항에 대한 피드백을 기다리겠습니다. 특히 타임프레임 형식 불일치 문제는 중요한 기술적 이슈이므로 반드시 해결해야 합니다.