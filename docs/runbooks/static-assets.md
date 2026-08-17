# Static Assets Runbook — 정적 자원 vendoring 운영

> **대상**: SCAManager 의 `src/static/vendor/` 디렉토리에 호스팅된 외부 자바스크립트/CSS 라이브러리. 운영자/개발자 참조용.
>
> 외부 CDN 대신 `src/static/vendor/` 에 검증된 버전을 호스팅한다.

---

## 왜 vendoring 하는가

기존: `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js">` 처럼 외부 CDN 직접 참조.

문제:
- **사내망/방화벽 환경**에서 jsdelivr.net 접속 차단 → 차트 로드 실패 → 사용자에겐 "버그난 페이지"
- **CDN 자체 장애** 시 모든 차트 페이지 동시 마비
- **JS 무결성 검증 부재** — CDN 침해 시 임의 코드 실행 위험

해결: 검증된 버전을 git 트리에 직접 호스팅 (`src/static/vendor/`).

---

## 현재 vendored 자원

| 파일 | 버전 | 크기 | 용도 |
|------|------|------|------|
| `src/static/vendor/chart.umd.min.js` | Chart.js 4.4.0 UMD min | 204,948 B | 차트 페이지 4종 — `dashboard` · `repo_detail` · `analysis_detail` · `repo_insights` (`insights_me` 폐기) |
| `src/static/vendor/htmx.min.js` | htmx 1.9.12 | 48,101 B | `base.html` 전역 `hx-boost` |

> 🔴 이 표는 **vendoring 인벤토리 전량**이어야 하고, 이를 대조하는 **기계 가드는 없다**.
> 재측정: `ls -l src/static/vendor/` · 소비처 `grep -rn "static/vendor/" src/templates/`
> 전례 2회 — ① htmx 행 누락(2026-08-01 #1266 에서 적발·정정) ② **그 정정이 같은 결함을 재생산**:
> #1266 이 htmx 행을 표 중간 **빈 줄 뒤에** 붙여, 행은 있는데 표 밖 평문으로 렌더됐다(2026-08-17 적발).
> **표 안에 빈 줄을 넣지 말 것.**
>
> **폰트는 CDN 의존이 아니다** — 2026-08-17 이전 판은 이 자리에 *"폰트 자원(Pretendard, Crimson Pro,
> Google Fonts)은 현재 CDN 의존 유지"* 라 적었으나 실측은 정반대다: `base.html` `<link>` 9건이 전량
> `/static/*` 로컬이고(외부 폰트 CDN = 2026-08-06 R52 제거, Crimson Pro = 사이클 93 Step 1 삭제),
> `src/main.py:96` CSP `font-src 'self' data:` 가 외부 폰트를 애초에 차단한다. vendoring 대기 폰트 = 0.

---

## 구조 + Mount

### 디렉토리

```
src/
└── static/
    └── vendor/
        ├── chart.umd.min.js    # Chart.js 4.4.0 UMD min
        └── htmx.min.js         # htmx 1.9.12 (base.html 전역 hx-boost)
```

### `src/main.py` 의 조건부 mount

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    # 🔴 표준 `StaticFiles` 가 아니라 서브클래스다 — Cache-Control/ETag 를 붙인다.
    app.mount("/static", CachedStaticFiles(directory=str(_STATIC_DIR)), name="static")
```

**조건부 mount 이유**: pytest 환경 등 디렉토리 미존재 시 안전 fallback.

### 템플릿 참조

```html
<!-- 차트 4종 — dashboard.html / repo_detail.html / analysis_detail.html / repo_insights.html
     (insights_me.html 폐기). 재측정: grep -rn "static/vendor/chart.umd.min.js" src/templates/ -->
<script src="/static/vendor/chart.umd.min.js"></script>

<!-- htmx 는 base.html 단일 로드 — 이를 상속하는 전 페이지에 적용 -->
<script src="/static/vendor/htmx.min.js"></script>
```

---

## 운영 검증

### 배포 후 즉시 확인

```bash
# Railway 배포 URL 기준
curl -I https://your-app.railway.app/static/vendor/chart.umd.min.js
# 기대: HTTP/2 200 + Content-Length 약 200KB
```

### 회귀 가드

| 가드 (위치는 `grep -n "<이름>"` 으로) | 무엇을 고정하는가 |
|------|------|
| `tests/unit/test_main.py::test_static_chartjs_returns_200` | 200 + 본문 100,000 B 초과 + 첫 200 B 에 `Chart.js` 시그니처 |
| `tests/unit/test_main.py::test_static_missing_file_returns_404` | 없는 자원은 graceful 404 |
| `tests/unit/test_main.py::test_static_file_cache_control_revalidates` | 🔴 `CachedStaticFiles` 의 `no-cache` — immutable 장기 캐시 회귀 차단(2026-06-18 운영 사고) |
| `tests/unit/test_main.py::test_static_file_304_on_matching_etag` | ETag 일치 시 304 |
| `tests/unit/test_main.py::test_static_404_no_long_cache` | 404 응답에 장기 캐시 금지 |
| `tests/unit/test_htmx_vendor.py` (3건) | htmx 파일 존재 + `base.html` `<script>` + `<body hx-boost>` |
| `tests/unit/ui/test_router.py::test_chart_aspect_ratio_false` | `maintainAspectRatio:false` + `chart-wrap-inner` + `clamp(200px` |
| `tests/unit/ui/test_router.py::test_themechange_event_listeners` | 테마 전환 시 차트 재빌드 리스너 |
| `tests/unit/templates/test_dashboard_i18n_render.py` (2건) | dashboard `repos` 모드의 vendor `<script>` 로드 조건 — 경계(`length > 1`) 포함 |

🔴 **이 목록에 없는 축**: vendor 디렉토리 목록과 위 §현재 vendored 자원 표를 대조하는 가드는 **없다**.
가드가 실패하면 (1) `src/static/vendor/<파일>` 누락 또는 (2) `src/main.py` mount 코드 회귀 의미.

---

## 신규 vendor 자원 추가 절차

새 라이브러리를 vendoring 할 때:

### 1. 다운로드 + 검증

```bash
mkdir -p src/static/vendor
curl -sSL https://unpkg.com/<package>@<version>/<dist-path> \
     -o src/static/vendor/<library>.min.js

# 크기/시그니처 sanity check — 버전 헤더가 없으면 4단계 가드의 시그니처 assert 를 쓸 수 없다
ls -la src/static/vendor/
head -c 200 src/static/vendor/<library>.min.js
```

🔴 **`.pre-commit-config.yaml` 계약 2건** — 모르면 커밋 단계에서 막힌다:
- `check-added-large-files --maxkb=500` 이 **500 KB 초과 파일을 거부**한다(현재 최대 = chart 204,948 B).
  큰 배포본은 min 빌드/서브셋으로 줄이거나 예외를 먼저 합의할 것.
- `trailing-whitespace` · `end-of-file-fixer` 는 `^(alembic/versions/|src/static/vendor/)` 로 제외돼
  **vendor 산출물을 재작성하지 않는다**. 새 자원을 vendor 밖에 두면 이 보호가 사라진다.
  집행: `tests/unit/scripts/test_precommit_entry_interpreter.py::test_autofixers_exclude_records_and_vendored_files`

### 2. 템플릿 갱신

```html
<script src="/static/vendor/<library>.min.js"></script>
```

### 3. `docs/architecture.md` `src/` 트리 동기화 의무

```
src/
└── static/
    └── vendor/
        ├── chart.umd.min.js    # 기존
        ├── htmx.min.js         # 기존
        └── <library>.min.js    # 신규 — 한 줄 description
```

🔴 **이 단계에는 기계 집행이 없다.** `scripts/check_architecture_tree_sync.py` 는 `src/` 의
**최상위 패키지(24개)와 최상위 모듈(7개)만** 대조한다(`_packages()` = `iterdir()` 1단계,
`_top_modules()` = `glob("*.py")`). 즉 `src/static/vendor/<신규>.min.js` 를 architecture.md 에
안 적어도 그 가드는 **초록으로 통과한다** — 등재는 사람이 한다.
(트리 정본은 `docs/architecture.md` 다. CLAUDE.md 에는 `src/` 트리가 없다 — CLAUDE.md:64 가
 architecture.md 로 위임한다.)

### 4. 회귀 가드 추가 (`tests/unit/test_main.py`)

```python
def test_static_<library>_returns_200(client):
    response = client.get("/static/vendor/<library>.min.js")
    assert response.status_code == 200
    assert len(response.content) > <expected_size_bytes>
```

### 5. STATE.md 갱신

STATE.md 최신 블록에 신규 vendor 자원 명시.

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

# 🔴 `make` 이 없는 머신이 있다(CLAUDE.md §핵심 명령) — pytest 를 직접 부른다.
py -3 -m pytest tests/unit/test_main.py tests/unit/test_htmx_vendor.py

# push 전에는 6-step ② 대로 전체를 돌린다 — 영역 서브셋 대체 금지
py -3 -m pytest tests/unit
```

### 4. 차트 페이지 visual smoke test

`/repos/{owner}/{repo}` 데스크탑/모바일 양쪽에서 차트 정상 렌더링 확인. claude-dark 테마 전환 시 색 재빌드도 확인.

### 5. STATE 기록

업그레이드는 STATE.md 최신 블록에 "vendor 업그레이드" 명시.

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
| claude-dark 테마 전환 후 차트 색 stale | `themechange` 이벤트 리스너 깨짐 | base.html `dispatchEvent` + 페이지 `addEventListener` 페어 확인. `test_themechange_event_listeners` 가드가 차단 |
| 데스크탑에서 차트 빈약 (200px 짜리 작은 차트) | `chart-wrap-inner` clamp 회귀 | CSS 의 `height: clamp(200px, 30vw, 320px)` 확인. `test_chart_aspect_ratio_false` 가드가 차단 |

---

## 향후 개선 후보

- **Pretendard 폰트 vendoring** — 제거할 CDN 의존은 **이미 0** 이다(§현재 vendored 자원 주석 참조).
  지금은 CSP 가 외부 폰트를 막아 **system 폰트 폴백으로 렌더 중**이고, `src/static/vendor/` 에
  웹폰트를 넣으면 `tokens.css:16` 의 `--font-sans` 스택이 코드 변경 없이 살아난다
  (`base.html:22-23` — "나중에 `src/static/vendor/` 로 vendoring 하면 코드 변경 없이 살아난다").
- **Subresource Integrity (SRI)** — vendored 파일에 SHA-384 hash 검증 추가
- **자동 업그레이드 PR** — Renovate/Dependabot 같은 dependency manager 가 vendor 디렉토리 인식 못 함 → 수동 정기 점검 (월 1회 권장)

---

## 관련 문서

- `.claude/rules/ui.md:91` — "신규 정적 자원은 `src/static/vendor/` 하위" (정적·템플릿 편집 시 자동 로드)
- `.claude/rules/security.md:69` — CSP 상 외부 CDN `<script src>` 금지 → vendor 경로 강제
- `docs/architecture.md` `src/` 트리 — vendored 파일 + 버전 정본 (chart 4.4.0 · htmx 1.9.12)
- `docs/STATE.md` — 수치·서사 정본 (배지 파생은 `check_docs_sync.py --fix`)
- `tests/unit/test_main.py::test_static_*` · `tests/unit/test_htmx_vendor.py` — 회귀 가드
