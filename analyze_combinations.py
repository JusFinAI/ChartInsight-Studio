#!/usr/bin/env python3
"""
백트래킹 알고리즘의 가능한 조합 수 분석
"""

def analyze_possible_combinations():
    """
    현재 VP 시퀀스에서 이론적으로 가능한 모든 조합 수 계산
    """

    # 현재 VP 시퀀스 정보
    all_attempts = manager.get_debug_attempts()
    if not all_attempts:
        print("아직 시도된 조합이 없습니다.")
        return

    # 첫 번째 시도의 VP 시퀀스 길이 확인
    first_attempt = all_attempts[0]
    vp_sequence_length = len(vp_sequence)  # 실제로는 points_so_far에서 확인해야 함

    print("=== VP 시퀀스 분석 ===")
    print(f"VP 시퀀스 길이: {len(vp_sequence)}")

    # 각 위치의 타입 확인
    print("\nVP 시퀀스 상세:")
    for i, vp in enumerate(vp_sequence):
        print(f"  [{i}] 인덱스={vp.get('index')}, 타입={vp.get('type')}, 값={vp.get('value')","}")

    # IHS 패턴의 expected_type 결정 로직 시뮬레이션
    def get_expected_type(points_count, pattern_type='IHS'):
        """주어진 포인트 수에 대해 다음에 필요한 타입 반환"""
        if pattern_type == 'HS':
            return 'peak' if points_count % 2 == 0 else 'valley'
        else:  # IHS
            return 'valley' if points_count % 2 == 0 else 'peak'

    print("\n=== IHS 패턴 expected_type 시뮬레이션 ===")
    for count in range(7):  # 0~6 포인트까지
        expected = get_expected_type(count, 'IHS')
        print(f"포인트 {count}개일 때 다음 타입: {expected}")

    # 각 위치에서 선택 가능한 후보 수 계산
    print("\n=== 각 위치별 선택 가능 후보 수 ===")

    for pos in range(len(vp_sequence)):
        expected_type = get_expected_type(pos, 'IHS')

        candidates_at_pos = []
        for i in range(pos, len(vp_sequence)):
            candidate = vp_sequence[i]
            cur_type = 'peak' if str(candidate.get('type', '')).endswith('peak') else 'valley'

            if cur_type == expected_type:
                pairs_skipped = (i - pos) // 2
                if pairs_skipped <= 2:  # max_skip = 2
                    candidates_at_pos.append({
                        'i': i,
                        'index': candidate.get('index'),
                        'type': candidate.get('type'),
                        'pairs_skipped': pairs_skipped
                    })

        print(f"pos={pos}, expected_type={expected_type}, 선택가능후보={len(candidates_at_pos)}개")

        if len(candidates_at_pos) <= 5:  # 5개 이하면 모두 표시
            for cand in candidates_at_pos:
                print(f"    i={cand['i']}, 인덱스={cand['index']}, 스킵={cand['pairs_skipped']}")
        else:
            print("    (후보들이 많아 생략)")

def calculate_theoretical_max():
    """
    현재 VP 시퀀스에서 이론적으로 가능한 최대 조합 수 계산
    """

    print("\n=== 현재 VP 시퀀스 기반 이론적 최대 조합 수 ===")

    # 백트래킹의 각 단계별 선택지 수
    def count_combinations_at_step(step, remaining_skips):
        """특정 단계에서 가능한 조합 수 계산"""
        if step == 6:  # 6포인트 완성
            return 1

        expected_type = 'valley' if step % 2 == 0 else 'peak'  # IHS 모드

        total = 0
        for i in range(step, len(vp_sequence)):
            candidate = vp_sequence[i]
            cur_type = 'peak' if str(candidate.get('type', '')).endswith('peak') else 'valley'

            if cur_type == expected_type:
                pairs_skipped = (i - step) // 2
                if pairs_skipped <= remaining_skips:
                    # 이 후보를 선택하고 다음 단계로
                    remaining_for_next = remaining_skips - pairs_skipped
                    total += count_combinations_at_step(step + 1, remaining_for_next)

        return total

    # 각 스킵 수에 대해 계산
    for max_skips in [0, 1, 2]:
        theoretical_count = count_combinations_at_step(0, max_skips)
        print(f"max_skips={max_skips}: 이론적 최대 조합 수 = {theoretical_count:,}")

    print("\n=== VP 시퀀스 길이 영향 분석 ===")
    print(f"현재 VP 시퀀스 길이: {len(vp_sequence)}")

    # 각 위치별로 선택 가능한 후보 수를 더 자세히 분석
    print("\n각 단계별 선택지 분석:")
    for step in range(6):
        expected_type = 'valley' if step % 2 == 0 else 'peak'
        candidates = []

        for i in range(step, len(vp_sequence)):
            candidate = vp_sequence[i]
            cur_type = 'peak' if str(candidate.get('type', '')).endswith('peak') else 'valley'

            if cur_type == expected_type:
                pairs_skipped = (i - step) // 2
                if pairs_skipped <= 2:
                    candidates.append((i, pairs_skipped))

        print(f"Step {step} (expected: {expected_type}): {len(candidates)}개 후보")
        if len(candidates) <= 8:  # 8개 이하면 상세 표시
            for i, (pos, skips) in enumerate(candidates):
                print(f"    [{i+1}] pos={pos}, 스킵={skips}")

def analyze_vp_sequence_impact():
    """
    VP 시퀀스의 길이와 분포가 조합 수에 미치는 영향 분석
    """

    print("\n=== VP 시퀀스 특성 분석 ===")

    # 타입별 분포
    type_counts = {}
    for vp in vp_sequence:
        vp_type = vp.get('type', 'unknown')
        type_counts[vp_type] = type_counts.get(vp_type, 0) + 1

    print("VP 시퀀스 타입 분포:")
    for vp_type, count in type_counts.items():
        print(f"  {vp_type}: {count}개")

    # IHS 패턴에서 필요한 타입 시퀀스: V-P-V-P-V-P
    required_sequence = ['valley', 'peak', 'valley', 'peak', 'valley', 'peak']
    print("\nIHS 패턴 필요 시퀀스: V-P-V-P-V-P")
    print(f"현재 VP 시퀀스에서 각 타입의 위치:")

    for i, vp in enumerate(vp_sequence):
        vp_type = 'peak' if str(vp.get('type', '')).endswith('peak') else 'valley'
        required = required_sequence[i % 6] if i < 6 else 'N/A'
        match = "✅" if vp_type == required else "❌"
        print(f"  [{i}] {vp.get('index')} ({vp_type}) - 필요: {required} {match}")

    # 각 타입이 필요한 위치에 얼마나 있는지
    print("\n타입 분포 적절성:")
    for req_type in ['valley', 'peak']:
        positions = [i for i, vp in enumerate(vp_sequence)
                    if ('peak' if str(vp.get('type', '')).endswith('peak') else 'valley') == req_type]
        print(f"  {req_type} 위치들: {positions}")

def compare_with_different_lengths():
    """
    다른 길이의 VP 시퀀스에서 조합 수가 어떻게 변하는지 시뮬레이션
    """

    print("\n=== VP 시퀀스 길이 영향 시뮬레이션 ===")

    current_length = len(vp_sequence)

    # 간단한 시뮬레이션: 현재 타입 분포를 유지하면서 길이 변경
    type_pattern = []
    for vp in vp_sequence:
        vp_type = 'peak' if str(vp.get('type', '')).endswith('peak') else 'valley'
        type_pattern.append(vp_type)

    print(f"현재 타입 패턴: {type_pattern}")

    # 더 긴 시퀀스 시뮬레이션 (현재 패턴 반복)
    for sim_length in [current_length, current_length + 5, current_length + 10]:
        print(f"\n시뮬레이션 길이: {sim_length}")

        # 기본 백트래킹 카운팅 (간단 버전)
        def simple_count(step, remaining_skips, seq_length):
            if step == 6:
                return 1

            expected_type = 'valley' if step % 2 == 0 else 'peak'
            total = 0

            for i in range(step, min(step + 10, seq_length)):  # 최대 10개만 확인
                # 타입 패턴으로부터 예상
                pattern_idx = i % len(type_pattern)
                cur_type = type_pattern[pattern_idx]

                if cur_type == expected_type:
                    pairs_skipped = (i - step) // 2
                    if pairs_skipped <= remaining_skips:
                        total += simple_count(step + 1, remaining_skips - pairs_skipped, seq_length)

            return total

        for max_skips in [0, 1, 2]:
            count = simple_count(0, max_skips, sim_length)
            print(f"  max_skips={max_skips}: 약 {count:,}개")

    print("
결론: 조합 수는 VP 시퀀스의 길이와 타입 분포에 직접적으로 의존합니다.")

def show_current_restrictions():
    """
    현재 구현의 제한사항 확인
    """

    print("\n=== 현재 구현의 제한사항 ===")

    # 1. candidates 제한
    max_candidates = 10  # 하드코딩된 값
    print(f"max_candidates 제한: {max_candidates}개")

    # 2. 시간순 정렬 제한
    print("시간순 정렬: 최신 패턴 우선 (reverse=True)")

    # 3. 중복 제거
    print("중복 제거: 동일한 매핑은 한 번만 저장")

    # 4. VP 시퀀스 길이
    print(f"VP 시퀀스 길이: {len(vp_sequence)}개")

    print("\n=== 제한 완화 시나리오 ===")
    print("1. max_candidates = 1000으로 증가")
    print("2. 모든 조합 저장 (중복 포함)")
    print("3. 시간순 정렬 제거")
    print("4. 더 긴 VP 시퀀스 사용")

if __name__ == "__main__":
    import pandas as pd

    print("백트래킹 조합 분석을 시작합니다...")
    analyze_possible_combinations()
    calculate_theoretical_max()
    show_current_restrictions()
