**Head and Shoulders (H&S) / Inverse H&S (IH&S) 패턴 탐지 알고리즘 V1.0**

**1. 개요**

### 1.1 알고리즘의 목적

본 문서는 `TrendDetector`(Peak/Valley 및 추세 분석 알고리즘 V4.x 기반)에서 탐지된 고점(Peak)과 저점(Valley) 정보를 활용하여, 가격 차트에서 대표적인 추세 반전 패턴인 **Head and Shoulders (H&S)** 및 **Inverse Head and Shoulders (IH&S)** 패턴을 객관적이고 실시간으로 자동 감지하는 알고리즘을 정의합니다.

핵심 목표는 다음과 같습니다:

- **객관적 패턴 검출**: 특정 성공률을 보장하는 패턴만을 선별하는 것이 아니라, Price Action 및 구조적 특징에 기반하여 H&S/IH&S 형태에 부합하는 패턴을 **기계적이고 일관된 규칙**으로 모두 검출하는 데 중점을 둡니다.
- **실시간 감지**: 미래 데이터를 사용하지 않고, 패턴이 형성되는 과정(각 극점 발생 시점)을 추적하여 **현재 시점까지의 정보만으로** 패턴의 유효성을 판단하고 완성 여부를 감지합니다.
- **파라미터 최소화**: 특정 종목이나 타임프레임에 과도하게 최적화(fitting)되는 것을 방지하기 위해, 임의의 비율(%)이나 기간 같은 **조정 가능한 파라미터 사용을 최소화**하고, 극점의 상대적 위치와 가격 레벨 비교 등 구조적 정의에 집중합니다.
- **확장성 기반:** 객관적으로 검출된 모든 패턴(성공/실패 포함)은 향후 통계 분석, 특징(feature) 추출, 머신러닝 기반 성공 확률 예측 모델 개발 등을 위한 기초 데이터로 활용될 수 있습니다.

### 1.2 패턴 기본 정의

- **Head and Shoulders (H&S)**: 일반적으로 상승 추세의 마지막 국면에서 나타나며, **하락 추세로의 반전**을 예고하는 패턴입니다. 세 개의 봉우리(왼쪽 어깨, 머리, 오른쪽 어깨)와 두 개의 골짜기(넥라인 지점)로 구성됩니다.
- **Inverse Head and Shoulders (IH&S)**: 일반적으로 하락 추세의 마지막 국면에서 나타나며, **상승 추세로의 반전**을 예고하는 패턴입니다. H&S와 대칭적인 구조로, 세 개의 골짜기와 두 개의 봉우리로 구성됩니다.

### 1.3 기반 알고리즘

이 패턴 감지 알고리즘은 사전에 실행된 **`TrendDetector` (Peak/Valley 및 추세 분석 알고리즘 V4.x)**가 제공하는 다음 정보를 입력으로 사용합니다:

- **JS Peak/Valley 리스트**: 주요 추세 전환점 정보.
- **Secondary Peak/Valley 리스트**: 중간 규모 전환점 정보.
- **캔들 데이터 (OHLC)**: 규칙 검증에 필요한 개별 캔들 정보.

### 1.4 핵심 용어 (H&S 기준)

- **P1 (Left Shoulder Peak):** 상승 추세 이후 형성되는 첫 번째 중요한 고점 (JS 또는 Secondary Peak).
- **V2 (Left Neckline Valley):** P1 이후 형성되는 첫 번째 중요한 저점 (JS 또는 Secondary Valley). 왼쪽 넥라인 지점.
- **P2 (Head Peak):** V2 이후 형성되는 고점. **반드시 P1보다 높아야 합니다 (`P2['value'] > P1['value']`)**. 패턴 내 최고점. (JS 또는 Secondary Peak)
- **V3 (Right Neckline Valley):** P2 이후 형성되는 저점. **V2 캔들의 몸통(Open-Close) 범위 내에 위치해야 유효**합니다. 오른쪽 넥라인 지점. (JS 또는 Secondary Valley)
- **P3 (Right Shoulder Peak):** V3 이후 형성되는 고점. **반드시 P2보다 낮아야 합니다 (`P3['value'] < P2['value']`)**. 또한, V3부터 P3 형성 과정 중 **최소 한 번 이상 가격(캔들 High)이 P1의 종가(`P1['Close']`) 수준에 도달**해야 유효한 P3로 간주됩니다. (JS 또는 Secondary Peak)
- **넥라인 (Neckline):** 패턴의 완성 및 돌파 기준선. 초기에는 V3의 저점 값 (`V3['value']`)을 기준으로 하는 **수평 넥라인**으로 정의합니다.
- **넥라인 돌파 (Neckline Break):** P3 형성 이후, 가격(캔들 종가)이 정의된 넥라인 레벨 아래로 하락 마감하는 것. 패턴 완성 신호.

_(IH&S의 경우 위 용어에서 Peak와 Valley의 역할 및 가격 비교 조건이 반대로 적용됩니다.)_

**2. H&S / IH&S 탐지 알고리즘 상세**

패턴 형성을 추적하기 위해 각 패턴별로 상태(Stage)를 정의하고 관리합니다. 여기서는 H&S를 기준으로 설명하며, IH&S는 대칭적으로 적용됩니다. 패턴 감지기(`HeadAndShouldersDetector`)는 `PatternManager` (또는 유사한 관리자)에 의해 관리되며, 각 캔들 정보를 받아 상태를 업데이트합니다.

### 2.1 H&S 탐지 상태(Stage) 정의

- **Stage 0: `Initial`**: 감지기 초기 상태.
- **Stage 1: `LeftShoulderPeakDetected`**: 유효한 P1 감지 및 저장.
- **Stage 2: `LeftNecklineValleyDetected`**: P1 이후 유효한 V2 감지 및 저장 (V2 캔들 O/C 값 포함).
- **Stage 3: `HeadPeakDetected`**: V2 이후 유효한 P2 감지 및 저장. **검증:** P2 > P1 확인.
- **Stage 4: `RightNecklineValleyDetected`**: P2 이후 유효한 V3 감지 및 저장. **검증:** V3 가격이 V2 캔들 몸통 범위 내인지 확인.
- **Stage 4.5: `CheckingRightShoulderRally`**: V3 이후 P3 형성 전, 반등 강도 확인 단계. 내부 플래그 `p1_close_level_reached` 관리 (`current['High'] >= P1['Close']` 발생 시 True 설정).
- **Stage 5: `RightShoulderPeakDetected`**: V3 이후 유효한 P3 감지 및 저장. **검증:** ① `P3 < P2`, ② `p1_close_level_reached is True`.
- **Stage 6: `AwaitingNecklineBreak`**: 모든 구성요소 확인 완료. 넥라인(`V3['value']`) 하향 돌파 대기.
- **Stage 7: `Completed`**: 넥라인 하향 돌파 확인 (`Close < V3['value']`).
- **Stage 8: `Failed`**: 각 단계별 리셋 조건 만족 시 진입.

### 2.2 H&S 패턴 완성 및 리셋 규칙 요약

**패턴 완성 조건 (Stage 6 -> 7):**

- `현재 Close < V3['value']`

**주요 리셋 조건 (패턴 실패 -> Stage 8):**

- Stage 1 리셋: V2 감지 전 P1 고점 상회 (`현재 High > P1['value']`).
- Stage 2 리셋: P2 감지 전 V2 저점 하회 (`현재 Close < V2['value']`).
- Stage 3 리셋:
    - P2 검증 실패 (`P2['value'] <= P1['value']`).
    - 유효 V3 감지 전 P2 고점 상회 (`현재 High > P2['value']`).
- Stage 4 리셋:
    - V3 검증 실패 (V2 몸통 범위 벗어남).
    - V3 형성/확정 중 V2 저점 하회 (`현재 Close < V2['value']`).
- Stage 4.5 리셋: 유효 P3 감지 전 P2 고점 상회 (`현재 High > P2['value']`).
- Stage 5 리셋:
    - P3 검증 실패 (`P3['value'] >= P2['value']` 또는 `p1_close_level_reached is False`).
    - P3 형성/확정 중 P2 고점 상회 (`현재 Close > P2['value']`).
- Stage 6 리셋: 넥라인 돌파 전 P3 고점 상회 (`현재 Close > P3['value']`).

### 2.3 Inverse Head and Shoulders (IH&S) 대칭 규칙

IH&S 패턴은 H&S와 정확히 반대 개념으로 탐지합니다.

- **구조:** V1(LS) -> P2(LN) -> V2(Head, V2<V1) -> P3(RN) -> V3(RS, V3>V2) -> Neckline(P2-P3) 상향 돌파.
- **V3 유효성:** `min(P2_캔들_Open, P2_캔들_Close) <= V3['value'] <= max(P2_캔들_Open, P2_캔들_Close)`
- **P3 형성 과정 검증:** V3 이후 `현재 캔들['Low'] <= V1['Close']` 발생 여부 확인 (`v1_close_level_reached` 플래그).
- **P3 유효성:** `V3['value'] > V2['value']` **AND** `v1_close_level_reached is True`.
- **넥라인 정의:** `neckline_level = P3['value']`.
- **패턴 완성:** `현재 Close > neckline_level`.
- **리셋 조건:** H&S의 가격 비교 방향을 반대로 적용.

**3. 구현 고려사항**

- **P/V 데이터 접근:** 감지기는 `TrendDetector`로부터 실시간으로 업데이트되는 JS 및 Secondary Peak/Valley 리스트 정보에 접근해야 합니다.
- **캔들 정보 저장:** V2(H&S) 또는 P2(IH&S) 극점이 확정될 때, 해당 캔들의 Open, Close 값을 함께 저장하여 이후 V3/P3 유효성 검증에 사용해야 합니다.
- **상태 관리:** 각 H&S/IH&S 패턴 후보마다 독립적인 상태(Stage)를 추적하고 관리해야 합니다 (`PatternManager` 또는 유사 클래스 역할).
- **극점 식별:** 감지 로직은 Peak/Valley 리스트에서 P1, V2, P2, V3, P3에 해당하는 극점을 순서와 조건을 만족하며 찾아내야 합니다. `_get_extremum_before` 와 같은 Helper 함수가 유용하게 사용될 수 있습니다.
- **넥라인 처리:** 초기에는 V3/P3 레벨을 기준으로 하는 수평 넥라인을 사용하지만, 향후 V2/P2와 V3/P3를 잇는 추세선(기울기 고려)으로 확장할 수 있습니다.

**4. 한계 및 개선 방향**

- **P/V 탐지 의존성:** 기반 P/V 탐지 알고리즘의 정확성과 속도에 크게 의존합니다.
- **규칙의 엄격성:** 정의된 규칙이 실제 시장의 다양한 변형 패턴을 얼마나 포괄할 수 있는지 추가 검증이 필요합니다.
- **넥라인 단순화:** 현재 수평 넥라인 가정은 실제 기울어진 넥라인 패턴을 놓칠 수 있습니다.
- **보조 지표 미사용:** 거래량, 모멘텀 등 추가 정보를 활용하면 패턴 신뢰도를 높일 수 있으나, 현재 로직에는 포함되지 않았습니다.
- **대칭성/품질 미고려:** P1≈P3 같은 대칭성이나 패턴의 형태적 품질은 현재 필수 조건에서 제외되었습니다.