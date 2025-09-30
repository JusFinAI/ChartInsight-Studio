#!/usr/bin/env python3
"""
실패한 조합들의 원인 분석
"""

def analyze_failed_combinations():
    """
    실패한 조합들이 왜 실패했는지 상세 분석
    """

    # 모든 시도된 조합들 확인
    all_attempts = manager.get_debug_attempts()
    failed_attempts = [a for a in all_attempts if not a['eval_result']]

    print(f"분석할 실패 조합 수: {len(failed_attempts)}")

    # 각 실패 조합의 상세 분석
    for i, attempt in enumerate(failed_attempts[:10]):  # 처음 10개만
        print(f"\n=== 실패 조합 {i+1} 분석 ===")
        points = attempt['time_ordered']
        mapping = attempt['mapping']

        print(f"기간: {points[0].get('actual_date')} ~ {points[-1].get('actual_date')}")
        print(f"위치: pos={attempt['pos']}, 스킵={attempt['skips_left']}")

        # IHS 매핑에서 각 포인트 확인
        p1 = mapping.get('P1')
        v1 = mapping.get('V1')
        p2 = mapping.get('P2')
        v2 = mapping.get('V2')
        p3 = mapping.get('P3')
        v3 = mapping.get('V3')

        if not all([p1, v1, p2, v2, p3, v3]):
            print("❌ 매핑 정보 불완전")
            continue

        print("포인트별 분석:")
        print(f"  P1 (왼쪽 어깨): {p1.get('value')","} - 인덱스 {p1.get('index')}")
        print(f"  V1 (왼쪽 겨드랑이): {v1.get('value')","} - 인덱스 {v1.get('index')}")
        print(f"  P2 (머리): {p2.get('value')","} - 인덱스 {p2.get('index')}")
        print(f"  V2 (오른쪽 겨드랑이): {v2.get('value')","} - 인덱스 {v2.get('index')}")
        print(f"  P3 (오른쪽 어깨): {p3.get('value')","} - 인덱스 {p3.get('index')}")
        print(f"  V3 (최종 저점): {v3.get('value')","} - 인덱스 {v3.get('index')}")

        # 실패 원인 추정
        failure_reasons = []

        # 1. 기본 조건: P2가 가장 높아야 함
        if p2.get('value') <= p1.get('value') or p2.get('value') <= p3.get('value'):
            failure_reasons.append("기본조건: 머리(P2)가 가장 높지 않음")

        # 2. 균형 규칙
        l_mid = 0.5 * (p1.get('value') + v2.get('value'))
        r_mid = 0.5 * (p3.get('value') + v3.get('value'))

        if p1.get('value') < r_mid:
            failure_reasons.append(f"균형규칙: P1({p1.get('value')","}) < R_mid({r_mid:.".0f")")

        if p3.get('value') < l_mid:
            failure_reasons.append(f"균형규칙: P3({p3.get('value')","}) < L_mid({l_mid:.".0f")")

        # 3. 대칭 규칙 (시간)
        try:
            p1_ts = p1.get('actual_date')
            p2_ts = p2.get('actual_date')
            p3_ts = p3.get('actual_date')

            if p1_ts and p2_ts and p3_ts:
                l_time = (p2_ts - p1_ts).total_seconds()
                r_time = (p3_ts - p2_ts).total_seconds()

                if l_time <= 0 or r_time <= 0:
                    failure_reasons.append("대칭규칙: 시간 차이 0 이하")
                elif r_time > 2.5 * l_time:
                    failure_reasons.append(f"대칭규칙: 오른쪽 시간이 너무 김 (R/L = {r_time/l_time:.".2f")")
                elif l_time > 2.5 * r_time:
                    failure_reasons.append(f"대칭규칙: 왼쪽 시간이 너무 김 (L/R = {l_time/r_time:.".2f")")
        except Exception as e:
            failure_reasons.append(f"대칭규칙: 시간 계산 오류 - {e}")

        print("실패 원인:")
        if failure_reasons:
            for reason in failure_reasons:
                print(f"  ❌ {reason}")
        else:
            print("  ❓ 명확한 실패 원인을 찾을 수 없음")

        # 추가 분석: 각 포인트 간의 관계
        print("포인트 관계 분석:")
        print(f"  왼쪽 어깨(P1) vs 오른쪽 어깨(P3): {p1.get('value')","} vs {p3.get('value')","}")
        print(f"  머리(P2) vs 왼쪽 어깨(P1): {p2.get('value')","} vs {p1.get('value')","}")
        print(f"  머리(P2) vs 오른쪽 어깨(P3): {p2.get('value')","} vs {p3.get('value')","}")

        try:
            p1_ts = p1.get('actual_date')
            p3_ts = p3.get('actual_date')
            if p1_ts and p3_ts:
                total_time = (p3_ts - p1_ts).total_seconds()
                print(f"  전체 패턴 시간: {total_time / (24*3600)".1f"}일")
        except:
            pass

def find_potential_good_combinations():
    """
    실패했지만 조건을 거의 만족하는 조합들을 찾아봄
    """

    all_attempts = manager.get_debug_attempts()
    failed_attempts = [a for a in all_attempts if not a['eval_result']]

    print("
=== 조건을 거의 만족하는 조합들 찾기 ===")

    good_candidates = []

    for attempt in failed_attempts[:20]:  # 처음 20개만 확인
        points = attempt['time_ordered']
        mapping = attempt['mapping']

        p1 = mapping.get('P1')
        p2 = mapping.get('P2')
        p3 = mapping.get('P3')
        v1 = mapping.get('V1')
        v2 = mapping.get('V2')
        v3 = mapping.get('V3')

        if not all([p1, v1, p2, v2, p3, v3]):
            continue

        # 조건 체크
        conditions = {
            'p2_is_highest': p2.get('value') > p1.get('value') and p2.get('value') > p3.get('value'),
            'balance_left': p1.get('value') >= 0.5 * (p3.get('value') + v3.get('value')),
            'balance_right': p3.get('value') >= 0.5 * (p1.get('value') + v2.get('value'))
        }

        # 시간 대칭 체크 (간단 버전)
        try:
            p1_ts = p1.get('actual_date')
            p2_ts = p2.get('actual_date')
            p3_ts = p3.get('actual_date')

            if p1_ts and p2_ts and p3_ts:
                l_time = (p2_ts - p1_ts).total_seconds()
                r_time = (p3_ts - p2_ts).total_seconds()

                if l_time > 0 and r_time > 0:
                    time_ratio = max(l_time, r_time) / min(l_time, r_time)
                    conditions['time_symmetry'] = time_ratio <= 2.5
                else:
                    conditions['time_symmetry'] = False
            else:
                conditions['time_symmetry'] = False
        except:
            conditions['time_symmetry'] = False

        # 조건을 많이 만족하는 조합들 찾기
        satisfied_count = sum(conditions.values())
        if satisfied_count >= 2:  # 2개 이상 조건 만족하면 후보로
            good_candidates.append({
                'attempt': attempt,
                'satisfied_conditions': satisfied_count,
                'conditions': conditions
            })

    print(f"조건을 많이 만족하는 조합들: {len(good_candidates)}개")

    for i, candidate in enumerate(good_candidates[:5]):  # 처음 5개만
        attempt = candidate['attempt']
        points = attempt['time_ordered']
        first_date = points[0].get('actual_date')
        last_date = points[-1].get('actual_date')

        if isinstance(first_date, pd.Timestamp) and isinstance(last_date, pd.Timestamp):
            first_str = first_date.strftime('%Y-%m-%d')
            last_str = last_date.strftime('%Y-%m-%d')

            print(f"\n후보 {i+1}: {first_str} ~ {last_str}")
            print(f"  만족한 조건 수: {candidate['satisfied_conditions']}/4")
            print("  조건 상세:"            for cond_name, satisfied in candidate['conditions'].items():
                status = "✅" if satisfied else "❌"
                print(f"    {status} {cond_name}")

            print(f"  위치: pos={attempt['pos']}, 스킵={attempt['skips_left']}")

if __name__ == "__main__":
    import pandas as pd

    print("실패 조합 분석을 시작합니다...")
    analyze_failed_combinations()
    find_potential_good_combinations()
