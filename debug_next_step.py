#!/usr/bin/env python3
"""
다음 단계 실행을 위한 디버그 코드
"""

def prepare_next_step():
    """
    다음 단계(pos=6에서 시작)를 준비하고 예측
    """

    print("=== 다음 단계 준비 (pos=6) ===")

    # 현재 상태
    current_pos = 6
    current_skips_left = 2
    current_points_count = 6

    print(f"현재 위치: pos={current_pos}")
    print(f"남은 스킵: {current_skips_left}")
    print(f"현재 포인트 수: {current_points_count}")

    # 다음에 찾아야 할 타입 결정 (IHS 모드)
    expected_type = 'peak' if current_points_count % 2 == 1 else 'valley'
    print(f"다음에 찾을 타입: {expected_type}")

    # pos=6부터 탐색할 후보들
    print("
=== pos=6부터의 탐색 후보들 ===")
    candidates_from_pos_6 = []

    for i in range(current_pos, len(vp_sequence)):
        candidate = vp_sequence[i]
        cur_type = 'peak' if str(candidate.get('type', '')).endswith('peak') else 'valley'

        if cur_type == expected_type:
            pairs_skipped = (i - current_pos) // 2
            if pairs_skipped <= current_skips_left:
                candidates_from_pos_6.append({
                    'i': i,
                    'index': candidate.get('index'),
                    'type': candidate.get('type'),
                    'value': candidate.get('value'),
                    'pairs_skipped': pairs_skipped,
                    'can_use': pairs_skipped <= current_skips_left
                })

    print(f"발견된 후보 수: {len(candidates_from_pos_6)}")
    for cand in candidates_from_pos_6:
        print(f"  i={cand['i']}, 인덱스={cand['index']}, 타입={cand['type']}, 값={cand['value']:,}, 스킵={cand['pairs_skipped']}, 사용가능={cand['can_use']}")

    # 첫 번째 유효한 후보
    if candidates_from_pos_6:
        first_candidate = candidates_from_pos_6[0]
        print(f"\n=== 첫 번째 후보 상세 정보 ===")
        print(f"선택될 후보: i={first_candidate['i']}, 인덱스={first_candidate['index']}")
        print(f"타입: {first_candidate['type']}, 값: {first_candidate['value']:,}")
        print(f"스킵 사용: {first_candidate['pairs_skipped']}")

        # 다음 상태 예측
        next_pos = first_candidate['i'] + 1
        next_skips_left = current_skips_left - first_candidate['pairs_skipped']
        next_points_count = current_points_count + 1

        print("
=== 다음 상태 예측 ===")
        print(f"다음 pos: {next_pos}")
        print(f"남은 스킵: {next_skips_left}")
        print(f"다음 포인트 수: {next_points_count}")

        next_expected_type = 'valley' if next_points_count % 2 == 0 else 'peak'
        print(f"다음에 찾을 타입: {next_expected_type}")

        # pos=6에서 선택 가능한 모든 조합 시뮬레이션
        print("
=== 가능한 모든 조합 시뮬레이션 ===")

        # 간단한 시뮬레이션: 첫 번째 선택 후 나머지 과정
        remaining_positions = []
        for i in range(next_pos, len(vp_sequence)):
            rem_candidate = vp_sequence[i]
            rem_type = 'peak' if str(rem_candidate.get('type', '')).endswith('peak') else 'valley'
            if rem_type == next_expected_type:
                remaining_positions.append((i, rem_candidate.get('index'), rem_candidate.get('type')))

        print(f"다음 단계에서 선택 가능한 후보들: {len(remaining_positions)}개")
        for i, (pos, idx, typ) in enumerate(remaining_positions[:3]):  # 처음 3개만
            print(f"  [{i+1}] pos={pos}, 인덱스={idx}, 타입={typ}")

def check_why_evaluation_failed():
    """
    왜 evaluate_candidate가 실패했는지 상세 분석
    """

    print("\n=== evaluate_candidate 실패 원인 상세 분석 ===")

    # 현재 매핑에서 각 포인트 확인
    time_ordered = list(reversed(points_so_far))

    p1 = time_ordered[0]  # P1
    v1 = time_ordered[1]  # V1
    p2 = time_ordered[2]  # P2
    v2 = time_ordered[3]  # V2
    p3 = time_ordered[4]  # P3
    v3 = time_ordered[5]  # V3

    print("IHS 매핑 확인:")
    print(f"  P1: {p1.get('index')} ({p1.get('value'):,})")
    print(f"  V1: {v1.get('index')} ({v1.get('value'):,})")
    print(f"  P2: {p2.get('index')} ({p2.get('value'):,})")
    print(f"  V2: {v2.get('index')} ({v2.get('value'):,})")
    print(f"  P3: {p3.get('index')} ({p3.get('value'):,})")
    print(f"  V3: {v3.get('index')} ({v3.get('value'):,})")

    # 각 검증 단계별 확인
    print("\n=== 단계별 검증 ===")

    # 1. 기본 조건: P3 < P2
    basic_condition = p3.get('value') < p2.get('value')
    print(f"1. 기본조건 (P3 < P2): {basic_condition}")
    if not basic_condition:
        print(f"   P3({p3.get('value'):,}) >= P2({p2.get('value'):,})")

    # 2. 균형 규칙
    l_mid = 0.5 * (p1.get('value') + v2.get('value'))
    r_mid = 0.5 * (p3.get('value') + v3.get('value'))
    balance_condition = p1.get('value') >= r_mid and p3.get('value') >= l_mid

    print("2. 균형규칙:")
    print(f"   L_mid = 0.5 * ({p1.get('value'):,} + {v2.get('value'):,}) = {l_mid:,.0f}")
    print(f"   R_mid = 0.5 * ({p3.get('value'):,} + {v3.get('value'):,}) = {r_mid:,.0f}")
    print(f"   P1 >= R_mid: {p1.get('value'):,} >= {r_mid:,.0f} = {p1.get('value') >= r_mid}")
    print(f"   P3 >= L_mid: {p3.get('value'):,} >= {l_mid:,.0f} = {p3.get('value') >= l_mid}")
    print(f"   균형조건 통과: {balance_condition}")

    # 3. 대칭 규칙
    try:
        p1_ts = p1.get('actual_date')
        p2_ts = p2.get('actual_date')
        p3_ts = p3.get('actual_date')

        if p1_ts and p2_ts and p3_ts:
            l_time = (p2_ts - p1_ts).total_seconds()
            r_time = (p3_ts - p2_ts).total_seconds()

            print("3. 대칭규칙:")
            print(f"   L_time = {l_time:,}초 ({p2_ts} - {p1_ts})")
            print(f"   R_time = {r_time:,}초 ({p3_ts} - {p2_ts})")

            symmetry_condition = (l_time > 0 and r_time > 0 and
                                r_time <= 2.5 * l_time and l_time <= 2.5 * r_time)

            print(f"   L_time > 0: {l_time > 0}")
            print(f"   R_time > 0: {r_time > 0}")
            print(f"   R_time <= 2.5 * L_time: {r_time} <= {2.5 * l_time} = {r_time <= 2.5 * l_time}")
            print(f"   L_time <= 2.5 * R_time: {l_time} <= {2.5 * r_time} = {l_time <= 2.5 * r_time}")
            print(f"   대칭조건 통과: {symmetry_condition}")

            if l_time > 0 and r_time > 0:
                ratio = l_time / r_time if r_time > 0 else 0
                print(f"   시간 비율 (L/R): {ratio:.2f}")
        else:
            print("3. 대칭규칙: 날짜 정보 부족")
    except Exception as e:
        print(f"3. 대칭규칙: 오류 - {e}")

if __name__ == "__main__":
    prepare_next_step()
    check_why_evaluation_failed()
