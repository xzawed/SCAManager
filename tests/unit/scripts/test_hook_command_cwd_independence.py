"""훅 command 는 cwd 상대 경로로 스크립트를 부르면 안 된다 (R67).

Claude Code 는 훅을 **셸의 현재 cwd** 에서 실행한다. `$PY scripts/x.py` /
`$PY .claude/hooks/x.py` 는 cwd 가 리포 밖이면 `can't open file` exit 2 이고,
PreToolUse 의 비정상 종료는 차단이라 세션이 자력 복구 불가였다.

계약: 파싱된 JSON command 의 스크립트 토큰은 `${CLAUDE_PROJECT_DIR:-.}/` 접두를
써야 한다. 변수가 비어 있으면 오늘의 상대 경로로 폴백하고, 설정돼 있으면 절대화된다.
`$CLAUDE_PROJECT_DIR/…`(기본값 없음) 는 미설정 시 `/scripts/…` 가 되므로 거부한다.

🔴 **왜 기본값 전개인가 — 변수가 온다는 것을 처방 시점에는 몰랐다.** backlog R67 이
반증 수단 (a) 로 지목한 *"훅 실행 시 `CLAUDE_PROJECT_DIR` 이 실제로 설정되는가"* 는
리포 밖에서는 원리적으로 관측 불가다(훅을 발화시키려면 Claude Code 세션이어야 한다).
그래서 형태를 **설정 여부 양쪽에서 옳게** 골랐다. 그 뒤 실훅 계측이 값을 확정했다 —
2026-08-15, `posttool_pytest_smoke.py` 에 임시 덤프를 심고 실제 편집 1회를 발생시켜
`CLAUDE_PROJECT_DIR='f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager'`(리포 루트, 슬래시 정규화)
를 읽었다. **계측이 확정한 것은 이 머신의 이 세션 하나**이므로 폴백은 그대로 둔다.

🔴 산문 grep 금지 — `CLAUDE_PROJECT_DIR` 문자열이 주석·설명에 있어도 통과가 아니다.
   판정은 `json.loads` 한 command 문자열의 **스크립트 토큰** 만 본다.

Hook commands must not invoke scripts by a cwd-relative path. The parsed JSON
command tokens must use `${CLAUDE_PROJECT_DIR:-.}/` so an unset var falls back
to today's relative path instead of becoming `/scripts/…`.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"

# 승인된 접두 — 기본값 전개가 본체다. `$CLAUDE_PROJECT_DIR/` 단독은 여기 없다.
# Approved prefix: default-expansion is the point. Bare `$CLAUDE_PROJECT_DIR/` is not.
_PREFIX = "${CLAUDE_PROJECT_DIR:-.}/"
_TAILS = ("scripts/", ".claude/hooks/")


def _commands_from(settings: dict) -> list[str]:
    """JSON 객체에서 훅 command 문자열만 추출한다 (주석·다른 키는 무시).
    Extract only hook command strings from a parsed settings object."""
    out: list[str] = []
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    out.append(cmd)
    return out


def _script_tokens(command: str) -> list[str]:
    """command 에서 훅/가드 스크립트를 가리키는 토큰만 모은다.

    공백 분리 — settings.json 의 현행 형태(`$PY <path.py>`)와 맞다.
    경로가 따옴표로 묶여 공백을 포함하면 이 추출기는 토큰을 놓친다 = fail-closed
    (전제 붕괴 단언이 0토큰을 잡는다).
    Collect script tokens by whitespace; a quoted path with spaces is missed
    on purpose (fail-closed — the premise assert catches zero tokens).
    """
    out: list[str] = []
    for tok in command.split():
        if not tok.endswith(".py"):
            continue
        if any(tail in tok for tail in _TAILS):
            out.append(tok)
    return out


def _is_approved_script_token(token: str) -> bool:
    """토큰이 승인된 기본값-전개 접두 + 허용 꼬리인가.
    Is the token the approved default-expansion prefix plus an allowed tail?"""
    if not token.startswith(_PREFIX):
        return False
    rest = token[len(_PREFIX):]
    return rest.startswith("scripts/") or rest.startswith(".claude/hooks/")


# ── 탐지기 자체 검증 (공허 통과 차단) ────────────────────────────────────
# Detector self-check — these must fail the checker, or the live assert is theatre.


def test_detector_flags_bare_relative_scripts_path():
    """`$PY scripts/x.py` 는 오늘 깨진 바로 그 형태 — 탐지기가 잡아야 한다."""
    tokens = _script_tokens(
        "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
        "$PY scripts/check_retro_cadence.py"
    )
    assert tokens == ["scripts/check_retro_cadence.py"]
    assert not _is_approved_script_token(tokens[0])


def test_detector_flags_bare_relative_hook_path():
    """`$PY .claude/hooks/x.py` 도 같은 축이다."""
    tokens = _script_tokens(
        "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
        "$PY .claude/hooks/block_credential_dump.py"
    )
    assert tokens == [".claude/hooks/block_credential_dump.py"]
    assert not _is_approved_script_token(tokens[0])


def test_detector_flags_absolute_var_without_default():
    """`$CLAUDE_PROJECT_DIR/scripts/x.py` 는 미설정 시 `/scripts/x.py` — 오늘보다 나쁘다.

    계약은 '절대화'가 아니라 '설정돼 있으면 절대, 없으면 상대 폴백' 이다.
    Bare `$CLAUDE_PROJECT_DIR/…` expands to `/scripts/…` when unset — worse than today.
    """
    tokens = _script_tokens(
        "$PY $CLAUDE_PROJECT_DIR/scripts/check_retro_cadence.py"
    )
    assert tokens == ["$CLAUDE_PROJECT_DIR/scripts/check_retro_cadence.py"]
    assert not _is_approved_script_token(tokens[0])


def test_detector_accepts_default_expansion():
    """승인 형태는 통과해야 한다 — 거부하면 가드 자살."""
    token = f"{_PREFIX}scripts/check_retro_cadence.py"
    assert _script_tokens(f"$PY {token}") == [token]
    assert _is_approved_script_token(token)
    hook = f"{_PREFIX}.claude/hooks/block_credential_dump.py"
    assert _is_approved_script_token(hook)


def test_prose_mention_is_not_a_command_token():
    """산문에 CLAUDE_PROJECT_DIR 이 있어도 command 토큰이 아니면 계약 충족이 아니다.

    `\"CLAUDE_PROJECT_DIR\" in raw_text` 검사는 이 케이스를 통과시킨다.
    A substring search for the env var name would pass this decoy.
    """
    fake = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "$PY scripts/bare.py",
                            "note": "should use CLAUDE_PROJECT_DIR",
                        }
                    ]
                }
            ]
        }
    }
    commands = _commands_from(fake)
    tokens = [t for cmd in commands for t in _script_tokens(cmd)]
    assert tokens == ["scripts/bare.py"]
    assert all(not _is_approved_script_token(t) for t in tokens)


# ── 저장소 불변식 ────────────────────────────────────────────────────────


def test_settings_json_is_valid():
    """settings.json 이 유효한 JSON — 깨지면 모든 훅이 조용히 죽는다."""
    payload = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_every_hook_command_uses_project_dir_default_expansion():
    """🔴 파싱된 command 의 스크립트 토큰은 전부 `${CLAUDE_PROJECT_DIR:-.}/` 접두.

    cwd 상대 `scripts/X.py` · `.claude/hooks/X.py` 로의 회귀를 막는다.
    Every parsed script token must carry the default-expansion prefix.
    """
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    commands = _commands_from(settings)
    assert len(commands) >= 9, f"훅 command 가 {len(commands)}개 — 전제 붕괴"

    tokens: list[str] = []
    for cmd in commands:
        found = _script_tokens(cmd)
        assert found, f"스크립트 토큰을 못 찾았다 (추출기 전제 붕괴): {cmd!r}"
        tokens.extend(found)

    bare = [t for t in tokens if not _is_approved_script_token(t)]
    assert not bare, (
        "cwd 상대(또는 기본값 없는) 스크립트 경로가 남아 있다 — R67 회귀.\n"
        f"  거부된 토큰: {bare}\n"
        f"  해결 / Fix: `$PY {_PREFIX}scripts/x.py` 형태 (bare `$CLAUDE_PROJECT_DIR/` 금지)."
    )
