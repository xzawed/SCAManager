"""파일 도구 · 위임 실행의 차단면 — settings 의 거부 목록을 훅의 .env 이름 판정과 대조한다(원장 #1940 M08).
File tools and delegated execution: the settings deny list is checked against the hook's .env name test.

credential 훅은 셸 도구(Bash · PowerShell)와 운영 MCP 만 본다. Read · Grep · Glob 으로 .env 를 여는 길과 Grok 위임
실행은 그 훅 밖이다 — 그 길은 `.claude/settings.json` `permissions.deny` 가 막는다. Claude Code 는 Read 거부를
Grep · Glob 과, 파일 이름을 적은 셸의 cat · grep · ls 에도 적용하고 bypass 모드에서도 막는다(11-28 미끼 파일로 실측 —
`test -f` · `cp .env.example .env` 는 통과). 이 시험은 두 목록이 갈라지지 않게 잰다:

  - 훅이 .env 꼴로 보는 이름(훅의 탐침 + 흔한 변형) → Read 거부가 하나 이상 맞는다
  - 템플릿(.env.example 등) · 닮은 이름(env.py 등) → 어떤 Read 거부도 맞지 않는다 — 템플릿은 Read · Edit 로 고친다
  - 모든 Read 거부는 `//**/` 로 시작한다 — 상대 꼴(`**/.env`)은 세션 작업 폴더 아래만 보아, 워크트리에서 일할 때
    주 체크아웃의 .env 를 놓친다
  - Grok 은 계획 모드(`grok_build_plan` — 셸 · 편집 · MCP 를 Grok 쪽에서 거부)만 쓴다 — 셸을 도는 위임 도구는 거부
    목록에, 계획 · 상태 도구는 밖에 있다

알려진 한계: Read 거부는 이름 목록이라 흔한 변형만 덮는다(`.env.<드문 이름>` 은 셸 훅만 막는다). `.env.*` 를 통째로
막으면 템플릿까지 막히고, 디스크 전체(`//`) 규칙에서는 예외(`!`)를 낼 수 없다.
Known limit: the Read deny list names common variants only; a blanket `.env.*` would also block the templates.
"""
import fnmatch
import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_ANCHOR = "//**/"


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_credential_dump_for_file_tool_tests", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_hook()

# 훅의 탐침에 더해 재는 흔한 변형 — .gitignore 의 꼴 · 배포 환경 이름 · 사본(원장 #1940 M08 의 사건 꼴).
# Common variants measured on top of the hook's own probes.
_COMMON_DOTENV_NAMES = (
    ".env.production", ".env.development", ".env.staging.local", ".env.test", ".env-old", ".env_prod",
    "docker.env", "env.backup-20261125", "prod_env.bak", "dotenv-old", "env.orig", ".env~",
)
# 닮았지만 .env 꼴이 아닌 이름 — 막히면 일상 편집 · 검색이 막힌다 / look-alikes that must stay readable
_LOOKALIKES = ("env.py", "environment.py", "env.py.bak", "backup.sh", "env-vars.md", "venv.cfg")
# 셸을 도는 Grok 도구 · 막지 않는 Grok 도구 / Grok tools that run a shell, and those that do not
_GROK = "mcp__plugin_grok_grok-build__"
_GROK_EXECUTING = ("grok_build_delegate", "grok_build_verify", "grok_cli")
_GROK_KEPT = ("grok_build_plan", "grok_build_status", "grok_build_usage", "grok_auth_check")


def _deny_rules():
    data = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    return data.get("permissions", {}).get("deny", [])


def _read_globs():
    """`Read(<패턴>)` 의 패턴 목록 / the patterns of the Read deny rules."""
    return [rule[len("Read("):-1] for rule in _deny_rules() if rule.startswith("Read(") and rule.endswith(")")]


def _rules_hitting(name):
    """이 파일 이름에 맞는 Read 거부 — `//**/<이름 글롭>` 꼴만 있으므로 이름에 글롭을 댄다.
    The Read deny rules matching this file name (every rule is `//**/<name glob>`)."""
    return [glob for glob in _read_globs() if fnmatch.fnmatchcase(name, glob[len(_ANCHOR):])]


def test_read_deny_rules_cover_the_whole_disk():
    """Read 거부가 있고, 모두 디스크 전체 꼴(`//**/<이름>`)이다 — 상대 꼴은 다른 작업 폴더의 .env 를 놓친다."""
    globs = _read_globs()
    assert globs, ".claude/settings.json 에 Read 거부가 없다 — 파일 도구로 .env 를 여는 길이 열려 있다."
    loose = [glob for glob in globs if not glob.startswith(_ANCHOR) or "/" in glob[len(_ANCHOR):]]
    assert not loose, (
        f"디스크 전체 꼴이 아닌 Read 거부: {loose}\n"
        "`**/.env` · `.env` 는 세션 작업 폴더 아래만 본다 — 워크트리에서 일하면 주 체크아웃의 .env 가 열린다."
    )


def test_every_dotenv_like_name_is_denied_for_file_tools():
    """🔴 훅이 .env 꼴로 보는 이름은 파일 도구에서도 막힌다 — 탐침은 훅에서 가져온다(손 사본 아님)."""
    names = tuple(_MOD._DOTENV_NAME_PROBES) + _COMMON_DOTENV_NAMES
    not_dotenv = [name for name in names if not _MOD._is_dotenv_name(name)]
    assert not not_dotenv, f"훅이 .env 꼴로 보지 않는 이름이 목록에 있다(목록 · 훅 둘 중 하나가 틀렸다): {not_dotenv}"
    open_names = [name for name in names if not _rules_hitting(name)]
    assert not open_names, (
        f"셸 훅은 막지만 파일 도구(Read · Grep · Glob)로는 열리는 이름: {open_names}\n"
        "해결: .claude/settings.json permissions.deny 에 `Read(//**/<이름 글롭>)` 을 더한다."
    )


def test_templates_and_lookalikes_stay_readable():
    """템플릿 · 닮은 이름은 어떤 Read 거부에도 맞지 않는다 — 훅도 .env 꼴로 보지 않는다(두 판정이 같은 편이다)."""
    names = tuple(sorted(_MOD._DOTENV_TEMPLATES)) + _LOOKALIKES
    blocked = {name: _rules_hitting(name) for name in names if _rules_hitting(name)}
    assert not blocked, f"막히면 안 되는 이름이 Read 거부에 맞는다: {blocked}"
    hook_blocked = [name for name in names if _MOD._is_dotenv_name(name)]
    assert not hook_blocked, f"훅이 템플릿 · 닮은 이름을 .env 꼴로 본다: {hook_blocked}"


def test_grok_runs_in_plan_mode_only():
    """Grok 위임 실행(셸)은 훅을 거치지 않는다 — 실행 도구는 거부하고, 계획 · 상태 도구는 남긴다(원장 #1940 M08)."""
    rules = set(_deny_rules())
    missing = [tool for tool in _GROK_EXECUTING if _GROK + tool not in rules]
    assert not missing, f"셸을 도는 Grok 도구가 거부 목록에 없다: {missing}"
    over = [tool for tool in _GROK_KEPT if _GROK + tool in rules or f"{_GROK}*" in rules]
    assert not over, f"계획 · 상태 도구까지 막았다 — claim-review 를 부를 길이 없다: {over}"
