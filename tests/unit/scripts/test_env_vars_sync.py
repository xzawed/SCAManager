"""H1 env-vars 싱크 체커 회귀 가드 — config.py Settings ↔ env-vars.md 등재 정합."""
import sys
from pathlib import Path

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
    (tmp_path / "docs" / "reference" / "env-vars.md").write_text(
        "| `DATABASE_URL` | desc | ex |\n", encoding="utf-8",
    )
    ok, msgs = check_env_vars_sync.check_sync(tmp_path)
    assert not ok
    assert any("BRAND_NEW_SECRET" in m for m in msgs)


def test_env_vars_sync_allowlist_excludes_internal(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "src" / "config.py").write_text(
        "class Settings(BaseSettings):\n"
        "    database_url: str\n"
        "    api_auth_disabled: bool = False\n",  # allowlist 가정 시 통과
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "env-vars.md").write_text(
        "| `DATABASE_URL` | desc | ex |\n| `API_AUTH_DISABLED` | desc | ex |\n",
        encoding="utf-8",
    )
    ok, msgs = check_env_vars_sync.check_sync(tmp_path)
    assert ok, msgs
