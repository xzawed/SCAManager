import os
import pytest


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test_secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")

    # 기존 캐시된 settings 인스턴스 우회
    import importlib
    import src.config as cfg
    importlib.reload(cfg)

    assert cfg.settings.github_webhook_secret == "test_secret"
    assert cfg.settings.telegram_chat_id == "-100123"


# ---------------------------------------------------------------------------
# 온프레미스 PostgreSQL 전환을 위한 신규 설정 필드 테스트 (Task 2)
# ---------------------------------------------------------------------------

def _reload_settings(monkeypatch, extra: dict | None = None) -> "Settings":
    """공통 필수 환경변수를 설정한 뒤 src.config를 reload해 신선한 Settings 반환."""
    import importlib
    import src.config as cfg

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    if extra:
        for k, v in extra.items():
            monkeypatch.setenv(k, v)
    importlib.reload(cfg)
    return cfg.settings


def test_db_sslmode_default_empty(monkeypatch):
    # db_sslmode 필드는 기본값이 빈 문자열이어야 한다
    # db_sslmode field default must be an empty string.
    s = _reload_settings(monkeypatch)
    assert s.db_sslmode == ""


def test_db_force_ipv4_default_false(monkeypatch):
    # db_force_ipv4 필드는 기본값이 False여야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_force_ipv4 is False


def test_claude_review_max_tokens_default_8192(monkeypatch):
    # 🔴 감사 단일출처: AI 리뷰 max_tokens 기본값은 8192 여야 한다 (#931 — 1500 절단 parse_error
    # 만성 실패 근본 수정). 이 기본값이 낮아지면 한국어 JSON 응답 절단으로 회귀하므로 가드.
    # Audit single-source: AI review max_tokens default must be 8192 (#931 root fix for chronic
    # 1500-truncation parse_error). Lowering it regresses Korean JSON truncation — guard it.
    s = _reload_settings(monkeypatch)
    assert s.claude_review_max_tokens == 8192


def test_claude_review_max_tokens_env_override(monkeypatch):
    # env 로 재정의 가능 + ge=1 제약 (config.py Field(default=8192, ge=1))
    s = _reload_settings(monkeypatch, {"CLAUDE_REVIEW_MAX_TOKENS": "4096"})
    assert s.claude_review_max_tokens == 4096


def test_db_pool_size_default_5(monkeypatch):
    # db_pool_size 필드는 기본값이 5여야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_size == 5


def test_db_max_overflow_default_10(monkeypatch):
    # db_max_overflow 필드는 기본값이 10이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_max_overflow == 10


def test_db_pool_timeout_default_30(monkeypatch):
    # db_pool_timeout 필드는 기본값이 30이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_timeout == 30


def test_db_pool_recycle_default_1800(monkeypatch):
    # db_pool_recycle 필드는 기본값이 1800이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_recycle == 1800


def test_db_sslmode_reads_from_env(monkeypatch):
    # DB_SSLMODE 환경변수 설정 시 해당 값이 반영되어야 한다
    # When DB_SSLMODE env var is set, that value must be reflected.
    s = _reload_settings(monkeypatch, extra={"DB_SSLMODE": "require"})
    assert s.db_sslmode == "require"


def test_db_force_ipv4_reads_from_env(monkeypatch):
    # DB_FORCE_IPV4=true 환경변수 설정 시 True로 반영되어야 한다
    s = _reload_settings(monkeypatch, extra={"DB_FORCE_IPV4": "true"})
    assert s.db_force_ipv4 is True


def test_verifier_base_url_default_empty(monkeypatch):
    # verifier_base_url 기본값은 빈 문자열 → OpenAI 기본 엔드포인트 (회귀 방지)
    # verifier_base_url default is empty → OpenAI default endpoint (regression guard)
    s = _reload_settings(monkeypatch)
    assert s.verifier_base_url == ""


def test_verifier_base_url_reads_from_env(monkeypatch):
    # VERIFIER_BASE_URL 설정 시 반영 → 무료/저가 OpenAI-호환 공급자(GitHub Models 등) 전환
    # When VERIFIER_BASE_URL is set, it is reflected → switch to free/cheap OpenAI-compatible provider
    s = _reload_settings(monkeypatch, extra={"VERIFIER_BASE_URL": "https://models.github.ai/inference"})
    assert s.verifier_base_url == "https://models.github.ai/inference"


def test_db_pool_size_reads_from_env(monkeypatch):
    # DB_POOL_SIZE 환경변수 설정 시 해당 정수값이 반영되어야 한다
    # When DB_POOL_SIZE env var is set, the integer value must be reflected.
    s = _reload_settings(monkeypatch, extra={"DB_POOL_SIZE": "20"})
    assert s.db_pool_size == 20


def test_non_supabase_url_no_ssl_added(monkeypatch):
    # 일반 온프레미스 URL에는 sslmode가 자동으로 추가되지 않아야 한다
    # A plain on-premises URL must not have sslmode added automatically.
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@localhost/db"},
    )
    assert "sslmode" not in s.database_url


def test_supabase_url_ssl_added(monkeypatch):
    # supabase.co URL에는 기존 동작대로 sslmode=require가 자동 추가되어야 한다
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@db.abc.supabase.co/postgres"},
    )
    assert "sslmode=require" in s.database_url


def test_supabase_pooler_url_ssl_added(monkeypatch):
    # 🔴 회귀 가드: pooler 호스트(aws-N...pooler.supabase.com, .com TLD)에도 sslmode=require 자동 추가.
    # Railway IPv4-only egress 는 pooler(.supabase.com) 강제 → 매칭이 '.supabase.co' 만으로 좁혀지면
    # pooler SSL 누락 → 마이그레이션/연결 운영 장애. _normalize_pg_url 의 hostname endswith 매칭을 잠근다.
    # Regression guard: pooler host (.supabase.com TLD) must also auto-add sslmode=require.
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"},
    )
    assert "sslmode=require" in s.database_url


def test_supabase_substring_in_credential_no_ssl(monkeypatch):
    # 🔴 회귀 가드: hostname 파싱 — 'supabase.com' 이 host 가 아니라 credential 에 있으면 SSL 미강제.
    # full-URL substring 매칭이었다면 SSL 이 오강제됐을 케이스(실제 host=onprem-db.internal).
    # Host-parsing guard: 'supabase.com' in the credential (not the host) must NOT force SSL.
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://supabase.com:pw@onprem-db.internal:5432/app"},
    )
    assert "sslmode" not in s.database_url


def test_supabase_url_preserves_existing_query(monkeypatch):
    # 🔴 회귀 가드: 기존 query 가 있으면 '&' 로 병합(? 중복 금지), 이미 sslmode 있으면 중복 추가 안 함.
    # Existing query merges with '&' (no double '?'); an existing sslmode param is not duplicated.
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@db.abc.supabase.co/postgres?connect_timeout=10"},
    )
    assert s.database_url.endswith("?connect_timeout=10&sslmode=require")
    s2 = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@db.abc.supabase.co/postgres?sslmode=disable"},
    )
    assert s2.database_url.count("sslmode") == 1


# ---------------------------------------------------------------------------
# MIGRATION_DATABASE_URL — RLS Phase 4 마이그레이션 credential 분리 (owner role)
# MIGRATION_DATABASE_URL — RLS Phase 4 migration credential separation (owner role)
#   alembic/env.py 가 effective_migration_url 을 sqlalchemy.url 로 사용:
#   설정 시 owner credential 로 마이그레이션, 미설정 시 DATABASE_URL 재사용(현행 보존).
# ---------------------------------------------------------------------------


def test_migration_database_url_default_empty(monkeypatch):
    # MIGRATION_DATABASE_URL 미설정 시 빈 문자열이어야 한다 (inert-when-unset).
    # Unset MIGRATION_DATABASE_URL must default to an empty string (inert-when-unset).
    s = _reload_settings(monkeypatch)
    assert s.migration_database_url == ""


def test_migration_database_url_normalizes_postgres_scheme(monkeypatch):
    # postgres:// → postgresql:// 정규화 (database_url 과 동일 validator).
    # postgres:// → postgresql:// normalization (same validator as database_url).
    s = _reload_settings(
        monkeypatch,
        extra={"MIGRATION_DATABASE_URL": "postgres://owner:pw@localhost/db"},
    )
    assert s.migration_database_url.startswith("postgresql://")


def test_migration_database_url_supabase_ssl_added(monkeypatch):
    # supabase.co 호스트면 sslmode=require 자동 추가 (database_url 과 동일).
    # supabase.co host auto-adds sslmode=require (same as database_url).
    s = _reload_settings(
        monkeypatch,
        extra={"MIGRATION_DATABASE_URL": "postgresql://owner:pw@db.abc.supabase.co/postgres"},
    )
    assert "sslmode=require" in s.migration_database_url


def test_effective_migration_url_normalizes_postgres_scheme(monkeypatch):
    # 🔴 회귀 가드: MIGRATION_DATABASE_URL=postgres://... → effective_migration_url 도 postgresql:// 시작.
    # field validator(정규화) + property(precedence) 결합을 단일 케이스로 봉인 (기존엔 transitive 만 보장).
    # Combined field-normalize + property-precedence in one case (previously only transitive).
    s = _reload_settings(
        monkeypatch,
        extra={"MIGRATION_DATABASE_URL": "postgres://owner:pw@db.abc.supabase.co/postgres"},
    )
    assert s.effective_migration_url.startswith("postgresql://")
    assert "sslmode=require" in s.effective_migration_url  # supabase 호스트 SSL 도 property 통과 확인


def test_effective_migration_url_falls_back_to_database_url(monkeypatch):
    # MIGRATION_DATABASE_URL 미설정 → effective_migration_url 은 database_url 과 동일 (현행 동작).
    # Unset → effective_migration_url equals database_url (current behavior preserved).
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://app:pw@localhost/db"},
    )
    assert s.effective_migration_url == s.database_url


def test_effective_migration_url_prefers_migration_url(monkeypatch):
    # MIGRATION_DATABASE_URL 설정 → effective_migration_url 은 그것을 우선 사용 (owner credential).
    # Set → effective_migration_url prefers it (owner credential), not database_url.
    s = _reload_settings(
        monkeypatch,
        extra={
            "DATABASE_URL": "postgresql://app:pw@localhost/db",
            "MIGRATION_DATABASE_URL": "postgresql://owner:pw@localhost/db",
        },
    )
    assert s.effective_migration_url == "postgresql://owner:pw@localhost/db"
    assert s.effective_migration_url != s.database_url


# ---------------------------------------------------------------------------
# postgres:// URL 정규화 — fallback/worker/migration 3 필드 공유 validator 회귀 가드
#   (simplicity-2: 3개 byte-identical validator → pydantic 멀티필드 단일화 전후 동등성 봉인)
# postgres:// URL normalization — shared validator across fallback/worker/migration
#   (locks behavior before/after collapsing 3 identical validators into one multi-field validator)
# ---------------------------------------------------------------------------


def test_database_url_fallback_normalizes_postgres_scheme(monkeypatch):
    # DATABASE_URL_FALLBACK 의 postgres:// → postgresql:// 정규화.
    # DATABASE_URL_FALLBACK normalizes postgres:// → postgresql://.
    s = _reload_settings(
        monkeypatch, extra={"DATABASE_URL_FALLBACK": "postgres://u:p@localhost/db"})
    assert s.database_url_fallback.startswith("postgresql://")


def test_database_url_fallback_empty_passthrough(monkeypatch):
    # 미설정 시 빈 문자열 그대로 통과 (정규화 시도 없이 — required database_url 과 구분되는 가드 절).
    # Unset passes through as empty string (the guard clause distinguishing it from required database_url).
    s = _reload_settings(monkeypatch)
    assert s.database_url_fallback == ""


def test_database_url_worker_normalizes_postgres_scheme(monkeypatch):
    # DATABASE_URL_WORKER 의 postgres:// → postgresql:// 정규화.
    # DATABASE_URL_WORKER normalizes postgres:// → postgresql://.
    s = _reload_settings(
        monkeypatch, extra={"DATABASE_URL_WORKER": "postgres://w:p@localhost/db"})
    assert s.database_url_worker.startswith("postgresql://")


def test_database_url_worker_empty_passthrough(monkeypatch):
    # 미설정 시 빈 문자열 그대로 통과.
    # Unset passes through as empty string.
    s = _reload_settings(monkeypatch)
    assert s.database_url_worker == ""


# ---------------------------------------------------------------------------
# Phase 1 PR-1a — i18n 환경변수 5건 + field_validator 4건 검증 (Cycle 84+)
# Phase 1 PR-1a — i18n env vars 5 + field_validators 4 (Cycle 84+)
# ---------------------------------------------------------------------------


def test_default_locale_default_value(monkeypatch):
    """DEFAULT_LOCALE 기본값은 'en' 이어야 한다."""
    s = _reload_settings(monkeypatch)
    assert s.default_locale == "en"


def test_default_locale_reads_from_env(monkeypatch):
    """DEFAULT_LOCALE 환경변수 설정 시 반영되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"DEFAULT_LOCALE": "ko"})
    assert s.default_locale == "ko"


def test_default_locale_validation_empty(monkeypatch):
    """DEFAULT_LOCALE 이 공백이면 ValueError 발생해야 한다."""
    with pytest.raises(ValueError, match="DEFAULT_LOCALE must not be empty"):
        _reload_settings(monkeypatch, extra={"DEFAULT_LOCALE": ""})


def test_default_locale_validation_invalid_chars(monkeypatch):
    """DEFAULT_LOCALE 에 영숫자/하이픈 외 문자 포함 시 ValueError."""
    with pytest.raises(ValueError, match="must contain only alphanumeric"):
        _reload_settings(monkeypatch, extra={"DEFAULT_LOCALE": "en@US"})


def test_default_locale_strips_whitespace(monkeypatch):
    """DEFAULT_LOCALE 좌우 공백은 제거되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"DEFAULT_LOCALE": "  ja  "})
    assert s.default_locale == "ja"


def test_supported_locales_default_value(monkeypatch):
    """SUPPORTED_LOCALES 기본값은 'en,ko,ja' 이어야 한다."""
    s = _reload_settings(monkeypatch)
    assert s.supported_locales == "en,ko,ja"


def test_supported_locales_reads_from_env_normalized(monkeypatch):
    """SUPPORTED_LOCALES 공백 포함 입력 시 정규화되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"SUPPORTED_LOCALES": "en, ko, ja"})
    assert s.supported_locales == "en,ko,ja"


def test_supported_locales_validation_empty(monkeypatch):
    """SUPPORTED_LOCALES 이 공백이면 ValueError."""
    with pytest.raises(ValueError, match="SUPPORTED_LOCALES must not be empty"):
        _reload_settings(monkeypatch, extra={"SUPPORTED_LOCALES": ""})


def test_supported_locales_validation_only_commas(monkeypatch):
    """SUPPORTED_LOCALES 가 쉼표만 있고 언어 코드 없으면 ValueError."""
    with pytest.raises(ValueError, match="must contain at least one"):
        _reload_settings(monkeypatch, extra={"SUPPORTED_LOCALES": ",,,"})


def test_supported_locales_validation_invalid_code_length(monkeypatch):
    """언어 코드 길이가 2~10 자 범위 밖이면 ValueError (1자)."""
    with pytest.raises(ValueError, match="must be 2~10 characters"):
        _reload_settings(monkeypatch, extra={"SUPPORTED_LOCALES": "e,ko,ja"})


def test_supported_locales_validation_invalid_chars(monkeypatch):
    """언어 코드에 영숫자/하이픈 외 문자 포함 시 ValueError."""
    with pytest.raises(ValueError, match="must contain only alphanumeric"):
        _reload_settings(monkeypatch, extra={"SUPPORTED_LOCALES": "en,ko@KR"})


def test_locale_fallback_default_value(monkeypatch):
    """LOCALE_FALLBACK 기본값은 'en' 이어야 한다."""
    s = _reload_settings(monkeypatch)
    assert s.locale_fallback == "en"


def test_locale_fallback_reads_from_env(monkeypatch):
    """LOCALE_FALLBACK 환경변수 설정 시 반영되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"LOCALE_FALLBACK": "ja"})
    assert s.locale_fallback == "ja"


def test_locale_fallback_validation_empty(monkeypatch):
    """LOCALE_FALLBACK 이 공백이면 ValueError."""
    with pytest.raises(ValueError, match="LOCALE_FALLBACK must not be empty"):
        _reload_settings(monkeypatch, extra={"LOCALE_FALLBACK": ""})


def test_i18n_translations_dir_default_value(monkeypatch):
    """I18N_TRANSLATIONS_DIR 기본값은 'src/i18n/translations' 이어야 한다."""
    s = _reload_settings(monkeypatch)
    assert s.i18n_translations_dir == "src/i18n/translations"


def test_i18n_translations_dir_reads_from_env(monkeypatch):
    """I18N_TRANSLATIONS_DIR 환경변수 설정 시 반영되어야 한다."""
    s = _reload_settings(
        monkeypatch,
        extra={"I18N_TRANSLATIONS_DIR": "/app/i18n/translations"},
    )
    assert s.i18n_translations_dir == "/app/i18n/translations"


def test_i18n_disabled_default_false(monkeypatch):
    """I18N_DISABLED 기본값은 False (활성) 이어야 한다."""
    s = _reload_settings(monkeypatch)
    assert s.i18n_disabled is False


def test_i18n_disabled_reads_from_env_true(monkeypatch):
    """I18N_DISABLED=true 환경변수 설정 시 True 로 반영되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"I18N_DISABLED": "true"})
    assert s.i18n_disabled is True


def test_i18n_disabled_reads_from_env_zero(monkeypatch):
    """I18N_DISABLED=0 환경변수 설정 시 False 로 반영되어야 한다."""
    s = _reload_settings(monkeypatch, extra={"I18N_DISABLED": "0"})
    assert s.i18n_disabled is False


def test_is_disabled_i18n_helper_integration(monkeypatch):
    """is_disabled('I18N') helper 통합 — Phase 1 PR-1a 페어 (사이클 78 NEW-P0-2)."""
    from src.shared.feature_kill_switch import is_disabled

    # 미설정 default = False
    monkeypatch.delenv("I18N_DISABLED", raising=False)
    assert is_disabled("I18N") is False

    # 1 = True
    monkeypatch.setenv("I18N_DISABLED", "1")
    assert is_disabled("I18N") is True

    # 0 = False
    monkeypatch.setenv("I18N_DISABLED", "0")
    assert is_disabled("I18N") is False

    # true (case-insensitive) = True
    monkeypatch.setenv("I18N_DISABLED", "true")
    assert is_disabled("I18N") is True
