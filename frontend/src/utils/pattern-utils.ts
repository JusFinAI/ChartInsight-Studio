/**
 * 패턴 타입에 따른 색상 클래스를 반환합니다.
 * @param patternType 패턴 타입
 * @returns CSS 클래스명
 */
export function getPatternColor(patternType: string): string {
  switch (patternType) {
    case 'doubleTop':
    case 'headAndShoulders':
    case 'risingWedge':
    case 'bearishChannel':
    case 'bearishFlag':
    case 'bearishPennant':
      return 'bg-rose-500'; // 하락 패턴
    
    case 'doubleBottom':
    case 'inverseHeadAndShoulders':
    case 'fallingWedge':
    case 'bullishChannel':
    case 'bullishFlag':
    case 'bullishPennant':
      return 'bg-emerald-500'; // 상승 패턴
    
    case 'triangle':
    case 'symmetricTriangle':
    case 'ascendingTriangle':
    case 'descendingTriangle':
    case 'rectangle':
      return 'bg-amber-500'; // 중립 패턴 (방향성 불분명)
    
    default:
      return 'bg-blue-500'; // 기본 색상
  }
}

/**
 * 패턴 타입에 따른 설명을 반환합니다.
 * @param patternType 패턴 타입
 * @returns 패턴 설명
 */
export function getPatternDescription(patternType: string): string {
  switch (patternType) {
    case 'doubleTop':
      return '하락 반전 패턴으로, 두 번의 고점 형성 후 지지선 붕괴';
    
    case 'doubleBottom':
      return '상승 반전 패턴으로, 두 번의 저점 형성 후 저항선 돌파';
    
    case 'headAndShoulders':
      return '하락 반전 패턴으로, 좌측 어깨-머리-우측 어깨 형태의 구조';
    
    case 'inverseHeadAndShoulders':
      return '상승 반전 패턴으로, 좌측 어깨-머리-우측 어깨의 역형태';
    
    case 'triangle':
      return '통합 패턴으로, 가격이 점점 좁아지는 삼각형 형태';
    
    case 'symmetricTriangle':
      return '통합 패턴으로, 고점은 하락하고 저점은 상승하는 대칭 삼각형';
    
    case 'ascendingTriangle':
      return '상승 지속 패턴으로, 수평 저항선과 상승하는 지지선 형성';
    
    case 'descendingTriangle':
      return '하락 지속 패턴으로, 수평 지지선과 하락하는 저항선 형성';
    
    case 'risingWedge':
      return '하락 반전 패턴으로, 상승하는 지지선과 저항선이 수렴';
    
    case 'fallingWedge':
      return '상승 반전 패턴으로, 하락하는 지지선과 저항선이 수렴';
    
    case 'rectangle':
      return '통합 패턴으로, 가격이 수평 지지선과 저항선 사이에서 움직임';
    
    case 'bullishChannel':
      return '상승 지속 패턴으로, 가격이 평행한 상승 추세선 사이에서 움직임';
    
    case 'bearishChannel':
      return '하락 지속 패턴으로, 가격이 평행한 하락 추세선 사이에서 움직임';
    
    case 'bullishFlag':
      return '상승 지속 패턴으로, 급등 후 단기 하락 조정';
    
    case 'bearishFlag':
      return '하락 지속 패턴으로, 급락 후 단기 상승 조정';
    
    case 'bullishPennant':
      return '상승 지속 패턴으로, 급등 후 삼각형 형태의 통합';
    
    case 'bearishPennant':
      return '하락 지속 패턴으로, 급락 후 삼각형 형태의 통합';
    
    default:
      return '가격 패턴';
  }
} 