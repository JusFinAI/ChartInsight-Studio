아래 문서는 “최신 HS/IHS 탐지 로직으로의 정리”를 위한 실행 계획서입니다. 아직 코드는 수정하지 않습니다. 각 Task는 바로 적용 가능한 편집 프롬프트로 사용할 수 있도록 목적/변경 범위/수정 포인트/검증 기준을 포함합니다. 대상 파일은 `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db/patterns.py` 및 `run_full_analysis.py` 입니다.

### 공통 배경
- 현재 최신 로직: `_find_hs_ihs_structural_points` → `evaluate_candidate`에서 6포인트(HS: V1-P1-V2-P2-V3-P3 / IHS: P1-V1-P2-V2-P3-V3)를 완전하게 구성·검증 후 후보 반환. 이후 `check_for_hs_ihs_start`가 감지기 생성.
- 예전 로직 잔재: 감지기(`HeadAndShouldersDetector`, `InverseHeadAndShouldersDetector`)의 `update()`에서 P3/V3 실시간 탐지/균형·대칭 규칙 재검증/세분화된 스테이지 전환(LeftShoulder..., RightNeckline...) 수행.
- 목표: 구조 검증은 “탐색 단계에서 1회만” 수행. 감지기는 “완성 조건 확인기(AwaitingCompletion 중심)”로 단순화.

---

## Task 1) 감지기 초기화 정합성: 6포인트 모두 할당 + AwaitingCompletion로 통일
- 목적: 최신 로직에 맞춰 감지기 생성 시 이미 완전한 구조(6포인트)를 보유하도록 일관화. 이후 `update()`는 완성 조건만 평가.
- 변경 범위: `PatternManager.check_for_hs_ihs_start`
- 핵심 수정 포인트:
  - HS 분기에서 `detector.P3`를 `structural_points['P3']`로 반드시 설정.
  - IHS는 이미 `P3_ihs`를 설정 중이나 동일 개념을 문서화.
  - 두 패턴 모두 `stage = "AwaitingCompletion"`로 설정(현 상태는 HS: RightNecklineValleyDetected, IHS: RightNecklinePeakDetected → 최신 로직과 불일치).
  - `evaluate_candidate(structural_points, pattern_type)`는 `_find_hs_ihs_structural_points`에서 이미 수행되므로 이중 검증 제거.
- 검증 기준:
  - 디버그 콘솔: 감지기 생성 직후 `detector.stage`가 `"AwaitingCompletion"`인지 확인.
  - `manager.get_debug_attempts()`로 직전 구조 포인트가 6개 모두 정상 기록됐는지 확인(날짜, 인덱스 함께).

---

## Task 2) HeadAndShouldersDetector.update 단순화: 실시간 P3 탐지/구조 검증 제거
- 목적: 감지기는 “완성 조건”만 확인. 구조 검증 및 실시간 P3 탐지는 탐색단계에서 끝냄.
- 변경 범위: `HeadAndShouldersDetector.update`
- 핵심 수정 포인트:
  - Stage 흐름을 `"AwaitingCompletion"` → `"Completed"`/`"Failed"`만 사용(예전 스테이지: LeftShoulderPeakDetected, LeftNecklineValleyDetected, HeadPeakDetected, RightNecklineValleyDetected 제거).
  - `RightNecklineValleyDetected`에서 P3 후보를 실시간으로 찾고 균형/대칭을 재검증하는 블록 제거.
  - `"AwaitingCompletion"` 시:
    - aggressive 모드: 음봉 + 종가 < 직전 저점(기존 구현 유지)
    - neckline 모드: V2~V3 넥라인(기울기) 하향 돌파(기존 계산 유지)
  - 리셋 조건 정리: 구조 확정 이후의 “과도한” 무효화(예: V2/P2 돌파 등)는 제거하거나 제한. 데이터 인덱스 오류/필수 포인트 누락 같은 치명적 오류만 실패 처리.
- 검증 기준:
  - 분석 로그에서 P3 탐색/균형/대칭 재검증 로그가 더 이상 출력되지 않아야 함.
  - 동일 데이터로 이전 대비 감지기 상태 전이가 단순해지고, 완성 조건 충족 시에만 `"Completed"`로 전환.

---

## Task 3) InverseHeadAndShouldersDetector.update 단순화: 실시간 V3 탐지/구조 검증 제거
- 목적: IHS도 HS와 동일하게 “완성 조건 확인기”로 단순화.
- 변경 범위: `InverseHeadAndShouldersDetector.update`
- 핵심 수정 포인트:
  - Stage 흐름을 `"AwaitingCompletion"` 중심으로 단순화.
  - `RightNecklinePeakDetected`에서 V3를 실시간으로 찾고 균형/대칭 재검증하는 블록 제거.
  - `"AwaitingCompletion"` 시:
    - aggressive 모드: 양봉 + 종가 > 직전 고점(기존 구현 유지)
    - neckline 모드: P2~P3 넥라인 상향 돌파(기존 계산 유지)
  - 리셋 조건 정리(HS와 동일 원칙).
- 검증 기준:
  - V3 탐색/균형/대칭 재검증 로그가 더 이상 나오지 않아야 함.
  - 완성 조건만으로 `"Completed"`/`"Failed"`가 결정.

---

## Task 4) 스테이지/상태 상수 정리 및 최소화
- 목적: 감지기의 역할 축소에 따라 불필요해진 스테이지 제거.
- 변경 범위: 두 감지기 클래스의 상태 정의/사용
- 핵심 수정 포인트:
  - 유지: `"AwaitingCompletion"`, `"Completed"`, `"Failed"`
  - 제거 대상: `LeftShoulderValleyDetected`, `LeftNecklinePeakDetected`, `HeadValleyDetected`, `RightNecklinePeakDetected`, `LeftShoulderPeakDetected`, `LeftNecklineValleyDetected`, `HeadPeakDetected`, `RightNecklineValleyDetected` 등
  - `PatternDetector.reset()` 호출 경로 점검(필요 최소 수준으로 유지)
- 검증 기준:
  - 상태 전이 로그에서 이전 스테이지 문자열이 더 이상 나타나지 않음.
  - 감지기는 생성 즉시 `"AwaitingCompletion"`로 시작.

---

## Task 5) 이중 구조 검증 제거: evaluate_candidate는 탐색 단계에서만
- 목적: 균형/대칭/머리비율 검증을 한 번만 수행.
- 변경 범위: `HeadAndShouldersDetector.update`, `InverseHeadAndShouldersDetector.update`
- 핵심 수정 포인트:
  - 업데이트 내에서 `evaluate_candidate` 유사 로직 삭제.
  - `_find_hs_ihs_structural_points → evaluate_candidate`에서 이미 통과한 조합만 감지기로 생성하는 것을 문서화.
- 검증 기준:
  - 검증 관련 로그가 탐색 단계에서만 출력됨.
  - 감지기 업데이트 로그는 완성 조건 판별과 관련된 내용으로만 구성.

---

## Task 6) run_full_analysis.py 연동 확인
- 목적: 상위 호출부는 동일하게 동작하면서, 감지기는 “완성 조건 확인”만 수행하도록 함.
- 변경 범위: `run_full_analysis.py` (구조상 큰 수정 없음)
- 핵심 확인 포인트:
  - `manager.check_for_hs_ihs_start(all_peaks, all_valleys, completion_mode='neckline')` 호출 → 감지기 생성 시 `"AwaitingCompletion"`로 시작.
  - 루프 내 `manager.update_all(current_candle_dict, newly_registered_peak, newly_registered_valley)`에서 감지기는 완성 조건만 평가.
- 검증 기준:
  - 루프 처리량/시간에 저하 없음(오히려 감소 기대).
  - 패턴 완료 로그는 감지기 업데이트 단계에서만 출력.

---

## Task 7) 디버깅/관측 개선 유지
- 목적: 분석과 시각화 지원 도구 유지.
- 변경 범위: `PatternManager` 도구 메서드들
- 유지/강화 항목:
  - `all_attempts`(모든 후보) 누적
  - `get_debug_attempts()`, `print_debug_attempts(limit)` (연/월/일 포함 포맷 유지: `%Y%m%d`)
  - 감지기 생성 시 구조 포인트(인덱스+날짜) 일괄 로깅

---

## Task 8) 호환 플래그(옵션) 도입(선택)
- 목적: 필요시 예전 실시간 P3/V3 탐지 로직을 켜서 회귀 테스트 가능.
- 변경 범위: 감지기 클래스/매니저
- 제안:
  - 환경변수 또는 매개변수 `REALTIME_P3_ENABLED`(기본 False)
  - True일 때만 예전 P3/V3 실시간탐지 코드 경로 유지(개발/비교용)
- 검증 기준:
  - 플래그 Off(default)에서 최신동작, On에서 과거 동작 재현 가능.

---

## Task 9) 수용 기준(acceptance) 및 수동 테스트 시나리오
- 수용 기준:
  - `_find_hs_ihs_structural_points`로 반환된 구조 포인트가 감지기 생성 시 그대로 주입되고, 감지기 스테이지는 항상 `"AwaitingCompletion"`로 시작.
  - 감지기 업데이트에서 구조 검증 관련 로그가 사라지고, 완성 조건 판단 로그만 출력.
  - 동일 데이터로 실행 시 “탐색 후보 수”는 동일하지만 “감지기 업데이트 처리량”은 감소.
- 수동 테스트:
  - 디버그 콘솔에서:
    - “감지기 생성 직후 상태” 확인:
      - `len(manager.active_detectors)`, 각 `detector.stage == "AwaitingCompletion"`
    - “성공/실패 조합 확인”:
      - `attempts = manager.get_debug_attempts()` / 성공/실패 카운트
    - “연도 포함 포인트 출력”:
      - 성공 조합 한 개를 골라, 각 포인트의 `index`와 `actual_date.strftime('%Y%m%d')` 출력
  - 그래프 확인:
    - `main_dashboard.py`로 표시된 HS/IHS 박스/넥라인이 감지된 포인트들과 일치하는지 육안 검증.

---

## Task 10) 위험요인 및 롤백 계획
- 위험:
  - 실시간 P3/V3 탐지 제거로 인해 “완전하지 않은 구조”를 포착하던 과거 기능 손실
  - 공격적/넥라인 완성 조건만으로는 약간의 민감도 변화 가능
- 대응:
  - Task 8의 호환 플래그로 과거 경로 유지 가능
  - 단계적 배포: 로컬 → 내부 검증 → 프로파일링 후 적용
  - 로그 레벨/형식 유지로 회귀 비교 용이

---

## Task 11) 적용 순서(권장)
1. Task 1: 감지기 초기화 정합성(6포인트 모두 할당 + AwaitingCompletion) 및 이중 평가 제거
2. Task 2/3: 두 감지기 `update()` 정리(실시간 P3/V3/균형·대칭 제거)
3. Task 4: 스테이지 상수 최소화
4. Task 5: 구조 검증 이중 제거 최종 점검
5. Task 6: 상위 연동 확인(성능/로그/완성동작)
6. Task 7/8: 디버깅 도구/호환 옵션 정리
7. Task 9/10: 수용 기준 테스트 + 위험 관리

---

원하시면 위 Task들 중 하나를 골라, 구체적인 “변경 전/후” 코드 스니펫(파일 경로/함수/안전한 편집 단위 포함)과 디버그 콘솔 검증 절차를 곁들인 세부 실행 프롬프트로 풀어드리겠습니다.

