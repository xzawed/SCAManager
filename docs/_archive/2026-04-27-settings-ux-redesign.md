# Settings UI/UX 리디자인 — B+A 하이브리드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 설정 페이지 6개 카드를 정보 흐름 방향(수신/발신) 기준으로 재구성하고 신규 사용자 온보딩 배너를 추가한다. "웹훅"이라는 단어가 수신/발신/Railway 세 맥락에서 혼용되던 문제를 구조적으로 해결한다.

**Architecture:** `settings.html` 프레젠테이션 레이어만 변경 — 카드 순서·명칭·그룹화 재편. `settings.py`에 `onboarding_needed` 플래그 추가(1줄). 폼 필드명·백엔드 저장 로직·JS 함수 시그니처는 전혀 변경하지 않는다.

**Tech Stack:** Jinja2 HTML template, Python/FastAPI route, pytest

---

## 변경 파일 요약

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `tests/unit/ui/test_settings_webhook_banner.py` | 수정 | 온보딩 배너 + 새 카드 구조 + 회귀 테스트 5개 추가 |
| `src/ui/routes/settings.py` | 수정 | `onboarding_needed` 변수 계산 후 template context에 추가 (3줄) |
| `src/templates/settings.html` | 수정 | 카드 구조 재편 (4개 구역 변경) |

## 새 카드 구조 (Before → After)

```
Before                          After
────────────────────────────    ────────────────────────────────────────
① 빠른 설정 (프리셋)      →    [온보딩 배너] (조건부, 새로 추가)
[고급 설정 아코디언]           ① 빠른 설정 (프리셋)  — 변경 없음
  ② PR 들어왔을 때         →   [고급 설정 아코디언]
  ③ 이벤트 후 피드백       →     ② 분석 동작 규칙  ← ②+③ 합침
④ 알림 채널               →   ③ 알림 발신 채널  ← 명칭 변경 + OTP 이동
⑤ 시스템 & 토큰           →   ④ 통합 & 연결  ← 명칭 변경 + Telegram OTP 제거
⑥ 위험 구역                    ⑤ 위험 구역  — 변경 없음
```

---

## Task 1: 테스트 먼저 작성 (Red)

**Files:**
- Modify: `tests/unit/ui/test_settings_webhook_banner.py`

- [ ] **Step 1: 기존 테스트 파일 끝에 5개 테스트 추가**

파일 `tests/unit/ui/test_settings_webhook_banner.py` 의 마지막 줄 뒤에 다음 코드를 추가한다.

```python
# ── 온보딩 배너 테스트 ────────────────────────────────────────────────────────

def _settings_get_custom(
    stale: bool = False,
    notify_chat_id: str | None = None,
    telegram_connected: bool = False,
):
    """알림 채널 설정 + Telegram 연결 여부를 커스터마이즈한 헬퍼.
    Helper to customise notification channel settings and Telegram link state.
    """
    from src.config_manager.manager import RepoConfigData  # pylint: disable=import-outside-toplevel
    from src.models.user import User as UserModel  # pylint: disable=import-outside-toplevel

    config = RepoConfigData(repo_full_name="owner/repo", notify_chat_id=notify_chat_id)
    custom_user = UserModel(
        id=99,
        github_id="99999",
        github_login="customuser",
        github_access_token="gho_custom",
        telegram_user_id="tg_123" if telegram_connected else None,
    )
    app.dependency_overrides[require_login] = lambda: custom_user
    try:
        with patch("src.ui.routes.settings.SessionLocal", return_value=_make_db_ctx()), \
             patch("src.ui.routes.settings.get_repo_config", return_value=config), \
             patch("src.repositories.repo_config_repo.find_by_full_name",
                   return_value=_make_config_orm()), \
             patch(
                 "src.ui.routes.settings._detect_stale_webhook",
                 new_callable=AsyncMock,
                 return_value=stale,
             ):
            return client.get("/repos/owner%2Frepo/settings")
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


def test_settings_shows_onboarding_banner_when_no_channel():
    """알림 채널 미설정 + Telegram 미연결 → 온보딩 배너 표시.
    Shows onboarding banner when no notification channel is configured and Telegram is not linked.
    """
    resp = _settings_get_custom(notify_chat_id=None, telegram_connected=False)
    assert resp.status_code == 200
    assert "onboardingBanner" in resp.text


def test_settings_no_onboarding_banner_when_notify_chat_id_set():
    """notify_chat_id 설정 시 → 온보딩 배너 미표시.
    No onboarding banner when notify_chat_id is configured.
    """
    resp = _settings_get_custom(notify_chat_id="-100123456", telegram_connected=False)
    assert resp.status_code == 200
    assert "onboardingBanner" not in resp.text


def test_settings_no_onboarding_banner_when_telegram_connected():
    """Telegram 연결 완료 시 → 온보딩 배너 미표시.
    No onboarding banner when Telegram account is linked.
    """
    resp = _settings_get_custom(notify_chat_id=None, telegram_connected=True)
    assert resp.status_code == 200
    assert "onboardingBanner" not in resp.text


def test_settings_new_card_structure_present():
    """새 카드 헤더 텍스트 확인 + 구 카드 헤더 부재 확인.
    Verify new card header text is present and old card headers are gone.
    """
    resp = _settings_get(stale=False)
    assert resp.status_code == 200
    # 새 카드 이름이 있어야 함
    assert "분석 동작 규칙" in resp.text
    assert "알림 발신 채널" in resp.text
    assert "통합 &amp; 연결" in resp.text
    # 구 카드 이름이 없어야 함
    assert "이벤트 후 피드백" not in resp.text
    assert "시스템 &amp; 토큰" not in resp.text


def test_settings_all_form_fields_present_after_restructure():
    """구조 개편 후 모든 폼 필드가 유지되는지 회귀 테스트.
    Regression: all form field names must survive the card restructure.
    """
    resp = _settings_get(stale=False)
    assert resp.status_code == 200
    required_fields = [
        "pr_review_comment", "auto_merge", "merge_threshold",
        "approve_threshold", "reject_threshold", "commit_comment",
        "create_issue", "railway_deploy_alerts", "notify_chat_id",
        "discord_webhook_url", "slack_webhook_url", "n8n_webhook_url",
        "custom_webhook_url", "email_recipients", "leaderboard_opt_in",
        "auto_merge_issue_on_failure",
    ]
    for field in required_fields:
        assert field in resp.text, f"Missing form field: {field}"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py -v -q 2>&1 | tail -20
```

Expected: 5개 신규 테스트 모두 FAILED
- `test_settings_shows_onboarding_banner_when_no_channel` → `onboardingBanner not in resp.text`
- `test_settings_new_card_structure_present` → `분석 동작 규칙 not in resp.text`

기존 2개 테스트(`test_settings_shows_stale_banner_when_check_suite_missing`, `test_settings_no_banner_when_check_suite_present`)는 계속 PASS여야 한다.

- [ ] **Step 3: 커밋**

```bash
git add tests/unit/ui/test_settings_webhook_banner.py
git commit -m "test(settings): onboarding banner + new card structure + regression tests"
```

---

## Task 2: Backend — `onboarding_needed` 플래그 추가

**Files:**
- Modify: `src/ui/routes/settings.py:154-162`

- [ ] **Step 1: `repo_settings` 함수의 return 직전에 변수 추가**

`src/ui/routes/settings.py` 의 `return templates.TemplateResponse(...)` 직전(현재 154번째 줄)을 아래처럼 수정한다.

```python
    # 알림 채널 미설정 + Telegram 미연결 → 온보딩 배너 표시
    # Show onboarding banner when no notification channel is configured and Telegram is not linked.
    onboarding_needed = (
        not config.notify_chat_id and
        not current_user.is_telegram_connected
    )

    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
        "hook_ok": bool(hook_ok), "hook_fail": bool(hook_fail),
        "saved": bool(saved), "save_error": bool(save_error),
        "current_user": current_user,
        "railway_webhook_url": railway_webhook_url,
        "railway_api_token_set": railway_api_token_set,
        "webhook_stale": webhook_stale,
        "onboarding_needed": onboarding_needed,
    })
```

- [ ] **Step 2: Hook 결과 확인 (src/ 파일 수정 후 자동 실행)**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py::test_settings_new_card_structure_present -v 2>&1 | tail -5
```

Expected: FAILED (아직 template을 안 바꿨으므로) — 정상

- [ ] **Step 3: 커밋**

```bash
git add src/ui/routes/settings.py
git commit -m "feat(settings): add onboarding_needed flag to template context"
```

---

## Task 3: Template — 온보딩 배너 추가

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: webhook_stale 배너 바로 뒤에 온보딩 배너 삽입**

파일에서 다음 블록을 찾는다:

```html
    {% if webhook_stale %}
    <div class="alert alert-warning alert-dismissible d-flex align-items-center mb-4" role="alert" id="webhookStaleBanner">
```

그 앞에 다음 HTML을 삽입한다:

```html
    {% if onboarding_needed %}
    <!-- 온보딩 배너 — 알림 채널 미설정 + Telegram 미연결 시 표시 -->
    <!-- Onboarding banner — shown when no notification channel and Telegram not linked -->
    <div class="s-card" id="onboardingBanner" style="margin-bottom:1rem;border:1.5px solid var(--accent);">
      <div class="s-card-hdr" style="background:linear-gradient(135deg,#6366f1,#8b5cf6)">
        <span class="hdr-icon">🚀</span>
        <span class="hdr-title">빠른 시작</span>
        <span class="hdr-badge">알림 채널 미설정</span>
      </div>
      <div class="s-card-body">
        <p style="font-size:13px;color:var(--text-muted);margin:0 0 .75rem;">분석 결과를 받으려면 아래 단계를 완료하세요.</p>
        <div style="display:flex;flex-direction:column;gap:.45rem;font-size:13px;">
          <a href="#notifyCard" style="color:var(--accent);font-weight:600;">
            ① 알림 채널 설정 → 아래 <strong>알림 발신 채널</strong>에서 Telegram 또는 다른 채널을 연결하세요
          </a>
          <span style="color:var(--text-muted);">
            ② 리뷰 수준 결정 → 위 <strong>빠른 설정</strong>에서 프리셋을 선택하세요 (선택 사항)
          </span>
        </div>
      </div>
    </div>
    {% endif %}

```

- [ ] **Step 2: ① 빠른 설정 카드에 id 추가 (앵커 링크용)**

파일에서:
```html
    <div class="s-card" style="margin-bottom:1rem;">
      <div class="s-card-hdr hdr-preset">
        <span class="hdr-icon">🚀</span>
        <span class="hdr-title">빠른 설정</span>
```

다음으로 교체:
```html
    <div class="s-card" id="presetCard" style="margin-bottom:1rem;">
      <div class="s-card-hdr hdr-preset">
        <span class="hdr-icon">🚀</span>
        <span class="hdr-title">빠른 설정</span>
```

- [ ] **Step 3: 온보딩 배너 테스트 통과 확인**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py::test_settings_shows_onboarding_banner_when_no_channel tests/unit/ui/test_settings_webhook_banner.py::test_settings_no_onboarding_banner_when_notify_chat_id_set tests/unit/ui/test_settings_webhook_banner.py::test_settings_no_onboarding_banner_when_telegram_connected -v 2>&1 | tail -10
```

Expected: 3개 모두 PASSED

- [ ] **Step 4: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(settings): add onboarding banner for new users without notification channel"
```

---

## Task 4: Template — ② 분석 동작 규칙 카드 (PR 들어왔을 때 + 이벤트 후 피드백 합침)

**Files:**
- Modify: `src/templates/settings.html`

고급 설정 아코디언 내부에서 두 카드(② PR 들어왔을 때, ③ 이벤트 후 피드백)를 단일 카드로 합친다.

- [ ] **Step 1: ② 카드 헤더 변경 (PR 들어왔을 때 → 분석 동작 규칙)**

찾는 내용:
```html
      <!-- ② PR 들어왔을 때 / When a PR arrives -->
      <div class="s-card">
        <div class="s-card-hdr hdr-gate">
          <span class="hdr-icon">📋</span>
          <span class="hdr-title">PR 들어왔을 때</span>
          <span class="hdr-badge" id="approveBadge">{{ config.approve_mode }}</span>
        </div>
```

교체 내용:
```html
      <!-- ② 분석 동작 규칙 / Analysis behavior rules -->
      <div class="s-card">
        <div class="s-card-hdr hdr-gate">
          <span class="hdr-icon">⚡</span>
          <span class="hdr-title">분석 동작 규칙</span>
          <span class="hdr-badge" id="approveBadge">{{ config.approve_mode }}</span>
        </div>
```

- [ ] **Step 2: ② 카드 본문에 "PR 이벤트" 섹션 레이블 추가**

② 카드 `s-card-body` 가 열리는 직후(`<div class="s-card-body">` 바로 다음)에 섹션 레이블을 추가한다.

찾는 내용:
```html
        <div class="s-card-body">

          <!-- PR 코드리뷰 댓글 / PR code review comment -->
```

교체 내용:
```html
        <div class="s-card-body">

          <div class="s-section-label">PR 이벤트</div>
          <!-- PR 코드리뷰 댓글 / PR code review comment -->
```

- [ ] **Step 3: ③ 이벤트 후 피드백 카드 내용을 ② 카드 끝에 합치고 ③ 카드 삭제**

현재 ② 카드는 `<!-- ③ 이벤트 후 피드백 -->` 바로 앞에서 닫힌다. 다음 패턴을 찾아 교체한다.

찾는 내용 (② 카드 닫힘 ~ ③ 카드 전체):
```html
        </div>
      </div>

      <!-- ③ 이벤트 후 피드백 / Post-event feedback -->
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

          <!-- 팀 인사이트 리더보드 옵트인 (기본 비활성) / Team Insights leaderboard opt-in (disabled by default) -->
          <div class="toggle-row" style="margin-top:.75rem;">
            <div class="toggle-info">
              <div class="t-title">팀 리더보드 공개</div>
              <div class="t-desc">이 리포를 팀 인사이트 리더보드에 포함<br>
                <span style="color:var(--c-warning,#f59e0b);font-size:.78rem;">옵션 기능 — 팀 합의 후 활성화 권장</span>
              </div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" name="leaderboard_opt_in" value="on"
                     {% if config.leaderboard_opt_in %}checked{% endif %}>
              <span class="toggle-track"></span>
            </label>
          </div>

        </div>
      </div>
```

교체 내용 (② 카드 안에 Push/Railway/팀 섹션 추가 후 닫음):
```html
          <div class="s-divider"></div>
          <div class="s-section-label">Push / 배포 이벤트</div>
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
          <div class="toggle-row">
            <div class="toggle-info">
              <div class="t-title">Railway 빌드 실패 알림</div>
              <div class="t-desc">Railway 빌드 실패 이벤트 수신 시<br>해당 리포에 로그 포함 Issue 자동 생성</div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" name="railway_deploy_alerts" id="railway_deploy_alerts" value="on"
                     {% if config.railway_deploy_alerts %}checked{% endif %}>
              <span class="toggle-track"></span>
            </label>
          </div>

          <div class="s-divider"></div>
          <div class="s-section-label">팀 설정</div>
          <!-- 팀 인사이트 리더보드 옵트인 (기본 비활성) / Team Insights leaderboard opt-in (disabled by default) -->
          <div class="toggle-row">
            <div class="toggle-info">
              <div class="t-title">팀 리더보드 공개</div>
              <div class="t-desc">이 리포를 팀 인사이트 리더보드에 포함<br>
                <span style="color:var(--c-warning,#f59e0b);font-size:.78rem;">옵션 기능 — 팀 합의 후 활성화 권장</span>
              </div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" name="leaderboard_opt_in" value="on"
                     {% if config.leaderboard_opt_in %}checked{% endif %}>
              <span class="toggle-track"></span>
            </label>
          </div>

        </div>
      </div>
```

- [ ] **Step 4: 카드 구조 테스트 확인**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py::test_settings_new_card_structure_present tests/unit/ui/test_settings_webhook_banner.py::test_settings_all_form_fields_present_after_restructure -v 2>&1 | tail -10
```

Expected: 2개 모두 PASSED (분석 동작 규칙 present, 이벤트 후 피드백 absent, 전체 필드 present)

- [ ] **Step 5: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(settings): merge PR/push cards into 분석 동작 규칙"
```

---

## Task 5: Template — ③ 알림 발신 채널 (알림 채널 카드 이름 변경 + Telegram OTP 이동)

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: 알림 채널 카드 헤더 변경 + id 추가**

찾는 내용:
```html
    <div class="s-card notify-full">
        <div class="s-card-hdr hdr-notify">
          <span class="hdr-icon">🔔</span>
          <span class="hdr-title">알림 채널</span>
          <span class="hdr-badge">선택</span>
        </div>
        <div class="s-card-body">
          <div class="channel-grid">
```

교체 내용:
```html
    <div class="s-card notify-full" id="notifyCard">
        <div class="s-card-hdr hdr-notify">
          <span class="hdr-icon">🔔</span>
          <span class="hdr-title">알림 발신 채널</span>
          <span class="hdr-badge">SCAManager → 외부</span>
        </div>
        <div class="s-card-body">
          <div class="s-section-label">메신저 / 이메일</div>
          <div class="channel-grid">
```

- [ ] **Step 2: Telegram Chat ID 필드 다음에 Telegram OTP 섹션 삽입**

Telegram Chat ID `field-row` 닫힘 태그 바로 뒤에 OTP 섹션을 삽입한다.

찾는 내용 (Telegram Chat ID 필드 끝부분):
```html
              <div class="masked-field">
                <input class="field-input" type="password" name="notify_chat_id"
                       value="{{ config.notify_chat_id or '' }}"
                       placeholder="-100xxxxxxxxx" autocomplete="off">
                <button type="button" class="mask-toggle" onclick="toggleFieldMask(this)"
                        aria-label="값 보이기/숨기기">👁️</button>
              </div>
            </div>
            <div class="field-row adv-only">
              <label class="field-label">Discord Webhook</label>
```

교체 내용:
```html
              <div class="masked-field">
                <input class="field-input" type="password" name="notify_chat_id"
                       value="{{ config.notify_chat_id or '' }}"
                       placeholder="-100xxxxxxxxx" autocomplete="off">
                <button type="button" class="mask-toggle" onclick="toggleFieldMask(this)"
                        aria-label="값 보이기/숨기기">👁️</button>
              </div>
            </div>

            <!-- Telegram 계정 연결 OTP (⑤에서 이동) / Telegram account linking OTP (moved from system card) -->
            <div class="field-row">
              <label class="field-label">Telegram 계정 연결</label>
              <div id="telegram-connect-section">
                {% if current_user.is_telegram_connected %}
                <p class="text-success" style="font-size:13px;margin:0;">✅ Telegram 계정이 연결되어 있습니다.</p>
                {% else %}
                <p style="font-size:13px;color:var(--text-muted);margin-bottom:.5rem;">
                  Telegram 봇에서 /connect 명령으로 계정을 연결하세요.
                </p>
                <button type="button" class="hook-btn" id="issueTelegramOtp">
                  🔗 연결 코드 발급 / Issue Code
                </button>
                <div id="telegramOtpDisplay" style="display:none;margin-top:.65rem;">
                  <code id="telegramOtpCode" style="font-size:1.4rem;font-weight:700;letter-spacing:.12em;"></code>
                  <span style="font-size:12px;color:var(--text-muted);margin-left:.5rem;">
                    (<span id="telegramOtpCountdown">5:00</span> 후 만료)
                  </span>
                  <p style="font-size:11px;color:var(--text-muted);margin-top:.35rem;margin-bottom:0;">
                    이전 코드는 무효화됩니다. / Previous codes are invalidated.
                  </p>
                </div>
                <script>
                  // Telegram OTP 발급 버튼 — 알림 발신 채널 카드로 이동 (B+A 리디자인)
                  // Telegram OTP button — moved to notification channel card (B+A redesign)
                  (function () {
                    var btn = document.getElementById('issueTelegramOtp');
                    if (!btn) { return; }
                    btn.addEventListener('click', async function () {
                      btn.disabled = true;
                      try {
                        var resp = await fetch('/api/users/me/telegram-otp', { method: 'POST' });
                        if (!resp.ok) { btn.disabled = false; return; }
                        var data = await resp.json();
                        document.getElementById('telegramOtpCode').textContent = data.otp;
                        document.getElementById('telegramOtpDisplay').style.display = '';
                        var remaining = data.ttl_minutes * 60;
                        var cd = document.getElementById('telegramOtpCountdown');
                        var timer = setInterval(function () {
                          remaining -= 1;
                          var m = Math.floor(remaining / 60);
                          var s = remaining % 60;
                          cd.textContent = m + ':' + (s < 10 ? '0' : '') + s;
                          if (remaining <= 0) {
                            clearInterval(timer);
                            document.getElementById('telegramOtpDisplay').style.display = 'none';
                            btn.disabled = false;
                          }
                        }, 1000);
                      } catch (e) {
                        console.error('Telegram OTP issuance failed:', e);
                        btn.disabled = false;
                      }
                    });
                  }());
                </script>
                {% endif %}
              </div>
            </div>

            <div class="field-row adv-only">
              <label class="field-label">Discord Webhook</label>
```

- [ ] **Step 3: n8n Webhook 필드 앞에 "자동화 연동 Webhook (발신)" 섹션 레이블 추가**

찾는 내용:
```html
            <div class="field-row adv-only">
              <label class="field-label">n8n Webhook</label>
```

교체 내용:
```html
            <div class="field-row adv-only">
              <div class="s-section-label" style="grid-column:1/-1;margin-bottom:.25rem;">자동화 연동 Webhook (발신)</div>
            </div>
            <div class="field-row adv-only">
              <label class="field-label">n8n Webhook</label>
```

- [ ] **Step 4: channel-grid 닫힘 태그 뒤에 있는 `</div><!-- /settings-grid -->` 앞 구조 확인**

channel-grid 이후 `</div>` 닫힘 순서가 올바른지 확인한다:
```html
          </div>  ← channel-grid 닫힘
        </div>    ← s-card-body 닫힘
      </div>      ← s-card notify-full 닫힘
    </div>        ← settings-grid 닫힘
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py -v 2>&1 | tail -15
```

Expected: 전체 7개 테스트 모두 PASSED

- [ ] **Step 6: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(settings): rename 알림 채널 → 알림 발신 채널, move Telegram OTP"
```

---

## Task 6: Template — ④ 통합 & 연결 (시스템 & 토큰 카드 재편)

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: ⑤ 카드 헤더 변경**

찾는 내용:
```html
  <div class="s-card" style="margin-bottom:1rem;">
    <div class="s-card-hdr hdr-hook">
      <span class="hdr-icon">🔧</span>
      <span class="hdr-title">시스템 &amp; 토큰</span>
    </div>
```

교체 내용:
```html
  <div class="s-card" style="margin-bottom:1rem;">
    <div class="s-card-hdr hdr-hook">
      <span class="hdr-icon">🔗</span>
      <span class="hdr-title">통합 &amp; 연결</span>
    </div>
```

- [ ] **Step 2: CLI Hook 섹션 레이블 → GitHub 수신 Webhook 섹션 추가 + 버튼 레이블 변경**

찾는 내용:
```html
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
```

교체 내용:
```html
      <div class="s-section-label">GitHub 수신 Webhook</div>
      <div class="hook-btns" style="margin-bottom:.5rem;">
        <button type="submit" class="hook-btn" form="reinstall_webhook_form"
                data-reinstall-webhook>🔗 GitHub 수신 Webhook 재등록</button>
      </div>
      <span class="field-hint">GitHub이 SCAManager로 push·PR·check_suite 이벤트를 전송합니다.</span>

      <div class="s-divider"></div>
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
      </div>
```

- [ ] **Step 3: Railway 섹션 레이블 추가 (Railway API 토큰 앞)**

찾는 내용:
```html
      <div class="s-divider"></div>

      <div class="s-section-label">Railway API 토큰 <span class="field-hint" style="font-weight:400;text-transform:none;letter-spacing:0;">로그 조회용</span></div>
```

교체 내용:
```html
      <div class="s-divider"></div>

      <div class="s-section-label">Railway 연동</div>
      <div class="s-section-label" style="font-size:10px;text-transform:none;letter-spacing:0;color:var(--text-muted);margin-top:-.4rem;margin-bottom:.6rem;">API 토큰 (로그 조회용)</div>
```

- [ ] **Step 4: Telegram 연결 섹션 삭제 (③으로 이동됐으므로)**

찾아서 삭제할 블록:
```html
      <div class="s-divider"></div>

      <!-- Telegram 연결 서브섹션 / Telegram Connection subsection -->
      <div class="s-section-label">Telegram 연결 / Telegram Connection</div>
      <div class="mb-4" id="telegram-connect-section">
        {% if current_user.is_telegram_connected %}
        <p class="text-success mb-2" style="font-size:13px;">✅ Telegram 계정이 연결되어 있습니다.</p>
        {% else %}
        <p style="font-size:13px;color:var(--text-muted);margin-bottom:.6rem;">
          Telegram 봇에서 /connect 명령으로 계정을 연결하세요.
        </p>
        <button type="button" class="hook-btn" id="issueTelegramOtp">
          🔗 연결 코드 발급 / Issue Code
        </button>
        <div id="telegramOtpDisplay" style="display:none;margin-top:.65rem;">
          <code id="telegramOtpCode" style="font-size:1.4rem;font-weight:700;letter-spacing:.12em;"></code>
          <span style="font-size:12px;color:var(--text-muted);margin-left:.5rem;">
            (<span id="telegramOtpCountdown">5:00</span> 후 만료)
          </span>
          <p style="font-size:11px;color:var(--text-muted);margin-top:.35rem;margin-bottom:0;">
            이전 코드는 무효화됩니다. / Previous codes are invalidated.
          </p>
        </div>

        <script>
          // Telegram OTP 발급 버튼 클릭 핸들러 — 미연결 상태에서만 렌더링
          // Click handler for Telegram OTP issuance — rendered only when not connected.
          (function () {
            var btn = document.getElementById('issueTelegramOtp');
            if (!btn) { return; }
            btn.addEventListener('click', async function () {
              btn.disabled = true;
              try {
                var resp = await fetch('/api/users/me/telegram-otp', { method: 'POST' });
                if (!resp.ok) { btn.disabled = false; return; }
                var data = await resp.json();
                // OTP 코드 표시
                // Display the issued OTP code.
                document.getElementById('telegramOtpCode').textContent = data.otp;
                document.getElementById('telegramOtpDisplay').style.display = '';

                // 카운트다운 타이머 (5분) — Countdown timer (5 minutes).
                var remaining = data.ttl_minutes * 60;
                var cd = document.getElementById('telegramOtpCountdown');
                var timer = setInterval(function () {
                  remaining -= 1;
                  var m = Math.floor(remaining / 60);
                  var s = remaining % 60;
                  cd.textContent = m + ':' + (s < 10 ? '0' : '') + s;
                  if (remaining <= 0) {
                    clearInterval(timer);
                    // 만료 시 OTP 표시 영역 숨김 및 버튼 재활성화
                    // Hide OTP display and re-enable button upon expiry.
                    document.getElementById('telegramOtpDisplay').style.display = 'none';
                    btn.disabled = false;
                  }
                }, 1000);
              } catch (e) {
                // 네트워크 오류 등 예외 발생 시 버튼을 재활성화하여 재시도 허용
                // Re-enable button on network or other errors so the user can retry.
                console.error('Telegram OTP issuance failed:', e);
                btn.disabled = false;
              }
            });
          }());
        </script>
        {% endif %}
      </div>
```

위 블록을 완전히 삭제한다 (③ 알림 발신 채널 카드에 동일 코드가 있으므로).

- [ ] **Step 5: webhook stale 배너의 버튼 레이블 변경**

찾는 내용:
```html
      <button type="button" onclick="document.querySelector('[data-reinstall-webhook]')?.click();" class="btn btn-sm btn-warning ms-auto">Webhook 재등록</button>
```

교체 내용:
```html
      <button type="button" onclick="document.querySelector('[data-reinstall-webhook]')?.click();" class="btn btn-sm btn-warning ms-auto">GitHub 수신 Webhook 재등록</button>
```

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
python -m pytest tests/unit/ui/test_settings_webhook_banner.py -v 2>&1 | tail -15
```

Expected: 7개 모두 PASSED

- [ ] **Step 7: 커밋**

```bash
git add src/templates/settings.html
git commit -m "refactor(settings): rename 시스템&토큰 → 통합&연결, clarify GitHub inbound webhook"
```

---

## Task 7: 전체 검증 + PR

- [ ] **Step 1: 전체 테스트 실행**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

Expected: `1709 passed` (또는 그 이상), 0 failed

- [ ] **Step 2: lint 검사**

```bash
python -m pylint src/ui/routes/settings.py src/templates/ 2>&1 | tail -5
```

Expected: 에러 없음 (templates는 HTML이므로 pylint 미적용, settings.py만 검사)

- [ ] **Step 3: PR 생성**

```bash
git push -u origin feat/settings-ux-redesign
gh pr create \
  --title "feat(settings): UI/UX 리디자인 — B+A 하이브리드 (수신/발신 웹훅 분리 + 온보딩 배너)" \
  --body "## Summary

- 설정 페이지 카드 구조를 데이터 흐름 방향(수신/발신) 기준으로 재편
- ② PR/③ 피드백 카드 → **② 분석 동작 규칙** 단일 카드로 합침 (PR 이벤트 + Push 이벤트 서브섹션)
- ④ 알림 채널 → **③ 알림 발신 채널 (SCAManager → 외부)** 명칭 변경, Telegram OTP 이동
- ⑤ 시스템 & 토큰 → **④ 통합 & 연결**, GitHub 수신 Webhook 섹션 명시, Telegram OTP 제거
- 신규 사용자에게 **온보딩 배너** 조건부 표시 (알림 채널 미설정 + Telegram 미연결 시)
- 백엔드 로직·폼 필드명 변경 없음 — 순수 프레젠테이션 레이어 변경

## Test plan
- [ ] 온보딩 배너 3가지 조건 테스트 통과
- [ ] 새 카드 구조 헤더 검증 테스트 통과
- [ ] 폼 필드 회귀 테스트 통과 (16개 필드 전부 유지)
- [ ] 전체 테스트 스위트 1709 passed

🤖 Generated with [Claude Code](https://claude.ai/claude-code)"
```

---

## 자가 검토 (Self-Review)

### 1. 스펙 커버리지
- ✅ 온보딩 배너 (조건부 표시) — Task 3
- ✅ ② 분석 동작 규칙 (PR + Push 합침) — Task 4
- ✅ ③ 알림 발신 채널 명칭 변경 + Telegram OTP 이동 — Task 5
- ✅ ④ 통합 & 연결 명칭 변경 + GitHub 수신 Webhook 명시 — Task 6
- ✅ webhook stale 배너 버튼 레이블 변경 — Task 6 Step 5
- ✅ 폼 필드 회귀 테스트 — Task 1

### 2. Placeholder 검사
없음 — 모든 단계에 완전한 코드 포함.

### 3. 타입 일관성
- `onboarding_needed: bool` — settings.py에서 계산, template에서 `{% if onboarding_needed %}` 로 사용 — 일치.
- `telegram-connect-section` id — Task 5에서 새 위치에 존재, Task 6에서 구 위치 삭제 — 중복 없음.
- `data-reinstall-webhook` 속성 — Task 6 Step 2에서 추가, Task 6 Step 5 stale 배너에서 참조 — 일치.
