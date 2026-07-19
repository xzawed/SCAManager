"""railway.toml buildCommand 가 호출하는 명령의 **조달 출처**를 강제하는 가드.

🔴 사고 / Incident (2026-07-19 발견): buildCommand 의 tflint 설치 단계는 `unzip` 을 호출하는데
`nixpacks.toml` `aptPkgs` 에 `unzip` 이 **한 번도 없었다**(#654 tflint 도입 이래). 결과:

    /bin/bash: line 1: unzip: command not found
    WARNING: tflint install failed — tflint analyzer will be disabled

설치 단계가 전부 `|| echo 'WARNING: ...'` 로 감싸여 있어 **빌드는 성공**했고,
`src/analyzer/io/tools/tflint.py::is_enabled()` 는 `shutil.which("tflint") is None` 이면
조용히 False 를 반환한다 → Terraform/HCL 분석이 **도입 이래 무동작**이었고 아무 에러도 없었다.
The install step is wrapped in `|| echo WARNING`, so the build succeeded and the analyzer
silently disabled itself — never running since it was introduced.

🔴 이것은 같은 날 P0(`[[deploy.cronJobs]]` 무효 키 → cron 5종 미실행)와 **같은 실패 모드**다:
설정은 존재하고, 실행은 0이고, 아무도 모른다. 그 사고는 `test_railway_cron_guard.py` 로,
이 사고는 이 파일로 봉인한다.
Same failure mode as the cron P0: config present, execution zero, nobody notified.

이 가드가 강제하는 것: buildCommand 가 호출하는 **모든** 명령은 조달 출처가 아래 레지스트리에
등재돼야 하고, apt 출처로 선언된 명령은 실제로 `aptPkgs` 에 있어야 한다. 신규 명령을
buildCommand 에 추가하면 등재를 강제당하므로, "설치 명령이 없는 도구를 쓴다" 가 CI 에서 막힌다.
Every command invoked by buildCommand must declare a provenance, and apt-sourced ones must
actually appear in aptPkgs — so a new tool cannot be used without confirming its availability.
"""
import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY_TOML = _ROOT / "railway.toml"
_NIXPACKS_TOML = _ROOT / "nixpacks.toml"
_REQUIREMENTS = _ROOT / "requirements.txt"

# 조달 출처 / provenance kinds
_BASE = "base-image"        # Debian 기본 제공 (coreutils / curl / bash)
_APT = "apt"                # nixpacks.toml aptPkgs
_SETUP = "nixpacks-setup"   # nixpacks.toml [phases.setup] cmds
_PIP = "pip"                # requirements.txt → /opt/venv/bin (PATH 등재됨)

# 🔴 buildCommand 가 호출하는 명령 → 조달 출처. 신규 명령 추가 시 여기 등재 의무.
# Registry of commands invoked by buildCommand → where each comes from.
_COMMAND_PROVENANCE = {
    "chmod": _BASE,
    "curl": _BASE,
    "echo": _BASE,
    "sh": _BASE,
    "gem": _APT,          # ruby-full
    "unzip": _APT,        # 🔴 이번 사고의 당사자 / the command this incident was about
    "npm": _SETUP,        # nodesource setup_20.x
    "solc-select": _PIP,  # slither-analyzer 의 전이 의존 / transitive dep of slither-analyzer
}

# apt 출처 명령 → 실제 패키지명 (명령명 ≠ 패키지명인 경우가 있다: gem ← ruby-full)
_APT_PACKAGE = {"gem": "ruby-full", "unzip": "unzip"}
# pip 출처 명령 → requirements.txt 에 있어야 할 배포판명
_PIP_DISTRIBUTION = {"solc-select": "slither-analyzer"}
# nixpacks setup 출처 명령 → setup cmds 에 있어야 할 표지 문자열
_SETUP_MARKER = {"npm": "nodejs"}


def _build_command() -> str:
    return tomllib.loads(_RAILWAY_TOML.read_text(encoding="utf-8"))["build"]["buildCommand"]


def _apt_packages() -> list[str]:
    cfg = tomllib.loads(_NIXPACKS_TOML.read_text(encoding="utf-8"))
    return cfg["phases"]["setup"]["aptPkgs"]


def _setup_cmds() -> str:
    cfg = tomllib.loads(_NIXPACKS_TOML.read_text(encoding="utf-8"))
    return "\n".join(cfg["phases"]["setup"]["cmds"])


def _invoked_commands(build_command: str) -> set[str]:
    """buildCommand 에서 실제 호출되는 명령어 집합 추출.

    셸 구분자(`&&` `||` `|` `;` 개행)로 자른 뒤 각 조각의 **첫 단어** = 호출 명령.
    여는 괄호는 그룹핑이라 벗겨낸다. 완전한 셸 파서는 아니지만 이 buildCommand 의
    구조(괄호로 감싼 `cmd || echo` 체인)에는 정확하다.
    Splits on shell separators and takes each segment's first word.
    """
    commands = set()
    for segment in re.split(r"&&|\|\||[|;\n]", build_command):
        stripped = segment.strip().lstrip("(").strip()
        if stripped:
            commands.add(stripped.split()[0])
    return commands


def test_every_invoked_command_declares_a_provenance():
    """🔴 buildCommand 신규 명령은 조달 출처 등재 의무 — 미등재 = 어디서 오는지 아무도 모름.

    `unzip` 이 정확히 이 상태였다: 호출은 하는데 설치처가 없었고, 실패는 WARNING 으로 삼켜졌다.
    """
    unregistered = _invoked_commands(_build_command()) - set(_COMMAND_PROVENANCE)
    assert not unregistered, (
        f"buildCommand 가 조달 출처 미등재 명령을 호출한다: {sorted(unregistered)}\n"
        "→ _COMMAND_PROVENANCE 에 등재하고, 그 출처에 실제로 설치되는지 확인할 것.\n"
        "  (설치 단계가 `|| echo WARNING` 로 감싸여 있어 빌드는 성공하고 도구만 조용히 죽는다)"
    )


def test_apt_sourced_commands_are_present_in_aptpkgs():
    """🔴 이번 사고를 직접 잡는 단언 — apt 출처 선언 명령이 실제 aptPkgs 에 있는가.

    `unzip` 을 aptPkgs 에서 빼면 이 테스트가 깨진다(= 회귀 시 CI 차단).
    """
    packages = _apt_packages()
    missing = {
        cmd: _APT_PACKAGE[cmd]
        for cmd, src in _COMMAND_PROVENANCE.items()
        if src == _APT and _APT_PACKAGE[cmd] not in packages
    }
    assert not missing, (
        f"apt 출처로 선언됐으나 nixpacks.toml aptPkgs 에 없는 명령: {missing}\n"
        f"현재 aptPkgs={packages}\n"
        "→ 빌드 시 `command not found` 로 해당 analyzer 가 조용히 비활성화된다."
    )


def test_pip_sourced_commands_have_their_distribution_pinned():
    """pip 출처 명령은 requirements.txt 에 배포판이 있어야 한다 (전이 의존 포함).

    `solc-select` 는 직접 선언이 아니라 `slither-analyzer` 를 통해 들어온다 — 그 배포판이
    사라지면 solc-select 도 함께 사라지므로 여기서 묶어 단언한다.
    """
    requirements = _REQUIREMENTS.read_text(encoding="utf-8")
    missing = {
        cmd: dist
        for cmd, src in _COMMAND_PROVENANCE.items()
        if src == _PIP and (dist := _PIP_DISTRIBUTION[cmd]) not in requirements
    }
    assert not missing, f"pip 출처 명령의 배포판이 requirements.txt 에 없다: {missing}"


def test_setup_sourced_commands_have_their_install_marker():
    """nixpacks [phases.setup] 출처 명령은 setup cmds 에 설치 흔적이 있어야 한다."""
    cmds = _setup_cmds()
    missing = {
        cmd: marker
        for cmd, src in _COMMAND_PROVENANCE.items()
        if src == _SETUP and (marker := _SETUP_MARKER[cmd]) not in cmds
    }
    assert not missing, f"nixpacks setup 에 설치 흔적이 없는 명령: {missing}"


def test_tflint_install_step_still_uses_unzip():
    """🔴 대조군 — 사고 당사자 단계가 그대로인지 확인.

    tflint 설치를 tar 등 다른 방식으로 바꾸면 `unzip` 의존이 사라지므로 이 테스트가 깨진다.
    그때는 _COMMAND_PROVENANCE 에서 `unzip` 을 함께 정리하라는 신호다(dead 등재 방지).
    Control: if the tflint step stops needing unzip, drop unzip from the registry too.
    """
    build_command = _build_command()
    assert "tflint" in build_command, "tflint 설치 단계 소실 — 가드 전제가 무너졌다"
    assert "unzip" in build_command, (
        "tflint 설치가 더 이상 unzip 을 쓰지 않는다 — _COMMAND_PROVENANCE 의 unzip 등재도 정리할 것"
    )
