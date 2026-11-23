"""semgrep 은 앱과 다른 venv 에 산다 — 그 정확 전이 핀이 앱 의존성 · 감사 · 판올림을 묶지 않는다 (회고 원장 L09 · 사용자 11-15 결정).

## 사고

semgrep 은 subprocess CLI 로만 부르는데 앱과 같은 venv(`requirements.txt`)에 설치돼 있었다. 그 정확 전이 핀
(`mcp==1.29.0` · `opentelemetry-api~=1.37`)이 이 창에서 required pip-audit 를 막아 무관한 PR 6건 · main 1회가 red 였고,
예외 PR 이 3번 났으며, fastapi 는 0.141 에 묶였다(P1-7 · P1-34 · P2-77).

## 이 파일이 잠그는 것 (설정 파일을 구조로 읽는다 — 글자 존재가 아니라)

1. `requirements.txt` 에 semgrep 요구가 없고, `requirements-semgrep.txt` 가 semgrep 하나를 정확 핀한다.
2. 이미지는 semgrep 을 `/opt/venv` 가 아닌 자기 venv 에 설치하고 그 `semgrep` 만 PATH 디렉터리에 링크한다.
3. CI 의 단위 시험 잡도 같다 — 그리고 그 venv 의 bin 을 PATH 에 올리지 않는다(올리면 그 venv 의 python 이 앱 시험을 돈다).
4. 앱 감사(`-r requirements.txt`)에는 예외가 없고, semgrep 환경은 따로 감사한다(`scripts/semgrep_audit.py`).
5. 그 감사 예외의 «도달 불가» 전제 — semgrep 호출 꼴(고정) · 룰 경로 패턴의 별 개수.
"""
from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

import yaml

from tests.unit.scripts._wiring_shape import invokes

_ROOT = Path(__file__).resolve().parents[3]
_SEMGREP_REQS = "requirements-semgrep.txt"


def _requirement_names(path: Path) -> list[str]:
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", line)
        assert m, f"요구 줄을 못 읽었다: {raw!r}"
        names.append(m.group(0).lower())
    return names


def _dockerfile_instructions() -> list[tuple[str, str]]:
    """(명령, 인자) — 줄 끝 `\\` 이어 붙이기 · 주석 줄 제외."""
    out, buf = [], ""
    for raw in (_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if not buf and raw.lstrip().startswith("#"):
            continue
        buf += raw.rstrip()
        if buf.endswith("\\"):
            buf = buf[:-1] + " "
            continue
        if buf.strip():
            op, _, rest = buf.strip().partition(" ")
            out.append((op.upper(), rest.strip()))
        buf = ""
    return out


def _venv_install_of_semgrep(command: str) -> tuple[str, str] | None:
    """한 셸 명령에서 (semgrep venv 경로, 링크 대상) — 셋이 다 있을 때만, 아니면 None.

    `-m venv V` · `V/bin/pip … -r requirements-semgrep.txt` · `ln … V/bin/semgrep TARGET`.
    """
    tokens = shlex.split(command.replace("&&", " && ").replace(";", " ; "))
    # 경로 = `-m venv` 뒤 첫 «옵션 아닌» 토큰 / the first non-option token after `-m venv`
    venvs = [next((t for t in tokens[i + 1:] if not t.startswith("-")), "") for i in range(1, len(tokens) - 1)
             if tokens[i] == "venv" and tokens[i - 1] == "-m"]
    for venv in venvs:
        pip, cli = f"{venv}/bin/pip", f"{venv}/bin/semgrep"
        if pip not in tokens or _SEMGREP_REQS not in tokens[tokens.index(pip):]:
            continue
        if "ln" in tokens and cli in tokens and tokens.index("ln") < tokens.index(cli) < len(tokens) - 1:
            return venv, tokens[tokens.index(cli) + 1]
    return None


def test_the_app_requirements_do_not_carry_semgrep():
    names = _requirement_names(_ROOT / "requirements.txt")
    assert names, "requirements.txt 에서 요구를 하나도 못 읽었다 — 판정이 공허하다"
    assert "semgrep" not in names, "semgrep 이 앱 requirements 에 있다 — 그 정확 전이 핀이 앱을 다시 묶는다"


def test_semgrep_has_its_own_exactly_pinned_requirements_file():
    path = _ROOT / _SEMGREP_REQS
    assert path.is_file(), f"{_SEMGREP_REQS} 가 없다"
    assert _requirement_names(path) == ["semgrep"], "semgrep 전용 파일에는 semgrep 하나만 둔다"
    assert re.search(r"(?m)^semgrep==\d+\.\d+\.\d+\s*$", path.read_text(encoding="utf-8")), "정확 핀(==)이 아니다"


def test_the_image_installs_semgrep_into_its_own_venv_and_links_only_the_cli():
    instructions = _dockerfile_instructions()
    assert any(op == "COPY" and _SEMGREP_REQS in arg for op, arg in instructions), f"{_SEMGREP_REQS} 를 복사하지 않는다"
    found = [r for op, arg in instructions if op == "RUN" and (r := _venv_install_of_semgrep(arg))]
    assert found, "semgrep 을 자기 venv 에 설치하는 RUN 이 없다"
    venv, target = found[0]
    assert venv != "/opt/venv", "semgrep venv 가 앱 venv 와 같다"
    assert target.startswith("/usr/local/bin"), f"semgrep 링크가 PATH 디렉터리가 아니다: {target}"
    bare = [arg for op, arg in instructions if op == "RUN" and _SEMGREP_REQS in arg
            and not _venv_install_of_semgrep(arg)]
    assert not bare, f"앱 venv 의 pip 으로 semgrep 을 까는 RUN 이 있다: {bare}"


def _ci() -> dict:
    return yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def _runs(job: dict) -> list[str]:
    return [s["run"] for s in job.get("steps", []) if isinstance(s.get("run"), str)]


def test_ci_unit_job_installs_semgrep_into_a_venv_kept_off_path():
    """🔴 CI 단위 잡의 실바이너리 시험(`test_semgrep_vendored_rules.py`)이 semgrep 을 찾되, 그 venv 의 python 이
    앱 시험을 돌지 않게 — bin 을 PATH 에 올리지 않고 `semgrep` 만 링크한다."""
    job = _ci()["jobs"]["test-and-analyze"]
    found = [r for run in _runs(job) if (r := _venv_install_of_semgrep(run))]
    assert found, "단위 시험 잡이 semgrep 을 자기 venv 에 설치하지 않는다 — 실바이너리 시험이 조용히 skip 된다"
    venv, _target = found[0]
    leaked = [run for run in _runs(job) if "GITHUB_PATH" in run and f"{venv}/bin" in run]
    assert not leaked, "semgrep venv 의 bin 을 PATH 에 올렸다 — 그 venv 의 python 이 앱 시험을 돈다"


def _pip_audit_calls(job: dict) -> list[list[str]]:
    calls = []
    for run in _runs(job):
        for line in run.splitlines():
            if "pip_audit" in line and not line.lstrip().startswith("#"):
                calls.append(shlex.split(line))
    return calls


def _semgrep_calls() -> list[tuple[str, ast.List]]:
    """`src/` 전체에서 첫 원소가 `"semgrep"` 인 리스트 리터럴(subprocess 인자) — (파일, 리스트 노드)."""
    found = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant)
                    and node.elts[0].value == "semgrep"):
                found.append((path.relative_to(_ROOT).as_posix(), node))
    return found


def _semgrep_argv_lists() -> list[tuple[str, list]]:
    """(파일, 원소 값들) — 상수가 아닌 원소는 None."""
    return [(where, [e.value if isinstance(e, ast.Constant) else None for e in node.elts])
            for where, node in _semgrep_calls()]


# semgrep 호출의 고정 꼴(상수는 값, 나머지는 식의 글자) — 감사 예외의 전제가 이 꼴에 기댄다: 경로 필터 인자
# (`--include` · `--exclude`)가 없어 wcmatch 패턴은 룰에서만 오고, 대상은 우리가 지은 임시 파일이며, `--trace` · `mcp` 가 없다.
# 바꾸려면 scripts/semgrep_audit.py 의 예외마다 전제를 다시 본 뒤 이 값을 고친다.
# The pinned semgrep call (constants by value, the rest as source text). The audit exceptions rely on it:
# no path-filter flags, the target is our own temp file, no `--trace` or `mcp`. Re-check every exception before changing it.
_SEMGREP_CALL_SHAPE = [
    "semgrep", "scan", "f'--config={rules_config()}'", "--json", "--metrics=off", "--disable-version-check",
    "--timeout", "str(STATIC_ANALYSIS_TIMEOUT)", "ctx.tmp_path",
]


def test_the_semgrep_exception_premises_still_hold():
    """🔴 semgrep 감사 예외의 «도달 불가» 전제 — 앱은 `semgrep scan` 만 부르고 `--trace` 도 `mcp` 도 주지 않는다.

    mcp 서버 · 클라이언트 권고는 `semgrep mcp` 에서만, OpenTelemetry 전파 권고는 `--trace` 에서만 닿는다
    (`scripts/semgrep_audit.py` 의 예외 목록). 이 전제가 깨지면 그 예외를 지워야 하는데, 지금까지 그것을 재는 곳이 0이었다(P2-86).
    wcmatch 권고(CVE-2026-132276)는 우리가 주지 않는 경로 필터 인자와 임시 파일이 아닌 대상에 기대므로, 호출 꼴을 통째로
    고정한다 — 새 인자는 어떤 것이든 전제를 다시 보게 한다(빠진 인자 목록으로 막으면 목록 밖 인자가 조용히 지나간다).
    """
    calls = _semgrep_calls()
    assert calls, "src/ 에서 semgrep 호출을 하나도 못 찾았다 — 판정이 공허하다(호출 꼴이 바뀌었는지 볼 것)"
    for where, node in calls:
        argv = [e.value if isinstance(e, ast.Constant) else None for e in node.elts]
        assert argv[1:2] == ["scan"], f"{where}: semgrep 을 `scan` 이 아닌 꼴로 부른다 — {argv[:3]}"
        assert "--trace" not in argv, f"{where}: `--trace` — OpenTelemetry 예외 전제가 깨진다"
        assert "mcp" not in argv, f"{where}: `semgrep mcp` — mcp 예외 전제가 깨진다"
        shape = [e.value if isinstance(e, ast.Constant) else ast.unparse(e) for e in node.elts]
        assert shape == _SEMGREP_CALL_SHAPE, (
            f"{where}: semgrep 호출 꼴이 바뀌었다 — scripts/semgrep_audit.py 의 예외 전제를 다시 보고 고정값을 고친다\n"
            f"  지금 {shape}\n  고정 {_SEMGREP_CALL_SHAPE}"
        )


# 룰 경로 패턴을 읽는 폴더 — 옮겨지면 아래 시험이 «하나도 못 읽었다» 로 red 다
# The vendored rule folder; if it moves, the test below goes red on "read nothing".
_RULES_DIR = _ROOT / "src" / "analyzer" / "configs" / "semgrep" / "rules"


def _rule_path_globs() -> tuple[int, list[str]]:
    """(읽은 룰 수, 룰 `paths:` 의 include · exclude 패턴) — semgrep 이 wcmatch 로 대조하는 패턴은 이것뿐이다
    (semgrep 1.185.0 · 1.186.0 `target_manager.py` 의 `filter_includes` · `filter_excludes`)."""
    count, globs = 0, []
    for path in sorted([*_RULES_DIR.rglob("*.yml"), *_RULES_DIR.rglob("*.yaml")]):
        for rule in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("rules") or []:
            count += 1
            paths = rule.get("paths") or {}
            for key in ("include", "exclude"):
                globs += [str(p) for p in paths.get(key) or []]
    return count, globs


def _stars_outside_globstar(glob: str) -> int:
    """경로 globstar(`**`)를 뺀 별 개수 — 권고가 느려지는 것은 이 별이 여럿일 때다."""
    return glob.replace("**", "").count("*")


def test_the_star_count_sees_both_shapes():
    """두 심음 — globstar 와 별 하나(`**/*.m`)는 하나로, 별 둘(`**/*_*.m`)은 둘로 센다."""
    assert _stars_outside_globstar("**/*.m") == 1
    assert _stars_outside_globstar("**/*_*.m") == 2


def test_the_rule_path_globs_carry_one_star_at_most():
    """🔴 wcmatch 예외(CVE-2026-132276) 전제 — 별(`*`)이 여럿인 패턴이어야 느려진다(별 k 개면 O(n^k)).

    semgrep 은 룰 `paths:` 의 include · exclude 만 wcmatch 로 대조하고, 우리는 룰을 고정 묶음으로만 준다. 패턴마다
    globstar 를 뺀 별이 하나까지면 그 대조는 별 하나의 꼴이다(실측 — scripts/semgrep_audit.py).
    """
    count, globs = _rule_path_globs()
    assert count > 0, f"{_RULES_DIR} 에서 룰을 하나도 못 읽었다 — 판정이 공허하다"
    many = [g for g in globs if _stars_outside_globstar(g) > 1]
    assert many == [], f"별이 둘 이상인 룰 경로 패턴 — scripts/semgrep_audit.py 의 CVE-2026-132276 예외를 다시 본다: {many}"


def test_the_app_audit_has_no_exceptions_and_semgrep_is_audited_separately():
    calls = _pip_audit_calls(_ci()["jobs"]["dependency-audit"])
    app = [c for c in calls if "requirements.txt" in c]
    assert app, f"앱 감사가 없다: {calls}"
    assert not any("--ignore-vuln" in c for c in app), "앱 감사에 예외가 남았다 — 다 semgrep 전이 의존이었다"
    assert not any(_SEMGREP_REQS in c for c in app), "앱 감사가 semgrep 파일도 같이 본다"
    assert any(invokes(run, "scripts/semgrep_audit.py") for run in _runs(_ci()["jobs"]["dependency-audit"])), (
        "semgrep 환경 감사 스텝이 없다 — 예외 · 막는 조건은 scripts/semgrep_audit.py 가 갖는다"
    )
