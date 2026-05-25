# 리포별 코드 인사이트 페이지 Design Spec — SCAManager
**Date**: 2026-05-12
**Status**: Approved by user

---

## 1. 개요 (Overview)

현재 대시보드는 전체 리포 통합 KPI만 제공하고 리포별 반복 문제·개선 방향이 없다.  
이 기능은 **대시보드에 리포 카드 섹션을 추가**하고, 카드 클릭 시 **전용 인사이트 페이지**(`/repos/{name}/insights`)로 이동해 해당 리포의 반복 이슈·문제 파일·AI 제안·카테고리 비율·AI 종합 진단을 한 화면에 제공한다.

**목표**: 사용자가 코드의 반복 문제를 발견하고 어떤 방향으로 개선해야 하는지 실질적인 지침을 얻는다.

---

## 2. 페이지 흐름 (Page Flow)

```
대시보드 (/dashboard)
  └─ [신규] 리포별 인사이트 카드 섹션
       ├─ 리포 A 카드 (등급·반복이슈수·추세) → 클릭
       ├─ 리포 B 카드
       └─ ...
            ↓
리포 인사이트 페이지 (/repos/{name}/insights)  ← 신규
  ├─ 헤더: 리포명 + 종합 등급 + 기간 선택 (7/30/90일)
  ├─ KPI 4종 카드
  ├─ 반복 이슈 랭킹 + 카테고리 비율 도넛 차트 (2열)
  ├─ 문제 파일 TOP 5 (프로그레스 바)
  ├─ AI 제안 모음 TOP 10
  └─ AI 내러티브 카드 (API 키 있을 때만)
```

---

## 3. 신규/변경 파일 목록

### 신규 생성
| 파일 | 역할 |
|------|------|
| `src/ui/routes/repo_insights.py` | `GET /repos/{name}/insights` 라우트 |
| `src/services/repo_insight_service.py` | 리포별 집계 서비스 함수 5종 |
| `src/templates/repo_insights.html` | 인사이트 전용 Jinja2 템플릿 |
| `src/static/css/repo_insights.css` | 인사이트 페이지 전용 CSS (CPD 방지용 분리) |
| `alembic/versions/0031_repo_insights_cache.py` | `insight_narrative_cache.repo_id` 컬럼 추가 |

### 변경
| 파일 | 변경 내용 |
|------|----------|
| `src/templates/dashboard.html` | 리포별 인사이트 카드 섹션 추가 |
| `src/services/dashboard_service.py` | `repo_insight_cards()` 함수 추가 |
| `src/ui/routes/dashboard.py` | `repo_insight_cards()` 호출 + context 전달 |
| `src/main.py` | `repo_insights` 라우터 등록 |
| `docs/architecture.md` | 신규 파일 트리 동기화 |

---

## 4. 데이터 레이어

### 4.1 신규 서비스 함수 (`repo_insight_service.py`)

모두 `Analysis.result` JSON을 Python-side 루프로 처리 (최근 30건 상한).

```python
def repo_kpi(db: Session, repo_id: int, days: int = 30, now: datetime | None = None) -> dict:
    """
    Returns:
      {
        "avg_score": float | None,
        "grade": str,
        "analysis_count": int,
        "top_recurring_issue": str | None,   # 가장 많이 반복된 이슈 메시지
        "top_recurring_count": int,
        "high_security_count": int,
        "score_delta": float | None,         # 전기간 대비 평균점수 변화
      }
    """

def repo_recurring_issues(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict]:
    """
    Returns: [
      {
        "message": str,
        "count": int,
        "category": str,   # "code_quality" | "security"
        "severity": str,   # "error" | "warning"
        "tool": str,
        "language": str,
      }, ...
    ]  빈도 내림차순
    """

def repo_problem_files(
    db: Session, repo_id: int, days: int = 30, n: int = 5, now: datetime | None = None
) -> list[dict]:
    """
    result["file_feedbacks"][].file 빈도 집계.
    Returns: [{"file": str, "count": int, "pct": float}, ...]
    pct = count / max_count * 100  (프로그레스 바용)
    """

def repo_ai_suggestions(
    db: Session, repo_id: int, days: int = 30, n: int = 10, now: datetime | None = None
) -> list[dict]:
    """
    result["ai_suggestions"][] 수집 후 앞 60자 prefix 기준 유사 그룹화.
    Returns: [{"suggestion": str, "count": int}, ...]  빈도 내림차순
    """

def repo_category_breakdown(
    db: Session, repo_id: int, days: int = 30, now: datetime | None = None
) -> dict:
    """
    Returns:
      {
        "security_error": int,
        "security_warning": int,
        "code_quality_error": int,
        "code_quality_warning": int,
        "total": int,
      }
    """
```

### 4.2 대시보드 리포 카드용 함수 (`dashboard_service.py` 추가)

```python
def repo_insight_cards(
    db: Session, days: int = 30, user_id: int | None = None
) -> list[dict]:
    """
    사용자 소유 리포별 요약 (대시보드 카드 섹션용).
    Returns: [
      {
        "repo_id": int,
        "full_name": str,
        "avg_score": float | None,
        "grade": str,
        "recurring_issue_count": int,   # 반복 이슈 종류 수
        "score_trend": "up" | "down" | "flat",
        "insights_url": str,            # "/repos/{name}/insights"
      }, ...
    ]
    """
```

### 4.3 DB 마이그레이션 (`0031_repo_insights_cache.py`)

```python
# insight_narrative_cache 테이블 확장
op.add_column(
    "insight_narrative_cache",
    sa.Column("repo_id", sa.Integer(),
              sa.ForeignKey("repositories.id", ondelete="CASCADE"),
              nullable=True)
)

# 기존 유니크 제약 교체
op.drop_constraint("uq_insight_narrative_cache_user_days_lang", ...)
op.create_index(
    "uq_insight_narrative_cache",
    "insight_narrative_cache",
    ["user_id", "days", "language", "repo_id"],
    unique=True,
    postgresql_where=sa.text("repo_id IS NOT NULL"),  # partial index
)
# repo_id = NULL → 기존 전체 대시보드 캐시 (하위 호환 유지)
# repo_id = N    → 리포별 AI 내러티브 캐시 (1h TTL)
```

---

## 5. 라우트 (`repo_insights.py`)

```python
@router.get("/repos/{repo_name:path}/insights", response_class=HTMLResponse)
async def repo_insights(
    request: Request,
    repo_name: str,
    current_user: CurrentUser,
    days: int = 30,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = find_repo_by_full_name(db, repo_name, current_user.id)
    if not repo:
        raise HTTPException(404)

    kpi = repo_kpi(db, repo.id, days)
    recurring = repo_recurring_issues(db, repo.id, days)
    problem_files = repo_problem_files(db, repo.id, days)
    ai_suggestions = repo_ai_suggestions(db, repo.id, days)
    breakdown = repo_category_breakdown(db, repo.id, days)

    # AI 내러티브 (API 키 있을 때만)
    narrative = None
    if repo_config and repo_config.anthropic_api_key:
        narrative = await repo_insight_narrative(db, repo.id, days, ...)

    return templates.TemplateResponse("repo_insights.html", {
        "request": request,
        "current_user": current_user,
        "repo": repo,
        "days": days,
        "kpi": kpi,
        "recurring_issues": recurring,
        "problem_files": problem_files,
        "ai_suggestions": ai_suggestions,
        "breakdown": breakdown,
        "narrative": narrative,
        "locale": ...,
    })
```

---

## 6. UI 컴포넌트 상세

### 6.1 대시보드 — 리포별 인사이트 카드 섹션

기존 `merge_failures` 섹션 아래 추가.

```
┌─ 리포별 인사이트 ─────────────────────── [30일 ▾] ─┐
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ user/repo-A  │ │ user/repo-B  │ │ user/repo-C  │ │
│  │ 등급  [B]    │ │ 등급  [A]    │ │ 등급  [C]    │ │
│  │ 반복이슈 3종 │ │ 반복이슈 1종 │ │ 반복이슈 8종 │ │
│  │ 추세  ↑      │ │ 추세  →      │ │ 추세  ↓      │ │
│  │ [인사이트 →] │ │ [인사이트 →] │ │ [인사이트 →] │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────┘
```

- 리포 없을 경우: 빈 상태(empty state) 표시
- 추세 아이콘: `score_trend` 값에 따라 ↑(green) / ↓(danger) / →(text-2)

### 6.2 인사이트 페이지 레이아웃

#### 헤더
```
← 대시보드    📦 user/repo-name    [B등급]
              최근 30일 · 분석 12건 기준    [7일] [30일] [90일]
```

#### KPI 4카드
| 카드 | 주 값 | 보조 |
|------|------|------|
| 평균 점수 | 72.4 (B등급) | 전기간 대비 delta |
| 총 분석수 | 12건 | delta |
| 최다 반복 이슈 | "line too long" | 7회 반복 |
| 보안 HIGH | 3건 | delta |

#### 반복 이슈 + 카테고리 비율 (2열)

**반복 이슈 테이블 (좌, 60%)**
| # | 이슈 메시지 | 횟수 | 도구 | 카테고리 |
|---|------------|------|------|----------|
| 1 | line too long (E501) | 7 | pylint | code_quality |
| 2 | missing docstring | 5 | pylint | code_quality |
| 3 | SQL injection risk | 3 | bandit | security |

각 행: severity 배지(error=danger색 / warning=warning색), tool 배지, reveal 애니메이션

**카테고리 비율 도넛 (우, 40%)**
- Chart.js 도넛, 4색 (security_error / security_warning / cq_error / cq_warning)
- `--accent`, `--accent-2`, `--danger`, `--warning` 토큰 사용

#### 문제 파일 TOP 5
```
src/worker/pipeline.py      ██████████  8회
src/services/dashboard.py   ████████    6회
src/models/analysis.py      █████       4회
```
- CSS `width: {pct}%` 인라인으로 프로그레스 바 표현
- hover 시 `::before` 좌측 accent 바 (기존 `.admin-table` 패턴)

#### AI 제안 모음
번호 매긴 리스트, 각 항목에 `{count}회 언급` 배지.  
`ai_review_status != "success"` 분석은 집계에서 제외.

#### AI 내러티브 카드
- API 키 없을 때: 카드 자체 숨김 (`{% if narrative %}`)
- 캐시 1h TTL, `?refresh=1` 강제 갱신 지원
- 로딩 중: `.skeleton` shimmer 애니메이션 (기존 base.html 패턴)

---

## 7. CSS 분리 원칙

`src/static/css/repo_insights.css` 신규 생성.  
이유: `admin.css` 분리와 동일 — SonarQube CPD 임계치(3%) 초과 방지.  
인사이트 페이지 전용 `.ri-*` 클래스 prefix 사용.

---

## 8. 성능 제약

- 집계 대상: **최근 30건 분석 상한** (분석 수가 많아도 Python 루프 O(30×이슈수))
- AI 내러티브 캐시: **1h TTL** (기존 `insight_narrative_cache` 패턴 동일)
- 리포 카드 섹션: **최대 10개 리포** (사용자 소유 리포가 많을 경우 "더 보기" 링크)

---

## 9. 접근성 & 모바일

- `prefers-reduced-motion` 적용 (기존 base.html 패턴 상속)
- 모바일 768px: KPI 4카드 → 2열, 반복이슈+도넛 2열 → 1열 스택
- 인터랙티브 요소 `min-height: 44px` (WCAG 2.5.5, 기존 `.claude/rules/ui.md` 의무)
- Chart.js 도넛에 `aria-label` 추가

---

## 10. 테스트 계획

| 테스트 | 위치 | 검증 항목 |
|--------|------|----------|
| `test_repo_insight_service.py` | `tests/unit/services/` | 각 서비스 함수 반환값, 빈 데이터 처리, days 필터 |
| `test_repo_insights_route.py` | `tests/unit/api/` | 404(리포 없음), 200(정상), 권한 격리 |
| `test_repo_insights_css.py` | `tests/integration/` | `.ri-*` 클래스 존재, mobile 44px |
| `test_repo_insight_cards.py` | `tests/unit/services/` | `repo_insight_cards()` 빈 리포·정상 케이스 |

---

## 11. 구현 제외 범위 (YAGNI)

- 리포간 비교 페이지 (별도 기능)
- 이슈 자동 수정 제안 실행 (별도 기능)
- 팀/멀티유저 공유 인사이트 (leaderboard 폐기 정책 준수)
- 실시간 WebSocket 업데이트
