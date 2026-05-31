# 사이클 143 i18n 완성 + 프로세스 강화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** repo_detail.html · analysis_detail.html HTML 영역 하드코딩 한국어 i18n 전환 + GitHub PR 템플릿 + 정책 보강으로 사이클 142 회고 잔여 항목을 완료한다.

**Architecture:** 기존 `i18n_args` Jinja2 필터 패턴을 그대로 확장한다. 신규 키를 ko/en/ja JSON에 추가하고 템플릿에서 `{{ 'namespace.key' | i18n_args(locale | default('ko')) }}` 로 교체한다. TDD: test-writer로 키 존재 테스트 먼저 작성(Red) → JSON 추가(Green) → 템플릿 교체 → PR.

**Tech Stack:** Python 3.14 · FastAPI · Jinja2 · pytest · ko/en/ja JSON 번역 파일

---

## 파일 맵

| 파일 | 역할 | Sprint |
|---|---|---|
| `src/i18n/translations/ko.json` | analysis_detail.issue_form.* / repo_detail.cost.* / repo_detail.issue_mgmt.* 신규 키 | 1-A, 2, 3 |
| `src/i18n/translations/en.json` | 동일 (영어 번역값) | 1-A, 2, 3 |
| `src/i18n/translations/ja.json` | 동일 (일본어 번역값) | 1-A, 2, 3 |
| `src/templates/analysis_detail.html` | L814,818,822 라벨 i18n 교체 | 1-A |
| `src/templates/repo_detail.html` | L449,451,495,496,504-519 일반 텍스트 / L609,613,616,622,641,654-656 이슈 UI | 2, 3 |
| `tests/unit/test_i18n_analysis_detail.py` | 신규 — analysis_detail 키 존재 테스트 | 1-A |
| `tests/unit/test_i18n_repo_detail.py` | 신규 — repo_detail 키 존재 테스트 (Sprint 2+3 누적) | 2, 3 |
| `tests/integration/test_i18n_smoke.py` | 기존 파일에 /repos/ 엔드포인트 locale 테스트 1건 추가 | 3 |
| `.github/pull_request_template.md` | 신규 — 정책 18/11 체크리스트 자동 적용 | 1-B |
| `CLAUDE.md` | 완료 6-step에 PR 본문 섹션 명시 추가 | 1-C |
| `.claude/policies/active.md` | 정책 11 PR 본문 8조합 체크리스트 표준 형식 코드블록 | 1-C |

---

## Sprint 1 — 소규모 i18n + 프로세스 인프라

### Task 1: analysis_detail.html i18n — Red (테스트 먼저)

**Files:**
- Create: `tests/unit/test_i18n_analysis_detail.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
"""analysis_detail i18n 키 존재 테스트 — Sprint 1-A (사이클 143).

Tests that analysis_detail.issue_form.* keys exist in all 3 locales.
"""
from __future__ import annotations
import json
import pathlib
import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_ISSUE_FORM_KEYS = ["title", "body", "labels"]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_FORM_KEYS)
def test_analysis_detail_issue_form_key_exists(locale: str, key: str):
    """analysis_detail.issue_form.<key>가 모든 locale에 존재해야 한다.
    analysis_detail.issue_form.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "analysis_detail" in data, f"[{locale}] analysis_detail 네임스페이스 없음"
    assert "issue_form" in data["analysis_detail"], f"[{locale}] issue_form 서브키 없음"
    assert key in data["analysis_detail"]["issue_form"], (
        f"[{locale}] analysis_detail.issue_form.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _ISSUE_FORM_KEYS)
def test_analysis_detail_issue_form_value_non_empty(locale: str, key: str):
    """analysis_detail.issue_form.<key> 값이 비어있지 않아야 한다.
    Value of analysis_detail.issue_form.<key> must be non-empty.
    """
    data = _load(locale)
    val = data.get("analysis_detail", {}).get("issue_form", {}).get(key)
    assert isinstance(val, str) and val.strip(), (
        f"[{locale}] analysis_detail.issue_form.{key} 값이 비어있음: {val!r}"
    )
```

- [ ] **Step 2: 테스트 실행 — Red 확인**

```bash
python -m pytest tests/unit/test_i18n_analysis_detail.py -v
```

Expected: **18 FAILED** — `issue_form` 키가 아직 없으므로 전부 실패

---

### Task 2: analysis_detail.html i18n — Green (JSON 키 추가 + 템플릿 교체)

**Files:**
- Modify: `src/i18n/translations/ko.json`
- Modify: `src/i18n/translations/en.json`
- Modify: `src/i18n/translations/ja.json`
- Modify: `src/templates/analysis_detail.html:814,818,822`

- [ ] **Step 1: Python으로 3개 JSON 파일에 키 추가**

```python
import json, pathlib

NEW_KEYS = {
    "ko": {"title": "제목", "body": "본문", "labels": "라벨 (쉼표 구분)"},
    "en": {"title": "Title", "body": "Body", "labels": "Labels (comma separated)"},
    "ja": {"title": "タイトル", "body": "本文", "labels": "ラベル (カンマ区切り)"},
}
base = pathlib.Path("src/i18n/translations")
for locale, vals in NEW_KEYS.items():
    path = base / f"{locale}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["analysis_detail"]["issue_form"] = vals
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{locale}.json updated")
```

실행: `python -c "<위 코드>"`

- [ ] **Step 2: analysis_detail.html L814, L818, L822 교체**

현재 L814:
```html
      <label class="issue-modal-label">제목
```
변경 후:
```html
      <label class="issue-modal-label">{{ 'analysis_detail.issue_form.title' | i18n_args(locale | default('ko')) }}
```

현재 L818:
```html
      <label class="issue-modal-label">본문
```
변경 후:
```html
      <label class="issue-modal-label">{{ 'analysis_detail.issue_form.body' | i18n_args(locale | default('ko')) }}
```

현재 L822:
```html
      <label class="issue-modal-label">라벨 (쉼표 구분)
```
변경 후:
```html
      <label class="issue-modal-label">{{ 'analysis_detail.issue_form.labels' | i18n_args(locale | default('ko')) }}
```

- [ ] **Step 3: 테스트 실행 — Green 확인**

```bash
python -m pytest tests/unit/test_i18n_analysis_detail.py -v
```

Expected: **18 passed**

- [ ] **Step 4: 통합 smoke 확인**

```bash
python -m pytest tests/integration/test_i18n_smoke.py -v
```

Expected: **11 passed**

- [ ] **Step 5: 브랜치 생성 + 커밋**

```bash
git checkout main && git pull origin main
git checkout -b fix/cycle-143-sprint-1a-analysis-detail-i18n
git add src/i18n/translations/ko.json src/i18n/translations/en.json \
        src/i18n/translations/ja.json src/templates/analysis_detail.html \
        tests/unit/test_i18n_analysis_detail.py
git commit -m "fix(i18n): analysis_detail.html issue_form 라벨 i18n — Sprint 1-A (사이클 143)"
```

- [ ] **Step 6: Codex 검증 의뢰 (push 전, 정책 18) → push → PR**

```bash
# Codex 샌드박스 오류 시 Claude 직접 검증 후 진행
git push -u origin fix/cycle-143-sprint-1a-analysis-detail-i18n
gh pr create \
  --title "fix(i18n): analysis_detail.html issue_form 라벨 i18n (사이클 143 Sprint 1-A)" \
  --body "## Summary
Sprint 1-A — analysis_detail.html Issue 생성 모달 라벨 3건 i18n.

## 변경 내용
- analysis_detail.issue_form.{title,body,labels} 키 신규 (ko/en/ja)
- analysis_detail.html L814,818,822 하드코딩 한국어 → i18n_args

## 테스트
- test_i18n_analysis_detail.py 18케이스 신규 ✅

## 🔍 사용자 검증 필요
- [ ] CI 통과 확인
- [ ] EN locale에서 /analyses/{id} 진입 시 Issue 생성 모달 라벨이 영어로 표시되는지 확인

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex OK / Claude 직접 검증 대체 OK
🤖 Generated with Claude Code"
```

---

### Task 3: GitHub PR 템플릿 생성 (Sprint 1-B)

**Files:**
- Create: `.github/pull_request_template.md`

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git pull origin main
git checkout -b chore/cycle-143-sprint-1b-pr-template
```

- [ ] **Step 2: `.github/pull_request_template.md` 파일 작성**

```markdown
## Summary

<!-- 변경 내용을 1-3줄로 요약 -->

## 변경 내용

<!-- 구체적인 변경 사항 -->

## 테스트

<!-- 테스트 방법 및 결과 -->

## 🔍 사용자 검증 필요

- [ ] CI 통과 확인
- [ ] (UI 변경 시) 4테마(dark/light/pastel/catppuccin) × 2뷰포트(데스크탑/모바일) 8조합 시각 확인

<!-- UI/CSS/HTML 변경 PR은 아래 8조합 체크리스트를 작성해 주세요 -->
<!--
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |
-->

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)

- [ ] Codex OK / Claude 직접 검증 대체 OK

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 3: 커밋 + push + PR**

```bash
git add .github/pull_request_template.md
git commit -m "chore: GitHub PR 단일 템플릿 추가 — 정책 18/11 체크리스트 (사이클 143 Sprint 1-B)"
git push -u origin chore/cycle-143-sprint-1b-pr-template
gh pr create \
  --title "chore: GitHub PR 단일 템플릿 추가 — 정책 18/11 체크리스트 (사이클 143 Sprint 1-B)" \
  --body "## Summary
Sprint 1-B — .github/pull_request_template.md 신규 생성.

## 변경 내용
- 정책 18 Codex 검증 의뢰 체크리스트 포함
- 정책 11 UI 변경 8조합 체크리스트 주석 포함 (UI PR에서 활성화)
- GitHub 자동 적용 (단일 파일 방식 — 공식 확인)

## 🔍 사용자 검증 필요
- [ ] CI 통과 확인
- [ ] 새 PR 생성 시 GitHub UI에서 템플릿 자동 적용 확인

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex OK / Claude 직접 검증 대체 OK
🤖 Generated with Claude Code"
```

---

### Task 4: CLAUDE.md + 정책 보강 (Sprint 1-C)

**Files:**
- Modify: `CLAUDE.md:359` (완료 6-step 항목)
- Modify: `.claude/policies/active.md` (정책 11 섹션)

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git pull origin main
git checkout -b chore/cycle-143-sprint-1c-policy-update
```

- [ ] **Step 2: CLAUDE.md L359 완료 6-step 수정**

현재 L359 (`완료 시 필수 6-step`):
```
- **완료 시 필수 6-step**: 작업이 완료되면 반드시 ① 커밋 → ② Codex 검증 의뢰 (push 전, 정책 18) → ③ `git push` → ④ PR 생성(`gh pr create`) → ⑤ ...
```

`④ PR 생성` 항목 뒤에 추가:
```
④ PR 생성(`gh pr create`) — **PR 본문에 반드시 `## 🔍 Codex 검증 의뢰 (push 전, 정책 18)` 섹션 포함** (`.github/pull_request_template.md` 사용 또는 수동 추가) →
```

- [ ] **Step 3: `.claude/policies/active.md` 정책 11 섹션에 표준 8조합 코드블록 추가**

정책 11 섹션 끝부분에 추가:

```markdown
**표준 8조합 체크리스트 코드블록 (UI 변경 PR 본문 필수)**:
\`\`\`
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |
\`\`\`
```

- [ ] **Step 4: 커밋 + push + PR**

```bash
git add CLAUDE.md .claude/policies/active.md
git commit -m "chore(policy): CLAUDE.md 6-step PR 본문 섹션 명시 + 정책 11 8조합 표준 형식 (사이클 143 Sprint 1-C)"
git push -u origin chore/cycle-143-sprint-1c-policy-update
gh pr create \
  --title "chore(policy): CLAUDE.md 6-step + 정책 11 표준 형식 보강 (사이클 143 Sprint 1-C)" \
  --body "## Summary
Sprint 1-C — 정책 18/11 프로세스 보강.

## 변경 내용
- CLAUDE.md 완료 6-step: PR 본문 Codex 검증 의뢰 섹션 포함 명시
- .claude/policies/active.md 정책 11: 8조합 체크리스트 코드블록 표준 형식 추가

## 🔍 사용자 검증 필요
- [ ] CI 통과 확인

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex OK / Claude 직접 검증 대체 OK
🤖 Generated with Claude Code"
```

---

## Sprint 2 — repo_detail.html 일반 텍스트 i18n

### Task 5: repo_detail.html 일반 텍스트 — Red (테스트 먼저)

**Files:**
- Create: `tests/unit/test_i18n_repo_detail.py`

- [ ] **Step 1: 테스트 파일 작성**

```python
"""repo_detail i18n 키 존재 테스트 — Sprint 2 (사이클 143).

Tests that repo_detail.* keys exist in all 3 locales.
Sprint 3 keys will be appended to this same file.
"""
from __future__ import annotations
import json
import pathlib
import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]

_SPRINT2_TOP_KEYS = [
    "recent_score",
    "analysis_unit",
    "history_empty",
    "history_empty_hint",
]
_SPRINT2_COST_KEYS = [
    "title",
    "period",
    "tokens",
    "no_data",
    "disclaimer",
    "model_change",
    "settings_link",
]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_TOP_KEYS)
def test_repo_detail_sprint2_top_key_exists(locale: str, key: str):
    """repo_detail.<key>가 모든 locale에 존재해야 한다.
    repo_detail.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data, f"[{locale}] repo_detail 없음"
    assert key in data["repo_detail"], f"[{locale}] repo_detail.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_TOP_KEYS)
def test_repo_detail_sprint2_top_value_non_empty(locale: str, key: str):
    """repo_detail.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] repo_detail.{key} 비어있음: {val!r}"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_COST_KEYS)
def test_repo_detail_sprint2_cost_key_exists(locale: str, key: str):
    """repo_detail.cost.<key>가 모든 locale에 존재해야 한다.
    repo_detail.cost.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data
    assert "cost" in data["repo_detail"], f"[{locale}] repo_detail.cost 서브키 없음"
    assert key in data["repo_detail"]["cost"], f"[{locale}] repo_detail.cost.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT2_COST_KEYS)
def test_repo_detail_sprint2_cost_value_non_empty(locale: str, key: str):
    """repo_detail.cost.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get("cost", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] repo_detail.cost.{key} 비어있음: {val!r}"
```

- [ ] **Step 2: 테스트 실행 — Red 확인**

```bash
python -m pytest tests/unit/test_i18n_repo_detail.py -v
```

Expected: **66 FAILED** (Sprint 2 키 미존재)

---

### Task 6: repo_detail.html 일반 텍스트 — Green (JSON + 템플릿)

**Files:**
- Modify: `src/i18n/translations/ko.json`, `en.json`, `ja.json`
- Modify: `src/templates/repo_detail.html`

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git pull origin main
git checkout -b fix/cycle-143-sprint-2-repo-detail-general-i18n
```

- [ ] **Step 2: Python으로 3개 JSON 파일에 Sprint 2 키 추가**

```python
import json, pathlib

NEW_TOP = {
    "ko": {
        "recent_score": "최근 점수:",
        "analysis_unit": "건 분석",
        "history_empty": "분석 이력이 없습니다",
        "history_empty_hint": "Push 또는 PR 이벤트 후 첫 분석이 완료되면 차트가 표시됩니다",
    },
    "en": {
        "recent_score": "Recent Score:",
        "analysis_unit": "analyses",
        "history_empty": "No analysis history",
        "history_empty_hint": "The chart will appear after the first analysis is complete following a Push or PR event.",
    },
    "ja": {
        "recent_score": "最近スコア:",
        "analysis_unit": "件",
        "history_empty": "分析履歴がありません",
        "history_empty_hint": "PushまたはPRイベント後、最初の分析が完了するとグラフが表示されます。",
    },
}
NEW_COST = {
    "ko": {
        "title": "이번 달 AI 리뷰 예상 비용",
        "period": "({month} 01일 ~ 말일, 서버사이드 Webhook 분석 기준)",
        "tokens": "(입력+출력 {count} 토큰)",
        "no_data": "데이터 없음 — 이번 달 토큰 추적 분석이 아직 없습니다.",
        "disclaimer": "※ Anthropic 공식 요금 기준 추정값입니다. 실제 청구금액과 다를 수 있으며, pre-push 훅 비용(사용자 API 키)은 포함되지 않습니다.",
        "model_change": "모델 변경:",
        "settings_link": "설정 페이지",
    },
    "en": {
        "title": "Estimated AI Review Cost This Month",
        "period": "({month} 1st – last day, server-side Webhook analysis basis)",
        "tokens": "(input+output {count} tokens)",
        "no_data": "No data — no token-tracked analyses this month yet.",
        "disclaimer": "※ Estimated based on Anthropic official pricing. Actual charges may differ. Pre-push hook costs (user API key) are not included.",
        "model_change": "Change model:",
        "settings_link": "Settings page",
    },
    "ja": {
        "title": "今月のAIレビュー予想コスト",
        "period": "({month}月1日〜末日、サーバーサイドWebhook分析基準)",
        "tokens": "(入力+出力 {count} トークン)",
        "no_data": "データなし — 今月はトークン追跡分析がまだありません。",
        "disclaimer": "※ Anthropic公式料金に基づく推定値です。実際の請求額と異なる場合があり、pre-pushフックのコスト（ユーザーAPIキー）は含まれません。",
        "model_change": "モデル変更:",
        "settings_link": "設定ページ",
    },
}
base = pathlib.Path("src/i18n/translations")
for locale in ["ko", "en", "ja"]:
    path = base / f"{locale}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["repo_detail"].update(NEW_TOP[locale])
    data["repo_detail"]["cost"] = NEW_COST[locale]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{locale}.json updated")
```

실행: `python -c "<위 코드>"`

- [ ] **Step 3: repo_detail.html 템플릿 교체 (7개 위치)**

**L449** — `최근 점수:` 교체:
```html
      <span style="font-size: var(--fs-sm, 0.875rem); color: var(--text-2, rgba(255,255,255,0.6));">{{ 'repo_detail.recent_score' | i18n_args(locale | default('ko')) }} {{ (_latest.score | round(1)) if _latest.score is not none else '—' }}/100</span>
```

**L451** — `건 분석` 교체:
```html
      <span style="font-size: var(--fs-xs, 0.75rem); color: var(--text-3, rgba(255,255,255,0.4));">{{ analyses | length }}{{ 'repo_detail.analysis_unit' | i18n_args(locale | default('ko')) }}</span>
```

**L495** — `분석 이력이 없습니다` 교체:
```html
      <span class="chart-empty-title" id="chartEmptyText">{{ 'repo_detail.history_empty' | i18n_args(locale | default('ko')) }}</span>
```

**L496** — `Push 또는 PR 이벤트...` 교체:
```html
      <span class="chart-empty-sub">{{ 'repo_detail.history_empty_hint' | i18n_args(locale | default('ko')) }}</span>
```

**L504** — `이번 달 AI 리뷰 예상 비용` 교체:
```html
    <span style="font-size:13px;font-weight:600;color:var(--text-1);">{{ 'repo_detail.cost.title' | i18n_args(locale | default('ko')) }}</span>
```

**L505** — `({{ monthly_cost_month }} 01일 ~ 말일...)` 교체:
```html
    <span style="font-size:11px;color:var(--text-2);">{{ 'repo_detail.cost.period' | i18n_args(locale | default('ko'), month=monthly_cost_month) }}</span>
```

**L511** — `(입력+출력 ... 토큰)` 교체:
```html
      {{ 'repo_detail.cost.tokens' | i18n_args(locale | default('ko'), count="{:,}".format(monthly_token_count)) }}
```

**L514** — `데이터 없음...` 교체:
```html
    <span style="margin-left:auto;font-size:13px;color:var(--text-2);">{{ 'repo_detail.cost.no_data' | i18n_args(locale | default('ko')) }}</span>
```

**L518** — `※ Anthropic 공식 요금...` 교체:
```html
    {{ 'repo_detail.cost.disclaimer' | i18n_args(locale | default('ko')) }}
```

**L519** — `모델 변경: <a>설정 페이지</a>` 교체:
```html
    {{ 'repo_detail.cost.model_change' | i18n_args(locale | default('ko')) }} <a href="/repos/{{ repo_name }}/settings" style="color:var(--accent);">{{ 'repo_detail.cost.settings_link' | i18n_args(locale | default('ko')) }}</a>
```

- [ ] **Step 4: 테스트 실행 — Green 확인**

```bash
python -m pytest tests/unit/test_i18n_repo_detail.py -v
```

Expected: **66 passed**

- [ ] **Step 5: 전체 관련 테스트 확인**

```bash
python -m pytest tests/unit/test_i18n_repo_detail.py tests/integration/test_i18n_smoke.py -v
```

Expected: **77 passed** (66+11)

- [ ] **Step 6: 커밋 + Codex 검증 의뢰 + push + PR**

```bash
git add src/i18n/translations/ko.json src/i18n/translations/en.json \
        src/i18n/translations/ja.json src/templates/repo_detail.html \
        tests/unit/test_i18n_repo_detail.py
git commit -m "fix(i18n): repo_detail.html 일반 텍스트 i18n — Sprint 2 (사이클 143)"
# Codex 검증 의뢰 후
git push -u origin fix/cycle-143-sprint-2-repo-detail-general-i18n
gh pr create \
  --title "fix(i18n): repo_detail.html 일반 텍스트 i18n (사이클 143 Sprint 2)" \
  --body "## Summary
Sprint 2 — repo_detail.html 일반 텍스트 영역 하드코딩 한국어 ~11건 i18n 전환.

## 변경 내용
- repo_detail.{recent_score,analysis_unit,history_empty,history_empty_hint} 신규 (ko/en/ja)
- repo_detail.cost.{title,period,tokens,no_data,disclaimer,model_change,settings_link} 신규 (ko/en/ja)
- repo_detail.html 해당 위치 i18n_args 교체

## 테스트
- test_i18n_repo_detail.py 66케이스 신규 ✅

## 🔍 사용자 검증 필요
- [ ] CI 통과 확인
- [ ] EN locale에서 /repos/{owner}/{repo} 진입 시 점수 표시, 빈 이력, AI 비용 섹션이 영어로 표시되는지 확인

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex OK / Claude 직접 검증 대체 OK
🤖 Generated with Claude Code"
```

---

## Sprint 3 — repo_detail.html 이슈 등록 UI i18n

### Task 7: 이슈 등록 UI — Red (테스트 추가)

**Files:**
- Modify: `tests/unit/test_i18n_repo_detail.py` (Sprint 3 케이스 추가)

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git pull origin main
git checkout -b fix/cycle-143-sprint-3-repo-detail-issue-mgmt-i18n
```

- [ ] **Step 2: test_i18n_repo_detail.py 에 Sprint 3 케이스 추가**

파일 끝에 다음 추가:

```python
# ---------------------------------------------------------------------------
# Sprint 3 — issue_mgmt 서브 네임스페이스
# ---------------------------------------------------------------------------
_SPRINT3_ISSUE_MGMT_KEYS = [
    "title",
    "tab_static",
    "tab_ai",
    "filter_unregistered",
    "modal_title",
    "form_title",
    "form_body",
    "form_labels",
    "btn_cancel",
    "btn_skip",
    "btn_create_next",
]


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT3_ISSUE_MGMT_KEYS)
def test_repo_detail_sprint3_issue_mgmt_key_exists(locale: str, key: str):
    """repo_detail.issue_mgmt.<key>가 모든 locale에 존재해야 한다.
    repo_detail.issue_mgmt.<key> must exist in all locales.
    """
    data = _load(locale)
    assert "repo_detail" in data
    assert "issue_mgmt" in data["repo_detail"], f"[{locale}] repo_detail.issue_mgmt 없음"
    assert key in data["repo_detail"]["issue_mgmt"], (
        f"[{locale}] repo_detail.issue_mgmt.{key} 없음"
    )


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _SPRINT3_ISSUE_MGMT_KEYS)
def test_repo_detail_sprint3_issue_mgmt_value_non_empty(locale: str, key: str):
    """repo_detail.issue_mgmt.<key> 값이 비어있지 않아야 한다.
    Value must be non-empty.
    """
    val = _load(locale).get("repo_detail", {}).get("issue_mgmt", {}).get(key)
    assert isinstance(val, str) and val.strip(), (
        f"[{locale}] repo_detail.issue_mgmt.{key} 비어있음: {val!r}"
    )
```

- [ ] **Step 3: 테스트 실행 — Red 확인 (Sprint 3 부분만)**

```bash
python -m pytest tests/unit/test_i18n_repo_detail.py -k "issue_mgmt" -v
```

Expected: **66 FAILED** (issue_mgmt 미존재)

---

### Task 8: 이슈 등록 UI — Green (JSON + 템플릿)

**Files:**
- Modify: `src/i18n/translations/ko.json`, `en.json`, `ja.json`
- Modify: `src/templates/repo_detail.html`
- Modify: `tests/integration/test_i18n_smoke.py`

- [ ] **Step 1: Python으로 issue_mgmt 키 추가**

```python
import json, pathlib

NEW_ISSUE_MGMT = {
    "ko": {
        "title": "🔁 반복 이슈 — Issue 등록 관리",
        "tab_static": "🔴 정적 분석 이슈",
        "tab_ai": "💡 AI 제안사항",
        "filter_unregistered": "미등록만 보기",
        "modal_title": "📝 GitHub Issue 생성",
        "form_title": "제목",
        "form_body": "본문",
        "form_labels": "라벨 (쉼표 구분)",
        "btn_cancel": "취소",
        "btn_skip": "이 항목 건너뜀",
        "btn_create_next": "생성 후 다음 →",
    },
    "en": {
        "title": "🔁 Recurring Issues — Issue Registration",
        "tab_static": "🔴 Static Analysis Issues",
        "tab_ai": "💡 AI Suggestions",
        "filter_unregistered": "Show unregistered only",
        "modal_title": "📝 Create GitHub Issue",
        "form_title": "Title",
        "form_body": "Body",
        "form_labels": "Labels (comma separated)",
        "btn_cancel": "Cancel",
        "btn_skip": "Skip this item",
        "btn_create_next": "Create & Next →",
    },
    "ja": {
        "title": "🔁 繰り返しイシュー — Issue登録管理",
        "tab_static": "🔴 静的解析イシュー",
        "tab_ai": "💡 AI提案事項",
        "filter_unregistered": "未登録のみ表示",
        "modal_title": "📝 GitHub Issue作成",
        "form_title": "タイトル",
        "form_body": "本文",
        "form_labels": "ラベル (カンマ区切り)",
        "btn_cancel": "キャンセル",
        "btn_skip": "この項目をスキップ",
        "btn_create_next": "作成して次へ →",
    },
}
base = pathlib.Path("src/i18n/translations")
for locale in ["ko", "en", "ja"]:
    path = base / f"{locale}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["repo_detail"]["issue_mgmt"] = NEW_ISSUE_MGMT[locale]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{locale}.json updated")
```

실행: `python -c "<위 코드>"`

- [ ] **Step 2: repo_detail.html 템플릿 교체 (6개 위치)**

**L609** — `🔁 반복 이슈 — Issue 등록 관리` 교체:
```html
  <h3 class="panel-title">{{ 'repo_detail.issue_mgmt.title' | i18n_args(locale | default('ko')) }}</h3>
```

**L613** — `🔴 정적 분석 이슈` 교체:
```html
      {{ 'repo_detail.issue_mgmt.tab_static' | i18n_args(locale | default('ko')) }} <span class="issue-tab-count" id="repoStaticCount"></span>
```

**L616** — `💡 AI 제안사항` 교체:
```html
      {{ 'repo_detail.issue_mgmt.tab_ai' | i18n_args(locale | default('ko')) }} <span class="issue-tab-count" id="repoAiCount"></span>
```

**L622** — `미등록만 보기` 교체:
```html
      <input type="checkbox" id="showUnregisteredOnly"> {{ 'repo_detail.issue_mgmt.filter_unregistered' | i18n_args(locale | default('ko')) }}
```

**L641** — `📝 GitHub Issue 생성` 교체:
```html
    <h4 class="issue-modal-title">{{ 'repo_detail.issue_mgmt.modal_title' | i18n_args(locale | default('ko')) }}</h4>
```

**L654~656** — 버튼 3개 교체:
```html
      <button type="button" class="btn-secondary" id="bulkCancel">{{ 'repo_detail.issue_mgmt.btn_cancel' | i18n_args(locale | default('ko')) }}</button>
      <button type="button" class="btn-secondary" id="bulkSkip">{{ 'repo_detail.issue_mgmt.btn_skip' | i18n_args(locale | default('ko')) }}</button>
      <button type="button" class="btn-primary"   id="bulkSubmit">{{ 'repo_detail.issue_mgmt.btn_create_next' | i18n_args(locale | default('ko')) }}</button>
```

**L643, L648, L650** — 모달 form 라벨 교체:

L643:
```html
      <label class="issue-modal-label">{{ 'repo_detail.issue_mgmt.form_title' | i18n_args(locale | default('ko')) }}
```
L648:
```html
      <label class="issue-modal-label">{{ 'repo_detail.issue_mgmt.form_body' | i18n_args(locale | default('ko')) }}
```
L650:
```html
      <label class="issue-modal-label">{{ 'repo_detail.issue_mgmt.form_labels' | i18n_args(locale | default('ko')) }}
```

- [ ] **Step 3: test_i18n_smoke.py에 /repos/ 엔드포인트 locale 테스트 추가**

`tests/integration/test_i18n_smoke.py` 파일 끝에 추가:

```python
# ── repo_detail locale smoke (사이클 143 Sprint 3) ─────────────────────────


@pytest.mark.parametrize("locale", ["en", "ja"])
def test_repo_detail_redirects_to_login_for_unauthenticated(client, locale):
    """/repos/{owner}/{repo} — 미인증 시 locale 무관하게 302 리다이렉트.

    Unauthenticated access to /repos/ redirects regardless of locale.
    요청 자체가 require_login에 의해 처리되므로 locale 주입 오류가 발생하지 않아야 한다.
    The request handled by require_login — no locale injection error should occur.
    """
    response = client.get(
        "/repos/testowner/testrepo",
        cookies={"preferred_language": locale},
    )
    # 미인증 → 302 (로그인 리다이렉트) or 401 — 500이 아님을 확인
    assert response.status_code in (302, 401, 404), (
        f"[{locale}] /repos/ 접근 시 예상치 못한 상태 코드: {response.status_code}"
    )
```

- [ ] **Step 4: 전체 테스트 실행 — Green 확인**

```bash
python -m pytest tests/unit/test_i18n_repo_detail.py tests/unit/test_i18n_analysis_detail.py tests/integration/test_i18n_smoke.py -v
```

Expected: **132 passed** (66+66 unit + 18 analysis_detail unit + 13 smoke) — 단, Sprint 1-A가 아직 main에 없으면 analysis_detail 18건 제외 시 **114 passed**

> 참고: Sprint 3 PR은 Sprint 1-A, Sprint 2 PR 머지 후 진행. test_i18n_repo_detail.py 누적 = 66(Sprint 2) + 66(Sprint 3) = 132케이스.

- [ ] **Step 5: 커밋 + Codex 검증 의뢰 + push + PR**

```bash
git add src/i18n/translations/ko.json src/i18n/translations/en.json \
        src/i18n/translations/ja.json src/templates/repo_detail.html \
        tests/unit/test_i18n_repo_detail.py \
        tests/integration/test_i18n_smoke.py
git commit -m "fix(i18n): repo_detail.html 이슈 등록 UI i18n — Sprint 3 (사이클 143)"
# Codex 검증 의뢰 후
git push -u origin fix/cycle-143-sprint-3-repo-detail-issue-mgmt-i18n
gh pr create \
  --title "fix(i18n): repo_detail.html 이슈 등록 UI i18n (사이클 143 Sprint 3)" \
  --body "## Summary
Sprint 3 — repo_detail.html 이슈 등록 관리 UI 하드코딩 한국어 ~11건 i18n 전환.

## 변경 내용
- repo_detail.issue_mgmt.{title,tab_static,tab_ai,filter_unregistered,modal_title,form_title,form_body,form_labels,btn_cancel,btn_skip,btn_create_next} 신규 (ko/en/ja)
- repo_detail.html L609,613,616,622,641,643,648,650,654-656 i18n_args 교체
- test_i18n_smoke.py /repos/ locale smoke 1건 추가

## 테스트
- test_i18n_repo_detail.py Sprint 3 케이스 +66 (누적 132) ✅
- test_i18n_smoke.py +1 ✅

## 🔍 사용자 검증 필요 (정책 11)
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |

- [ ] CI 통과 확인
- [ ] EN locale에서 /repos/{owner}/{repo} 이슈 등록 패널 진입 시 탭/버튼/모달 라벨이 영어로 표시되는지 확인

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex OK / Claude 직접 검증 대체 OK
🤖 Generated with Claude Code"
```

---

## Sprint 완료 후 — docs 동기화

### Task 9: STATE.md + cycle-history.md + README 갱신

**Files:**
- Modify: `docs/STATE.md`
- Modify: `docs/cycle-history.md`
- Modify: `README.md`

- [ ] **Step 1: 브랜치 생성**

```bash
git checkout main && git pull origin main
git checkout -b docs/cycle-143-final-sync
```

- [ ] **Step 2: STATE.md 헤더 갱신**

```
현재 수치 (2026-05-31 기준 — **사이클 143 완료**: i18n 완성 + 프로세스 강화):
전체 3591 수집 (단위 3329+132+18+… + 통합 151+2)
```

> 실제 수치는 `pytest --collect-only -q tests/ 2>&1 | tail -3` 실측 후 기재.

- [ ] **Step 3: README.md Tests 배지 갱신**

```bash
# 실측 후 수치 반영
# [![Tests](https://img.shields.io/badge/Tests-3591%2B_total_(...)-brightgreen...)]
```

- [ ] **Step 4: cycle-history.md 사이클 143 항목 추가**

```markdown
## 사이클 143

**날짜**: 2026-05-31 | **PR**: #XXX~#XXX | **상태**: ✅ 머지 완료

**작업 내용**: i18n 완성 + 프로세스 강화 — analysis_detail·repo_detail HTML i18n + GitHub PR 템플릿 + 정책 보강

| PR | 내용 |
|----|------|
| #XXX | fix(i18n): analysis_detail.html issue_form 라벨 3건 (Sprint 1-A) |
| #XXX | chore: GitHub PR 단일 템플릿 (Sprint 1-B) |
| #XXX | chore(policy): CLAUDE.md + 정책 11 보강 (Sprint 1-C) |
| #XXX | fix(i18n): repo_detail.html 일반 텍스트 ~11건 (Sprint 2) |
| #XXX | fix(i18n): repo_detail.html 이슈 등록 UI ~11건 (Sprint 3) |

**신규 테스트**: +111케이스 (단위 3329→3480+, 통합 11→13)
```

- [ ] **Step 5: 커밋 + push + PR**

```bash
git add docs/STATE.md docs/cycle-history.md README.md
git commit -m "docs: 사이클 143 완료 이력 동기화"
git push -u origin docs/cycle-143-final-sync
gh pr create --title "docs: 사이클 143 완료 이력 동기화" --body "..."
```

---

## Self-Review 체크리스트

**Spec coverage:**
- ✅ Sprint 1-A: analysis_detail.html 3키 → Task 1-2
- ✅ Sprint 1-B: GitHub PR 템플릿 → Task 3
- ✅ Sprint 1-C: CLAUDE.md + 정책 → Task 4
- ✅ Sprint 2: repo_detail.html 일반 텍스트 11키 → Task 5-6
- ✅ Sprint 3: repo_detail.html 이슈 UI 11키 → Task 7-8
- ✅ docs 동기화 → Task 9

**Placeholder 스캔:** 없음. 모든 코드 스텝에 실제 코드 포함.

**Type 일관성:** `i18n_args` 필터 시그니처가 모든 Task에서 동일 패턴 사용. JSON 키 네임스페이스가 Task 간 일관.

**주의사항:**
- Sprint 3은 Sprint 1-A, Sprint 2 PR이 main에 머지된 후 시작 권장 (test_i18n_repo_detail.py가 Sprint 2 기반)
- L451 `건 분석` — 숫자 뒤에 텍스트: `{{ analyses | length }}{{ 'repo_detail.analysis_unit' | ... }}` 형식으로 Jinja2 연결
- L505 `monthly_cost_month` 변수명: 실제 템플릿 컨텍스트 변수명 확인 필요 (`grep -n "monthly_cost_month" src/ui/routes/repo_detail.py`)
