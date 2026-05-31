"""Phase 2 PR-8 회귀 가드 — settings.html + admin 3 템플릿 다국어 렌더링.

Phase 2 PR-8 regression guards — settings + admin 3 templates multilingual rendering.

검증 범위 (Coverage):
1. admin_tenants.html — 헤더 / 테이블 헤더 7 / empty / info 4 li / kill-switch 안내
2. admin_rls_audit.html — 헤더 / 테이블 헤더 4 / status 2 / info 5 li
3. admin_operations.html — 헤더 / KPI 5 카드 (cache / api_cost / cache_dist / merge / latency) / info 5 li
4. settings.html — 헤더 / mode toggle / 6 카드 헤더 / save 버튼 / danger zone
5. en/ko/ja 3 언어 + locale=None default fallback
"""
from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    env = Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    register_i18n_filters(env)
    tmpl = env.get_template(template_name)
    return tmpl.render(**context)


class _FakeUser:
    github_login = "alice"
    display_name = "Alice"
    is_telegram_connected = False
    preferred_language = "ko"


# ── admin_tenants.html ──────────────────────────────────────────────────────


def _tenants_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "tenants": [],
        "total_tenants": 0,
    }
    base.update(overrides)
    return base


def test_admin_tenants_renders_korean_empty():
    out = _render("admin_tenants.html", locale="ko", **_tenants_ctx())
    assert "🏢 Tenant 인벤토리" in out
    assert "총 테넌트" in out
    assert "📭 등록된 테넌트가 없습니다" in out
    assert "💡 운영 안내" in out


def test_admin_tenants_renders_english_with_data():
    tenants = [type("T", (), {
        "id": 1, "github_login": "alice", "email": "a@b.c",
        "repo_count": 3, "analysis_count": 10,
        "last_analysis_at": datetime(2026, 5, 5, 10, 0),
        "created_at": datetime(2026, 1, 1),
    })()]
    out = _render(
        "admin_tenants.html", locale="en",
        **_tenants_ctx(tenants=tenants, total_tenants=1),
    )
    assert "🏢 Tenant Inventory" in out
    assert "Total tenants" in out
    assert "Last analysis" in out
    assert "Operations notes" in out


def test_admin_tenants_renders_japanese():
    out = _render("admin_tenants.html", locale="ja", **_tenants_ctx())
    assert "🏢 Tenant インベントリ" in out
    assert "総テナント" in out
    assert "登録されたテナントがありません" in out


# ── admin_rls_audit.html ────────────────────────────────────────────────────


def _rls_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "matrix": [
            {"table": "repositories", "pattern": "user_id", "since": "0026", "status": "applied"},
            {"table": "missing_table", "pattern": "tenant_id", "since": "TBD", "status": "missing"},
        ],
        "summary": {"total": 2, "applied": 1, "missing": 1},
    }
    base.update(overrides)
    return base


def test_admin_rls_audit_renders_korean():
    out = _render("admin_rls_audit.html", locale="ko", **_rls_ctx())
    assert "🛡️ RLS Policy Audit" in out
    assert "총 테이블" in out
    assert "✅ 적용 1건" in out
    assert "❌ 미적용 1건" in out
    assert ">테이블</th>" in out
    assert ">격리 패턴</th>" in out
    assert "💡 RLS 운영 안내" in out


def test_admin_rls_audit_renders_english():
    out = _render("admin_rls_audit.html", locale="en", **_rls_ctx())
    assert "🛡️ RLS Policy Audit" in out
    assert "Total tables" in out
    assert "✅ Applied 1" in out
    assert "❌ Missing 1" in out
    assert ">Table</th>" in out
    assert ">Isolation pattern</th>" in out


def test_admin_rls_audit_renders_japanese():
    out = _render("admin_rls_audit.html", locale="ja", **_rls_ctx())
    assert "🛡️ RLS Policy Audit" in out
    assert "総テーブル数" in out
    assert "✅ 適用 1件" in out
    assert ">分離パターン</th>" in out


# ── admin_operations.html ───────────────────────────────────────────────────


def _ops_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "days": 7,
        "kpi": {
            "cache": {"cache_hit_rate_pct": 85, "total_calls": 100,
                      "cache_read_tokens": 5000, "cache_creation_tokens": 1000},
            "api_cost": {"estimated_usd": 1.23, "input_tokens": 50000, "model": "claude-sonnet-4-6"},
            "merge": {"days": 7, "success_rate_pct": 75, "success_count": 6, "total_attempts": 8},
            "pipeline_latency": {"available": False, "p95_ms": 0, "reason": "Phase 2 보류"},
            # Phase 5 PR-17 (사이클 84) — i18n KPI 2 카드
            "language_distribution": {
                "distribution": {"en": 1, "ko": 1, "ja": 1},
                "percentages": {"en": 33.3, "ko": 33.3, "ja": 33.3},
                "total_users": 3,
            },
            "i18n_fallback": {
                "lookups_total": 100,
                "lookups_hit": 95,
                "lookups_fallback": 3,
                "lookups_missing": 2,
                "fallback_rate_pct": 5.0,
                "memory_only": True,
            },
        },
    }
    base.update(overrides)
    return base


def test_admin_operations_renders_korean():
    out = _render("admin_operations.html", locale="ko", **_ops_ctx())
    assert "📈 Operations 운영 모니터링" in out
    assert "최근 7일" in out
    assert "⚡ Cache Hit Rate" in out
    assert "💰 API 비용 추정" in out
    assert "📊 Cache 토큰 분포" in out
    assert "🔀 Merge Success" in out
    assert "🕒 Pipeline Latency" in out
    assert "📭 Phase 2 영역" in out  # latency pending
    assert "💡 Phase 1 운영 안내" in out


def test_admin_operations_renders_english():
    out = _render("admin_operations.html", locale="en", **_ops_ctx())
    assert "📈 Operations Monitoring" in out
    assert "Last 7 days" in out
    assert "💰 API cost estimate" in out
    assert "Last 7 days success rate" in out
    assert "📭 Phase 2 area" in out


def test_admin_operations_renders_japanese():
    out = _render("admin_operations.html", locale="ja", **_ops_ctx())
    assert "📈 Operations 運用モニタリング" in out
    assert "最近 7 日" in out
    assert "💰 API コスト推定" in out
    assert "最近 7 日成功率" in out


# ── settings.html (focused on visible text) ─────────────────────────────────


class _Cfg:
    def __init__(self, **kwargs):
        defaults = {
            "approve_mode": "auto",
            "approve_threshold": 75,
            "reject_threshold": 50,
            "merge_threshold": 75,
            "auto_merge": False,
            "auto_merge_issue_on_failure": False,
            "pr_review_comment": True,
            "commit_comment": False,
            "create_issue": False,
            "railway_deploy_alerts": False,
            "notify_chat_id": None,
            "discord_webhook_url": None,
            "slack_webhook_url": None,
            "email_recipients": None,
            "custom_webhook_url": None,
            "n8n_webhook_url": None,
        }
        defaults.update(kwargs)
        self.__dict__.update(defaults)


def _settings_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "repo_name": "owner/repo",
        "config": _Cfg(),
        "hook_ok": False,
        "hook_fail": False,
        "saved": False,
        "save_error": False,
        "railway_webhook_url": None,
        "railway_api_token_set": False,
        "webhook_stale": False,
        "onboarding_needed": False,
        "initial_mode": "simple",
    }
    base.update(overrides)
    return base


def test_settings_renders_korean_headers_and_save():
    """settings.html — 한국어 5 카드 헤더 + mode toggle + save (Q5 — 언어 카드 제거 사이클 84 회고).

    settings.html — Korean 5 card headers + mode toggle + save (Q5 — language card removed in Cycle 84 retro).
    """
    out = _render("settings.html", locale="ko", **_settings_ctx())
    # Title block
    assert "설정 — owner/repo" in out
    # H1 + back
    assert "← 상세" in out
    assert "리포지토리 설정" in out
    # Mode toggle
    assert "보기 모드" in out
    assert "✨ Simple" in out and "필수 항목만" in out
    assert "⚙️ Advanced" in out and "전체 설정" in out
    # 5 card headers (사이클 84 Q5 — 언어 카드 제거, 헤더 dropdown 단일 진실 소스)
    # 5 card headers (Cycle 84 Q5 — language card removed, header dropdown is single source of truth)
    assert ">언어 설정<" not in out  # 회귀 가드 / regression guard
    assert ">빠른 설정<" in out
    assert ">PR 동작 규칙<" in out
    assert ">이벤트 후 자동화<" in out
    assert ">알림 채널 (발신)<" in out
    assert ">통합 &amp; 인증 (수신)<" in out
    assert ">위험 구역<" in out
    # Save
    assert "💾 설정 저장" in out


def test_settings_renders_english_headers():
    out = _render("settings.html", locale="en", **_settings_ctx())
    assert "Settings — owner/repo" in out
    assert "← Detail" in out
    assert "Repository Settings" in out
    assert "View mode" in out
    assert "Essentials only" in out
    # 사이클 84 Q5 — Language card removed (header dropdown = single source of truth)
    assert ">Language<" not in out  # 회귀 가드 / regression guard
    assert ">Quick Settings<" in out
    assert ">PR Behavior Rules<" in out
    assert ">Post-event automation<" in out
    assert ">Outbound Channels<" in out
    assert ">Integration &amp; Auth (Inbound)<" in out
    assert ">Danger zone<" in out
    assert "💾 Save settings" in out


def test_settings_renders_japanese_headers():
    out = _render("settings.html", locale="ja", **_settings_ctx())
    assert "設定 — owner/repo" in out
    assert "← 詳細" in out
    assert "リポジトリ設定" in out
    assert "表示モード" in out
    # 사이클 84 Q5 — 言語設定 card removed (header dropdown = single source of truth)
    assert ">言語設定<" not in out  # 회귀 가드 / regression guard
    assert ">クイック設定<" in out
    assert ">PR 動作ルール<" in out
    assert ">イベント後の自動化<" in out
    assert ">通知チャンネル (発信)<" in out
    assert ">危険ゾーン<" in out
    assert "💾 設定を保存" in out


def test_settings_renders_korean_preset_names():
    """settings.html — 한국어 3 preset name + hint."""
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert ">최소</div>" in out and "PR 댓글만" in out
    assert ">표준</div>" in out and "균형잡힌 기본 설정" in out
    assert ">엄격</div>" in out and "보안·품질 최우선" in out
    assert "이 프리셋 적용 →" in out


def test_settings_renders_english_preset_names():
    out = _render("settings.html", locale="en", **_settings_ctx())
    assert ">Minimal</div>" in out and "PR comment only" in out
    assert ">Standard</div>" in out and "Balanced defaults" in out
    assert ">Strict</div>" in out and "Security &amp; quality first" in out
    assert "Apply this preset →" in out


def test_settings_renders_japanese_preset_names():
    out = _render("settings.html", locale="ja", **_settings_ctx())
    assert ">最小</div>" in out and "PR コメントのみ" in out
    assert ">標準</div>" in out and "バランスの取れたデフォルト" in out
    assert ">厳格</div>" in out and "セキュリティ・品質最優先" in out


def test_settings_renders_korean_pr_rules_toggles():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert "PR 코드리뷰 댓글" in out
    assert "자동 Merge" in out
    assert "Merge 임계값" in out
    assert "이상 → Merge" in out


def test_settings_renders_korean_gate_buttons():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert ">비활성" in out and ">자동" in out and ">반자동" in out
    assert "승인 기준점" in out
    assert "반려 기준점" in out
    assert "이상 → 승인" in out
    assert "미만 → 반려" in out


def test_settings_renders_english_gate_buttons():
    out = _render("settings.html", locale="en", **_settings_ctx())
    assert ">Off" in out and ">Auto" in out and ">Semi-auto" in out
    assert "Approve threshold" in out
    assert "Reject threshold" in out


def test_settings_renders_korean_post_event_toggles():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert "Push 이벤트" in out
    assert "커밋 코멘트" in out
    assert "점수 미달 시 Issue 생성" in out
    assert "Railway 배포" in out
    assert "Railway 빌드 실패 알림" in out


def test_settings_renders_korean_notify_labels():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert "Telegram Chat ID" in out  # 영문 키 보존
    assert "미설정 시 전역 Chat ID 사용" in out  # 한국어 hint
    assert "Telegram 계정 연결" in out
    assert "🔗 연결 코드 발급" in out


def test_settings_renders_korean_inbound():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert "GitHub 수신 Webhook" in out
    assert "🔗 GitHub 수신 Webhook 재등록" in out
    assert "CLI Hook (pre-push)" in out
    assert "Railway API 토큰" in out
    assert "Railway Webhook URL" in out


def test_settings_renders_korean_danger():
    out = _render("settings.html", locale="ko", **_settings_ctx())
    assert "위험 구역" in out
    assert "위험한 작업 펼치기" in out
    assert "리포지토리 삭제" in out
    assert "🗑️ 삭제" in out


def test_settings_renders_korean_onboarding_banner():
    """settings.html onboarding banner — 한국어."""
    out = _render("settings.html", locale="ko", **_settings_ctx(onboarding_needed=True))
    assert ">시작하세요<" in out
    assert "알림 채널 미설정" in out
    assert "분석 결과를 받으려면" in out


def test_settings_renders_english_webhook_stale_banner():
    """settings.html webhook_stale banner — 영문."""
    out = _render("settings.html", locale="en", **_settings_ctx(webhook_stale=True))
    assert "Webhook reinstall required" in out
    assert "Reinstall GitHub Webhook" in out


# ── locale fallback ─────────────────────────────────────────────────────────


def test_admin_tenants_locale_none_defaults_to_ko():
    out = _render("admin_tenants.html", **_tenants_ctx())
    assert "Tenant 인벤토리" in out  # ko default


def test_settings_locale_none_defaults_to_ko():
    out = _render("settings.html", **_settings_ctx())
    assert "리포지토리 설정" in out  # ko default


# ── 사이클 146/147 render-parity 가드 (회고 P1-4) ───────────────────────────
# Cycle 146/147 render-parity guards (retro P1-4) — settings 네임스페이스 키가
# JSON 에만 존재하고 템플릿이 오타 키를 호출하면 raw 키 노출 → 키 존재 테스트는
# 통과하나 렌더 가드는 실패. 사이클 144 #696 패턴을 사이클 146 키에 적용.


class _CfgWithModel(_Cfg):
    """`settings` 네임스페이스 model 카드 렌더에 필요한 review_model 속성 추가.

    Adds the review_model attribute required by the `settings` namespace model card.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("review_model", None)
        super().__init__(**kwargs)


# claude_models — 모델 선택 카드 <option> 렌더용 (settings.html:1082 for 루프)
# claude_models — feeds the model select card <option> loop (settings.html:1082)
_CLAUDE_MODELS = [
    {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6"},
    {"id": "claude-opus-4-1", "label": "Opus 4.1"},
]


def _settings_ctx_146(**overrides) -> dict:
    """사이클 146/147 키 렌더에 필요한 model 카드 + claude_models 포함 context."""
    base = _settings_ctx(config=_CfgWithModel(), claude_models=_CLAUDE_MODELS)
    base.update(overrides)
    return base


def test_settings_renders_korean_settings_namespace_keys():
    """settings 네임스페이스 키 (model 카드 + preset 라벨 + JS 필드) 한국어 렌더 검증.

    Renders Korean text for `settings` namespace keys (model card + preset labels + JS fields).
    오타 키면 raw 'settings.model_card_title' 등이 노출되어 실패.
    """
    out = _render("settings.html", locale="ko", **_settings_ctx_146())
    # model 카드 (사이클 146 — alembic 0032) / model card
    assert "AI 코드리뷰 모델" in out
    assert "전역 기본값 사용" in out
    assert "리포별 AI 리뷰 모델을 선택합니다" in out  # model_hint
    # JS 인라인 PRESET_LABELS (settings.html:1174~1176) — 렌더 출력에 문자열로 포함
    # JS inline PRESET_LABELS appear as literal strings in rendered output
    assert "minimal: '최소'" in out
    assert "standard: '표준'" in out
    assert "strict: '엄격'" in out
    # JS 인라인 field 라벨 (settings.html:1196~1204)
    assert "pr_review_comment: 'PR 코드리뷰 댓글'" in out
    assert "approve_threshold: '승인 기준점'" in out
    assert "merge_threshold: 'Merge 임계값'" in out
    # mode 라벨 (settings.html:1221~1222)
    assert "⚡ 자동" in out
    assert "📱 반자동" in out


def test_settings_renders_english_settings_namespace_keys():
    """settings 네임스페이스 키 영어 렌더 검증."""
    out = _render("settings.html", locale="en", **_settings_ctx_146())
    assert "AI Code Review Model" in out
    assert "Use global default" in out
    assert "minimal: 'Minimal'" in out
    assert "standard: 'Standard'" in out
    assert "strict: 'Strict'" in out


def test_settings_renders_japanese_settings_namespace_keys():
    """settings 네임스페이스 키 일본어 렌더 검증."""
    out = _render("settings.html", locale="ja", **_settings_ctx_146())
    assert "AIコードレビューモデル" in out
    assert "グローバルデフォルトを使用" in out
    assert "minimal: '最小'" in out


def test_settings_renders_save_toast_ok_when_saved():
    """saved=True 시 save_toast_ok 번역 텍스트 렌더 (settings.html:411~413).

    Renders save_toast_ok translation when saved=True (settings.html:411~413).
    조건부 블록이므로 saved=True context override 로 활성화.
    """
    out_ko = _render("settings.html", locale="ko", **_settings_ctx_146(saved=True))
    assert "✅ 설정이 저장되었습니다." in out_ko
    out_en = _render("settings.html", locale="en", **_settings_ctx_146(saved=True))
    assert "Settings saved." in out_en


def test_settings_renders_save_toast_err_when_save_error():
    """save_error=True 시 save_toast_err 번역 텍스트 렌더 (settings.html:415~417)."""
    out = _render("settings.html", locale="ko", **_settings_ctx_146(save_error=True))
    assert "❌ 저장에 실패했습니다" in out


def test_settings_renders_common_theme_labels():
    """base.html 상속 — common.theme 4 테마 라벨 렌더 (테마 키 커버, base.html:664~667).

    Inherits base.html — renders common.theme 4 theme labels (theme key coverage).
    settings 가 base 를 상속하므로 테마 메뉴가 함께 렌더됨 → 테마 키 사각 차단.
    """
    out_ko = _render("settings.html", locale="ko", **_settings_ctx_146())
    assert "다크 오로라" in out_ko  # common.theme.dark_label
    assert "파스텔" in out_ko  # common.theme.pastel_label
    out_en = _render("settings.html", locale="en", **_settings_ctx_146())
    assert "Dark Aurora" in out_en


def test_settings_no_raw_settings_namespace_keys_leak():
    """렌더 출력에 raw 'settings.<key>' 미노출 회귀 가드 (오타 키 탐지).

    Regression guard — no raw 'settings.<key>' leaks into rendered output (typo key detection).
    'settings_page.' 는 별도 정상 네임스페이스이므로 제외. data-* 속성명도 제외.
    """
    out = _render("settings.html", locale="ko", **_settings_ctx_146())
    # 'settings.' 직후 식별자 패턴 — 단 'settings_page.' / 'settings-' 는 정상
    import re

    leaks = re.findall(r"(?<![\w-])settings\.[a-z_]+", out)
    assert not leaks, f"raw settings 키 노출: {leaks}"
