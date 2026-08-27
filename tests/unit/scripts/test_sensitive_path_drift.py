"""민감 경로 명시 리스트가 손유지라 **드리프트를 아무것도 잡지 못한다** (#1543).

`src/gate/sensitive_paths.py::_SENSITIVE_PATTERNS` 는 무검토 auto-merge 를 막는 **유일한
경로 인지 홀드**다. 점수 게이트는 경로 민감도를 모른다 — 60점만 넘으면 인증 변경도 그냥
머지된다(코드 자신이 `#1102~#1107` 6건 전부 `reviews=0`, 그중 `#1104` 는 토큰 유출 P0
였다고 적고 있다).

그 목록 안의 SCAManager 고유 파일은 손으로 적는다. 대조 대상이던 `.claude/rules/security.md`
가 삭제돼 **drift 를 강제하는 것이 없다.**

## 실측 (2026-08-27, main)

    운영 설정: repo_configs.auto_merge = true  (4개 리포 중 3개), merge_threshold = 60

강한 보안 원시요소(`hmac` · `secrets` · `src.crypto` · `src.shared.secure_compare`)를
**실제로 import 하는** 파일 14개 중 **10개가 hold 밖**이었다:

    src/webhook/providers/telegram.py   hmac + secure_compare   서명 검증
    src/webhook/providers/railway.py    crypto + secure_compare 서명 검증
    src/api/hook.py                     secure_compare          웹훅 인증
    src/api/internal_cron.py            secure_compare          cron 인증
    src/models/user.py                  crypto                  토큰 암호화
    src/gate/telegram_gate.py           hmac
    src/notifier/n8n.py                 hmac
    src/ui/routes/settings.py           secrets + crypto
    src/ui/routes/add_repo.py           secrets
    src/api/users.py                    secrets

가드가 존재하는 이유 그 자체인 부류가 가드 밖에 있었다.

## 왜 import 를 오라클로 쓰나

「보안 파일인가」를 사람의 판단이나 키워드 세기로 정하면 그 판정이 곧 드리프트한다.
`import hmac` 은 **기계 사실**이다 — 서명을 검증하거나 시크릿을 만들거나 토큰을 암호화하려면
그 이름을 적어야 한다.

넓은 신호(`subprocess` · `log_safety` · `auth.session`)는 일부러 뺐다 — 실측 60파일이라
그것으로 막으면 정상 PR 이 막히고 사용자가 가드를 끈다(가드의 자살).

## 마찰은 새 부류가 아니다

후보 10개의 변경 빈도는 최근 200 커밋에서 7~34회다. 이미 hold 인 `src/main.py` 가 **62회**로
그보다 높다 — 더 큰 마찰이 이미 수용되고 있다.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pathlib  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402

_ROOT = pathlib.Path(__file__).parents[3]
_SCRIPT = _ROOT / "scripts" / "check_sensitive_path_drift.py"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(cwd or _ROOT), check=False)


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_guard_exists_and_is_stdout_safe():
    """진입에 `_make_stdout_safe()` 가 없으면 Windows 에서 출력하다 죽는다."""
    assert _SCRIPT.exists(), "가드 스크립트가 없다"
    body = _SCRIPT.read_text(encoding="utf-8")
    assert "_make_stdout_safe()" in body, "stdout 안전화 호출이 없다"


def test_the_scan_actually_finds_something():
    """🔴 아무것도 못 재면 **초록이 아니라 red** 다 — 「안 쟀음」과 「통과」를 구별한다.

    원시요소 이름이 바뀌거나 스캔 경로가 어긋나면 0건이 되고, 그때 이 가드는 조용히
    모든 것을 통과시킨다.
    """
    from scripts.check_sensitive_path_drift import scan_strong_primitive_files  # noqa: PLC0415

    found = scan_strong_primitive_files(_ROOT)
    assert len(found) >= 10, f"강한 원시요소 파일이 {len(found)}개뿐 — 스캔이 눈멀었다"


def test_the_scanner_self_test_is_load_bearing():
    """🔴 계기 자기검증이 실제로 성립하는지 — 알려진 양성을 스캐너가 봐야 한다.

    첫 판은 **개수 바닥**(`_MIN_EXPECTED = 10`)이었다. 그러면 파일 5개를 정당하게
    지우는 순간 red 가 되고 그 처방이 「상수를 낮춰라」 — 곧 무장 해제다
    (Grok 01a04342 Q4). 개수 하한은 정당한 삭제를 벌하는 모양이다.

    지금은 알려진 양성 두 개를 스캐너가 보는지로 잰다. 개수와 무관하다.
    """
    from scripts.check_sensitive_path_drift import (  # noqa: PLC0415
        _SCANNER_SELF_TEST,
        scan_strong_primitive_files,
    )

    assert _SCANNER_SELF_TEST, "자기검증 표가 비었다 — 계기를 아무것도 확인하지 않는다"
    found = scan_strong_primitive_files(_ROOT)
    for path, primitive in _SCANNER_SELF_TEST.items():
        assert (_ROOT / path).exists(), f"{path} 가 사라졌다 — 자기검증 표가 늙었다"
        assert primitive in found.get(path, []), (
            f"스캐너가 {path} 의 {primitive} 를 못 봤다 — 계기가 깨졌다"
        )


def test_the_oracle_sees_third_party_crypto():
    """🔴 처음엔 stdlib 두 개만 봐서 `cryptography.fernet` 을 **아예 못 봤다**.

    `src/crypto.py` 가 hold 인 것은 손으로 적혀 있어서지 오라클이 본 것이 아니었다 —
    그 복제본이 새로 생기면 그대로 샌다(Grok 01a04342 Q1).
    """
    from scripts.check_sensitive_path_drift import scan_strong_primitive_files  # noqa: PLC0415

    found = scan_strong_primitive_files(_ROOT)
    assert "cryptography" in found.get("src/crypto.py", []), "서드파티 암호를 못 본다"
    assert "src.shared.ssrf" in found.get("src/notifier/_http.py", []), "SSRF 경유를 못 본다"


def test_the_oracle_sees_every_import_shape(tmp_path):
    """🔴 `import src.crypto` 는 루트가 `src` 라 첫 판이 놓쳤다. 상대 import 도 몰랐다.

    이 리포는 실제로 `import src.gate.actions.approve` 형태를 쓴다.
    """
    from scripts.check_sensitive_path_drift import scan_strong_primitive_files  # noqa: PLC0415

    pkg = tmp_path / "src" / "deep"
    pkg.mkdir(parents=True)
    (pkg / "dotted.py").write_text("import src.crypto\n", encoding="utf-8")
    (pkg / "relative.py").write_text("from ..crypto import x\n", encoding="utf-8")
    found = scan_strong_primitive_files(tmp_path)
    assert found.get("src/deep/dotted.py") == ["src.crypto"], f"점 표기를 놓쳤다: {found}"
    assert found.get("src/deep/relative.py") == ["src.crypto"], f"상대 import 를 놓쳤다: {found}"


def test_a_blinded_scan_fails_instead_of_passing(tmp_path, monkeypatch):
    """🔴 원시요소 이름이 바뀌어 스캔이 0건이 되면 **red** 여야 한다.

    「안 쟀음」이 「통과」로 보이면 그 초록은 아무것도 뜻하지 않는다.
    """
    # 🔴 `import x as mod` 와 `from x import y` 를 한 파일에서 같이 쓰면
    #    CodeQL `py/import-and-import-from` 를 자초한다(`check_dual_import.py` 가 잡는다).
    #    모듈 객체가 필요하면 importlib 으로 얻어 형태를 하나로 유지한다.
    # Keep a single import shape; get the module object via importlib.
    import importlib  # noqa: PLC0415

    mod = importlib.import_module("scripts.check_sensitive_path_drift")

    monkeypatch.setattr(mod, "_STRONG_MODULES", frozenset())
    monkeypatch.setattr(mod, "_STRONG_FROM", frozenset())
    monkeypatch.setattr(mod.pathlib.Path, "cwd", staticmethod(lambda: _ROOT))
    assert mod.main() == 1, "스캔이 0건인데 통과했다"


# ─── 본체 ────────────────────────────────────────────────────────────────────


def test_no_strong_primitive_file_escapes_the_merge_hold():
    """🔴 서명 검증·시크릿 생성·토큰 암호화를 하는 파일이 무검토 머지를 통과하면 안 된다."""
    proc = _run()
    assert proc.returncode == 0, (
        f"드리프트가 있다 — hold 밖의 보안 파일:\n{proc.stdout}\n{proc.stderr}"
    )


def test_the_guard_catches_a_newly_added_unlisted_security_file(tmp_path):
    """🔴 「초록인데 거짓」을 심어 red 를 확인한다.

    hold 목록에 없는 자리에 `hmac` 을 쓰는 파일을 새로 만들면 red 여야 한다. 이것이
    빨개지지 않으면 이 가드는 아무것도 강제하지 않는다.
    """
    from scripts.check_sensitive_path_drift import scan_strong_primitive_files  # noqa: PLC0415

    fake = tmp_path / "src" / "services"
    fake.mkdir(parents=True)
    (fake / "brand_new_signer.py").write_text(
        "import hmac\n\n\ndef sign(x):\n    return hmac.new(b'k', x).hexdigest()\n",
        encoding="utf-8")
    found = scan_strong_primitive_files(tmp_path)
    assert any("brand_new_signer" in f for f in found), "새 파일을 스캔이 못 봤다"

    proc = _run(cwd=tmp_path)
    assert proc.returncode != 0, "hold 밖의 새 보안 파일인데 초록이다"


def test_an_exemption_needs_a_reason():
    """면제가 사유 없이 가능하면 목록은 다시 손유지로 되돌아간다."""
    from scripts.check_sensitive_path_drift import REVIEWED_NOT_SENSITIVE  # noqa: PLC0415

    for path, reason in REVIEWED_NOT_SENSITIVE.items():
        assert len(reason) >= 16, f"{path} 의 면제 사유가 너무 짧다: {reason!r}"


@pytest.mark.parametrize("path", [
    "src/webhook/providers/telegram.py",
    "src/webhook/providers/railway.py",
    "src/api/hook.py",
    "src/api/internal_cron.py",
    "src/models/user.py",
    "src/gate/telegram_gate.py",
    "src/notifier/n8n.py",
    "src/ui/routes/settings.py",
    "src/ui/routes/add_repo.py",
    "src/api/users.py",
])
def test_each_measured_gap_is_now_held(path):
    """🔴 실측으로 hold 밖이던 10개가 실제로 막히는지 — 개별로 못 박는다.

    합계만 보면 하나가 빠져도 초록이 될 수 있다.
    """
    from src.gate.sensitive_paths import _SENSITIVE_PATTERNS  # noqa: PLC0415

    assert any(p.search(path) for p in _SENSITIVE_PATTERNS), f"{path} 가 여전히 hold 밖이다"


def test_the_hold_does_not_swallow_ordinary_files():
    """반대쪽 — 과하게 넓히면 정상 PR 이 막혀 사용자가 가드를 끈다(가드의 자살)."""
    from src.gate.sensitive_paths import _SENSITIVE_PATTERNS  # noqa: PLC0415

    ordinary = ["src/services/analytics_service.py", "src/ui/routes/overview.py",
                "src/shared/claude_metrics.py", "src/scorer/calculator.py",
                "src/analyzer/io/tools/eslint.py"]
    held = [f for f in ordinary if any(p.search(f) for p in _SENSITIVE_PATTERNS)]
    assert not held, f"평범한 파일까지 막는다: {held}"
