# Settings 페이지 재설계 Implementation Plan

> **Status:** 📝 **계획 수립 완료** (2026-04-21). 단일 파일 리팩토링 — 백엔드 변경 없음.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **실행 환경 제약**: 이 플랜은 `make test` 가 정상 실행되는 환경(로컬 PC 또는 GitHub Codespaces)에서 실행해야 한다. `pytest`/`fastapi`/`sqlalchemy` 가 import 불가능한 환경에서는 PreToolUse Hook (`.claude/hooks/check_edit_allowed.py`) 이 `src/templates/*.html` 편집을 자동 차단한다 (CLAUDE.md "모바일 환경 보호 — 수정 금지 파일" 규약).

**Goal:** 설정 페이지의 정보 아키텍처를 의도 기반 6 카드(① 빠른 설정 / ② PR 들어왔을 때 / ③ 이벤트 후 피드백 / ④ 알림 채널 / ⑤ 시스템 & 토큰 / ⑥ 위험 구역) 로 재편하고, 프리셋에 P1 diff 미리보기 + P2 적용 하이라이트를 추가한다. 저장 오류 시 고급설정 아코디언을 자동으로 펼쳐 문제 필드 위치를 드러낸다.

**Architecture:** 단일 파일 리팩토링. `src/templates/settings.html` 만 변경 대상이며 ORM / API / 라우터 / PRESETS 9개 필드 구성 / 기존 JS 헬퍼 5종 시그니처 모두 불변. 신규 JS 헬퍼 3종(`onPresetToggle`, `renderPresetDiff`, `flashPresetChanges`) 과 CSS `@keyframes preset-flash` 를 추가하며, 설정 저장 오류 시 `?save_error=1` 쿼리 감지 → 고급설정 `<details open>` 자동 토글 JS 한 조각을 추가한다.

**Tech Stack:** Jinja2 템플릿, 바닐라 JS(ES2015), CSS `@keyframes`, HTML5 `<details>`/`<summary>` 아코디언. 테스트: pytest + FastAPI TestClient (settings.html 렌더 스모크 검증).

---

## File Map

| 상태 | 파일 | 역할 |
|------|------|------|
| 수정 | `src/templates/settings.html` | 유일한 변경 대상 — 6 카드 재편 + P1 diff + P2 하이라이트 + 오류 아코디언 자동 펼침 |
| 수정 | `tests/test_ui_router.py` | 렌더 스모크 테스트 3종 추가 (form 필드 보존 · railway_deploy_alerts toggle-switch · 프리셋 `<details>` 존재) |
| 수정 | `CLAUDE.md` | `### UI / 템플릿` 섹션의 "settings.html 구조 규약" 항목 6 카드 + P1/P2 + 헬퍼 8종 명시 갱신 |
| 수정 | `docs/STATE.md` | 그룹 9 항목 추가 + 테스트 수치 3개 증가 반영 |
| (불변) | `src/ui/router.py` | `repo_settings` GET context(`railway_webhook_url`, `railway_api_token_set`) 와 `update_repo_settings` POST 핸들러 불변. 참조만. |
| (불변) | `src/config_manager/manager.py` | `RepoConfigData` 14 필드 불변. 참조만. |
| (불변) | `src/models/repo_config.py` | `RepoConfig` ORM 불변. 참조만. |

---

## Task 1: 렌더 스모크 테스트 선작성 (TDD Red)

**Files:**
- Modify: `tests/test_ui_router.py`

백엔드 불변 강조: 이 Task 는 **템플릿 변경을 검증하는 회귀 안전망** 만 추가한다. POST 핸들러·`RepoConfigData`·PRESETS JS 객체 9개 필드 구성 불변.

- [ ] **Step 1: `tests/test_ui_router.py` 파일 끝에 스모크 테스트 3종 추가**

```python
def test_settings_form_fields_preserved():
    """settings.html 리팩토링 후 16개 form name= 속성이 모두 보존되는지 확인."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    body = r.text
    required_names = [
        "pr_review_comment", "approve_mode", "approve_threshold", "reject_threshold",
        "commit_comment", "create_issue", "auto_merge", "merge_threshold",
        "railway_deploy_alerts", "railway_api_token",
        "notify_chat_id", "discord_webhook_url", "slack_webhook_url",
        "email_recipients", "custom_webhook_url", "n8n_webhook_url",
    ]
    for name in required_names:
        assert f'name="{name}"' in body, f"Missing form field: {name}"


def test_settings_railway_alerts_uses_toggle_switch():
    """railway_deploy_alerts 체크박스가 toggle-switch 클래스 안에 있어야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    import re
    pattern = re.compile(
        r'<label[^>]*class="[^"]*toggle-switch[^"]*"[^>]*>'
        r'[\s\S]*?name="railway_deploy_alerts"',
        re.MULTILINE,
    )
    assert pattern.search(r.text), (
        "railway_deploy_alerts must be wrapped in a .toggle-switch label "
        "for UX consistency with other toggles"
    )


def test_settings_has_preset_details_elements():
    """프리셋 3종 모두 <details id='preset-*'> 요소로 렌더링되어야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
    for preset in ("minimal", "standard", "strict"):
        assert f'id="preset-{preset}"' in r.text, f"Missing <details id=preset-{preset}>"
    for fn in ("onPresetToggle", "renderPresetDiff", "flashPresetChanges"):
        assert fn in r.text, f"Missing JS helper: {fn}"
```

- [ ] **Step 2: 테스트 실행 — 일부 실패 확인 (Red)**

```bash
python -m pytest tests/test_ui_router.py::test_settings_form_fields_preserved tests/test_ui_router.py::test_settings_railway_alerts_uses_toggle_switch tests/test_ui_router.py::test_settings_has_preset_details_elements -v
```

기대: `test_settings_form_fields_preserved` PASS (현재 16개 name 속성 모두 존재), `test_settings_railway_alerts_uses_toggle_switch` FAIL (현재 raw checkbox), `test_settings_has_preset_details_elements` FAIL (`renderPresetDiff` / `flashPresetChanges` 미존재).

- [ ] **Step 3: 커밋**

```bash
git add tests/test_ui_router.py
git commit -m "test(ui): settings 재설계 스모크 테스트 3종 선작성 (Red)

form 필드 16개 보존 · railway_deploy_alerts toggle-switch · 프리셋
<details> + 신규 JS 헬퍼 3종 검증."
```

---

## Task 2: PR 카드 재편 — `auto_merge` + `merge_threshold` 이동

**Files:**
- Modify: `src/templates/settings.html`

백엔드 필드명·POST 핸들러·`RepoConfigData` 불변. `auto_merge`/`merge_threshold` 의 `name=` 속성이 그대로이므로 form 파싱 로직 변경 없음. JS 헬퍼 5종 시그니처 불변 (`toggleMergeThreshold(checked)` 호출처 그대로).

- [ ] **Step 1: 카드 ② PR 동작 카드 헤더·타이틀 변경**

`src/templates/settings.html` 에서 기존 카드 ① 블록의 헤더 부분을 수정:

```html
<!-- ① PR 들어왔을 때 -->
<div class="s-card">
  <div class="s-card-hdr hdr-gate">
    <span class="hdr-icon">📋</span>
    <span class="hdr-title">PR 들어왔을 때</span>
    <span class="hdr-badge" id="approveBadge">{{ config.approve_mode }}</span>
  </div>
  <div class="s-card-body">
    ...
```

- [ ] **Step 2: PR 카드 `<div class="s-card-body">` 내부 필드 순서 재배치**

기존 카드 ① body 의 마지막 `<div id="semiAutoHint">` 블록 아래에 카드 ② 에서 가져온 `auto_merge` 토글 + `merge_threshold` 슬라이더를 이동 삽입:

```html
<div class="s-divider"></div>
<div class="s-section-label">자동 Merge</div>

<div class="toggle-row">
  <div class="toggle-info">
    <div class="t-title">자동 Merge</div>
    <div class="t-desc">점수 이상 시 squash merge.<br>
      <code style="font-size:10px;">pull_requests: write</code> 권한 필요</div>
  </div>
  <label class="toggle-switch">
    <input type="checkbox" id="autoMergeChk" name="auto_merge" value="on"
           {% if config.auto_merge %}checked{% endif %}
           onchange="toggleMergeThreshold(this.checked)">
    <span class="toggle-track"></span>
  </label>
</div>

<div id="mergeThresholdRow" class="{% if not config.auto_merge %}is-hidden{% endif %}" style="margin-top:.75rem;">
  <div class="threshold-row" style="margin-bottom:0">
    <div class="threshold-label">
      <span>Merge 임계값</span>
      <span style="color:var(--success);font-size:11px;font-weight:600;">이상 → Merge</span>
    </div>
    <div class="threshold-ctrl">
      <input type="range" class="approve-range" name="merge_threshold"
             min="0" max="100" value="{{ config.merge_threshold }}"
             oninput="document.getElementById('mergeVal').value=this.value">
      <input type="number" id="mergeVal" class="num-input"
             min="0" max="100" value="{{ config.merge_threshold }}"
             oninput="this.previousElementSibling.value=this.value">
    </div>
  </div>
</div>
```

- [ ] **Step 3: 기존 카드 ② (Push 동작) 에서 `auto_merge` + `merge_threshold` 블록 삭제**

기존 `<div class="s-divider"></div><div class="s-section-label">Auto Merge</div>` 이후 `toggle-row` 부터 `</div><!-- /mergeThresholdRow -->` 까지 제거. Push 카드에는 `commit_comment` 와 `create_issue` 토글만 남긴다 (다음 Task 에서 이 카드를 완전히 재편).

- [ ] **Step 4: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/test_ui_router.py -v
```

기대: `test_settings_form_fields_preserved` PASS 유지 (16개 name 속성 전부 존재), `test_post_settings_with_auto_merge_checked` PASS 유지 (name 속성 그대로).

- [ ] **Step 5: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(ui): settings 카드 ① 를 'PR 들어왔을 때'로 재편 — auto_merge 이동

기존 Push 카드의 auto_merge + merge_threshold 를 PR 카드로 이동.
name= 속성 불변이므로 POST 핸들러 변경 없음."
```

---

## Task 3: 피드백 카드 통합 + `railway_deploy_alerts` toggle-switch 통일

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. `railway_deploy_alerts` 의 `name=` 속성은 그대로이나 HTML 구조가 raw `<input type="checkbox">` → `.toggle-switch` label 로 변경된다. 저장 시 `form.get("railway_deploy_alerts") == "on"` 이 여전히 true/false 를 구분하도록 `value="on"` 속성을 명시한다.

- [ ] **Step 1: 기존 카드 ② (Push 동작) 전체를 "이벤트 후 피드백" 카드로 교체**

```html
<!-- ③ 이벤트 후 피드백 -->
<div class="s-card">
  <div class="s-card-hdr hdr-merge">
    <span class="hdr-icon">📬</span>
    <span class="hdr-title">이벤트 후 피드백</span>
  </div>
  <div class="s-card-body">

    <div class="s-section-label">Push 이후</div>
    <div class="toggle-row">
      <div class="toggle-info">
        <div class="t-title">커밋 코멘트</div>
        <div class="t-desc">Push 커밋에 AI 리뷰 결과를<br>GitHub 커밋 코멘트로 게시</div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" name="commit_comment" value="on"
               {% if config.commit_comment %}checked{% endif %}>
        <span class="toggle-track"></span>
      </label>
    </div>

    <div class="s-divider"></div>
    <div class="s-section-label">점수 미달 시</div>
    <div class="toggle-row">
      <div class="toggle-info">
        <div class="t-title">이슈 자동 생성</div>
        <div class="t-desc">점수 미달 또는 보안 HIGH 발견 시<br>GitHub Issue 자동 생성</div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" name="create_issue" value="on"
               {% if config.create_issue %}checked{% endif %}>
        <span class="toggle-track"></span>
      </label>
    </div>

    <div class="s-divider"></div>
    <div class="s-section-label">Railway 빌드 실패 시</div>
    <div class="toggle-row">
      <div class="toggle-info">
        <div class="t-title">GitHub Issue 자동 생성</div>
        <div class="t-desc">Railway 빌드 실패 이벤트 수신 시<br>해당 리포에 로그 포함 Issue 자동 생성</div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" name="railway_deploy_alerts" id="railway_deploy_alerts" value="on"
               {% if config.railway_deploy_alerts %}checked{% endif %}>
        <span class="toggle-track"></span>
      </label>
    </div>

  </div>
</div>
```

- [ ] **Step 2: 기존 카드 ⑤ Railway 카드에서 토글 부분 제거, 토큰/Webhook URL 만 남기기**

이 부분은 Task 4 에서 완전히 통합한다. 이 Task 에서는 기존 카드 ⑤ 의 `<label class="toggle-row">...railway_deploy_alerts...</label>` 블록과 바로 아래 `<div class="s-divider"></div>` 를 삭제하여 중복을 제거.

- [ ] **Step 3: 테스트 실행 — toggle-switch 검증 PASS 확인**

```bash
python -m pytest tests/test_ui_router.py::test_settings_railway_alerts_uses_toggle_switch tests/test_ui_router.py::test_settings_form_fields_preserved -v
```

기대: 2개 PASS.

- [ ] **Step 4: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(ui): settings 카드 ② 를 '이벤트 후 피드백'으로 통합

Push 카드를 commit_comment / create_issue / railway_deploy_alerts 3종을
트리거별 소제목(Push 이후 / 점수 미달 시 / Railway 빌드 실패 시)으로
그룹핑. railway_deploy_alerts 를 toggle-switch 패턴으로 통일."
```

---

## Task 4: 시스템 & 토큰 카드 통합 + Railway API 토큰 `.masked-field` 통일

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. `railway_api_token` 의 sentinel(`"****"`) 저장 패턴과 POST 핸들러 불변. 단, HTML 구조만 `.masked-field` 패턴으로 통일 + 👁️ mask-toggle 버튼 추가.

- [ ] **Step 1: 기존 카드 ④ 시스템 + 카드 ⑤ Railway 토큰/Webhook 을 카드 ⑤ "시스템 & 토큰" 으로 통합**

`<form>` 바깥의 기존 `<!-- ④ 시스템 -->` 카드를 다음으로 교체:

```html
<!-- ⑤ 시스템 & 토큰 (메인 form 외부) -->
<div class="s-card" style="margin-bottom:1rem;">
  <div class="s-card-hdr hdr-hook">
    <span class="hdr-icon">🔧</span>
    <span class="hdr-title">시스템 &amp; 토큰</span>
  </div>
  <div class="s-card-body">

    <div class="s-section-label">CLI Hook</div>
    {% if hook_ok %}
    <div class="hook-alert ok">✅ <strong>.scamanager/</strong> 파일이 Repo에 커밋됐습니다.</div>
    {% endif %}
    {% if hook_fail %}
    <div class="hook-alert fail">❌ 파일 커밋 실패. GitHub 토큰 권한(repo 스코프)을 확인하세요.</div>
    {% endif %}
    <div class="hook-code">git pull &amp;&amp; bash .scamanager/install-hook.sh</div>
    <div class="hook-btns">
      <button type="submit" class="hook-btn" form="reinstall_hook_form">🔄 훅 파일 재커밋</button>
      <button type="submit" class="hook-btn" form="reinstall_webhook_form">🔗 Webhook 재등록</button>
    </div>

    <div class="s-divider"></div>

    <div class="s-section-label">Railway API 토큰 <span class="field-hint" style="font-weight:400;text-transform:none;letter-spacing:0;">로그 조회용</span></div>
    <div class="field-row">
      <div class="masked-field">
        <input class="field-input" type="password" name="railway_api_token"
               form="settingsForm"
               placeholder="railway_api_token (설정 시 빌드 로그 200줄 포함)"
               value="{{ '****' if railway_api_token_set else '' }}"
               autocomplete="off">
        <button type="button" class="mask-toggle" onclick="toggleFieldMask(this)"
                aria-label="값 보이기/숨기기">👁️</button>
      </div>
      <span class="field-hint">Railway 대시보드 → Account Settings → Tokens 에서 발급. 변경하지 않으려면 그대로 두세요.</span>
    </div>

    {% if railway_webhook_url %}
    <div class="s-section-label" style="margin-top:.85rem">Railway Webhook URL</div>
    <div class="field-row">
      <div style="display:flex;gap:.5rem;align-items:center">
        <input type="text" readonly class="field-input" id="railway-webhook-url"
               value="{{ railway_webhook_url }}" style="font-family:monospace;font-size:12px;flex:1">
        <button type="button" class="hook-btn"
                onclick="navigator.clipboard.writeText(document.getElementById('railway-webhook-url').value)">📋</button>
      </div>
      <span class="field-hint">Railway Project Settings → Webhooks 에 위 URL 을 추가하세요.</span>
    </div>
    {% else %}
    <div class="s-section-label" style="margin-top:.85rem">Railway Webhook URL</div>
    <span class="field-hint">설정 저장 후 Railway Webhook URL 이 자동 생성됩니다.</span>
    {% endif %}

  </div>
</div>
```

- [ ] **Step 2: 메인 `<form>` 에 `id="settingsForm"` 추가**

`<form method="post" action="/repos/{{ repo_name }}/settings">` 를 `<form id="settingsForm" method="post" action="/repos/{{ repo_name }}/settings">` 로 변경. Railway API 토큰 필드가 form 바깥에 있지만 HTML5 `form="settingsForm"` 속성으로 제출 시 포함된다.

- [ ] **Step 3: 기존 메인 `<form>` 내부의 `<!-- ⑤ Railway 배포 알림 -->` 카드 전체 삭제**

Task 3 에서 토글만 옮겼고 토큰 부분은 이 Task 에서 통합했으므로 기존 Railway 카드(669~717줄)는 완전히 제거.

- [ ] **Step 4: 테스트 실행 — 16개 form 필드 보존 재확인**

```bash
python -m pytest tests/test_ui_router.py::test_settings_form_fields_preserved -v
```

기대: PASS (`form="settingsForm"` 속성 덕분에 `name="railway_api_token"` 여전히 감지됨).

- [ ] **Step 5: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(ui): settings 카드 ④+⑤ 를 '시스템 & 토큰'으로 통합

CLI Hook + Webhook 재등록 + Railway API 토큰 + Railway Webhook URL 을
하나의 카드로 통합. Railway API 토큰을 .masked-field 패턴으로 통일
하여 👁️ mask-toggle 버튼 추가. form=settingsForm 속성으로 바깥 필드도
메인 폼에 포함."
```

---

## Task 5: 위험 구역을 별도 카드 ⑥ 로 분리

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. `/repos/{repo_name}/delete` POST 엔드포인트와 `onsubmit="return confirm(...)` 로직 불변.

- [ ] **Step 1: 카드 ⑤ "시스템 & 토큰" 내부의 기존 `<details><summary class="danger-summary">` 블록을 별도 카드로 분리**

카드 ⑤ body 끝에서 `<div class="s-divider"></div><details>...</details>` 블록을 제거하고, 카드 ⑤ 닫는 `</div></div>` 바로 아래에 새 카드 추가:

```html
<!-- ⑥ 위험 구역 (메인 form 외부) -->
<div class="s-card" style="margin-bottom:2rem;">
  <div class="s-card-hdr" style="background:linear-gradient(135deg,#991b1b,#dc2626)">
    <span class="hdr-icon">⚠️</span>
    <span class="hdr-title">위험 구역</span>
  </div>
  <div class="s-card-body">
    <details class="danger-summary-wrap">
      <summary class="danger-summary">⚠️ 위험한 작업 펼치기</summary>
      <div style="margin-top:.75rem;">
        <div class="toggle-row">
          <div class="toggle-info">
            <div class="t-title" style="color:var(--danger);">리포지토리 삭제</div>
            <div class="t-desc">SCAManager에서 이 리포지토리를 제거합니다.<br>
              GitHub Webhook과 모든 분석 이력이 영구 삭제됩니다.</div>
          </div>
          <form method="post" action="/repos/{{ repo_name }}/delete"
                onsubmit="return confirm('정말 「{{ repo_name }}」 리포지토리를 삭제하시겠습니까?\n\n모든 분석 이력과 GitHub Webhook이 영구 삭제됩니다.');">
            <button type="submit" style="background:var(--danger);color:#fff;border:none;border-radius:8px;padding:.6rem 1.1rem;font-weight:600;cursor:pointer;">
              🗑️ 삭제
            </button>
          </form>
        </div>
      </div>
    </details>
  </div>
</div>
```

- [ ] **Step 2: 전체 테스트 회귀**

```bash
python -m pytest tests/test_ui_router.py -v
```

기대: 기존 통과 테스트 유지.

- [ ] **Step 3: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(ui): settings 위험 구역을 독립 카드 ⑥ 로 분리

시스템 & 토큰 카드 내부의 <details danger-summary> 를 페이지 최하단
독립 카드로 분리. 빨간 그라디언트 헤더 + 기본 접힘 유지."
```

---

## Task 6: 프리셋 P1 — 펼침 diff 미리보기

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. PRESETS JS 객체 9개 필드 구성 불변. `applyPreset()`/`_setPair()`/`_showPresetToast()` 시그니처 불변. 신규 헬퍼 2종(`onPresetToggle` 변경, `renderPresetDiff` 추가). 기존 preset-table(정적 표시) 은 diff 테이블용 `<tbody id="preset-diff-*">` 로 교체된다.

- [ ] **Step 1: 프리셋 `<details>` 3종 내부를 diff 테이블 + 적용 버튼 구조로 교체**

각 프리셋 `<details>` 의 `<div class="preset-detail-body">` 를 다음 템플릿으로 교체 (minimal 예시 — standard/strict 도 동일 패턴, id 와 이름만 변경):

```html
<div class="preset-detail-body">
  <table class="preset-table">
    <thead>
      <tr style="font-size:11px;color:var(--text-muted);font-weight:600;">
        <td style="width:48%">필드</td>
        <td style="text-align:center;width:18%">현재값</td>
        <td style="text-align:center;width:6%"></td>
        <td style="text-align:right;width:28%">프리셋값</td>
      </tr>
    </thead>
    <tbody id="preset-diff-minimal"></tbody>
  </table>
  <p style="font-size:11px;color:var(--text-muted);margin-top:.5rem;line-height:1.5;">
    알림 채널 URL은 이 프리셋이 변경하지 않습니다.
  </p>
  <button type="button" class="btn-save-new" style="margin-top:.65rem;padding:.5rem;"
          onclick="applyPreset('minimal', document.getElementById('preset-minimal'))">
    이 프리셋 적용 →
  </button>
  <div class="pt-applied-label" id="pt-label-minimal" style="display:none">
    ✅ 적용됨 — 저장 버튼을 눌러주세요
  </div>
</div>
```

(standard / strict 는 `preset-diff-standard` / `preset-diff-strict` 및 `applyPreset('standard', ...)` / `applyPreset('strict', ...)` 로 변경)

- [ ] **Step 2: `onPresetToggle` 재정의 + `renderPresetDiff` 신규 추가**

기존 `function onPresetToggle(el, name) { ... }` 를 아래로 교체하고, 그 아래에 `renderPresetDiff` 를 신규 추가:

```javascript
function onPresetToggle(el, name) {
  if (!el.open) return;
  document.querySelectorAll('.preset-details').forEach(function(d) {
    if (d !== el) d.open = false;
  });
  renderPresetDiff(name, el);
}

function renderPresetDiff(name, el) {
  const p = PRESETS[name];
  if (!p) return;
  const tbody = document.getElementById('preset-diff-' + name);
  if (!tbody) return;

  const labels = {
    pr_review_comment: 'PR 코드리뷰 댓글',
    commit_comment: '커밋 코멘트',
    create_issue: '이슈 자동 생성',
    railway_deploy_alerts: 'Railway 빌드 실패 Issue',
    approve_mode: 'Approve 모드',
    auto_merge: '자동 Merge',
    approve_threshold: '승인 기준점',
    reject_threshold: '반려 기준점',
    merge_threshold: 'Merge 임계값',
  };

  function curVal(key) {
    if (key === 'approve_mode') {
      return document.getElementById('approveModeValue').value;
    }
    const el2 = document.querySelector('input[name="' + key + '"]');
    if (!el2) return '—';
    if (el2.type === 'checkbox') return el2.checked;
    return el2.value;
  }

  function fmt(val) {
    if (val === true) return '✅';
    if (val === false) return '⬜';
    if (val === 'disabled') return '🚫';
    if (val === 'auto') return '⚡ 자동';
    if (val === 'semi-auto') return '📱 반자동';
    return String(val);
  }

  let html = '';
  Object.keys(labels).forEach(function(key) {
    const cur = curVal(key);
    const next = p[key];
    const curNorm = (cur === 'true') ? true : (cur === 'false') ? false :
                    (!isNaN(cur) && cur !== '' ? Number(cur) : cur);
    const changed = String(curNorm) !== String(next);
    const arrow = changed ? '→' : '=';
    const rowStyle = changed ? '' : 'opacity:.45;';
    const nextStyle = changed ? 'font-weight:700;color:var(--accent);' : '';
    html +=
      '<tr style="' + rowStyle + '">' +
        '<td>' + labels[key] + '</td>' +
        '<td style="text-align:center">' + fmt(curNorm) + '</td>' +
        '<td style="text-align:center;font-weight:600;color:var(--text-muted)">' + arrow + '</td>' +
        '<td style="text-align:right;' + nextStyle + '">' + fmt(next) + '</td>' +
      '</tr>';
  });
  tbody.innerHTML = html;
}
```

- [ ] **Step 3: 테스트 실행 — `test_settings_has_preset_details_elements` 부분 통과**

```bash
python -m pytest tests/test_ui_router.py::test_settings_has_preset_details_elements -v
```

기대: `renderPresetDiff` 가 script 블록에 존재하므로 부분 통과 (`flashPresetChanges` 는 Task 7 에서 추가되므로 여전히 실패).

- [ ] **Step 4: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings 프리셋 P1 — 펼침 diff 미리보기 추가

프리셋 <details> 펼침 시 renderPresetDiff() 로 현재값 vs 프리셋값
diff 테이블 렌더. '이 프리셋 적용 →' 버튼으로 기존 자동 적용 대체.
변화 없는 필드는 흐리게 표시. PRESETS 객체·applyPreset 시그니처 불변."
```

---

## Task 7: 프리셋 P2 — 적용 하이라이트 + `@keyframes` CSS

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. `applyPreset()` 시그니처 불변 — 함수 마지막에 `flashPresetChanges(changedFields)` 호출 추가만 함.

- [ ] **Step 1: CSS `@keyframes preset-flash` 및 `.preset-just-applied` 클래스 추가**

`settings.html` 의 `<style>` 블록 끝(미디어 쿼리 직전)에 추가:

```css
  @keyframes preset-flash {
    0%   { box-shadow: 0 0 0 3px rgba(99,102,241,.5); background: rgba(99,102,241,.1); }
    100% { box-shadow: 0 0 0 0   rgba(99,102,241,0);  background: transparent; }
  }
  .preset-just-applied {
    animation: preset-flash 2.5s ease-out;
    border-radius: 8px;
  }
```

- [ ] **Step 2: `applyPreset()` 함수 최상단에 `changedFields` 수집 로직 삽입**

`applyPreset()` 함수 본체 맨 앞 (`const p = PRESETS[name]; if (!p) return;` 바로 다음) 에 추가:

```javascript
    const changedFields = [];
    const _cmp = {
      pr_review_comment: document.querySelector('input[name="pr_review_comment"]').checked,
      commit_comment: document.querySelector('input[name="commit_comment"]').checked,
      create_issue: document.querySelector('input[name="create_issue"]').checked,
      auto_merge: document.querySelector('input[name="auto_merge"]').checked,
      approve_mode: document.getElementById('approveModeValue').value,
      approve_threshold: Number(document.querySelector('input[name="approve_threshold"]').value),
      reject_threshold: Number(document.querySelector('input[name="reject_threshold"]').value),
      merge_threshold: Number(document.querySelector('input[name="merge_threshold"]').value),
    };
    const _rwAlert = document.querySelector('input[name="railway_deploy_alerts"]');
    if (_rwAlert) _cmp.railway_deploy_alerts = _rwAlert.checked;
    Object.keys(_cmp).forEach(function(k) {
      if (String(_cmp[k]) !== String(p[k])) changedFields.push(k);
    });
```

- [ ] **Step 3: `applyPreset()` 의 `_showPresetToast()` 호출 바로 위에 `flashPresetChanges(changedFields)` 추가**

```javascript
    flashPresetChanges(changedFields);
    _showPresetToast(PRESET_LABELS[name]);
```

- [ ] **Step 4: `flashPresetChanges()` 헬퍼 신규 추가**

`_showPresetToast()` 함수 바로 아래에 추가:

```javascript
  function flashPresetChanges(changedFields) {
    const FIELD_SELECTOR = {
      pr_review_comment: 'input[name="pr_review_comment"]',
      commit_comment: 'input[name="commit_comment"]',
      create_issue: 'input[name="create_issue"]',
      railway_deploy_alerts: 'input[name="railway_deploy_alerts"]',
      auto_merge: 'input[name="auto_merge"]',
      approve_mode: '.gate-btns',
      approve_threshold: 'input[name="approve_threshold"]',
      reject_threshold: 'input[name="reject_threshold"]',
      merge_threshold: 'input[name="merge_threshold"]',
    };
    changedFields.forEach(function(key) {
      const sel = FIELD_SELECTOR[key];
      if (!sel) return;
      const el = document.querySelector(sel);
      if (!el) return;
      const target = el.closest('.toggle-row, .threshold-row, .gate-btns') || el;
      target.classList.remove('preset-just-applied');
      void target.offsetWidth;
      target.classList.add('preset-just-applied');
      setTimeout(function() {
        target.classList.remove('preset-just-applied');
      }, 2500);
    });
  }
```

- [ ] **Step 5: 테스트 실행 — `test_settings_has_preset_details_elements` 전체 PASS**

```bash
python -m pytest tests/test_ui_router.py::test_settings_has_preset_details_elements -v
```

기대: PASS (3종 헬퍼 `onPresetToggle` + `renderPresetDiff` + `flashPresetChanges` 모두 존재).

- [ ] **Step 6: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings 프리셋 P2 — 적용 하이라이트 + @keyframes preset-flash

applyPreset() 시 변경 필드 목록 수집 → flashPresetChanges() 로 2.5초
동안 .preset-just-applied 클래스 + @keyframes preset-flash 애니메이션
적용. 기존 applyPreset 시그니처 불변."
```

---

## Task 8: 저장 오류 시 고급설정 아코디언 자동 펼침

**Files:**
- Modify: `src/templates/settings.html`

백엔드 불변. `?save_error=1` 쿼리 파라미터를 서버가 이미 세팅하므로 JS 에서 감지만 하면 됨.

- [ ] **Step 1: `<script>` 블록 하단의 기존 토스트 처리부 바로 위에 아코디언 자동 펼침 로직 추가**

`const toast = document.getElementById('saveToast');` 줄 바로 위에 추가:

```javascript
  (function() {
    const params = new URLSearchParams(location.search);
    if (params.get('save_error') === '1') {
      const adv = document.querySelector('.advanced-details');
      if (adv) adv.open = true;
    }
  })();
```

- [ ] **Step 2: 전체 테스트 회귀**

```bash
python -m pytest tests/test_ui_router.py -v
```

기대: 기존 통과 테스트 유지. (이 기능은 Playwright E2E 가 아닌 JS 로직이라 unit 테스트 회귀만 확인.)

- [ ] **Step 3: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings 저장 오류 시 고급설정 아코디언 자동 펼침

?save_error=1 쿼리 감지 시 .advanced-details.open=true 설정.
문제 필드(approve_threshold / reject_threshold) 위치가 접힌 아코디언
안에 있어 사용자가 오류 원인을 볼 수 없던 페인 포인트 해결."
```

---

## Task 9: 문서 갱신 (CLAUDE.md + STATE.md)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/STATE.md`

- [ ] **Step 1: `CLAUDE.md` 의 `### UI / 템플릿` 섹션에서 "settings.html 구조 규약" 항목 교체**

기존 `- **settings.html 구조 규약**: ...` 줄 전체를 아래로 교체:

```markdown
- **settings.html 구조 규약**: 의도 기반 6 카드 구성 — ① 빠른 설정(프리셋 3종 diff 미리보기) / ② PR 들어왔을 때(pr_review_comment·approve_mode·approve/reject_threshold·auto_merge·merge_threshold) / ③ 이벤트 후 피드백(commit_comment·create_issue·railway_deploy_alerts, toggle-switch 통일) / ④ 알림 채널(masked-field 6종) / ⑤ 시스템 & 토큰(CLI Hook + Webhook 재등록 + Railway API 토큰 + Railway Webhook URL) / ⑥ 위험 구역(리포 삭제, 기본 접힘). Progressive Disclosure 기존 JS 헬퍼 5종(`setApproveMode`·`toggleMergeThreshold`·`applyPreset`·`_setPair`·`_showPresetToast`) 시그니처 불변 + 신규 헬퍼 3종(`onPresetToggle`·`renderPresetDiff`·`flashPresetChanges`). 프리셋 P1 = 펼침 diff 미리보기, P2 = 적용 하이라이트(@keyframes preset-flash 2.5s). 알림 채널 URL은 프리셋이 건드리지 않음. 저장 오류 시 `?save_error=1` 쿼리 감지 → 고급설정 `<details open>` 자동 토글. 백엔드 필드명(pr_review_comment, approve_mode 등 14개) 및 PRESETS 9개 필드 구성 불변 원칙 — 5-way 동기화 체크리스트(ORM → dataclass → API body → 폼 → PRESETS) 적용 대상.
```

- [ ] **Step 2: `CLAUDE.md` 최하단 "현재 상태" 줄의 테스트 수치 갱신**

```markdown
최신 수치는 [docs/STATE.md](docs/STATE.md) 참조 — 단위 테스트 1110개 | E2E 38개 | pylint 10.00 | 커버리지 96.2%
```

> 실제 수치는 `make test` 결과로 교체. 스모크 테스트 3개 추가 시 1107 + 3 = 1110.

- [ ] **Step 3: `docs/STATE.md` 상단 테이블 테스트 수치 갱신**

```markdown
| 단위 테스트 | **1110개** | pytest (0 failed) |
```

- [ ] **Step 4: `docs/STATE.md` 에 그룹 9 추가**

`### 그룹 8 — 5-Round 감사 후속 테스트 보강 (2026-04-21)` 블록 바로 아래에 추가:

```markdown
### 그룹 9 — Settings 페이지 재설계 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 6 카드 재편 | ① 빠른 설정 / ② PR 들어왔을 때(auto_merge 이동) / ③ 이벤트 후 피드백(railway toggle-switch 통일) / ④ 알림 채널 / ⑤ 시스템 & 토큰 / ⑥ 위험 구역 | +2 |
| 프리셋 P1 diff | onPresetToggle 재정의 + renderPresetDiff() — 현재값 vs 프리셋값 diff 테이블 렌더 | — |
| 프리셋 P2 하이라이트 | flashPresetChanges() + @keyframes preset-flash 2.5s 애니메이션 | +1 |
| 저장 오류 UX | ?save_error=1 감지 시 .advanced-details.open=true 자동 펼침 | — |
| 백엔드 불변 | ORM·RepoConfigData·POST 핸들러·PRESETS 9개 필드·JS 헬퍼 5종 시그니처 전부 불변 | — |
```

- [ ] **Step 5: 커밋**

```bash
git add CLAUDE.md docs/STATE.md
git commit -m "docs: settings 재설계 — CLAUDE.md 구조 규약 + STATE.md 그룹 9 추가

6 카드 구성 + 프리셋 P1/P2 + JS 헬퍼 8종(기존 5 + 신규 3) 명시.
테스트 수치 1107 → 1110 갱신."
```

---

## Task 10: 완료 3-step (test + lint + push + STATE 최종 검증)

**Files:** (검사 + push 만)

- [ ] **Step 1: `make test` — 전체 테스트 통과 확인**

```bash
make test
```

기대: 1110개 PASS, 0 failed. (기존 1107 + 신규 3.)

- [ ] **Step 2: `make lint` — pylint 10.00 / flake8 0 / bandit HIGH 0 확인**

```bash
make lint
```

기대: `pylint 10.00/10` + `flake8 src/ → 0` + `bandit HIGH 0` 유지.

- [ ] **Step 3: `make test-cov` — 커버리지 96% 이상 유지**

```bash
make test-cov
```

기대: 커버리지 96.2% 이상 (`src/templates/` 는 커버리지 대상 아님, 스모크 테스트로 `src/ui/router.py` 99.4% 유지).

- [ ] **Step 4: git push**

```bash
git push origin main
```

- [ ] **Step 5: README.md 배지 동기화 확인**

`README.md` 14~18줄의 테스트 수·pylint·커버리지 배지가 `docs/STATE.md` 수치와 일치하는지 확인. 불일치 시 배지 교체 + 추가 커밋 + push.

- [ ] **Step 6: 최종 수치 검증**

```bash
python -m pytest tests/ -q
python -m pylint src/
python -m flake8 src/
```

기대: 모든 검사 통과.

---

## Verification (E2E 체크리스트)

```bash
make run   # 개발 서버 실행 (port 8000)
```

수동 검증 8단계:

1. `/repos/{repo}/settings` 접속 → **6 카드 위계 확인**: 상단부터 ① 빠른 설정 → (고급설정 아코디언 닫힘) → ④ 알림 채널 → ⑤ 시스템 & 토큰 → ⑥ 위험 구역. 고급설정 펼치면 ② PR 들어왔을 때 + ③ 이벤트 후 피드백 2컬럼 그리드 표시.
2. 프리셋 🌱 (최소) 카드 클릭 → **펼침 diff 미리보기** 렌더 확인: 현재값 vs `pr_review_comment=true` 등 9개 필드 diff 테이블, 변화 없는 필드 흐리게(opacity 낮음). "이 프리셋 적용 →" 버튼 표시.
3. "이 프리셋 적용 →" 클릭 → **P2 적용 하이라이트** 확인: 변경된 필드(토글/슬라이더)가 2.5초간 파란 glow 애니메이션. 2.5초 후 정상 복귀.
4. 카드 ③ "이벤트 후 피드백" 의 `railway_deploy_alerts` 토글이 **toggle-switch 모양**(44px × 24px 슬라이더) 으로 표시되는지 확인 (raw 체크박스 아님).
5. 카드 ⑤ "시스템 & 토큰" 의 Railway API 토큰 `.masked-field` 에서 **👁️ mask-toggle 버튼** 클릭 → password ↔ text 전환 동작 확인.
6. **저장 성공 경로**: 유효한 값으로 저장 → `?saved=1` → 녹색 토스트 표시 + 고급설정 아코디언 닫힌 상태 유지.
7. **저장 오류 경로**: `approve_threshold=50` + `reject_threshold=80` (승인 < 반려) 로 저장 → `?save_error=1` → 빨간 토스트 + **고급설정 아코디언 자동 펼침** 확인. 문제 필드(PR 카드의 슬라이더) 즉시 접근 가능.
8. **16개 form 필드 보존 확인** (curl 로 검증):
   ```bash
   curl -s "http://localhost:8000/repos/{repo}/settings" | grep -oE 'name="[a-z_]+"' | sort -u
   ```
   기대: 16개 이름 출력 — `approve_mode`, `approve_threshold`, `auto_merge`, `commit_comment`, `create_issue`, `custom_webhook_url`, `discord_webhook_url`, `email_recipients`, `merge_threshold`, `n8n_webhook_url`, `notify_chat_id`, `pr_review_comment`, `railway_api_token`, `railway_deploy_alerts`, `reject_threshold`, `slack_webhook_url`.

---

## Out of Scope (의도적 제외)

스펙 `docs/superpowers/specs/2026-04-21-settings-redesign-design.md` 의 "범위 밖(의도적 제외)" 4개 항목을 그대로 인용:

| 항목 | 제외 사유 | 권고 |
|------|----------|------|
| P3 영구 배지 (프리셋 상태 표시) | DB 스키마 확장 필요 | 별도 Phase |
| 알림 채널 암호화 통일 | 암호화 정책 결정 + 마이그레이션 필요 | 별도 Phase |
| `approve_mode` 3-버튼 접근성 (aria) | 독립적 개선 | 별도 이슈 |
| 오류 필드 직접 하이라이트 (서버 검증 실패 시) | 서버사이드 검증 응답 구조 확장 필요 | 별도 Phase |

이 Task-by-Task 플랜은 단일 파일(`src/templates/settings.html`) 수정 + 선택적 스모크 테스트 + 문서 갱신으로 **백엔드 불변 · 리뷰·롤백 용이성 · TDD 순서** 세 원칙을 모두 준수한다.
