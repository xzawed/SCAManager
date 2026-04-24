# Phase F.3 — Auto-merge 실패 어드바이저 설계 스펙 (2026-04-24)

## 요약

auto-merge 실패 시 Telegram 알림에 **권장조치 텍스트**를 추가하고,
옵션으로 **GitHub Issue를 자동 생성**하는 기능을 구현한다.

핵심 구성요소:
- `merge_failure_advisor.py` — reason tag → 한국어 권장조치 순수 함수
- `merge_failure_issue.py` — GitHub Issue 생성 + 24h 중복 방지 (railway_issue.py 패턴)
- `auto_merge_issue_on_failure` — RepoConfig 신규 boolean 옵션

백엔드 파이프라인(`run_analysis_pipeline`, `merge_pr` 시그니처) 불변.

---

## 해결 페인 포인트

| ID | 문제 | 해결 |
|----|------|------|
| P-알림 | Telegram 실패 알림에 사유만 있고 해결 방법 없음 | `get_advice(reason_tag)` 권장조치 줄 추가 |
| P-가시성 | auto-merge 실패가 알림으로만 전달 — 사후 추적 불가 | `auto_merge_issue_on_failure=true` 시 GitHub Issue 자동 생성 |
| P-중복 | Issue 반복 생성으로 스팸 발생 가능 | 24시간 내 `auto-merge-failure` 라벨 open Issue 존재 시 skip |

---

## 아키텍처

### 신규 파일

```
src/gate/merge_failure_advisor.py       ← 순수 함수 (I/O 없음)
src/notifier/merge_failure_issue.py     ← GitHub Issue 생성 (railway_issue.py 패턴)
```

### 수정 파일

```
src/gate/engine.py                      ← _notify_merge_failure + _run_auto_merge
src/models/repo_config.py              ← auto_merge_issue_on_failure 컬럼
src/config_manager/manager.py          ← RepoConfigData 필드
src/api/repos.py                       ← RepoConfigUpdate 필드
src/templates/settings.html            ← ② PR 카드 자동 Merge 섹션 토글
alembic/versions/0015_*.py             ← 마이그레이션
```

### 불변 제약

- `merge_pr()` 반환 타입 `tuple[bool, str | None]` 불변 (기존 호출부 호환)
- `_MERGEABLE_BLOCK` 불변 (QW1 완성)
- `merge_reasons.py` 상수 이름 불변 (MergeAttempt ORM enum 동기화)
- `run_gate_check()` 시그니처 불변
- PRESETS JS 객체 불변 (알림 채널 URL 미포함 원칙)

---

## 데이터 흐름

```
merge_pr() → (False, "unstable_ci: 머지 조건 미충족 (state=unstable)")
    ↓
_run_auto_merge():
    log_merge_attempt()                        ← F.1 기존 (불변)

    reason_tag = reason.split(":")[0].strip()  ← "unstable_ci"
    advice = get_advice(reason_tag)            ← merge_failure_advisor.py

    await _notify_merge_failure(
        ..., reason_tag=reason_tag, advice=advice
    )
    → Telegram 메시지:
        ⚠️ Auto Merge 실패
        📁 owner/repo — PR #42
        점수: 72점 (기준 75점 이상)
        사유: unstable_ci
        권장: CI 일부 실패. GitHub Actions 확인 후 재실행 또는 status check 통과 필요.
        🔗 GitHub에서 보기

    if config.auto_merge_issue_on_failure:
        try:
            await create_merge_failure_issue(...)
        except Exception:
            logger.warning(...)  ← 파이프라인 미중단
```

---

## 컴포넌트 상세

### 1. `merge_failure_advisor.py`

```python
# src/gate/merge_failure_advisor.py
from src.gate import merge_reasons as _r

_ADVICE: dict[str, str] = {
    _r.BRANCH_PROTECTION_BLOCKED:
        "Required Reviewers 미달 또는 Status Check 미통과. "
        "GitHub Settings → Branches → Protection rules 확인.",
    _r.DIRTY_CONFLICT:
        "PR에 머지 충돌 발생. rebase 또는 수동 머지 필요.",
    _r.BEHIND_BASE:
        "base branch가 앞서 있음. PR의 'Update branch' 버튼 또는 rebase.",
    _r.UNSTABLE_CI:
        "CI 일부 실패. GitHub Actions 확인 후 재실행 또는 status check 통과 필요.",
    _r.DRAFT_PR:
        "PR이 Draft 상태. 'Ready for review'로 전환 필요.",
    _r.UNKNOWN_STATE_TIMEOUT:
        "GitHub의 머지 가능 여부 계산 시간 초과. 잠시 후 재푸시하면 재시도됩니다.",
    _r.PERMISSION_DENIED:
        "GitHub Token 권한 부족. `repo` 스코프(classic) 또는 "
        "`pull_requests: write` + `contents: write`(fine-grained) 필요.",
    _r.NOT_MERGEABLE:
        "PR이 현재 머지 불가 상태. GitHub에서 직접 상태를 확인하세요.",
    _r.UNPROCESSABLE:
        "GitHub API 검증 실패. PR 상태를 확인하세요.",
    _r.CONFLICT_SHA_CHANGED:
        "푸시 중 PR HEAD SHA가 변경됐습니다. 다음 푸시 시 자동 재시도됩니다.",
    _r.NETWORK_ERROR:
        "GitHub API 연결 오류. 잠시 후 재시도됩니다.",
}

_DEFAULT = "GitHub PR 상태를 직접 확인하세요."


def get_advice(reason_tag: str) -> str:
    """reason tag를 한국어 권장조치 텍스트로 변환. 미등록 tag → 기본 안내."""
    return _ADVICE.get(reason_tag, _DEFAULT)
```

**설계 결정**:
- `merge_reasons.py` 상수를 key로 사용 → 오타 방지 + 자동완성 지원
- 미등록 tag는 예외 대신 기본 안내 반환 → 새로운 reason tag 추가 시 graceful degradation

---

### 2. `merge_failure_issue.py`

```python
# src/notifier/merge_failure_issue.py

LABEL = "auto-merge-failure"
_DEDUP_WINDOW_HOURS = 24

async def create_merge_failure_issue(
    *,
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    score: int,
    reason_tag: str,
    advice: str,
) -> None:
    """auto-merge 실패 시 GitHub Issue 생성. 24시간 내 동일 라벨 open Issue 있으면 skip."""
```

**중복 방지 로직** (`railway_issue.py` 동일 패턴):

```python
# GitHub Issues Search API
q = f"repo:{repo_full_name} label:{LABEL} is:open is:issue"
# search 결과 total_count > 0 이면 → return (skip)
```

**Issue 본문 형식**:

```markdown
## ⚠️ Auto-merge 실패

| 항목 | 내용 |
|------|------|
| PR | #{pr_number} |
| 점수 | {score}점 |
| 사유 | `{reason_tag}` |

### 권장 조치
{advice}

### 링크
[GitHub PR 바로가기](https://github.com/{repo_full_name}/pull/{pr_number})

---
_SCAManager auto-merge 실패 감지 — 수동 처리 후 이 Issue를 닫아주세요._
```

**라벨 생성**: `auto-merge-failure` 라벨 없으면 GitHub API가 자동 생성 (색상: `#e11d48`).

---

### 3. `engine.py` 변경

**`_notify_merge_failure` 시그니처**:

```python
async def _notify_merge_failure(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,          # 기존 — "unstable_ci: 머지 조건 미충족 ..."
    reason_tag: str,      # 신규
    advice: str,          # 신규
    chat_id: str | None,
) -> None:
```

**`_run_auto_merge` 추가 로직** (ok=False 분기):

```python
reason_tag = (reason or "unknown").split(":")[0].strip()
advice = get_advice(reason_tag)

await _notify_merge_failure(..., reason_tag=reason_tag, advice=advice)

if config.auto_merge_issue_on_failure:
    try:
        await create_merge_failure_issue(
            github_token=github_token,
            repo_full_name=repo_name,
            pr_number=pr_number,
            score=score,
            reason_tag=reason_tag,
            advice=advice,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "merge-failure Issue 생성 실패 (repo=%s, pr=%d): %s",
            repo_name, pr_number, exc,
        )
```

Issue 생성 실패는 `log_merge_attempt` 격리 패턴과 동일하게 파이프라인을 막지 않음.

---

### 4. RepoConfig 5-way 동기화

신규 필드: `auto_merge_issue_on_failure: bool = False`

| 위치 | 변경 |
|------|------|
| `src/models/repo_config.py` | `Column(Boolean, default=False, nullable=False, server_default="false")` |
| `src/config_manager/manager.py` | `RepoConfigData.auto_merge_issue_on_failure: bool = False` |
| `src/api/repos.py` | `RepoConfigUpdate.auto_merge_issue_on_failure: bool = False` |
| `src/templates/settings.html` | ② PR 카드 자동 Merge 섹션 — toggle-switch |
| `alembic/versions/0015_*.py` | `op.add_column('repo_configs', Column('auto_merge_issue_on_failure', Boolean, server_default='false', nullable=False))` |

---

### 5. Settings UI

**위치**: ② PR 들어왔을 때 카드 → "자동 Merge" 섹션 → `merge_threshold` 슬라이더 아래.

**Progressive Disclosure**: `auto_merge=ON`일 때만 노출 — `toggleMergeThreshold()` JS 함수 확장 또는 별도 `toggleMergeIssueOption()` 헬퍼 (기존 헬퍼 5종 시그니처 불변 원칙 준수 위해 별도 함수 선호).

```html
<!-- auto_merge ON 시에만 표시 (mergeThresholdRow 아래) -->
<div id="mergeIssueRow" class="{% if not config.auto_merge %}is-hidden{% endif %}"
     style="margin-top:.75rem;">
  <div class="toggle-row">
    <div class="toggle-info">
      <div class="t-title">Merge 실패 시 Issue 자동 생성</div>
      <div class="t-desc">auto-merge 실패 시 GitHub Issue 자동 생성.<br>
        <span style="font-size:10px">24시간 내 중복 Issue는 생성하지 않습니다.</span>
      </div>
    </div>
    <label class="toggle-switch">
      <input type="checkbox" name="auto_merge_issue_on_failure" value="on"
             {% if config.auto_merge_issue_on_failure %}checked{% endif %}>
      <span class="toggle-track"></span>
    </label>
  </div>
</div>
```

`toggleMergeIssueOption(checked)` JS — `mergeIssueRow`의 `is-hidden` 클래스 토글.  
`toggleMergeThreshold(checked)` 에서 내부적으로 `toggleMergeIssueOption(checked)` 연계 호출.

---

## 오류 처리

| 실패 지점 | 처리 방식 |
|-----------|----------|
| `get_advice()` | 예외 없음 (순수 dict 조회) — 미등록 tag는 기본 안내 반환 |
| GitHub Issues search API 실패 | `create_merge_failure_issue` 내부에서 `HTTPError` catch → log warning → return |
| GitHub Issue 생성 API 실패 | 동일 — 파이프라인 미중단 |
| `create_merge_failure_issue` 전체 실패 | `_run_auto_merge` 의 `broad-except` catch → log warning → 계속 진행 |
| Telegram 알림 실패 | 기존 `HTTPError` catch 불변 |

---

## 테스트 계획

### 신규 테스트 파일 2개

**`tests/unit/gate/test_merge_failure_advisor.py`** (3개):

```python
def test_get_advice_known_reasons():
    """모든 알려진 reason tag가 비어있지 않은 텍스트를 반환한다."""

def test_get_advice_unknown_reason():
    """미등록 tag는 기본 안내 문구를 반환한다."""
    assert get_advice("http_418") == "GitHub PR 상태를 직접 확인하세요."

def test_all_merge_reasons_covered():
    """merge_reasons.py의 모든 상수에 _ADVICE 항목이 존재한다 (회귀 방지)."""
    import src.gate.merge_reasons as r
    for attr in [r.BRANCH_PROTECTION_BLOCKED, r.DIRTY_CONFLICT, r.BEHIND_BASE,
                 r.UNSTABLE_CI, r.DRAFT_PR, r.UNKNOWN_STATE_TIMEOUT,
                 r.PERMISSION_DENIED, r.NOT_MERGEABLE, r.UNPROCESSABLE,
                 r.CONFLICT_SHA_CHANGED, r.NETWORK_ERROR]:
        assert get_advice(attr) != "GitHub PR 상태를 직접 확인하세요."
```

**`tests/unit/notifier/test_merge_failure_issue.py`** (3개):

```python
async def test_skips_when_open_issue_exists():
    """open Issue 있으면 Issues 생성 API를 호출하지 않는다."""

async def test_creates_issue_when_none_exists():
    """open Issue 없으면 Issue 생성 API를 1회 호출한다."""

async def test_handles_github_api_error_gracefully():
    """GitHub API 오류 시 예외를 raise하지 않고 조용히 처리한다."""
```

### 기존 테스트 파일 수정

**`tests/unit/gate/test_engine.py`** (3개 추가):

```python
async def test_notify_includes_advice_text():
    """Telegram 메시지에 권장조치 텍스트가 포함된다."""

async def test_issue_created_when_option_enabled():
    """auto_merge_issue_on_failure=True면 Issue 생성 함수가 호출된다."""

async def test_issue_skipped_when_option_disabled():
    """auto_merge_issue_on_failure=False(기본)면 Issue 생성 함수가 호출되지 않는다."""
```

**총 신규 테스트**: +9개 (advisor 3 + notifier 3 + engine 3)

---

## 범위 밖 (의도적 제외)

| 항목 | 제외 사유 |
|------|----------|
| F.4 대시보드 Auto-merge 이력 | 별도 Phase — MergeAttempt 데이터 축적 후 |
| F.5 BPR 호환성 체크 | 별도 Phase — F.3 advisor 완성 후 텍스트 재사용 |
| merge_method 컬럼 (squash/merge/rebase) | 별도 항목 — DB 마이그레이션 독립 |
| Issue 닫기 자동화 (PR merge 시) | 별도 Phase — webhook 연동 필요 |
| Slack/Discord Issue 알림 연동 | 별도 Phase — 채널 통합 설계 필요 |

---

## 셀프리뷰 체크리스트

- [x] Placeholder 없음 — 모든 섹션 완결
- [x] 내부 일관성 — `reason_tag` 추출 로직이 engine.py + notifier 양쪽에서 동일 방식
- [x] Scope 적절 — 단일 기능 추가, 기존 API 불변
- [x] 모호성 없음 — 24h 중복 방지 기준, Issue 본문 형식, 라벨 색상 명시
- [x] 5-way 동기화 — ORM → dataclass → API body → 폼 → 기본값 모두 명시
- [x] 오류 격리 — Issue 생성 실패가 Telegram 알림 또는 파이프라인을 막지 않음 명시
