# Static Assets Runbook — 정적 자원 vendoring 운영

> **대상**: SCAManager 의 `src/static/vendor/` 디렉토리에 호스팅된 외부 자바스크립트/CSS 라이브러리. 운영자/개발자 참조용.
>
> **도입 시점**: 2026-05-01, UI 감사 사이클 Step C (PR #166).

---

## 왜 vendoring 하는가

기존: `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js">` 처럼 외부 CDN 직접 참조.

문제:
- **사내망/방화벽 환경**에서 jsdelivr.net 접속 차단 → 차트 로드 실패 → 사용자에겐 "버그난 페이지"
- **CDN 자체 장애** 시 모든 차트 페이지 동시 marred
- **JS 무결성 검증 부재** — CDN 침해 시 임의 코드 실행 위험

해결: 검증된 버전을 git 트리에 직접 호스팅 (`src/static/vendor/`).

---

## 현재 vendored 자원

| 파일 | 버전 | 크기 | 용도 |
|------|------|------|------|
| `src/static/vendor/chart.umd.min.js` | Chart.js 4.4.0 UMD min | 약 204 KB | `repo_detail`/`analysis_detail`/`insights_me` 페이지 차트 |

> **주의**: 다른 외부 자원 (Pretendard 폰트, Crimson Pro, Google Fonts) 은 현재 CDN 의존 유지. 후속 단계에서 vendoring 검토.

---

## 구조 + Mount

### 디렉토리

```
src/
└── static/
    └── vendor/
        └── chart.umd.min.js    # Chart.js 4.4.0 UMD min
```

### `src/main.py` 의 조건부 mount

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
```

**조건부 mount 이유**: pytest 환경 등 디렉토리 미존재 시 안전 fallback.

### 템플릿 참조

```html
<!-- repo_detail.html / analysis_detail.html / insights_me.html -->
<script src="/static/vendor/chart.umd.min.js"></script>
```

---

## 운영 검증

### 배포 후 즉시 확인

```bash
# Railway 배포 URL 기준
curl -I https://your-app.railway.app/static/vendor/chart.umd.min.js
# 기대: HTTP/2 200 + Content-Length 약 200KB
```

### 회귀 가드 (`tests/unit/test_main.py`)

PR-4 (#173) 가 추가한 가드:

- `test_static_chartjs_returns_200`: 200 응답 + 100KB+ + Chart.js UMD 시그니처
- `test_static_missing_file_returns_404`: graceful 404

가드가 실패하면 (1) `src/static/vendor/chart.umd.min.js` 누락 또는 (2) `src/main.py` mount 코드 회귀 의미.

---

## 신규 vendor 자원 추가 절차

새 라이브러리를 vendoring 할 때:

### 1. 다운로드 + 검증

```bash
mkdir -p src/static/vendor
curl -sSL https://unpkg.com/<package>@<version>/<dist-path> \
     -o src/static/vendor/<library>.min.js

# 크기/시그니처 sanity check
ls -la src/static/vendor/
head -c 200 src/static/vendor/<library>.min.js
```

### 2. 템플릿 갱신

```html
<script src="/static/vendor/<library>.min.js"></script>
```

### 3. CLAUDE.md `src/` 트리 동기화 의무

```
src/
└── static/
    └── vendor/
        ├── chart.umd.min.js    # 기존
        └── <library>.min.js    # 신규 — 한 줄 description
```

CLAUDE.md "신규 파일 추가 체크리스트" (L286~) 적용.

### 4. 회귀 가드 추가 (`tests/unit/test_main.py`)

```python
def test_static_<library>_returns_200(client):
    response = client.get("/static/vendor/<library>.min.js")
    assert response.status_code == 200
    assert len(response.content) > <expected_size_bytes>
```

### 5. STATE.md 갱신

새 그룹 본문에 신규 vendor 자원 명시.

---

## 업그레이드 절차 (예: Chart.js 4.4.0 → 4.5.0)

### 1. 새 버전 다운로드

```bash
curl -sSL https://unpkg.com/chart.js@4.5.0 \
     -o src/static/vendor/chart.umd.min.js.new
```

### 2. 변경점 확인

```bash
# 크기 변화 확인 (큰 변동 시 의심)
wc -c src/static/vendor/chart.umd.min.js{,.new}

# 라이선스/버전 헤더 확인
head -c 200 src/static/vendor/chart.umd.min.js.new
```

### 3. 교체 + 회귀 테스트

```bash
mv src/static/vendor/chart.umd.min.js.new src/static/vendor/chart.umd.min.js
make test  # tests/unit/test_main.py::test_static_chartjs_returns_200
```

### 4. 차트 페이지 visual smoke test

`/repos/{owner}/{repo}` 데스크탑/모바일 양쪽에서 차트 정상 렌더링 확인. claude-dark 테마 전환 시 색 재빌드도 확인.

### 5. 신규 그룹 + STATE 기록

업그레이드는 STATE.md 그룹 본문에 "vendor 업그레이드" 명시 + 회귀 0 검증.

---

## NIXPACKS / Railway 빌드 영향

`src/static/vendor/` 는 git 트리에 포함되므로 **별도 빌드 단계 불필요**. NIXPACKS 가 source 복사 시 자동 포함. `requirements.txt` 변경도 0.

`railway.toml` / `nixpacks.toml` 모두 수정 불필요.

---

## 트러블슈팅

| 증상 | 원인 추정 | 조치 |
|------|----------|------|
| 차트가 빈 박스로 표시 | StaticFiles mount 실패 | `curl -I /static/vendor/chart.umd.min.js` 확인. 404 시 `_STATIC_DIR.exists()` 검증 |
| 200 응답이지만 차트 안 그려짐 | JS 파일 손상 (다운로드 실패) | 파일 크기 + UMD 시그니처 확인. `head -c 200 chart.umd.min.js` 에 "Chart.js v4" 포함되어야 |
| claude-dark 테마 전환 후 차트 색 stale | `themechange` 이벤트 리스너 깨짐 | base.html `dispatchEvent` + 페이지 `addEventListener` 페어 확인. PR-D2 의 `test_themechange_event_listeners` 가드가 차단 |
| 데스크탑에서 차트 빈약 (200px 짜리 작은 차트) | `chart-wrap-inner` clamp 회귀 | CSS 의 `height: clamp(200px, 30vw, 320px)` 확인. PR-D2 의 `test_chart_aspect_ratio_false` 가드가 차단 |

---

## 향후 개선 후보

- **Pretendard 폰트 vendoring** — `base.html` 의 jsdelivr CDN 의존 제거
- **Subresource Integrity (SRI)** — vendored 파일에 SHA-384 hash 검증 추가
- **자동 업그레이드 PR** — Renovate/Dependabot 같은 dependency manager 가 vendor 디렉토리 인식 못 함 → 수동 정기 점검 (월 1회 권장)

---

## 관련 문서

- `CLAUDE.md` UI/템플릿 카테고리 — Chart.js vendoring + StaticFiles mount 규칙
- `docs/STATE.md` 그룹 57 — Chart.js vendoring 도입 (PR #166) 본문
- `docs/design/2026-05-01-ui-redesign-claude-linear-hybrid.md` 진화 기록 — Step C 진행 사실
- `tests/unit/test_main.py::test_static_*` — 회귀 가드
