#!/usr/bin/env python3
"""PostToolUse pytest 스모크 훅 — 편집 후 대응 tests/unit 만 빠르게 실행.
PostToolUse pytest smoke hook — after an edit, quickly run only the matching tests/unit.

파이썬(src · alembic · scripts · 훅)은 경로 규칙으로 대응 시험을 정하고, 템플릿 · CSS 는 그 파일을 경로 문자열로 적은
시험들을 돌린다. 워크플로는 YAML 파싱만 본다(읽는 시험이 75 초 벽을 넘는다).
Python files map by path rule; templates and stylesheets run the tests naming them; workflows are parse-checked only.

회고 2026-07-18 P1 테마 C: 기존 훅은 `pytest tests/`(전체 5566)를 60s 타임아웃에 돌려 완주 불가 →
SIGTERM → `|| true` 로 삼켜져 **false-green**. 'Hook 신뢰' 필수 원칙의 토대가 붕괴했다. 편집된 src
경로 → 대응 tests/unit 서브디렉토리(없으면 collection 스모크)만 돌리면 실제로 완주하는 신호가 된다.
Retro 2026-07-18 P1 theme C: the old hook ran the full suite in a 60s timeout → SIGTERM → `|| true`
swallow → false-green. Scoping to the affected subarea makes the signal actually finish.

🔴 이 훅은 **best-effort 조기 실패 탐지** — 전체 게이트가 아니다. 전체 게이트는 push-time(6-step ②)로
위임된다. 비차단(advisory·항상 exit 0) — edit 을 막지 않는다.
This hook is best-effort early-failure detection, NOT the full gate (that stays at push-time 6-step ②).
Non-blocking (always exit 0).

🔴 출력 채널 — PostToolUse 의 plain stdout 은 에이전트에게 가지 않는다(디버그 로그 · 세션 기록에만 남는다).
   ❌(실패) · ⚠️(미완)는 JSON 한 개로 낸다 — `hookSpecificOutput.additionalContext`(에이전트) · `systemMessage`(사람).
   ✅ · ℹ️ 는 plain stdout 에만 둔다 — 편집마다 맥락에 더하면 경고가 죽는다. 시험 = `test_posttool_smoke_channel.py`.
Output channel: plain PostToolUse stdout never reaches the agent, so ❌/⚠️ go out as one JSON object
(additionalContext for the agent, systemMessage for the person); ✅/ℹ️ stay in plain stdout.

사용법 / Usage: PostToolUse 훅 (stdin 으로 tool_input JSON 수신).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# 스코프 실행 타임아웃(초) — 서브영역 단위라 대개 <30s. 훅 자체는 settings.json timeout 이 상한.
# Scoped-run timeout (s) — a subarea usually runs in <30s; settings.json timeout bounds the hook.
_RUN_TIMEOUT = 75

# 에이전트에게 넘기는 출력 끝 줄 수 · 줄 길이 상한 — `-q -x` 출력은 FAILED(ERROR) 줄 · 멈춤 줄 · 건수 줄로 끝난다.
# 맥락은 비용이라 배너 + 이 세 줄만 넘긴다.
# How many trailing output lines (and how wide) reach the agent: `-q -x` ends with the FAILED/ERROR, stop and count lines.
_AGENT_LINES = 3
_AGENT_WIDTH = 300
_SCOPE_NOTE = "best-effort 조기탐지 (전체 게이트 = push 전 단위 전체)"


def _norm(path):
    """경로 정규화 — 백슬래시 → 슬래시.
    Normalize path separators (backslash → slash)."""
    return (path or "").replace("\\", "/")


# 감시 대상 최상위 디렉토리 — src/ 만이 아니다.
# Watched top-level roots — not just src/.
#   🔴 `alembic/` 은 이번 사이클 최다 결함 영역(#1102 fileConfig 가 앱 로깅을 파괴)이고
#      `scripts/` 는 최다 churn(가드 스크립트 다수)인데 둘 다 훅이 **아예 발동하지 않았다**.
#      결함이 가장 많은 곳에 조기탐지가 0이었다.
#   🔴 `.claude/hooks` 추가 (#1441) — **훅 자신이 감시 밖이었다.** 훅은 모든 편집에 개입하는
#      표면이라 여기서 깨지면 세션 전체가 영향을 받는데, 정작 그 파일만 조기탐지가 0이었다.
#      바로 위 문단이 alembic·scripts 를 넣은 것과 같은 논리다 — 훅만 빠져 있었다.
#      Hooks themselves were unwatched, though a broken hook affects every edit in the session.
_WATCHED_ROOTS = ("src", "alembic", "scripts", ".claude/hooks")

# 템플릿 · 스타일 — 파일 이름으로 대응 시험이 정해지지 않는다. 그 파일을 경로 문자열로 적은 시험 파일들을 돌린다
# (원장 이관 K22 P2-31 — 주 편집면에 조기탐지 0). 실측: base.html 14개 5.9 s · settings.html 22개 11.6 s.
# Templates and stylesheets: run the test files that name the edited file in a string literal.
_NAMED_ROOTS = (("src/templates", ".html"), ("src/static/css", ".css"))
# 워크플로 — 그 파일을 읽는 시험이 75 초 벽을 넘는다(ci.yml 35개 · 110 s 실측) → YAML 파싱만 보고 그렇게 말한다.
# Workflows: the tests that read them exceed the 75 s wall, so only the YAML parse is checked — and said so.
_WORKFLOW_ROOT = ".github/workflows"


def _under(path, root):
    """정규화된 경로가 루트(여러 마디 가능) 아래인가."""
    return f"/{root}/" in path or path.startswith(f"{root}/")


def is_named_file(path):
    """템플릿 · 스타일 파일인가 — 그 파일을 경로 문자열로 적은 시험이 대상이다.
    Whether the edit is a template or stylesheet, whose targets are the tests naming it."""
    p = _norm(path)
    return any(p.endswith(suffix) and _under(p, root) for root, suffix in _NAMED_ROOTS)


def is_workflow_file(path):
    """GitHub 워크플로 파일인가 / whether the edit is a GitHub workflow."""
    p = _norm(path)
    return p.endswith((".yml", ".yaml")) and _under(p, _WORKFLOW_ROOT)


def tests_naming(path, repo):
    """`tests/unit` 에서 그 파일 이름 자체이거나 `/이름` 으로 끝나는 문자열을 적은 시험 파일(정렬된 상대 경로).

    이름만 닮은 값(`database.html` · `base.html.bak`)과 문장 속 언급은 고르지 않는다 — 따옴표가 이름(또는 `/` 로 끝나는
    경로 앞부분)에 바로 붙어야 한다.
    Test files holding a string literal that is the file's name or ends with `/<name>`.
    """
    name = Path(_norm(path)).name
    # 경로 앞부분은 «여는 따옴표와 같은 문자» 와 줄바꿈만 피한다 — 다른 따옴표는 글자다(`"o'reilly/x.html"` · Grok 반례).
    # The path prefix only avoids the opening quote and newlines; the other quote is an ordinary character.
    literal = re.compile(r"""(["'])(?:(?:(?!\1).)*/)?""" + re.escape(name) + r"\1")
    out = []
    for test in sorted((Path(repo) / "tests" / "unit").rglob("test_*.py")):
        try:
            text = test.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if literal.search(text):
            out.append(test.relative_to(repo).as_posix())
    return out


def _workflow_check(path):
    """워크플로 편집 판정 — (에이전트에게 알릴 것인가, 배너). YAML 파싱만 본다.

    깨지면 ❌ · 파서가 없어 못 쟀으면 ⚠️ — 둘 다 알린다. 성하면 «단언 0건» 을 밝히는 ℹ️ 이고 알리지 않는다(거짓 ✅ 금지).
    Workflow check: (notify the agent?, banner). ❌ when broken, ⚠️ when unparsed for lack of a parser, else ℹ️.
    """
    try:
        from ruamel.yaml import YAML  # pylint: disable=import-outside-toplevel  # 워크플로 편집 때만 / only on workflow edits
        from ruamel.yaml.error import YAMLError  # pylint: disable=import-outside-toplevel
    except ImportError:
        return True, "⚠️ 워크플로 YAML 을 못 쟀다 (파서 ruamel.yaml 이 없다 · push 게이트가 돈다)"
    try:
        YAML(typ="safe", pure=True).load(Path(_norm(path)).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        first = (str(exc).splitlines() or [type(exc).__name__])[0]
        return True, f"❌ 워크플로 YAML 파싱 실패 — {first[:160]}"
    return False, "ℹ️ YAML 파싱만 확인 (단언 0건 — 이 워크플로를 읽는 시험은 75 초 벽을 넘어 push 게이트가 돈다)"


def agent_message(banner_line, tail):
    """에이전트 · 사람에게 보낼 글 — 배너 한 줄 + 출력의 끝 `_AGENT_LINES` 줄(줄마다 `_AGENT_WIDTH` 자까지).
    The text for the agent and the person: the banner plus the last few output lines, each clipped."""
    lines = [line[:_AGENT_WIDTH] for line in (tail or "").splitlines() if line.strip()]
    return "\n".join([banner_line, *lines[-_AGENT_LINES:]])


def _emit(message):
    """에이전트 맥락(additionalContext)과 사람(systemMessage)에게 — stdout 전체가 이 JSON 한 개여야 읽힌다.
    Send to the agent's context and the person; Claude Code reads the fields only when stdout is exactly this JSON."""
    print(json.dumps({"systemMessage": message,
                      "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}},
                     ensure_ascii=True))


def is_watched_file(path):
    """편집 파일이 감시 대상 루트 하위 Python 파일인지.
    Whether the edited file lives under a watched root."""
    p = _norm(path)
    if not p.endswith(".py"):
        return False
    return any(f"/{r}/" in p or p.startswith(f"{r}/") for r in _WATCHED_ROOTS)


def is_src_file(path):
    """하위 호환 별칭 — 기존 호출부/테스트 보존.
    Backwards-compatible alias."""
    p = _norm(path)
    return "/src/" in p or p.startswith("src/")


def _after_src(path):
    """src/ 이후 상대 경로 반환 (src 아니면 '')."""
    p = _norm(path)
    if "/src/" in p:
        return p.split("/src/", 1)[1]
    if p.startswith("src/"):
        return p[len("src/"):]
    return ""


def _root_and_rest(path):
    """감시 루트와 그 이후 상대 경로 — (`"src"`, `"gate/engine.py"`) 형태."""
    p = _norm(path)
    # 🔴 **긴 루트 먼저** (Grok claim-review `01a0121f`) — 다중 세그먼트 루트(`.claude/hooks`)가
    #    선언 순서 때문에 짧은 루트에 먼저 잡히면 엉뚱한 대상이 나온다. 실측: 선언 순서로는
    #    `src/.claude/hooks/x.py` → 루트 `src` → `tests/unit/.claude`(존재하지 않는 경로).
    #    존재하지 않는 대상은 수집 스모크로 안전하게 강등되지만, 애초에 그 분기를 만들지 않는다.
    # Longest root first: a multi-segment root must not lose to a shorter prefix.
    for root in sorted(_WATCHED_ROOTS, key=len, reverse=True):
        if f"/{root}/" in p:
            return root, p.split(f"/{root}/", 1)[1]
        if p.startswith(f"{root}/"):
            return root, p[len(root) + 1:]
    return None, ""


def derive_test_target(path, repo=None):
    """편집 파일 → 대응 테스트 경로(디렉토리 또는 **파일**). 없으면 None.

    Map an edited file to its test target — a directory OR a specific file.

    · `src/gate/engine.py`  → `tests/unit/gate`            (서브영역 디렉토리)
    · `src/scheduler.py`    → `tests/unit/test_scheduler.py`  🔴 **정확 대응 파일**
    · `scripts/foo.py`      → `tests/unit/scripts/test_foo.py`
    · `alembic/env.py`      → `tests/unit/migrations`

    🔴 **왜 정확 대응 파일까지 보는가 (2026-07-19 회고 P2 D10)**: 이전 판은 `len(parts) < 2`
    이면 무조건 collection 스모크로 **강등**했다. 그런데 `src/` 직속 7파일 중 **6개가 정확히
    대응하는 테스트 파일을 갖고 있다**(config·crypto·database·logging_config·main·scheduler).
    즉 실행 가능한 단언이 있는데 0-단언 수집으로 내려앉고 있었다 — 그중 `logging_config.py` 는
    이 사이클의 토큰 유출 봉인 지점이고 `scheduler.py` 는 cron P0 대체 코어다.
    The previous version demoted every src-direct file to a 0-assertion collection smoke, even
    though 6 of 7 have an exact matching test file.
    """
    root, rest = _root_and_rest(path)
    if root is None:
        return None
    repo = repo or Path(__file__).resolve().parents[2]
    parts = [p for p in rest.split("/") if p]
    if not parts:
        return None

    if root == "alembic":
        return "tests/unit/migrations"

    stem = parts[-1][:-3] if parts[-1].endswith(".py") else parts[-1]
    if stem == "__init__":
        return None

    if root == "scripts":
        # 🔴 디렉토리 폴백을 두지 않는다 — 아래 훅 쪽과 같은 이유다. 시험 이름이 규칙과 어긋난 스크립트가
        #    `tests/unit/scripts` 전체로 떨어져, 그 스크립트를 검증하지 않는 남의 시험 수백 건이 75 초 벽에 걸렸다
        #    (원장 L11 P2-83 — 신호 없는 «미완»). None 이면 수집 스모크 + «단언 0건» 배너가 정직하게 나간다.
        # No directory fallback: it ran hundreds of unrelated tests into the 75 s wall.
        exact = f"tests/unit/scripts/test_{stem}.py"
        return exact if (repo / exact).is_file() else None

    if root == ".claude/hooks":
        # 🔴 디렉토리 폴백을 **두지 않는다** (Grok claim-review `01a0121f` 적발).
        #    초판은 대응 파일이 없으면 `tests/unit/hooks` 를 겨냥했는데, 그러면 그 훅을
        #    **검증하지 않는 남의 테스트 197개**가 돌고 배너가 `✅ 스모크 통과` 를 찍는다.
        #    이 훅이 없애려고 만들어진 바로 그 false-green 이다(파일 머리 docstring).
        #    `None` 이면 수집 스모크 + 「단언 0건 — 대응 테스트 없음」 배너가 나간다 — 정직하다.
        # No directory fallback: it would run 197 unrelated tests and print ✅ for a hook that
        # nothing verified — the exact false-green this hook exists to prevent.
        exact = f"tests/unit/hooks/test_{stem}.py"
        return exact if (repo / exact).is_file() else None

    # root == "src"
    if len(parts) >= 2:
        return f"tests/unit/{parts[0]}"
    exact = f"tests/unit/test_{stem}.py"
    return exact if (repo / exact).is_file() else None


def checkout_of(path, fallback):
    """편집한 파일이 든 체크아웃(git 최상위) — 못 찾으면 fallback.

    🔴 예전엔 이 훅 파일이 든 체크아웃에서 시험을 돌렸다 — 워크트리에서 고친 파일을 주 체크아웃의 옛 코드로 재고
       ✅ 를 찍었다(원장 L11 P1-30 · P2-47). 편집한 파일의 체크아웃에서 잰다. 상대 경로 · git 실패면 예전 동작.
    The checkout holding the edited file; the hook's own checkout measured stale code for worktree edits.
    """
    p = Path(_norm(path))
    if not p.is_absolute() or not p.parent.is_dir():
        return fallback
    try:
        r = subprocess.run(["git", "-C", str(p.parent), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return fallback
    top = (r.stdout or "").strip()
    return Path(top) if r.returncode == 0 and top else fallback


def _banner(rc, asserted):
    """결과 배너 — 🔴 **단언을 실행했는지**와 통과 여부를 구별한다.

    Build the result banner, distinguishing "assertions ran" from "collection only".

    🔴 사고 (2026-07-19 회고 P2 D12): 이전 판은 `--co`(수집만, **단언 0건**) 경로에도
    `✅ 스모크 통과` 를 출력했다. 아무것도 검증하지 않은 실행이 검증 통과로 보였다 —
    이 훅이 존재하는 이유였던 false-green 을 훅 자신이 재생산한 것이다.
    수집 성공은 "import 가 깨지지 않았다" 이지 "동작이 옳다" 가 아니다.
    A collection-only run asserts nothing; labelling it "passed" is the very false-green
    this hook was created to eliminate.
    """
    if rc is None:
        return "⚠️ 스모크 미완(타임아웃/오류)"
    if rc != 0:
        return "❌ 스모크 실패"
    return "✅ 스모크 통과" if asserted else "ℹ️ 수집만 확인 (단언 0건 — 대응 테스트 없음)"


def _run(cmd, cwd):
    """pytest 서브프로세스(cwd=repo 루트) — (returncode, tail 출력).
    Run a pytest subprocess from the repo root; return (returncode, tail output)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=cwd,
            timeout=_RUN_TIMEOUT, encoding="utf-8", errors="replace",
        )
        # stdout 이 비면 stderr — pytest 사용 오류(인자 · 플러그인)는 stderr 로만 나온다.
        # Fall back to stderr: pytest usage errors print only there.
        tail = "\n".join((r.stdout or r.stderr or "").splitlines()[-8:])
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return None, f"⏱️ 스모크 타임아웃({_RUN_TIMEOUT}s) — 전체 게이트는 push-time 에 실행 / smoke timed out"
    except OSError as e:
        return None, f"실행 오류 / run error: {e}"


def main():
    try:
        # 바이트로 읽어 UTF-8 로 — 로캘(cp949)로 읽으면 한글 경로가 바뀐다(원장 #1940 M06 P2-32) / bytes, decoded as UTF-8
        raw = getattr(sys.stdin, "buffer", sys.stdin).read()
        data = json.loads(raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw)
    except (json.JSONDecodeError, ValueError):
        return 0  # 입력 파싱 실패 — advisory 훅은 조용히 통과 / unparsable input, pass quietly
    path = data.get("tool_input", {}).get("file_path", "")
    # 🔴 `is_watched_file` — src/ + alembic/ + scripts/. **`is_src_file` 아니다.**
    #   (2026-07-20 세션5 회고 P1, 10 에이전트 수렴): #1145 가 감시 루트를 alembic/·scripts/ 로
    #   넓혔다고 봉인했으나, 진입점인 여기가 여전히 `is_src_file`(src 전용)로 단락시켜
    #   그 확장이 **런타임에서 통째로 dead** 였다. 순수 함수(`is_watched_file`·`derive_test_target`)
    #   테스트만 있었고 **main() 디스패치를 검증하는 테스트가 없어** false-green 이었다 —
    #   이 훅이 없애려던 바로 그 결함을 봉인 선언과 함께 재생산했다.
    # Entry point must gate on is_watched_file (src+alembic+scripts), NOT is_src_file; the D11
    # extension was dead in the runtime path because main() still short-circuited on is_src_file.
    if is_workflow_file(path):
        notify, banner = _workflow_check(path)
        line = f"{banner} — {_SCOPE_NOTE}"
        if notify:
            _emit(line)
        else:
            print(line)
        return 0
    named = is_named_file(path)
    if not (is_watched_file(path) or named):
        return 0  # 감시 대상 편집만 / only watched-root edits

    repo = checkout_of(path, Path(__file__).resolve().parents[2])
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if named:
        targets = tests_naming(path, repo)
        label = f"{len(targets)} files naming {Path(_norm(path)).name}"
    else:
        target = derive_test_target(path, repo)
        targets = [target] if target and (repo / target).exists() else []
        label = target
    asserted = bool(targets)
    if asserted:
        scope, cmd = label, [*base, *targets, "-x", "--timeout=15"]
    else:
        # 대응 테스트 없음 → collection 스모크(import/parametrize 파손 = #1041 클래스 조기 탐지).
        # No matching test → collection smoke (catches import/parametrize breakage).
        scope, cmd = "tests/unit (collect)", [*base, "tests/unit", "--co"]

    rc, tail = _run(cmd, cwd=str(repo))
    line = f"{_banner(rc, asserted)} [{scope}] — {_SCOPE_NOTE}"
    if rc != 0:
        # ❌(rc ≠ 0) · ⚠️(rc None — 타임아웃 · 실행 오류) — 에이전트가 알아야 할 결과다.
        # A failure or an unfinished run: the agent has to see it.
        _emit(agent_message(line, tail))
    else:
        # ✅ · ℹ️ — 세션 기록(plain stdout)에만 남긴다. / Pass or collect-only: keep it out of the context.
        print(line)
    return 0  # 비차단 advisory / non-blocking advisory


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main())
