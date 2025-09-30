#!/usr/bin/env python3
"""
향상된 패턴 분석 디버깅 코드 (날짜 기준 포인트 표시)
"""

def analyze_pattern_attempts():
    """
    모든 시도된 패턴 조합을 날짜 기준으로 분석
    """

    # 모든 시도된 조합들 확인
    all_attempts = manager.get_debug_attempts()
    print(f"총 시도된 조합 수: {len(all_attempts)}")

    if not all_attempts:
        print("아직 시도된 조합이 없습니다.")
        return

    # 성공한 조합들만 필터링
    successful_attempts = [attempt for attempt in all_attempts if attempt['eval_result']]
    print(f"성공한 조합 수: {len(successful_attempts)}")

    # 실패한 조합들만 필터링
    failed_attempts = [attempt for attempt in all_attempts if not attempt['eval_result']]
    print(f"실패한 조합 수: {len(failed_attempts)}")

    # 모든 조합을 시간순으로 정렬 (최신 패턴이 먼저 오도록)
    sorted_attempts = sorted(all_attempts, key=lambda x: x['time_ordered'][0].get('actual_date', pd.Timestamp('1900-01-01')), reverse=True)

    print("\n=== 시간순으로 정렬된 모든 조합 (처음 15개) ===")
    for i, attempt in enumerate(sorted_attempts[:15]):
        points = attempt['time_ordered']
        first_date = points[0].get('actual_date', 'N/A')
        last_date = points[-1].get('actual_date', 'N/A')
        result = '✅' if attempt['eval_result'] else '❌'

        # 날짜를 YYYY-MM-DD 형식으로 변환
        if isinstance(first_date, pd.Timestamp):
            first_date_str = first_date.strftime('%Y-%m-%d')
        else:
            first_date_str = str(first_date)

        if isinstance(last_date, pd.Timestamp):
            last_date_str = last_date.strftime('%Y-%m-%d')
        else:
            last_date_str = str(last_date)

        print(f"[{i+1}] {result} {first_date_str} ~ {last_date_str}")
        print(f"    패턴: {attempt['mapping'].get('pattern_type', 'N/A')}")

        # 포인트들을 날짜와 타입으로 상세 표시
        points_detail = []
        for p in points:
            date = p.get('actual_date', 'N/A')
            type_str = p.get('type', 'N/A')
            if isinstance(date, pd.Timestamp):
                date_str = date.strftime('%m%d')
            else:
                date_str = str(date)
            points_detail.append(f"{type_str}({date_str})")

        print(f"    포인트: {', '.join(points_detail)}")
        print(f"    위치: pos={attempt['pos']}, 스킵={attempt['skips_left']}")

        # 오류 정보 (실패한 경우)
        if 'error' in attempt:
            print(f"    오류: {attempt['error']}")

    # 성공한 조합들만 별도로 분석
    if successful_attempts:
        print("
=== 성공한 조합들만 상세 분석 ===")
        for i, attempt in enumerate(successful_attempts[:5]):  # 처음 5개만
            points = attempt['time_ordered']
            print(f"\n성공 조합 {i+1}:")
            print(f"  기간: {points[0].get('actual_date', 'N/A')} ~ {points[-1].get('actual_date', 'N/A')}")
            print(f"  포인트 수: {len(points)}")

            # 각 포인트의 상세 정보
            for j, p in enumerate(points):
                date = p.get('actual_date', 'N/A')
                if isinstance(date, pd.Timestamp):
                    date_str = date.strftime('%Y-%m-%d %H:%M')
                else:
                    date_str = str(date)

                print(f"    [{j}] {p.get('type', 'N/A')}: 값={p.get('value'):,}, 날짜={date_str}")

    # 차트 시각화용 데이터 준비
    chart_data = []
    for attempt in all_attempts:
        points = attempt['time_ordered']
        chart_data.append({
            'pattern_type': attempt['mapping']['pattern_type'],
            'eval_result': attempt['eval_result'],
            'start_date': points[0].get('actual_date'),
            'end_date': points[-1].get('actual_date'),
            'points': points,
            'pos': attempt['pos'],
            'skips_used': 2 - attempt['skips_left']
        })

    print(f"\n차트 시각화용 데이터 준비 완료: {len(chart_data)}개 조합")

    return chart_data

if __name__ == "__main__":
    import pandas as pd
    # 이 스크립트는 디버깅 콘솔에서 직접 실행하거나,
    # run_full_analysis.py의 디버깅 중간에 호출할 수 있습니다.

    # 사용법:
    # 1. 디버깅 콘솔에서: exec(open('debug_patterns_analysis.py').read())
    # 2. 또는: chart_data = analyze_pattern_attempts()

    print("디버깅 코드가 로드되었습니다.")
    print("디버깅 콘솔에서 analyze_pattern_attempts() 함수를 호출하세요.")
