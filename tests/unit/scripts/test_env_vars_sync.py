"""H1 env-vars 싱크 체커 회귀 가드 — config.py Settings ↔ env-vars.md 등재 정합."""
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_env_vars_sync  # noqa: E402


def test_env_vars_sync_passes_on_current_repo():
    ok, msgs = check_env_vars_sync.check_sync(_ROOT)
    assert ok, msgs


def test_env_vars_sync_flags_undocumented_field(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "src" / "config.py").write_text(
        "class Settings(BaseSettings):\n"
        "    database_url: str\n"
        "    brand_new_secret: str = \"\"\n",
        encoding="utf-8",
    )
    # env-vars.md 에 DATABASE_URL 만 등재, BRAND_NEW_SECRET 누락
    # env-vars.md lists only DATABASE_URL; BRAND_NEW_SECRET is intentionally absent
    (tmp_path / "docs" / "reference" / "env-vars.md").write_text(
        "| `DATABASE_URL` | desc | ex |\n", encoding="utf-8",
    )
    ok, msgs = check_env_vars_sync.check_sync(tmp_path)
    assert not ok
    assert any("BRAND_NEW_SECRET" in m for m in msgs)


def test_env_vars_sync_allowlist_excludes_internal(tmp_path):
    """_INTERNAL_FIELDS allowlist 에 등재된 필드는 env-vars.md 등재 없이도 통과해야 한다.
    Fields in _INTERNAL_FIELDS must pass even when absent from env-vars.md.

    vacuous 방지 설계:
    - config.py 에 internal_derived_only 필드 포함, env-vars.md 에 **미등재**
    - _INTERNAL_FIELDS 를 {"internal_derived_only"} 로 패치 → ok=True 검증
    - _INTERNAL_FIELDS 가 빈 frozenset 이면 ok=False 가 되어 allowlist 로직이 실제로 동작함을 확인
    Non-vacuous design:
    - config.py has `internal_derived_only` field; env-vars.md does NOT list it
    - patch _INTERNAL_FIELDS to {"internal_derived_only"} → expect ok=True
    - with empty _INTERNAL_FIELDS the same call must return ok=False, proving the logic fires
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "src" / "config.py").write_text(
        "class Settings(BaseSettings):\n"
        "    database_url: str\n"
        "    internal_derived_only: str = \"\"\n",  # env-vars.md 에 미등재 / not in env-vars.md
        encoding="utf-8",
    )
    # env-vars.md 에 database_url 만 등재 — internal_derived_only 의도적 누락
    # env-vars.md has only DATABASE_URL — internal_derived_only intentionally absent
    (tmp_path / "docs" / "reference" / "env-vars.md").write_text(
        "| `DATABASE_URL` | desc | ex |\n", encoding="utf-8",
    )

    # allowlist 에 internal_derived_only 추가 시 → ok=True (면제 적용)
    # With allowlist containing internal_derived_only → ok=True (exempted)
    with patch.object(check_env_vars_sync, "_INTERNAL_FIELDS", frozenset({"internal_derived_only"})):
        ok_with_allowlist, _ = check_env_vars_sync.check_sync(tmp_path)

    # allowlist 가 빈 frozenset 이면 → ok=False (면제 미적용 = 누락 탐지)
    # With empty allowlist → ok=False (no exemption = missing detected)
    with patch.object(check_env_vars_sync, "_INTERNAL_FIELDS", frozenset()):
        ok_without_allowlist, msgs_without = check_env_vars_sync.check_sync(tmp_path)

    assert ok_with_allowlist, "allowlist 패치 시 면제 필드가 통과해야 함 / exempted field must pass when allowlisted"
    assert not ok_without_allowlist, "allowlist 미적용 시 미등재 필드 탐지해야 함 / missing field must be detected without allowlist"
    assert any("INTERNAL_DERIVED_ONLY" in m for m in msgs_without), (
        "오류 메시지에 미등재 필드명이 포함돼야 함 / error message must mention the undocumented field"
    )
