"""파일 도구 · 위임 실행의 차단면 — settings 의 거부 목록을 훅의 .env 이름 판정과 대조한다(원장 #1940 M08).
File tools and delegated execution: the settings deny list is checked against the hook's .env name test.

credential 훅은 셸 도구(Bash · PowerShell)와 운영 MCP 만 본다. Read · Grep · Glob 으로 .env 를 여는 길과 Grok 위임
실행은 그 훅 밖이다 — 그 길은 `.claude/settings.json` `permissions.deny` 가 막는다. Claude Code 는 Read 거부를
Grep · Glob 과, 파일 이름을 적은 셸의 cat · grep · ls 에도 적용하고 bypass 모드에서도 막는다(11-28 미끼 파일로 실측 —
`test -f` · `cp .env.example .env` 는 통과). 거부는 두 층이다:

  - 작업 폴더 아래 — `Read(**/.env.*)` 로 전부 막고 템플릿만 `Read(!**/<템플릿>)` 로 뺀다(훅과 같은 «막고 안전한 꼴만
    통과» 원칙). `!` 는 상대 규칙에서만 예외를 낸다(문서) — 그래서 이 층은 세션 작업 폴더 아래만 덮는다(실측).
  - 디스크 전체 — `Read(//**/<이름 글롭>)` 의 이름 목록. 워크트리에서 일할 때 주 체크아웃의 .env 같은 폴더 밖 파일을 덮는다.
    `.env.*` 통째는 둘 수 없다 — 템플릿까지 막고, 디스크 전체 규칙에는 예외를 낼 수 없다.

이 시험이 재는 것: 훅이 .env 꼴로 보는 흔한 이름은 디스크 전체 층에서 막히고, 훅이 `.env.` 로 시작해 막는 이름은 작업
폴더 층에서 막히며, 템플릿 · 닮은 이름은 어느 층에서도 막히지 않는다. Grok 은 계획 모드만 쓴다.
"""
import fnmatch
import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_ANYWHERE = "//**/"
_UNDER_CWD = "**/"
_CATCH_ALL = "**/.env.*"


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_credential_dump_for_file_tool_tests", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_hook()

# 훅의 탐침에 더해 재는 흔한 변형 — .gitignore 의 꼴 · 배포 환경 이름 · 사본(원장 #1940 M08 의 사건 꼴) · 편집기 · 복제 이름.
# Common variants measured on top of the hook's own probes.
_COMMON_DOTENV_NAMES = (
    ".env.production", ".env.development", ".env.staging.local", ".env.test", ".env-old", ".env_prod",
    "docker.env", "env.backup-20261125", "prod_env.bak", "my-env.old", "env.orig", "env.original", ".env~", "prod.env~",
    ".env - copy", "prod.env - copy", ".env (1)", "env.backup (1)", ".env - 복사본", ".env.swp",
)
# witness-corpus: env 낱말이 든 이 리포 · 흔한 도구의 보통 파일 이름(마이그레이션 · 문서 · 가상환경) — 거부 꼴에서 뽑지 않았다
_LOOKALIKES = ("env.py", "environment.py", "env-vars.md", "venv.cfg", "env.py.bak", "venv.bak", "venv_backup")
# 셸을 도는 Grok 도구 · 막지 않는 Grok 도구 / Grok tools that run a shell, and those that do not
_GROK = "mcp__plugin_grok_grok-build__"
_GROK_EXECUTING = ("grok_build_delegate", "grok_build_verify", "grok_cli")
_GROK_KEPT = ("grok_build_plan", "grok_build_status", "grok_build_usage", "grok_auth_check")


def _deny_rules():
    data = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    return data.get("permissions", {}).get("deny", [])


def _read_patterns():
    """`Read(<패턴>)` 의 패턴 목록(순서 그대로) / Read deny patterns, in order."""
    return [rule[len("Read("):-1] for rule in _deny_rules() if rule.startswith("Read(") and rule.endswith(")")]


def _anywhere_hits(name):
    """디스크 전체 층에서 이 이름에 맞는 규칙 / disk-wide rules matching this file name."""
    return [p for p in _read_patterns() if p.startswith(_ANYWHERE) and fnmatch.fnmatchcase(name, p[len(_ANYWHERE):])]


def _denied_under_cwd(name):
    """작업 폴더 층 — 순서대로 맞추되 `!` 는 앞선 상대 규칙에서 뺀다(gitignore 부정) / cwd layer, `!` carves out."""
    denied = False
    for p in _read_patterns():
        if p.startswith("!" + _UNDER_CWD) and fnmatch.fnmatchcase(name, p[len("!" + _UNDER_CWD):]):
            denied = False
        elif p.startswith(_UNDER_CWD) and fnmatch.fnmatchcase(name, p[len(_UNDER_CWD):]):
            denied = True
    return denied


def test_read_deny_layers_have_the_expected_shape():
    """두 층의 꼴 — 상대 규칙은 작업 폴더 catch-all 과 템플릿 예외뿐이고(예외 = 훅의 템플릿 목록, 파생), 나머지는 디스크 전체다."""
    patterns = _read_patterns()
    assert _CATCH_ALL in patterns, "작업 폴더 아래 .env.* 전체 거부(`Read(**/.env.*)`)가 없다."
    carve_outs = {p[len("!" + _UNDER_CWD):] for p in patterns if p.startswith("!")}
    assert carve_outs == set(_MOD._DOTENV_TEMPLATES), (
        f"템플릿 예외 {sorted(carve_outs)} 가 훅의 템플릿 목록 {sorted(_MOD._DOTENV_TEMPLATES)} 과 다르다 — 둘 중 하나만 고쳤다."
    )
    first_carve = min(i for i, p in enumerate(patterns) if p.startswith("!"))
    assert patterns.index(_CATCH_ALL) < first_carve, "`!` 예외는 앞에 놓인 규칙에서만 뺀다 — catch-all 이 예외보다 먼저 와야 한다."
    stray = [p for p in patterns if p != _CATCH_ALL and not p.startswith(("!", _ANYWHERE))]
    assert not stray, f"작업 폴더 상대 규칙이 더 있다(폴더 밖을 못 덮는다): {stray}"
    loose = [p for p in patterns if p.startswith(_ANYWHERE) and "/" in p[len(_ANYWHERE):]]
    assert not loose, f"디스크 전체 규칙은 `//**/<이름 글롭>` 꼴이어야 한다: {loose}"


def test_every_dotenv_like_name_is_denied_for_file_tools():
    """🔴 훅이 .env 꼴로 보는 흔한 이름은 디스크 어디서나 파일 도구에서도 막힌다 — 탐침은 훅에서 가져온다(손 사본 아님)."""
    names = tuple(_MOD._DOTENV_NAME_PROBES) + _COMMON_DOTENV_NAMES
    not_dotenv = [name for name in names if not _MOD._is_dotenv_name(name)]
    assert not not_dotenv, f"훅이 .env 꼴로 보지 않는 이름이 목록에 있다(목록 · 훅 둘 중 하나가 틀렸다): {not_dotenv}"
    open_names = [name for name in names if not _anywhere_hits(name)]
    assert not open_names, (
        f"셸 훅은 막지만 파일 도구(Read · Grep · Glob)로는 폴더 밖에서 열리는 이름: {open_names}\n"
        "해결: .claude/settings.json permissions.deny 에 `Read(//**/<이름 글롭>)` 을 더한다."
    )


def test_dot_env_prefix_names_are_denied_under_the_working_folder():
    """훅이 `.env.` 머리로 막는 이름은 드문 꼬리여도 작업 폴더 아래에서는 파일 도구로 막힌다(catch-all)."""
    rare = (".env.foo", ".env.local.bak", ".env.ci", ".env.example.bak")
    assert all(_MOD._is_dotenv_name(name) for name in rare)
    open_names = [name for name in rare if not _denied_under_cwd(name)]
    assert not open_names, f"작업 폴더 아래에서 파일 도구로 열리는 .env.* 이름: {open_names}"


def test_templates_and_lookalikes_stay_readable():
    """템플릿 · 닮은 이름은 어느 층에서도 막히지 않는다 — 훅도 .env 꼴로 보지 않는다(두 판정이 같은 편이다)."""
    names = tuple(sorted(_MOD._DOTENV_TEMPLATES)) + _LOOKALIKES
    blocked = {name: _anywhere_hits(name) for name in names if _anywhere_hits(name)}
    assert not blocked, f"막히면 안 되는 이름이 디스크 전체 거부에 맞는다: {blocked}"
    cwd_blocked = [name for name in names if _denied_under_cwd(name)]
    assert not cwd_blocked, f"막히면 안 되는 이름이 작업 폴더 거부에 맞는다: {cwd_blocked}"
    hook_blocked = [name for name in names if _MOD._is_dotenv_name(name)]
    assert not hook_blocked, f"훅이 템플릿 · 닮은 이름을 .env 꼴로 본다: {hook_blocked}"


def test_grok_runs_in_plan_mode_only():
    """Grok 위임 실행(셸)은 훅을 거치지 않는다 — 실행 도구는 거부하고, 계획 · 상태 도구는 남긴다(원장 #1940 M08)."""
    rules = set(_deny_rules())
    missing = [tool for tool in _GROK_EXECUTING if _GROK + tool not in rules]
    assert not missing, f"셸을 도는 Grok 도구가 거부 목록에 없다: {missing}"
    over = [tool for tool in _GROK_KEPT if _GROK + tool in rules or f"{_GROK}*" in rules]
    assert not over, f"계획 · 상태 도구까지 막았다 — claim-review 를 부를 길이 없다: {over}"
