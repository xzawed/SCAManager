"""이미지 빌드(`Dockerfile` 의 RUN)가 호출하는 명령의 **조달 출처와 순서**를 강제하는 가드.

🔴 사고 / Incident (2026-07-19 발견): 옛 빌드 명령의 tflint 설치 단계는 `unzip` 을 호출했는데
시스템 패키지 목록에 `unzip` 이 **한 번도 없었다**(#654 tflint 도입 이래). 결과:

    /bin/bash: line 1: unzip: command not found
    WARNING: tflint install failed — tflint analyzer will be disabled

설치 단계가 `|| echo 'WARNING: ...'` 로 감싸여 있어 **빌드는 성공**했고, tflint 는 도입 이래
무동작이었다. 설정은 존재하고, 실행은 0이고, 아무도 모른다 — cron P0
(`src/scheduler.py` docstring)와 같은 실패 모드다.
The install step swallowed the failure, so the build succeeded and the analyzer silently died.

Dockerfile 은 실패를 삼키지 않는다(RUN 실패 = 빌드 실패). 이 가드는 그보다 먼저, 이미지를
빌드하지 않고도 두 가지를 잡는다:
  1. RUN 이 호출하는 **모든** 명령은 조달 출처가 아래 레지스트리에 등재돼 있다.
  2. 그 출처가 그 명령을 **처음 쓰는 자리보다 앞에서** 실제로 설치한다(Dockerfile 은 순서가 있다).
Every command a RUN invokes declares a provenance, and that provenance is installed earlier.
"""
import re

import pytest

from tests.unit.scripts._dockerfile import (
    DOCKERFILE,
    ROOT,
    all_invocations,
    apt_installs,
    run_steps,
)

_REQUIREMENTS = ROOT / "requirements.txt"

# 조달 출처 / provenance kinds
_BASE = "base-image"       # ubuntu 이미지 기본 제공 (coreutils · dash · passwd · apt)
_APT = "apt"               # Dockerfile `apt-get install`
_VENV = "venv"             # `python3.12 -m venv` 가 만든 venv bin
_PIP = "pip"               # requirements.txt → venv bin (PATH 등재됨)
_OWN_VENV = "own-venv"     # 절대 경로 `<V>/bin/<cmd>` — **바로 그** venv `<V>` 가 앞에서 만들어져야 한다(semgrep — 회고 원장 L09)

# 🔴 RUN 이 호출하는 명령 → 조달 출처. 신규 명령 추가 시 여기 등재 의무.
# Registry of commands invoked by the image build → where each comes from.
_COMMAND_PROVENANCE = {
    "apt-get": _BASE,
    "chmod": _BASE,
    "echo": _BASE,
    "install": _BASE,     # coreutils — 내려받은 golangci-lint 를 권한과 함께 놓는다(회고 원장 R-7)
    "ln": _BASE,
    "mkdir": _BASE,
    "rm": _BASE,
    "sh": _BASE,
    "sha256sum": _BASE,   # coreutils — 릴리스 내려받기를 고정한 값과 대조한다(회고 원장 R-7)
    "tar": _BASE,         # ubuntu 필수 패키지 — golangci-lint 릴리스 tarball 을 푼다(회고 원장 R-7)
    "useradd": _BASE,
    "curl": _APT,
    "gem": _APT,          # ruby-full
    "gpg": _APT,          # gnupg — NodeSource 서명 키
    "npm": _APT,          # nodejs — NodeSource 저장소
    "python3.12": _APT,
    "unzip": _APT,        # 🔴 이번 사고의 당사자 / the command this incident was about
    "pip": _VENV,
    "python": _VENV,
    "solc-select": _PIP,  # slither-analyzer 의 전이 의존 / transitive dep of slither-analyzer
}

# apt 출처 명령 → 설치돼 있어야 할 패키지 (명령명 ≠ 패키지명: gem ← ruby-full)
_APT_PACKAGE = {
    "curl": {"curl"},
    "gem": {"ruby-full"},
    "gpg": {"gnupg"},
    "npm": {"nodejs"},
    "python3.12": {"python3.12", "python3.12-venv"},
    "unzip": {"unzip"},
}
# pip 출처 명령 → requirements.txt 에 있어야 할 배포판명
_PIP_DISTRIBUTION = {"solc-select": "slither-analyzer"}


def _command(argv: list[str]) -> str:
    """argv 의 실행 파일명 — 앞선 `VAR=값` 할당은 건너뛴다."""
    rest = [w for w in argv if not re.match(r"^[A-Za-z_]\w*=", w)] or argv
    return rest[0]


def _violations(text: str, requirements: str) -> list[str]:
    """빌드 순서대로 걸으며 「출처가 앞에서 설치됐는가」를 판정한다. 위반 문장 목록."""
    problems: list[str] = []
    installed: set[str] = set()
    venvs: set[str] = set()
    venv = pip_installed = False
    for argv in all_invocations(text):
        cmd = _command(argv)
        own = re.fullmatch(r"(/\S+)/bin/[A-Za-z0-9_.-]+", cmd)
        source = _OWN_VENV if own else _COMMAND_PROVENANCE.get(cmd)
        if source is None:
            problems.append(f"조달 출처 미등재 명령: {cmd}")
        elif source == _OWN_VENV and own.group(1) not in venvs:
            problems.append(f"{cmd}: {own.group(1)} venv 생성 전에 호출된다")
        elif source == _APT and not _APT_PACKAGE[cmd] <= installed:
            problems.append(f"{cmd}: {sorted(_APT_PACKAGE[cmd] - installed)} 설치 전에 호출된다")
        elif source == _VENV and not venv:
            problems.append(f"{cmd}: venv 생성 전에 호출된다")
        elif source == _PIP and not (pip_installed and _PIP_DISTRIBUTION[cmd] in requirements):
            problems.append(f"{cmd}: requirements 설치 전이거나 {_PIP_DISTRIBUTION[cmd]} 이 없다")
        installed |= apt_installs(argv)
        # 명령 자리부터 읽는다 — 앞에 `VAR=값` 이 붙으면 argv[1:3] 이 밀려 venv 를 놓친다(Grok claim-review 반증).
        # Read from the command's position; a leading `VAR=value` shifts argv[1:3].
        args = argv[argv.index(cmd):]
        venv = venv or args[1:3] == ["-m", "venv"]
        if args[1:3] == ["-m", "venv"]:
            # 경로 = `-m venv` 뒤 첫 «옵션 아닌» 토큰(`--without-pip /opt/x` — Grok 반증)
            # The path is the first non-option token after `-m venv`.
            paths = [a for a in args[3:] if not a.startswith("-")]
            if paths:
                venvs.add(paths[0])
        pip_installed = pip_installed or (cmd == "pip" and "requirements.txt" in argv)
    return problems


def _real() -> list[str]:
    assert DOCKERFILE.is_file(), "Dockerfile 이 없다 — 이 가드가 공허해진다"
    return _violations(DOCKERFILE.read_text(encoding="utf-8"),
                       _REQUIREMENTS.read_text(encoding="utf-8"))


def test_every_invoked_command_is_provisioned_before_use():
    """🔴 등재 + 순서 — `unzip` 이 정확히 「호출은 하는데 설치처가 없는」 상태였다."""
    assert all_invocations(DOCKERFILE.read_text(encoding="utf-8")), "RUN 을 하나도 못 읽었다"
    problems = _real()
    assert not problems, (
        "Dockerfile 조달 위반:\n  " + "\n  ".join(problems) + "\n"
        "→ _COMMAND_PROVENANCE 에 등재하고, 그 출처를 명령보다 앞선 RUN 에서 설치할 것."
    )


@pytest.mark.parametrize("dockerfile, expected", [
    # 설치 뒤 사용 — 위반 없음
    ("RUN apt-get install -y unzip\nRUN unzip a.zip", []),
    # 🔴 사고 그 자체 — 설치 없이 사용
    ("RUN unzip a.zip", ["unzip: ['unzip'] 설치 전에 호출된다"]),
    # 🔴 설치가 사용보다 뒤 — 「어딘가에 설치가 있는가」만 보는 싼 판정은 통과시킨다
    ("RUN unzip a.zip\nRUN apt-get install -y unzip", ["unzip: ['unzip'] 설치 전에 호출된다"]),
    # 🔴 주석 속 설치는 설치가 아니다
    ("# RUN apt-get install -y unzip\nRUN unzip a.zip", ["unzip: ['unzip'] 설치 전에 호출된다"]),
    # 따옴표 안 `;` 는 명령 경계가 아니다 — unzip 을 명령으로 세면 안 된다
    ('RUN python3.12 -m venv /v && python -c "import a; unzip"',
     ["python3.12: ['python3.12', 'python3.12-venv'] 설치 전에 호출된다"]),
    ("RUN brand-new-tool --x", ["조달 출처 미등재 명령: brand-new-tool"]),
    # 자기 venv 의 절대 경로 명령 — 바로 그 venv 가 앞에서 만들어졌으면 위반 없음
    ("RUN apt-get install -y python3.12 python3.12-venv\n"
     "RUN python3.12 -m venv /opt/x && /opt/x/bin/pip install a", []),
    # 앞에 `VAR=값` 이 붙은 venv 생성도 venv 생성이다(Grok 반증 — 종전엔 위반으로 잘못 셌다)
    ("RUN apt-get install -y python3.12 python3.12-venv\n"
     "RUN FOO=bar python3.12 -m venv /opt/x && /opt/x/bin/pip install a", []),
    # 옵션이 붙은 venv 생성도 그 경로의 venv 생성이다(Grok 반증 — 옵션을 경로로 읽었다)
    ("RUN apt-get install -y python3.12 python3.12-venv\n"
     "RUN python3.12 -m venv --without-pip /opt/x\nRUN /opt/x/bin/python -V", []),
    # 🔴 그 venv 를 만들기 전에 부른다
    ("RUN apt-get install -y python3.12 python3.12-venv\n"
     "RUN /opt/x/bin/pip install a\nRUN python3.12 -m venv /opt/x",
     ["/opt/x/bin/pip: /opt/x venv 생성 전에 호출된다"]),
    # 🔴 다른 venv 가 있다고 그 venv 가 생기지는 않는다
    ("RUN apt-get install -y python3.12 python3.12-venv\n"
     "RUN python3.12 -m venv /opt/y && /opt/x/bin/pip install a",
     ["/opt/x/bin/pip: /opt/x venv 생성 전에 호출된다"]),
])
def test_judgement_on_planted_dockerfiles(dockerfile, expected):
    """판정식 뒤집기 — 심은 입력마다 잡혀야 할 것만 잡는다."""
    assert _violations(dockerfile, "slither-analyzer==1\n") == expected


def test_tflint_install_step_still_uses_unzip():
    """🔴 대조군 — 사고 당사자 단계가 그대로인지 확인.

    tflint 설치를 tar 등 다른 방식으로 바꾸면 `unzip` 의존이 사라지므로 이 테스트가 깨진다.
    그때는 _COMMAND_PROVENANCE 에서 `unzip` 을 함께 정리하라는 신호다(dead 등재 방지).
    Control: if the tflint step stops needing unzip, drop unzip from the registry too.
    """
    steps = " ".join(run_steps(DOCKERFILE.read_text(encoding="utf-8")))
    assert "tflint" in steps, "tflint 설치 단계 소실 — 가드 전제가 무너졌다"
    assert re.search(r"(?<![\w-])unzip ", steps), (
        "tflint 설치가 더 이상 unzip 을 쓰지 않는다 — _COMMAND_PROVENANCE 의 unzip 등재도 정리할 것"
    )
