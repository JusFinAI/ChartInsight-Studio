#!/usr/bin/env python3
"""
_find_hs_ihs_structural_points 함수의 리턴값 확인
"""

def check_structural_points_return():
    """
    _find_hs_ihs_structural_points 함수의 실제 리턴값 확인
    """

    print("=== _find_hs_ihs_structural_points 함수 리턴값 확인 ===")

    # 함수가 리턴하는 값들 확인
    print("함수 시그니처:")
    print("def _find_hs_ihs_structural_points(all_extremums, ...):")
    print("    return candidates, all_attempts")

    print("\n함수 내부 변수들:")
    print("- candidates: 검증 통과한 조합들 (List[Dict])")
    print("- all_attempts: 모든 시도된 조합들 (List[Dict])")
    print("- structural_points_list: ❌ 존재하지 않는 변수")

    # 사용자가 본 (5, 0), (7, 1), (9, 2) 형태의 데이터는 어디서 왔을까?
    print("\n=== 사용자가 본 데이터 분석 ===")
    print("사용자가 본: [(5, 0), (7, 1), (9, 2)]")

    # 이것이 어디서 왔는지 추정
    print("가능한 출처:")
    print("1. vp_sequence의 인덱스들")
    print("2. 디버깅 콘솔에서 잘못된 변수 출력")
    print("3. 백트래킹 중간 결과")

    # 실제로는 함수가 candidates, all_attempts를 리턴
    print("\n=== 올바른 리턴값 확인 ===")

    # 실제 candidates 확인
    try:
        # check_for_hs_ihs_start에서 호출된 결과 확인
        if hasattr(manager, '_debug_all_attempts'):
            debug_attempts = manager._debug_all_attempts
            print(f"저장된 시도 횟수: {len(debug_attempts)}")

            successful = [a for a in debug_attempts if a['eval_result']]
            print(f"성공한 조합 수: {len(successful)}")

            if successful:
                print("첫 번째 성공 조합:")
                first = successful[0]
                print(f"  패턴: {first['mapping']['pattern_type']}")
                print(f"  포인트: {[p.get('index') for p in first['time_ordered']]}")
    except:
        print("디버깅 정보 확인 불가")

if __name__ == "__main__":
    import pandas as pd

    print("함수 리턴값 분석을 시작합니다...")
    check_structural_points_return()
