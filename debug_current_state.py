#!/usr/bin/env python3
"""
현재 디버깅 상태에서 상세 정보를 출력하는 스크립트
"""

def analyze_current_state():
    """
    현재 상태 분석 및 다음 단계 예측
    """

    print("=== 현재 상태 분석 ===")

    # 1. 현재 포인트들의 시간순 분석
    points_analysis = []
    for i, point in enumerate(points_so_far):
        points_analysis.append({
            'index': i,
            'actual_index': point.get('index'),
            'type': point.get('type'),
            'value': point.get('value'),
            'date': point.get('actual_date')
        })

    print("시간순 포인트 분석:")
    for pa in points_analysis:
        print(f"  [{pa['index']}] 인덱스 {pa['actual_index']} ({pa['type']}) - 값: {pa['value']:,} - 날짜: {pa['date']}")

    # 2. IHS 패턴 조건 확인
    print("\n=== IHS 패턴 조건 확인 ===")

    # 매핑 결과에서 각 포인트 추출
    p1 = next(p for p in points_so_far if p.get('index') == 71)  # P1
    v1 = next(p for p in points_so_far if p.get('index') == 73)  # V1
    p2 = next(p for p in points_so_far if p.get('index') == 83)  # P2
    v2 = next(p for p in points_so_far if p.get('index') == 95)  # V2
    p3 = next(p for p in points_so_far if p.get('index') == 97)  # P3
    v3 = next(p for p in points_so_far if p.get('index') == 104) # V3

    print("IHS 패턴 포인트:")
    print(f"  P1 (왼쪽 어깨): 인덱스 {p1.get('index')}, 값 {p1.get('value'):,}")
    print(f"  V1 (왼쪽 겨드랑이): 인덱스 {v1.get('index')}, 값 {v1.get('value'):,}")
    print(f"  P2 (머리): 인덱스 {p2.get('index')}, 값 {p2.get('value'):,}")
    print(f"  V2 (오른쪽 겨드랑이): 인덱스 {v2.get('index')}, 값 {v2.get('value'):,}")
    print(f"  P3 (오른쪽 어깨): 인덱스 {p3.get('index')}, 값 {p3.get('value'):,}")
    print(f"  V3 (가장 최근 저점): 인덱스 {v3.get('index')}, 값 {v3.get('value'):,}")

    # 3. 패턴 검증 실패 원인 추정
    print("\n=== 패턴 검증 실패 원인 추정 ===")

    # 기본 조건: P3 < P2 (오른쪽 어깨 < 머리)
    if p3.get('value') >= p2.get('value'):
        print(f"❌ 기본조건 실패: P3({p3.get('value'):,}) >= P2({p2.get('value'):,})")

    # 균형 규칙: l_mid = 0.5*(P1 + V2), r_mid = 0.5*(P3 + V3)
    l_mid = 0.5 * (p1.get('value') + v2.get('value'))
    r_mid = 0.5 * (p3.get('value') + v3.get('value'))
    print(f"균형 계산: L_mid = 0.5*({p1.get('value'):,} + {v2.get('value'):,}) = {l_mid:,.0f}")
    print(f"         R_mid = 0.5*({p3.get('value'):,} + {v3.get('value'):,}) = {r_mid:,.0f}")

    if p1.get('value') < r_mid:
        print(f"❌ 균형규칙 실패: P1({p1.get('value'):,}) < R_mid({r_mid:,.0f})")
    if p3.get('value') < l_mid:
        print(f"❌ 균형규칙 실패: P3({p3.get('value'):,}) < L_mid({l_mid:,.0f})")

    # 대칭 규칙: 시간 비율
    try:
        p1_ts = p1.get('actual_date')
        p2_ts = p2.get('actual_date')
        p3_ts = p3.get('actual_date')

        if p1_ts and p2_ts and p3_ts:
            l_time = (p2_ts - p1_ts).total_seconds()
            r_time = (p3_ts - p2_ts).total_seconds()
            print(f"시간 계산: L_time = {l_time:,}초, R_time = {r_time:,}초")

            if l_time <= 0 or r_time <= 0:
                print("❌ 대칭규칙 실패: 시간 차이가 0 이하")
            elif r_time > 2.5 * l_time:
                print(f"❌ 대칭규칙 실패: R_time({r_time:,}) > 2.5 * L_time({l_time:,})")
            elif l_time > 2.5 * r_time:
                print(f"❌ 대칭규칙 실패: L_time({l_time:,}) > 2.5 * R_time({r_time:,})")
            else:
                print(f"✅ 대칭규칙 통과: {l_time/r_time:.2f} 배율")
    except Exception as e:
        print(f"시간 계산 오류: {e}")

    # 4. 다음 단계 예측
    print("\n=== 다음 단계 예측 ===")
    print(f"현재 위치 (pos): {pos}")
    print(f"남은 스킵 가능 횟수: {skips_left}")
    print(f"VP 시퀀스에서 탐색할 위치들: {pos} ~ {len(vp_sequence)-1}")

    # 다음에 탐색할 후보들 확인
    next_positions = []
    for i in range(pos, len(vp_sequence)):
        candidate = vp_sequence[i]
        cur_type = 'peak' if str(candidate.get('type', '')).endswith('peak') else 'valley'
        expected_type = 'peak'  # IHS 모드, len(points_so_far)=6이므로 홀수 → peak
        if cur_type == expected_type:
            pairs_skipped = (i - pos) // 2
            if pairs_skipped <= skips_left:
                next_positions.append((i, candidate.get('index'), candidate.get('type'), pairs_skipped))

    print(f"다음 탐색 후보들 (총 {len(next_positions)}개):")
    for np in next_positions[:5]:  # 처음 5개만 표시
        i, idx, typ, skipped = np
        print(f"  i={i}, 인덱스={idx}, 타입={typ}, 스킵={skipped}")

    if len(next_positions) > 5:
        print(f"  ... 그리고 {len(next_positions) - 5}개 더")

if __name__ == "__main__":
    analyze_current_state()
