"""훅 command 는 cwd 상대 경로로 스크립트를 부르면 안 된다 (R67).

Claude Code 는 훅을 **셸의 현재 cwd** 에서 실행한다. `$PY scripts/x.py` /
`$PY .claude/hooks/x.py` 는 cwd 가 리포 밖이면 `can't open file` exit 2 이고,
PreToolUse 의 비정상 종료는 차단이라 세션이 자력 복구 불가였다.

계약: 파싱된 settings.json **문서 전체**에서 모은 스크립트 토큰은
`${CLAUDE_PROJECT_DIR:-.}/` 접두를 써야 한다. 변수가 비어 있으면 오늘의 상대
경로로 폴백하고, 설정돼 있으면 절대화된다. `$CLAUDE_PROJECT_DIR/…`(기본값 없음) 는
미설정 시 `/scripts/…` 가 되므로 거부한다.

🔴 **이 파일이 단언하는 것 / 단언하지 않는 것.**
   이 파일은 **경로 계약**만 본다. 명령이 실제로 인터프리터를 호출하는지는
   배선 스위트(`test_session_start_wiring` · `test_credential_dump_hook` ·
   `test_check_edit_allowed` · `test_wiring_shape` 등)가 단언한다. `echo` 로
   인터프리터만 중성화한 채 접두를 남기면 이 파일은 초록이고 배선 스위트가
   붉다 — 관심사 분리이며, 그 분리를 여기에 적는다.

🔴 **왜 스키마를 나열하지 않는가.** `_commands_from` 이
   `hooks → event → group["hooks"] → hook["command"]` 만 걷자 그룹 레벨
   `command`(M8b) · `args` 리스트(M12) · `tools/` 같은 새 위치(M11) 가
   투명했다. 이제는 파싱된 JSON 을 재귀 순회해 **모든 문자열**에서 `.py` 로
   끝나는 토큰을 모은다. 새 이벤트 키·새 필드·새 디렉터리가 자동으로 보인다.

🔴 **note/산문도 스캔한다.** `note` 에 `scripts/x.py` 를 적는 것은 경로를
   숨기는 통로이지 설명이 아니다. 환경변수 **이름**만 있는 산문(`CLAUDE_PROJECT_DIR`)
   은 `.py` 토큰이 아니라서 계약을 충족시키지 못한다.

🔴 **`./` 는 허용, `..` 는 거부.** 접두 뒤 `./scripts/x.py` 는 cwd 동치라
   승인한다. `scripts/../../../x.py` 처럼 세그먼트에 `..` 가 있으면 거부한다
   (M10).

🔴 **왜 기본값 전개인가 — 변수가 온다는 것을 처방 시점에는 몰랐다.** backlog R67 이
반증 수단 (a) 로 지목한 *"훅 실행 시 `CLAUDE_PROJECT_DIR` 이 실제로 설정되는가"* 는
리포 밖에서는 원리적으로 관측 불가다(훅을 발화시키려면 Claude Code 세션이어야 한다).
그래서 형태를 **설정 여부 양쪽에서 옳게** 골랐다. 그 뒤 실훅 계측이 값을 확정했다 —
2026-08-15, `posttool_pytest_smoke.py` 에 임시 덤프를 심고 실제 편집 1회를 발생시켜
`CLAUDE_PROJECT_DIR='f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager'`(리포 루트, 슬래시 정규화)
를 읽었다. **계측이 확정한 것은 이 머신의 이 세션 하나**이므로 폴백은 그대로 둔다.

Hook commands must not invoke scripts by a cwd-relative path. Every `.py` token
in the parsed settings document must carry the default-expansion prefix.
Invocation shape is the wiring suite's job; this file asserts the path contract.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"

# 승인된 접두 — 기본값 전개가 본체다. `$CLAUDE_PROJECT_DIR/` 단독은 여기 없다.
# Approved prefix: default-expansion is the point. Bare `$CLAUDE_PROJECT_DIR/` is not.
_PREFIX = "${CLAUDE_PROJECT_DIR:-.}/"


def _all_strings(node: object) -> list[str]:
    """파싱된 JSON 의 모든 문자열 — 스키마 키를 나열하지 않는다.

    dict 값과 list 원소만 재귀한다(키는 `command`/`hooks` 같은 식별자라 `.py` 가 아니다).
    Walk every dict value and list element; do not enumerate schema keys.
    """
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        out: list[str] = []
        for value in node.values():
            out.extend(_all_strings(value))
        return out
    if isinstance(node, list):
        out = []
        for item in node:
            out.extend(_all_strings(item))
        return out
    return []


def _script_tokens(text: str) -> list[str]:
    """문자열에서 `.py` 로 끝나는 공백 분리 토큰만 모은다.

    디렉터리 allowlist 없음 — `tools/` · `.claude/hooks_v2/` 도 보인다.
    따옴표로 묶여 공백을 포함하면 토큰이 갈라진다 = fail-closed
    (문서 전체 토큰 수가 바닥 아래로 떨어지면 전제 단언이 잡는다).
    Whitespace-split tokens ending in `.py`; no directory allowlist.
    """
    return [tok for tok in text.split() if tok.endswith(".py")]


def _collect_script_tokens(settings: object) -> list[str]:
    """settings 문서 전체에서 스크립트 토큰을 모은다.
    Collect every script token from the whole parsed settings document."""
    tokens: list[str] = []
    for text in _all_strings(settings):
        tokens.extend(_script_tokens(text))
    return tokens


def _is_approved_script_token(token: str) -> bool:
    """토큰이 승인된 기본값-전개 접두이고, 접두 뒤에 `..` 세그먼트가 없는가.

    접두 직후 `./` 는 cwd 동치라 반복 제거 후 승인한다.
    `${PREFIX}./scripts/x.py` → 승인 / `${PREFIX}scripts/../x.py` → 거부.
    Approved iff the default-expansion prefix is present and no `..` segment follows.
    """
    if not token.startswith(_PREFIX):
        return False
    rest = token[len(_PREFIX):].replace("\\", "/")
    # 선행 `./` 만 벗긴다 — `..` 는 벗기지 않고 아래에서 거부한다.
    # Strip a leading `./` only; `..` is rejected below, not normalised away.
    while rest.startswith("./"):
        rest = rest[2:]
    if not rest or rest.endswith("/"):
        return False
    parts = rest.split("/")
    if any(part == ".." or part == "" for part in parts):
        return False
    return True


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


def test_detector_accepts_dot_slash_after_prefix():
    """접두 뒤 `./` 는 cwd 동치 — 거부하면 가드 자살 방향.

    `${PREFIX}./scripts/x.py` 는 전개 후 `././scripts/x.py` 또는 `<abs>/./scripts/x.py`.
    After the prefix, `./` is cwd-equivalent and must be accepted.
    """
    token = f"{_PREFIX}./scripts/check_retro_cadence.py"
    assert _script_tokens(f"$PY {token}") == [token]
    assert _is_approved_script_token(token)


def test_detector_rejects_dotdot_traversal():
    """접두 + `scripts/` 뒤에 `..` 가 있으면 승인이 아니다 (M10).

    `${PREFIX}scripts/../../../x.py` 는 리포 밖으로 나간다.
    A `..` segment after the prefix is not an approved path.
    """
    trav = f"{_PREFIX}scripts/../../../x.py"
    assert _script_tokens(f"$PY {trav}") == [trav]
    assert not _is_approved_script_token(trav)
    via_hooks = f"{_PREFIX}.claude/hooks/../../../x.py"
    assert not _is_approved_script_token(via_hooks)
    sibling = f"{_PREFIX}scripts/../evil.py"
    assert not _is_approved_script_token(sibling)


def test_env_var_name_in_prose_is_not_a_script_token():
    """산문의 `CLAUDE_PROJECT_DIR` 문자열은 `.py` 토큰이 아니라서 계약을 충족시키지 못한다.

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
    tokens = _collect_script_tokens(fake)
    assert tokens == ["scripts/bare.py"]
    assert all(not _is_approved_script_token(t) for t in tokens)


def test_note_field_py_path_is_scanned():
    """note 의 `.py` 경로도 스캔한다 — 스키마 밖 필드에 숨기는 통로를 닫는다.

    산문에 경로를 두는 것은 설명이 아니라 은닉이다. 그래서 허용하지 않는다.
    A `.py` path in a note is collected; hiding a bare path there must not pass.
    """
    fake = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"$PY {_PREFIX}scripts/ok.py",
                            "note": "also run scripts/hidden.py",
                        }
                    ]
                }
            ]
        }
    }
    tokens = _collect_script_tokens(fake)
    assert "scripts/hidden.py" in tokens
    assert not _is_approved_script_token("scripts/hidden.py")


def test_scan_sees_flat_group_command():
    """그룹 레벨 `command`(nested `hooks` 없음) 도 보인다 — M8b.

    스키마 나열기는 `group.get("hooks")` 만 걷고 이 형태를 놓쳤다.
    A group-level `command` is visible; the old walker missed it.
    """
    fake = {
        "hooks": {
            "Notification": [
                {
                    "type": "command",
                    "command": "$PY scripts/sneaky_flat.py",
                }
            ]
        }
    }
    tokens = _collect_script_tokens(fake)
    assert tokens == ["scripts/sneaky_flat.py"]
    assert not _is_approved_script_token(tokens[0])


def test_scan_sees_tools_and_hooks_v2_paths():
    """`tools/` · `.claude/hooks_v2/` 는 allowlist 밖이어도 보인다 — M11."""
    fake = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                f"$PY {_PREFIX}scripts/ok.py && "
                                "$PY tools/sneaky.py && "
                                "$PY .claude/hooks_v2/also.py"
                            ),
                        }
                    ]
                }
            ]
        }
    }
    tokens = _collect_script_tokens(fake)
    assert "tools/sneaky.py" in tokens
    assert ".claude/hooks_v2/also.py" in tokens
    assert not _is_approved_script_token("tools/sneaky.py")
    assert not _is_approved_script_token(".claude/hooks_v2/also.py")
    assert _is_approved_script_token(f"{_PREFIX}tools/ok.py")


def test_scan_sees_args_list():
    """`args` 리스트의 `.py` 경로도 보인다 — M12.

    command 는 접두가 있어도 args 의 bare 경로는 거절돼야 한다.
    A `.py` path in `args` is collected even when `command` is prefixed.
    """
    fake = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"$PY {_PREFIX}scripts/ok.py",
                            "args": ["scripts/bare_via_args.py"],
                        }
                    ]
                }
            ]
        }
    }
    tokens = _collect_script_tokens(fake)
    assert f"{_PREFIX}scripts/ok.py" in tokens
    assert "scripts/bare_via_args.py" in tokens
    assert not _is_approved_script_token("scripts/bare_via_args.py")


# ── 저장소 불변식 ────────────────────────────────────────────────────────


def test_settings_json_is_valid():
    """settings.json 이 유효한 JSON — 깨지면 모든 훅이 조용히 죽는다."""
    payload = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_every_hook_command_uses_project_dir_default_expansion():
    """🔴 문서 전체의 `.py` 토큰은 전부 `${CLAUDE_PROJECT_DIR:-.}/` 접두 + `..` 없음.

    스키마를 나열하지 않는다 — flat command · args · 새 디렉터리도 같은 바닥을 쓴다.
    Every `.py` token in the parsed document must carry the prefix and no `..`.
    """
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    tokens = _collect_script_tokens(settings)
    assert tokens, "스크립트 토큰 0개 — 추출기 전제 붕괴"
    # 🔴 공허 방지 하한 — settings 가 비면 이 테스트가 통과해선 안 된다.
    #    9 → 8 (2026-08-16): `check_open_decisions.py` SessionStart 훅을 **제거**했다.
    #    열린 일감이 `docs/backlog.md` 원장에서 GitHub Issue 로 옮겨가 그 카운터가
    #    읽을 원장 자체가 사라졌기 때문이다. 하한을 내리는 것은 **명시 결정**이고,
    #    내리지 않으면 이 테스트가 영구 red 로 남아 아무도 안 돌리게 된다.
    #    Floor lowered with the hook removal; an unexplained drop must still fail here.
    assert len(tokens) >= 8, (
        f"스크립트 토큰이 {len(tokens)}개 — 전제 붕괴 (settings 가 비면 통과하면 안 된다)"
    )

    bare = [t for t in tokens if not _is_approved_script_token(t)]
    assert not bare, (
        "cwd 상대(또는 기본값 없는/`..` 탈출) 스크립트 경로가 남아 있다 — R67 회귀.\n"
        f"  거부된 토큰: {bare}\n"
        f"  해결 / Fix: `$PY {_PREFIX}scripts/x.py` 형태 "
        f"(bare `$CLAUDE_PROJECT_DIR/` · `..` 세그먼트 금지)."
    )
