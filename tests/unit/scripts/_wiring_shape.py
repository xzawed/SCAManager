"""배선 판정 공통 술어 — "경로 문자열이 있다" 가 아니라 **"인터프리터가 그 스크립트를 실행한다"**.

## 왜 만드나 (2026-07-31 Grok claim-review + 실경로 뮤테이션 실측)

배선 가드 10곳이 전부 `"<경로>" in <명령>` **substring** 으로 배선을 판정하고 있었다.
그래서 명령을 `echo scripts/check_x.py` 로 바꿔 **실행만 제거**해도 경로 문자열이 남아
전부 초록이었다. 격리 worktree 에서 `assert mutated != orig` 로 적용을 증명하고
`tests/unit/scripts`+`tests/unit/hooks` 498건을 돌린 실측: 뮤테이션 12건 중 **11건 GREEN**.

무력화된 대상에는 SessionStart 카운터 2종 · 시크릿 덤프 차단 훅 · repo-integrity 백스톱 4종 ·
정책 19 claim-review 집행면 · lint-js 공허화 차단이 포함된다. 즉 "가드를 껐는데 가드 스위트가
초록" 이 통제면 전역에서 성립했다.

🔴 이것은 가설이 아니라 **이미 발동될 뻔한 경로**다. `#1243` 이 훅 command 6종을
`python X` → `PY=$(command -v py ...); $PY X` 로 전면 재작성했는데, 당시 배선 가드는 그
재작성과 `echo X` 를 **구별할 수 없었다**.

## 무엇을 강제하나 (AGENTS.md 불변식 1 — fail-closed)

명령을 셸 세그먼트로 나눠 **명령어(command word)가 파이썬 인터프리터인지** 구조적으로 판정한다.
allowlist 방식이라 모르는 형태는 "배선 아님" 으로 떨어진다(fail-closed) — 새로운 배선 형태가
생기면 여기에 명시적으로 추가해야 하고, 그 추가가 리뷰 대상이 된다.

## 🔴 이 술어가 잡지 못하는 것 (정직 기준)

1. **조건부 skip** — `if: false` 인 CI step 의 `run:` 은 형태상 실호출이라 배선으로 센다.
2. **런타임 실패** — 인터프리터가 실제로 존재하는지는 정적으로 알 수 없다
   (`$PY` 가 `python3` 로 풀렸는데 그 바이너리가 없는 환경 등).
3. **가드 본문의 공허함** — 실행되더라도 그 가드가 무엇을 검사하는지는 별개 문제다.

즉 이 모듈은 **"실행 연결이 끊겼는데 초록"** 만 끝낸다. 그 이상을 주장하면 이 파일 자체가
새 observer-lie 가 된다.

Wiring predicate: an invocation must actually run the script. The prior substring form let
`echo scripts/check_x.py` pass — 11 of 12 real-path mutations stayed green. Allowlist-based, so
unknown shapes fail closed. It does not detect conditionally-skipped steps, missing interpreters
at runtime, or a wired-but-vacuous guard body.
"""
from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterable

# 셸 세그먼트 구분자 — `;` `&&` `||` `|` 개행. 뒷 세그먼트의 실호출을 놓치지 않기 위함
# (`set -e && python scripts/x.py`).
# Shell segment separators, so a real call in a later segment is not missed.
_SEGMENT_SPLIT = re.compile(r";|&&|\|\||\||\n")

# 🔴 세그먼트를 **앞선 연산자와 함께** 자른다 — 죽은 분기를 걸러내기 위해서다.
#    `true || python scripts/x.py` 는 오른쪽이 **절대 실행되지 않는데** 초판은 배선으로
#    인정했다(Grok claim-review `019fbaf8` 적발). 배선을 지우지 않고 `true ||` 만 붙여도
#    가드가 초록인 형태라, 이 모듈이 막으려는 중성화 수법 그대로다.
# Split keeping the preceding operator so provably-dead branches can be dropped.
_SEGMENT_SPLIT_KEEP = re.compile(r"(&&|\|\||;|\||\n)")

# 항상 성공/실패하는 상수 명령 — 단락평가의 죽은 분기를 판정하는 데만 쓴다.
# Constant-outcome commands, used only to decide provably-dead short-circuit branches.
_ALWAYS_TRUE = frozenset({"true", ":"})
_ALWAYS_FALSE = frozenset({"false"})

# 선행 환경 할당 (`VAR=value`) — 명령어가 아니라 접두사다.
# 🔴 `re.ASCII` — 셸 식별자는 ASCII 만 허용되므로 `\w` 의 유니코드 확장을 끈다.
# Leading `VAR=value` assignment is a prefix, not the command word. ASCII-only: shell identifiers.
_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=", re.ASCII)

# 🔴 파이썬 인터프리터 allowlist — 여기 없는 명령어는 배선 아님(fail-closed).
# Allowlist of interpreters; anything else is not wired.
_INTERPRETERS = frozenset({"python", "py"})
_PYTHON_VERSIONED = re.compile(r"^python3(?:\.\d+)?$")

# 셸 변수 참조 (`$PY` / `${PY}`) — **그 자체로는 아무것도 증명하지 않는다**.
# 🔴 초판은 `$PY` 를 allowlist 에 직접 넣었다. 그래서 `PY=echo; $PY scripts/x.py` 가
#    "배선됨" 으로 통과했다(실측: `invokes(...)` → True). 변수 **이름**만 보고 **할당값**을
#    보지 않은 것 — 이 파일이 봉인하려던 fail-open 을 이 파일이 그대로 범했다
#    (다각도 근본원인 분석 2026-08-01, 인벤토리 렌즈 적발).
# A `$VAR` reference proves nothing by itself: the first version allowlisted `$PY`, so
# `PY=echo; $PY script.py` counted as wired. Resolve the assignment instead.
_VAR_REF = re.compile(r"^\$\{?([A-Za-z_]\w*)\}?$", re.ASCII)

# `VAR=값` 할당 — 값은 다음 `;` 까지(명령 치환 `$(...)` 안의 `;` 는 이 형태에 없다).
# `VAR=value` assignment; value runs to the next `;`.
_ASSIGN_CAPTURE = re.compile(r"(?:^|;)\s*([A-Za-z_]\w*)=([^;]*)", re.ASCII)

# 명령 치환 안의 `echo <토큰>` — 런처 탐지형(`PY=$(… && echo 'py -3' || echo python3)`)의
# **가능한 출력 전부**를 뽑는다. 하나라도 인터프리터가 아니면 그 할당은 신뢰할 수 없다.
# Every possible output of the launcher-probe substitution; ALL must be interpreters.
# 🔴 bare 분기에서 `)` 를 제외한다 — `\S+` 는 치환 종료 괄호까지 삼켜 `python3)` 로 잡히고,
#    그러면 **실제 배선(#1243 런처)을 거부**한다(가드 자살 — 정책 17). 실측으로 확인 후 좁힘.
# Exclude `)` from the bare branch: `\S+` swallowed the substitution's closing paren, which
# rejected the REAL wiring.
_ECHO_TARGET = re.compile(r"echo\s+(?:'([^']*)'|\"([^\"]*)\"|([^\s)'\"]+))")

# YAML 배선 키 (`run:` `entry:` `command:`) — 값만 떼어 명령으로 본다.
# 🔴 `[ \t]` 명시 + 선택 그룹 1개 — `\s*-?\s*` 는 인접 `\s*` 가 모호해 backtracking 이 초선형이다.
#    줄 단위로 보므로 개행을 포함하는 `\s` 자체가 부정확하기도 하다.
# Explicit `[ \t]` and a single optional group: `\s*-?\s*` backtracks super-linearly, and `\s`
# would wrongly span newlines for what is a per-line match.
_YAML_KEY = re.compile(r"^[ \t]*(?:-[ \t]*)?(?:run|entry|command)[ \t]*:[ \t]*(.*)$")

# JSON `"command": "..."` — settings.json 훅 배선. 이스케이프된 따옴표 허용.
# 🔴 unrolled loop (`[^"\\]*(?:\\.[^"\\]*)*`) — `(?:[^"\\]|\\.)*` 는 backtracking 이 초선형이다.
# JSON hook wiring in settings.json. Unrolled loop avoids the super-linear backtracking of the
# alternation form.
_JSON_COMMAND = re.compile(r'"command"\s*:\s*("[^"\\]*(?:\\.[^"\\]*)*")')


def _strip_comments(text: str) -> str:
    """라인별 `#`-to-EOL 제거 — 주석 안 경로가 '배선' 으로 오판되는 것 차단.

    실제 호출(`run: python scripts/x.py  # 설명`)은 `#` 앞에 오므로 보존된다.
    Strip `#`-to-EOL per line; a real call precedes the comment so it survives.
    """
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _join_continuations(text: str) -> str:
    """백슬래시 줄 연결(`cmd \\` + 다음 줄)을 한 줄로 병합 — 셸 의미론.

    🔴 실측 필요성: `codeql.yml` 의 실제 배선이
    `python scripts/check_codeql_alerts.py \\` + 인자 줄들 형태다. 병합하지 않으면 마지막 토큰이
    고립된 `\\` 라 `shlex` 가 ValueError 를 내고, fail-closed 규칙에 걸려 **실제 배선을
    미배선으로 오판**한다(가드 자살 — 정책 17).
    Join backslash line-continuations; without this the real `codeql.yml` wiring would be
    misjudged as unwired because a dangling escape makes shlex raise.
    """
    return re.sub(r"\\[ \t]*\n[ \t]*", " ", text)


def _command_word(tokens: list[str]) -> str:
    """선행 `VAR=value` 할당을 건너뛴 실제 명령어.
    The actual command word, skipping leading `VAR=value` assignments."""
    for token in tokens:
        if _ASSIGNMENT.match(token):
            continue
        return token
    return ""


def _is_interpreter(word: str) -> bool:
    """명령어 토큰이 파이썬 인터프리터인가 (allowlist — 모르면 False).
    Is the command word a Python interpreter? Unknown ⇒ False (fail-closed)."""
    return word in _INTERPRETERS or bool(_PYTHON_VERSIONED.match(word))


def _resolves_to_interpreter(var: str, command: str) -> bool:
    """`$VAR` 가 **인터프리터로 확정되는 값**에 할당돼 있는가 — 이름이 아니라 값을 본다.

    두 형태를 인정한다:
      1. 리터럴  `PY=python3`      → 그 값이 인터프리터여야 한다.
      2. 런처 탐지 `PY=$(command -v py … && echo 'py -3' || echo python3)`
         → 치환이 낼 수 있는 **모든 `echo` 출력**이 인터프리터여야 한다. 하나라도 아니면 거부.

    🔴 fail-closed: 할당을 못 찾거나(외부 env 주입 등) 형태를 모르면 False.
       "모르면 배선 아님" 이 이 모듈 전체의 규칙이다.
    Resolve the VALUE, not the name. Unknown/unresolvable ⇒ False.
    """
    values = [v for name, v in _ASSIGN_CAPTURE.findall(command) if name == var]
    if not values:
        return False
    # 🔴 셸은 **마지막 할당**을 쓴다(last-wins). 초판은 "모든 할당이 인터프리터여야" 로 두어
    #    `PY=echo; PY=python3; $PY x.py` 를 거부했다 — 셸은 python3 을 돌리므로 **가드 자살**
    #    방향의 오판이다(Grok claim-review `019fbaf8` 적발). 실제 셸 의미를 따른다.
    #    반대 방향 `PY=python3; PY=echo` 는 last-wins 로도 정확히 False 다.
    # The shell uses the LAST assignment; requiring all of them rejected a genuine invocation.
    value = values[-1].strip()
    if value.startswith("$("):
        targets = [a or b or c for a, b, c in _ECHO_TARGET.findall(value)]
        # 출력 후보가 하나도 없으면 무엇이 나올지 모른다 → 거부.
        # No candidate outputs means we cannot know what runs.
        if not targets:
            return False
        # 치환은 분기마다 다른 값을 낼 수 있으므로 **모든** 후보가 인터프리터여야 한다.
        # A substitution can yield any branch, so every candidate must be an interpreter.
        return all(_is_interpreter(_first_word(t)) for t in targets)
    return _is_interpreter(_first_word(value))


def _first_word(value: str) -> str:
    """값의 첫 단어 (빈 값이면 빈 문자열). / First word of a value, or ""."""
    parts = value.split()
    return parts[0] if parts else ""


def _segments(command: str) -> list[tuple[str, str]]:
    """`(표지, 세그먼트)` 목록 — 표지가 `"dead"` 면 **절대 실행되지 않는 분기**다.

    상수 명령(`true`/`:`/`false`)이 앞선 단락평가만 죽은 것으로 본다. 그 이상(실제 종료
    코드 예측)은 정적으로 불가하고, 무리하면 실배선을 거부하는 가드 자살이 된다(정책 17).
    Only constant-outcome short circuits are ruled dead; predicting real exit codes is not
    statically possible and over-reaching would reject genuine wiring.
    """
    parts = _SEGMENT_SPLIT_KEEP.split(command)
    out: list[tuple[str, str]] = []
    prev_op = ""
    prev_word = ""
    for piece in parts:
        if _SEGMENT_SPLIT_KEEP.fullmatch(piece):
            prev_op = piece
            continue
        text = piece.strip()
        if not text:
            continue
        dead = (prev_op == "||" and prev_word in _ALWAYS_TRUE) or (
            prev_op == "&&" and prev_word in _ALWAYS_FALSE
        )
        out.append(("dead" if dead else "live", text))
        prev_word = _first_word(text)
    return out


def _command_is_interpreter(word: str, command: str) -> bool:
    """명령어가 인터프리터인가 — `$VAR` 참조면 **할당값까지 해소**해 판정한다.
    Treat a `$VAR` command word by resolving its assignment, never by the name alone."""
    ref = _VAR_REF.match(word)
    if ref:
        return _resolves_to_interpreter(ref.group(1), command)
    return _is_interpreter(word)


def _mentions_path(tokens: Iterable[str], script_path: str) -> bool:
    """토큰 중 하나가 대상 스크립트를 가리키는가 (경로 구분자 정규화).

    🔴 접미사 일치는 **경로 경계**에서만 인정한다. 초판은 맨 `endswith` 라
    `python not_scripts/check_x.py` 가 대상 `scripts/check_x.py` 의 배선으로 잡혔다
    (Grok claim-review `019fbaf8` 적발). 배선을 **다른 파일로 몰래 갈아끼워도** 가드가
    초록인 형태다 — 이 모듈이 막으려는 바로 그 클래스라 좁힌다.
    `path/scripts/check_x.py`(경계 `/`)와 `./scripts/check_x.py` 는 계속 인정한다.
    Suffix matches must land on a path boundary; a bare endswith accepted `not_scripts/…`.
    """
    target = script_path.replace("\\", "/").lstrip("./")
    for token in tokens:
        norm = token.replace("\\", "/").lstrip("./")
        if norm == target or norm.endswith("/" + target):
            return True
    return False


def invokes(command: str, script_path: str) -> bool:
    """`command` 가 `script_path` 를 **실제로 실행**하는가.

    🔴 substring 아님 — 명령어가 인터프리터여야 한다. `echo scripts/x.py` 는 False.
    Not a substring test: the command word must be an interpreter.
    """
    if not command or not script_path:
        return False
    for op, segment in _segments(_join_continuations(_strip_comments(command))):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            # 파싱 불가(따옴표 불균형 등)는 fail-closed — "모르겠으면 배선 아님".
            # Unparseable ⇒ fail closed: unknown is not wired.
            continue
        if not tokens:
            continue
        if op == "dead":
            continue
        if _command_is_interpreter(_command_word(tokens), command) and _mentions_path(tokens, script_path):
            return True
    return False


def any_invokes(commands: Iterable[str], script_path: str) -> bool:
    """명령 목록 중 하나라도 스크립트를 실행하는가.
    Does any command in the list actually run the script?"""
    return any(invokes(c, script_path) for c in commands)


def surface_commands(text: str) -> list[str]:
    """원시 표면 텍스트(YAML/JSON)에서 **명령 후보**를 추출한다.

    - JSON `"command": "..."` 는 원문에서 추출한다(주석 제거 전 — JSON 문자열 안의 `#` 보존).
    - YAML 은 주석 제거 후, `run:`/`entry:`/`command:` 값 또는 (블록 스칼라 본문인) 줄 자체.
    Extract candidate commands from a raw surface: JSON hook commands from the original text
    (before comment stripping, so `#` inside JSON strings survives), YAML keys/blocks after it.
    """
    candidates: list[str] = []
    for raw in _JSON_COMMAND.findall(text):
        try:
            candidates.append(json.loads(raw))
        except ValueError:
            continue
    # 주석 제거 → 줄 연결 병합 순서. 반대로 하면 `cmd \` 뒤 주석 줄이 명령에 섞인다.
    # Strip comments first, then join continuations; the reverse order would splice a comment in.
    for line in _join_continuations(_strip_comments(text)).splitlines():
        if not line.strip():
            continue
        keyed = _YAML_KEY.match(line)
        # 키가 있으면 값만, 없으면 줄 자체(블록 스칼라 `run: |` 본문).
        candidates.append(keyed.group(1) if keyed else line)
    return candidates


def surface_invokes(text: str, script_path: str) -> bool:
    """원시 표면 텍스트 어딘가에서 스크립트가 **실행**되는가.
    Is the script actually invoked anywhere in this raw surface text?"""
    return any_invokes(surface_commands(text), script_path)
