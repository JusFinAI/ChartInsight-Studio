## ChartInsight Studio 개발 상세 진행 보고서
작성일 : 2025-08-17
### 📋 **개발 목표 및 범위**
- **목표**: `_temp_integration/DTDB_Pattern_Analysis_Dashboard_V03/analysis_engine.py`의 분석 로직을 FastAPI 백엔드에 통합하고, Next.js 프론트엔드에서 Plotly로 시각화
- **범위**: Trend Detection (Peak/Valley, ZigZag, Trend Periods) + Pattern Recognition (DT, DB, H&S, IHS)
- **아키텍처**: Docker Compose 기반 멀티 컨테이너 (Backend, Frontend, PostgreSQL, Airflow)

---

### 🔧 **백엔드 개발 완료 사항**

#### 1. **분석 엔진 통합 (`backend/app/analysis/engine.py`)**
- **소스**: `_temp_integration/DTDB_Pattern_Analysis_Dashboard_V03/analysis_engine.py`에서 복사
- **제거된 의존성**: `yfinance`, `dash`, 파일 기반 로깅
- **통합된 클래스들**:
  ```python
  class TrendDetector  # Peak/Valley 감지
  class PatternDetector  # 기본 패턴 감지기
  class DTDetector(PatternDetector)  # Double Top
  class DBDetector(PatternDetector)  # Double Bottom  
  class HSDetector(PatternDetector)  # Head & Shoulders
  class IHSDetector(PatternDetector)  # Inverse H&S
  class PatternManager  # 패턴 관리자
  ```
- **핵심 함수**: `run_full_analysis(df)` - 470라인 구현

#### 2. **ZigZag 포인트 Enrichment 로직**
- **문제**: 기존 `TrendDetector`가 `type`, OHLC 데이터 미포함
- **해결**: 141-154라인에서 수동 enrichment
  ```python
  # Enrich zigzag_points with type and OHLC data
  for point in detector.zigzag_points:
      candle = df[df.index == point['date']].iloc[0]
      point['type'] = 'js_peak' if point in detector.js_peaks else 'js_valley'
      point['open'] = float(candle['open'])
      # ... high, low, close
  ```

#### 3. **PatternManager 통합 및 중복 제거**
- **문제**: `AttributeError: 'TrendDetector' object has no attribute 'newly_registered_peak'`
- **해결**: 294-316라인에서 수동 새 extremum 감지
  ```python
  # Detect new extremums manually
  prev_peaks_count = len(detector.js_peaks)
  prev_valleys_count = len(detector.js_valleys)
  # ... process_candle ...
  if len(detector.js_peaks) > prev_peaks_count:
      new_peak = detector.js_peaks[-1]
  ```
- **중복 제거**: 381-403라인에서 동일 패턴 필터링

#### 4. **API 스키마 정의 (`backend/app/schemas/analysis.py`)**
```python
class ExtremumPoint(BaseModel):
    date: str
    value: float
    type: str
    open: float
    high: float
    low: float
    close: float

class FullAnalysisResponse(BaseModel):
    zigzag_points: List[ExtremumPoint]
    trend_periods: List[TrendPeriod]
    patterns: List[DetectedPattern]
    patterns_summary: PatternsSummary
    patterns_breakdown: PatternsBreakdown
```

#### 5. **API 엔드포인트 (`backend/app/routers/pattern_analysis.py`)**
- **엔드포인트**: `GET /api/v1/pattern-analysis/analysis/full-report`
- **파라미터**: `stock_code`, `timeframe`
- **응답 매핑**: 1290-1321라인에서 engine 결과를 스키마로 변환

---

### 🎨 **프론트엔드 개발 완료 사항**

#### 1. **API 서비스 레이어 (`frontend/src/services/api.ts`)**
- **인터페이스 정의**: `ExtremumPoint`, `TrendPeriod`, `DetectedPattern` (라인 680-720)
- **API 함수**: `fetchFullAnalysisReport()` (라인 730-761)

#### 2. **메인 페이지 컴포넌트 (`frontend/src/app/trading-lab/trading-radar/page.tsx`)**
- **상태 관리**: `analysisData` useState 추가 (라인 45)
- **데이터 로딩**: `loadData()` 함수에서 `fetchFullAnalysisReport()` 호출 (라인 115-130)
- **UI 개선**: 
  - 차트 타입 선택 라디오 버튼 제거 (라인 700-730 삭제)
  - 패턴 유형별 체크박스 추가 (라인 800-870)
  ```tsx
  <div className="space-y-2">
    <label className="flex items-center">
      <input type="checkbox" checked={showHS} onChange={(e) => setShowHS(e.target.checked)} />
      <span className="ml-2">H&S / Inverse H&S</span>
    </label>
    // ... DB/DT 체크박스
  </div>
  ```

#### 3. **차트 컴포넌트 (`frontend/src/components/ui/Chart.tsx`)**

##### A. **ZigZag 라인 구현 (완료)**
- **위치**: 140-165라인 `plotData` useMemo
- **방식**: zigzagPoints 배열을 scatter trace로 변환
```tsx
if (zigzagPoints && zigzagPoints.length > 1) {
  traces.push({
    x: zigzagPoints.map(point => point.date),
    y: zigzagPoints.map(point => point.value),
    type: 'scatter',
    mode: 'lines+markers',
    name: 'ZigZag',
    line: { color: isDarkMode ? '#10B981' : '#059669', width: 1.5 }
  });
}
```

##### B. **트렌드 배경 구현 (완료)**
- **위치**: 250-290라인 `layout` useMemo
- **방식**: trendPeriods를 rect shapes로 변환
```tsx
if (trendPeriods && trendPeriods.length > 0) {
  const trendShapes = trendPeriods.map(period => ({
    type: 'rect',
    x0: period.start_date,
    x1: period.end_date,
    fillcolor: period.trend === 'uptrend' ? 'rgba(34, 197, 94, 0.1)' : 
               period.trend === 'downtrend' ? 'rgba(239, 68, 68, 0.1)' : 
               'rgba(156, 163, 175, 0.05)'
  }));
}
```

##### C. **테마 감지 및 색상 조정 (완료)**
- **위치**: 50-55라인
```tsx
const isDarkMode = useMemo(() => {
  if (typeof window === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}, []);
```

##### D. **패턴 시각화 구현 (문제 있음)**
- **의도**: 사각형 밴드 + 얇은 넥라인 (패턴 구간 내부만)
- **현재 구현**: 330-410라인
  ```tsx
  // Pattern bands (rectangles)
  const patternShapes = patterns.map(pattern => ({
    type: 'rect',
    x0: pattern.start_date,
    x1: pattern.end_date,
    y0: Math.min(pattern.meta.neckline - bandHeight, minPrice),
    y1: Math.max(pattern.meta.neckline + bandHeight, maxPrice),
    fillcolor: `rgba(255, 193, 7, 0.15)`,
    line: { width: 0 }
  }));

  // Pattern necklines (thin lines within pattern period only)
  const necklineTraces = patterns.map(pattern => ({
    x: [pattern.start_date, pattern.end_date],
    y: [pattern.meta.neckline, pattern.meta.neckline],
    type: 'scatter',
    mode: 'lines',
    name: `${pattern.type} Neckline`,
    line: { color: isDarkMode ? '#F59E0B' : '#D97706', width: 1, dash: 'solid' }
  }));
  ```

---

### 🎯 **CSS 및 스타일링 개선**

#### 1. **Plotly Modebar 문제 해결 (`frontend/src/app/globals.css`)**
- **문제들**: 회색 배경, 세로 배치, 범례와 겹침, 위치 이상
- **해결**: 100-115라인
```css
.js-plotly-plot .modebar-container,
.js-plotly-plot .modebar {
  position: absolute !important;
  top: 6px !important;
  right: 10px !important;
  z-index: 50 !important;
  background: transparent !important;
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  gap: 4px !important;
}
```

#### 2. **범례 위치 조정**
- **Chart.tsx 360-365라인**: 범례를 하단으로 이동, 마진 조정

---

### 📊 **데이터 검증 및 디버깅**

#### 1. **API 응답 구조 검증**
```bash
# 성공적인 API 호출 확인
curl -s "http://localhost:8000/api/v1/pattern-analysis/analysis/full-report?stock_code=005930&timeframe=1d" | jq '{zigzag:(.zigzag_points|length), periods:(.trend_periods|length), total_patterns:(.patterns|length)}'
# 결과: {"zigzag": 85, "periods": 8, "total_patterns": 5}
```

#### 2. **중복 패턴 확인**
```bash
# 중복 패턴 검증
curl -s "..." | jq '[.patterns_breakdown.completed_hs[] | {start:(.meta.P1.date // .meta.V1.date), end:.date, neck:.meta.neckline}] | map({key: "\(.start)|\(.end)|\(.neck)"}) | group_by(.key) | map({key: .[0].key, count: length})'
# 결과: [{"key": "2023-12-11T15:00:00Z|2025-08-05T15:00:00Z|71600.0", "count": 5}]
```

#### 3. **브라우저 디버깅 스크립트 제작**
```javascript
// 넥라인 traces 확인
(() => {
  const gd = document.querySelector('.js-plotly-plot');
  const necks = (gd.data || []).filter(t => (t.name || '').includes('Neckline'));
  return necks.map(t => ({ name: t.name, x: t.x, y: t.y, lengthOK: Array.isArray(t.x) && t.x.length === 2 }));
})();

// 수평 shapes 확인  
(() => {
  const gd = document.querySelector('.js-plotly-plot');
  const shapes = (gd.layout?.shapes || []);
  return shapes.filter(s => s?.y0 === s?.y1).map(s => ({x0: s.x0, x1: s.x1, y: s.y0, dash: s.line?.dash}));
})();
```

---

### ❌ **현재 미해결 문제들**

#### 1. **패턴 시각화 핵심 문제**
- **증상**: "사각형 밴드와 얇은 넥라인 자체가 전혀 표시가 안되고 있고 토글하면 점선만 표시되고 있어"
- **디버깅 결과**: 
  - `necks.length = 0` (넥라인 traces 없음)
  - `shapeHoriz.length = 5` (수평 shapes는 존재하지만 전체 차트 범위로 확장)
- **의심 원인**:
  1. `showPatternNecklines` 토글과 패턴 렌더링 로직 연결 문제
  2. Plotly shapes vs traces 렌더링 우선순위 문제
  3. 색상/투명도로 인한 시각적 구별 불가

#### 2. **백엔드 중복 패턴 생성**
- **문제**: 동일한 패턴이 5개씩 생성됨
- **위치**: `PatternManager` 클래스의 completion 로직
- **영향**: 프론트엔드에서 중복 시각화 요소 생성

#### 3. **DB 컨테이너 누락**
- **문제**: `docker ps` 결과에 PostgreSQL 컨테이너들 없음
- **누락**: `postgres-tradesmart`, `postgres-airflow`
- **원인**: `docker compose --profile app down` 시 DB 컨테이너까지 종료

---

### 🔄 **시도했으나 실패한 해결 방법들**

#### 1. **패턴 시각화 문제**
1. **Layout shapes → Scatter traces 변환**: 동적으로 shapes를 traces로 변환했으나 효과 없음
2. **중복 제거 스크립트**: 브라우저에서 수동 중복 제거했으나 근본 해결 안됨
3. **색상/선 스타일 조정**: 다양한 색상과 dash 스타일 시도했으나 가시성 개선 안됨
4. **Plotly 레이아웃 조정**: 마진, z-index, 렌더링 순서 조정했으나 해결 안됨

#### 2. **백엔드 중복 문제**
1. **Deduplication 로직 추가**: `PatternManager`에 중복 방지 로직 추가했으나 여전히 중복 생성
2. **완료 조건 수정**: 패턴 완료 조건을 엄격하게 했으나 근본 원인 해결 안됨

---

### 📈 **개발 진행률**

| 영역 | 완료율 | 상태 |
|------|--------|------|
| 백엔드 분석 엔진 | 85% | 중복 패턴 생성 문제 외 완료 |
| API 엔드포인트 | 100% | 완료 |
| ZigZag 시각화 | 100% | 완료 |
| 트렌드 배경 | 100% | 완료 |
| 패턴 시각화 | 30% | 심각한 렌더링 문제 |
| UI/UX 개선 | 90% | Modebar 문제 해결 |
| 패턴 리스트 | 0% | 더미 데이터 사용 중 |

**전체 진행률: 약 75%**

가장 큰 블로커는 **패턴 시각화 렌더링 문제**로, 이 부분이 해결되어야 프로젝트 완성도가 크게 향상될 것입니다.