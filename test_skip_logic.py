#!/usr/bin/env python3
"""
_find_hs_ihs_structural_points 함수의 skip 로직을 테스트하는 스크립트
"""

def test_skip_logic():
    # 사용자의 예시: vp_sequence = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11]
    # 여기서는 간단하게 0-9 인덱스로 표현 (0이 가장 최근, 9가 가장 과거)
    vp_sequence = list(range(10))  # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    print(f"VP 시퀀스 (최신부터 과거순): {vp_sequence}")
    print("IHS 패턴의 경우:")
    print("  0(V3) -> 1(P3) -> 2(V2) -> 3(P2) -> 4(V1) -> 5(P1)")

    def find_pattern_combinations(pos: int, points_so_far: list, skips_left: int, max_skip: int = 2, pattern_type='IHS'):
        """
        실제 코드의 find_pattern_combinations 로직을 그대로 구현
        """
        candidates = []

        def inner_find_pattern_combinations(pos: int, points_so_far: list, skips_left: int):
            # 6포인트 완성 시 평가 및 저장
            if len(points_so_far) == 6:
                time_ordered = list(reversed(points_so_far))  # 역순으로 시간순 정렬
                candidates.append(time_ordered.copy())
                return

            # 다음에 찾아야 할 극점의 타입 결정
            if pattern_type == 'HS':
                expected_type = 'peak' if len(points_so_far) % 2 == 0 else 'valley'
            else:  # IHS
                expected_type = 'valley' if len(points_so_far) % 2 == 0 else 'peak'

            # pos 위치부터 시작하여 다음 후보를 찾는다
            for i in range(pos, len(vp_sequence)):
                candidate_point = vp_sequence[i]
                # 실제 코드에서는 candidate_point.get('type')을 확인하지만,
                # 여기서는 단순화를 위해 i % 2로 peak/valley 결정
                # 주의: 실제 코드에서는 vp_sequence의 각 요소가 실제 극점 객체
                cur_type = 'peak' if i % 2 == 0 else 'valley'

                if cur_type == expected_type:
                    # 건너뛴 V-P 쌍의 개수 계산
                    pairs_skipped = (i - pos) // 2

                    if pairs_skipped <= skips_left:
                        # 이 후보를 선택하고 다음 단계로 진행
                        new_points = points_so_far + [candidate_point]
                        inner_find_pattern_combinations(i + 1, new_points, skips_left - pairs_skipped)

        # 가장 최신 극점부터 탐색 시작
        inner_find_pattern_combinations(0, [], max_skip)
        return candidates

    # skip=0, 1, 2에 대해 결과 확인
    for max_skip in [0, 1, 2]:
        print(f"\n=== max_skip={max_skip} ===")
        candidates = find_pattern_combinations(0, [], 0, max_skip, 'IHS')
        print(f"발견된 조합 수: {len(candidates)}")
        for i, candidate in enumerate(candidates):
            print(f"  조합 {i+1}: {candidate}")
            print(f"    매핑: V3={candidate[0]}, P3={candidate[1]}, V2={candidate[2]}, P2={candidate[3]}, V1={candidate[4]}, P1={candidate[5]}")

if __name__ == "__main__":
    test_skip_logic()
