# 점수 이력 차트 동기화 + 분석 상세 트렌드 차트 — 설계 문서

**날짜:** 2026-04-12  
**상태:** 완료

---

## 배경 및 목적

1. **repo_detail 차트-필터 불일치**: 이력 페이지의 Chart.js 차트가 SSR 시점에 전체 100건으로 고정 렌더링되어, 사용자가 등급·날짜·검색·점수범위 필터를 적용해도 차트가 갱신되지 않는 문제.
2. **analysis_detail 점수 맥락 부재**: 분석 상세 페이지에서 해당 분석이 전체 흐름에서 어떤 위치인지(상승 중인지, 하락 중인지) 파악할 수 없고, 이전/다음 분석으로 이동하는 방법이 없는 문제.

---

## 설계 결정

| 항목 | 결정 |
|------|------|
| 차트-필터 동기화 | `buildChart(data)` 파라미터화 + `applyFilters()` 끝에 동기화 호출 |
| 차트 재빌드 방식 | `chart.destroy()` + 재생성 (Chart.js `update()` 대신 — 색상 변경도 통합) |
| 테마 재빌드 | `_chartData` 캐시 후 `buildChart()` (인자 없음) 재호출 |
| 트렌드 데이터 범위 | 최근 30건 (시간 오름차순) — 많을수록 차트가 좁아져 30건으로 제한 |
| 현재 분석 강조 | 빨간색 포인트(#ef4444), radius 7, 흰색 테두리 |
| 내비게이션 | id 기준 prev(내림차순 1건)/next(오름차순 1건) — created_at 대신 id 사용 (monotonic 보장) |
| Chart.js 로드 위치 | analysis_detail.html 개별 로드 (base.html 공통 추가 시 불필요한 페이지에서도 로드) |

---

## 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/templates/repo_detail.html` | `buildChart(data)` 파라미터화, `_chartData` 캐시, `applyFilters()` 차트 동기화 호출, `themechange` 수정 |
| `src/ui/router.py` | `analysis_detail()` — siblings(30건)/prev_id/next_id 쿼리 + context 추가 |
| `src/templates/analysis_detail.html` | 이전/다음 내비게이션 버튼, 트렌드 차트 Canvas, Chart.js CDN, CSS |

---

## 구현 상세

### repo_detail 차트 동기화

```javascript
let _chartData = [];
function buildChart(data) {
  if (data !== undefined) _chartData = data;
  // _chartData로 레이블/점수 추출 후 Chart 재생성
}
// applyFilters() 끝에서 필터 결과(시간 오름차순)를 buildChart()에 전달
// themechange: buildChart() — 인자 없이 _chartData 재사용
```

초기 렌더: `applyFilters()` 첫 호출 시 ALL_ANALYSES 전체(필터 미적용)가 차트에 반영됨.

### analysis_detail 트렌드 차트 쿼리

```python
# 시간 내림차순 30건 → reversed() → 오름차순
siblings = db.query(Analysis.id, Analysis.score, Analysis.created_at)
             .filter(repo_id == repo.id)
             .order_by(Analysis.created_at.desc()).limit(30).all()

# id 기준 prev/next
prev_id = db.query(Analysis.id)
            .filter(repo_id == repo.id, id < analysis_id)
            .order_by(Analysis.id.desc()).limit(1).scalar()
next_id = db.query(Analysis.id)
            .filter(repo_id == repo.id, id > analysis_id)
            .order_by(Analysis.id.asc()).limit(1).scalar()
```

---

## 테스트

- `tests/test_ui_router.py` — 3개 추가:
  - `test_analysis_detail_trend_data_returned`: trend_data 반환 검증 (길이·순서·키)
  - `test_analysis_detail_prev_next_navigation`: prev_id=1, next_id=3 정확성
  - `test_analysis_detail_single_analysis_no_siblings`: 1건 시 prev=None, next=None
- 단위 테스트 총 397개 통과 확인
