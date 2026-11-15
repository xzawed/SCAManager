"""semgrep 은 앱과 다른 venv 에 산다 — 그 정확 전이 핀이 앱 의존성 · 감사 · 판올림을 묶지 않는다 (회고 원장 L09 · 사용자 11-15 결정).

## 사고

semgrep 은 subprocess CLI 로만 부르는데 앱과 같은 venv(`requirements.txt`)에 설치돼 있었다. 그 정확 전이 핀
(`mcp==1.29.0` · `opentelemetry-api~=1.37`)이 이 창에서 required pip-audit 를 막아 무관한 PR 6건 · main 1회가 red 였고,
예외 PR 이 3번 났으며, fastapi 는 0.141 에 묶였다(P1-7 · P1-34 · P2-77).

## 이 파일이 잠그는 것 (설정 파일을 구조로 읽는다 — 글자 존재가 아니라)

1. `requirements.txt` 에 semgrep 요구가 없고, `requirements-semgrep.txt` 가 semgrep 하나를 정확 핀한다.
2. 이미지는 semgrep 을 `/opt/venv` 가 아닌 자기 venv 에 설치하고 그 `semgrep` 만 PATH 디렉터리에 링크한다.
3. CI 의 단위 시험 잡도 같다 — 그리고 그 venv 의 bin 을 PATH 에 올리지 않는다(올리면 그 venv 의 python 이 앱 시험을 돈다).
4. 앱 감사(`-r requirements.txt`)에는 예외가 없고, semgrep 환경은 따로 감사한다.
"""
from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

import yaml

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
    venvs = [tokens[i + 1] for i in range(1, len(tokens) - 1) if tokens[i] == "venv" and tokens[i - 1] == "-m"]
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


def _semgrep_argv_lists() -> list[tuple[str, list]]:
    """`src/` 전체에서 첫 원소가 `"semgrep"` 인 리스트 리터럴(subprocess 인자) — (파일, 원소 값들)."""
    found = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.List) and node.elts and isinstance(node.elts[0], ast.Constant)
                    and node.elts[0].value == "semgrep"):
                values = [e.value if isinstance(e, ast.Constant) else None for e in node.elts]
                found.append((path.relative_to(_ROOT).as_posix(), values))
    return found


def test_the_semgrep_exception_premises_still_hold():
    """🔴 semgrep 감사 예외의 «도달 불가» 전제 — 앱은 `semgrep scan` 만 부르고 `--trace` 도 `mcp` 도 주지 않는다.

    mcp 서버 · 클라이언트 권고는 `semgrep mcp` 에서만, OpenTelemetry 전파 권고는 `--trace` 에서만 닿는다
    (ci.yml 의 semgrep 감사 스텝). 이 전제가 깨지면 그 예외를 지워야 하는데, 지금까지 그것을 재는 곳이 0이었다(P2-86).
    """
    calls = _semgrep_argv_lists()
    assert calls, "src/ 에서 semgrep 호출을 하나도 못 찾았다 — 판정이 공허하다(호출 꼴이 바뀌었는지 볼 것)"
    for where, argv in calls:
        assert argv[1:2] == ["scan"], f"{where}: semgrep 을 `scan` 이 아닌 꼴로 부른다 — {argv[:3]}"
        assert "--trace" not in argv, f"{where}: `--trace` — OpenTelemetry 예외 전제가 깨진다"
        assert "mcp" not in argv, f"{where}: `semgrep mcp` — mcp 예외 전제가 깨진다"


def test_the_app_audit_has_no_exceptions_and_semgrep_is_audited_separately():
    calls = _pip_audit_calls(_ci()["jobs"]["dependency-audit"])
    app = [c for c in calls if "requirements.txt" in c]
    semgrep = [c for c in calls if _SEMGREP_REQS in c]
    assert app and semgrep, f"앱 감사와 semgrep 감사가 둘 다 있어야 한다: {calls}"
    assert not any("--ignore-vuln" in c for c in app), "앱 감사에 예외가 남았다 — 다 semgrep 전이 의존이었다"
    assert not any(_SEMGREP_REQS in c for c in app), "앱 감사가 semgrep 파일도 같이 본다"
