"""조달 계약 ⊆ CI 조달 — 「계약에 있으면 CI 가 검증한다」를 기계로 강제 (#1444).

## 사고 (2026-08-18 실측)

`PROVISIONED_ANALYZERS` 는 16종인데 CI 가 실제로 설치하는 것은 **11종**이었다.
빠진 5종: `golangci-lint` · `hadolint` · `ktlint` · `rubocop` · `tflint`.

그 결과가 이 Issue 의 표면 증상이다 — 그 도구들의 테스트가 **전량 mock** 이고
`tests/integration/` 에 실바이너리 테스트가 0건이었다. **조달되지 않으니 쓸 수가 없었다.**

🔴 계약의 뜻은 「이 도구가 사라지면 배포 회귀다」이다(`static.py` 가 그 부재를 `incomplete`
로 승격해 auto-merge 를 막는다). 그런데 CI 가 그 도구를 한 번도 실행해 본 적이 없으면,
**계약이 주장하는 것을 아무도 확인하지 않은 채** 런타임 차단만 걸려 있는 셈이다.

## 이 파일이 막는 것

계약에 도구를 추가하면서 CI 조달을 빠뜨리는 것. 그 조합은 조용히 통과하다가
운영에서만 드러난다 — 이 Issue 가 정확히 그 상태였다.

Contract ⊆ CI provisioning: adding a tool to the contract without provisioning it in CI
is exactly the state that produced this issue.
"""
import json
import re
import shlex
from pathlib import Path

import pytest
import yaml

from tests.unit.scripts._dockerfile import DOCKERFILE, run_steps, shell_script

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_REQS = _ROOT / "requirements.txt"

# 패키지 이름 ≠ 분석기 이름인 경우만 — 표가 커지면 그 자체가 손유지 부채다.
_PIP_ALIAS = {"slither-analyzer": "slither"}
_NPM_ALIAS = {"typescript": "tsc"}


def _ci_text() -> str:
    assert _CI.is_file(), "ci.yml 이 없다 — 이 테스트가 공허해진다"
    return _CI.read_text(encoding="utf-8")


def ci_provisioned() -> set[str]:
    """CI 가 실제로 설치하는 분석기 이름 집합 — **설치 명령에서** 뽑는다.

    🔴 산문 언급으로 통과하면 안 된다(`test_procurement_contract` 가 배운 형태).
    아래 다섯 경로만 조달로 센다:

    | 경로 | 근거 |
    |---|---|
    | `requirements.txt` 핀 | CI 가 `pip install -r requirements-dev.txt`(→ requirements) 한다 |
    | `apt-get install -y …` | 시스템 패키지 |
    | `npm install -g <pkg>` | 전역 node 도구 |
    | `gem install <name>` | ruby 도구 |
    | `-o /usr/bin/<name>` · `-b /usr/bin <name>` · `<name>_linux_amd64.zip` | 바이너리 직접 설치 |

    별칭이 필요한 것만 표로 둔다 — 배포판 이름 ≠ 분석기 이름인 경우.
    """
    ci = _ci_text()
    reqs = _REQS.read_text(encoding="utf-8")
    names: set[str] = set()

    # pip — requirements.txt 핀. 배포판 이름이 분석기 이름과 다르면 별칭으로 매핑한다.
    for line in reqs.splitlines():
        if (m := re.match(r"^([A-Za-z0-9_.-]+)\s*==", line.strip())):
            dist = m.group(1)
            names.add(_PIP_ALIAS.get(dist, dist))

    # apt-get install -y a b c
    for chunk in re.findall(r"apt-get install -y ([^\n]+)", ci):
        names |= {w for w in chunk.split() if not w.startswith("-")}

    # npm install -g pkg[@ver] …  (버전 접미사 제거)
    for chunk in re.findall(r"npm install -g ([^\n|&]+)", ci):
        for word in chunk.split():
            word = word.strip("'\"")
            if word.startswith("-") or "/" in word or not word:
                continue
            pkg = word.split("@")[0]
            names.add(_NPM_ALIAS.get(pkg, pkg))

    # gem install <name> [-v X]
    for chunk in re.findall(r"gem install ([^\n|&]+)", ci):
        names.add(chunk.split()[0])

    # 바이너리 직접 설치 3형
    names |= set(re.findall(r"-o /usr/bin/([A-Za-z0-9_-]+)", ci))
    names |= set(re.findall(r"-b /usr/bin\s+\S*\s*([A-Za-z0-9_-]+)?", ci)) - {None, ""}
    names |= set(re.findall(r"([A-Za-z0-9_-]+)_linux_amd64\.zip", ci))
    if "golangci-lint/master/install.sh" in ci:
        names.add("golangci-lint")

    return {n.strip() for n in names if n and n.strip()}


def test_every_contracted_analyzer_is_provisioned_in_ci():
    """🔴 계약 ⊆ CI 조달. 어긋나면 그 도구는 **한 번도 실행되지 않은 채** 계약만 걸려 있다."""
    from src.analyzer.io.static import PROVISIONED_ANALYZERS  # pylint: disable=import-outside-toplevel

    assert PROVISIONED_ANALYZERS, "계약이 비었다 — 이 테스트가 공허하다"
    missing = sorted(t for t in PROVISIONED_ANALYZERS if t not in ci_provisioned())
    assert not missing, (
        f"계약에 있는데 CI 가 설치하지 않는 분석기: {missing}\n"
        "→ `.github/workflows/ci.yml` 의 조달 step 에 추가하거나, 계약에서 빼라.\n"
        "   그대로 두면 그 도구는 CI 에서 한 번도 실행되지 않고, 통합 테스트는 영구 skip 이다."
    )


def test_the_extractor_is_not_vacuous():
    """🔴 추출기 자기검증 — 아무것도 못 뽑으면 위 단언이 자동 통과한다."""
    found = ci_provisioned()
    assert len(found) >= 8, f"CI 조달 추출이 {len(found)}건 — 정규식이 깨졌다: {sorted(found)}"
    for known in ("pylint", "shellcheck", "eslint"):
        assert known in found, f"명백히 조달되는 `{known}` 을 못 뽑는다"


@pytest.mark.parametrize("tool", ["rubocop", "golangci-lint", "slither"])
def test_the_three_tools_this_issue_names_are_provisioned(tool):
    """이 Issue 가 지목한 3종을 개별로 못박는다 — 회귀 시 어느 것인지 즉시 보이게."""
    assert tool in ci_provisioned(), f"{tool} 이 CI 에서 조달되지 않는다"


# ── 조달 버전이 고정돼 있고 두 환경이 같은 것을 쓴다 (2026-08-19) ─────────
#
# 🔴 hadolint·ktlint·tflint 세 도구만 `releases/latest/download/` 였다. 형제는 전부 핀이다.
#    계약 도구는 부재·오작동이 `incomplete` 로 승격해 auto-merge 를 막으므로,
#    상류 릴리스 하나가 **리포 변경 0줄로** 파이프라인을 세울 수 있었다.
#    그리고 CI 와 운영 빌드가 `latest` 를 **서로 다른 시점에** 해석하므로 둘이 조용히 갈렸다.
# 운영 빌드 정본 = 루트 `Dockerfile`. 그 **RUN 만** 읽는다 — 주석 속 버전은 핀이 아니다.
# The production pins live in the Dockerfile's RUN steps; comments never count as a pin.

# 두 환경이 같은 값을 가져야 하는 핀 — 계약 도구 + 그 런타임(solc·node).
# Pins both environments must share: contracted tools plus the runtimes they need.
_PINNED = ("hadolint", "ktlint", "tflint", "rubocop", "rubocop-ast", "golangci-lint",
           "typescript", "eslint", "solc", "node")
_RELEASE_PIN = re.compile(r"(hadolint|ktlint|tflint)/releases/download/([^/]+)/")


def _pins(text: str) -> dict:
    """설치 명령에서 (도구 → 버전 표기). 줄 이음(`\\`)은 먼저 잇는다."""
    text = re.sub(r"\\\s*\n\s*", " ", text)
    pins = dict(_RELEASE_PIN.findall(text))
    pins |= dict(re.findall(r"gem install (\S+) -v (\S+)", text))
    if (m := re.search(r"golangci-lint/\S+/install\.sh.{0,40}?-b /usr/bin (v\d[\w.]*)", text)):
        pins["golangci-lint"] = m.group(1)
    for chunk in re.findall(r"npm install -g ([^\n&|]+)", text):
        for word in shlex.split(chunk):
            name, _, spec = word.lstrip("@").partition("@")
            if spec:
                pins[("@" if word.startswith("@") else "") + name] = spec
    if (m := re.search(r"solc-select install (\S+)", text)):
        pins["solc"] = m.group(1)
    nodes = set(re.findall(r'node-version:\s*"?(\d+)', text)) | set(re.findall(r"node_(\d+)\.x", text))
    if nodes:
        # 둘 이상이면 어느 쪽과도 같지 않게 — 한 환경 안에서 갈린 것도 red 다.
        # More than one value never equals the other side: a split inside one file is red too.
        pins["node"] = ",".join(sorted(nodes))
    return pins


def _image_pins() -> dict:
    assert DOCKERFILE.is_file(), "Dockerfile 이 없다 — 운영 빌드 핀을 읽을 곳이 없다"
    return _pins("\n".join(run_steps(DOCKERFILE.read_text(encoding="utf-8"))))


def test_pin_reader_on_planted_text():
    """판정식 뒤집기 — 실제 설치 형태는 읽고, 주석 속 버전은 Dockerfile 에서 버린다."""
    ci = ("gem install rubocop -v 1.57.2 --no-document\n"
          "curl https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh \\\n"
          "  | sudo sh -s -- -b /usr/bin v1.55.2\n"
          "npm install -g 'typescript@>=6.0.3 <6.1.0'\n"
          'node-version: "20"\n')
    assert _pins(ci) == {"rubocop": "1.57.2", "golangci-lint": "v1.55.2",
                         "typescript": ">=6.0.3 <6.1.0", "node": "20"}
    planted = "# RUN gem install rubocop -v 9.9.9\nRUN gem install rubocop -v 1.57.2\n"
    assert _pins("\n".join(run_steps(planted))) == {"rubocop": "1.57.2"}


def test_no_procurement_installs_from_the_latest_tag():
    """🔴 `releases/latest` 재발 차단 — CI 와 이미지 빌드 모두.

    이 문자열이 하나라도 살아나면 그 도구는 다시 상류 시점에 묶인다.
    """
    for name, text in (("ci.yml", _ci_text()),
                       ("Dockerfile", "\n".join(run_steps(DOCKERFILE.read_text(encoding="utf-8"))))):
        assert text.strip(), f"{name} 이 비었다 — 이 검사가 공허하다"
        assert "releases/latest" not in text, (
            f"{name} 이 `releases/latest` 로 설치한다 — 버전을 고정할 것. "
            "고정 후 tests/integration/test_contracted_analyzers_real_binary.py 로 파서를 다시 잰다."
        )


@pytest.mark.parametrize("tool", _PINNED)
def test_ci_and_image_pin_the_same_versions(tool):
    """🔴 두 환경이 **같은 바이너리**를 쓴다 — 갈리면 CI 초록이 운영을 보증하지 못한다."""
    ci, image = _pins(_ci_text()), _image_pins()
    assert tool in ci, f"ci.yml 에서 `{tool}` 핀을 못 읽었다"
    assert tool in image, f"Dockerfile 에서 `{tool}` 핀을 못 읽었다"
    assert ci[tool] == image[tool], (
        f"`{tool}` 버전이 갈렸다 — CI {ci[tool]} vs Dockerfile {image[tool]}. "
        "두 파일을 같은 커밋에서 고칠 것."
    )


# ── 핀은 정확한 버전 하나다 — 범위 · 메이저만 · 버전 없음은 핀이 아니다 ─────────
#
# 🔴 위 대조는 «두 파일의 표기가 같은가» 만 본다. `eslint@9` 는 둘이 같아도 빌드마다 그때의 최신 9.x 로
#    풀리고, 버전 없는 전역 설치는 `_pins` 가 아예 못 본다 — Dockerfile 의 «전부 버전 핀» 주석이 거짓이었다.
# Equality passes `eslint@9` on both sides and never sees a bare package; a pin names one exact version.
_EXACT = re.compile(r"v?\d+\.\d+\.\d+")
# npm · npm 패키지 실행기(npx) 호출 — 절대 경로 호출(`/usr/bin/npm`)은 읽고, 숨은 폴더(`/root/.npm`) ·
# 다른 도구 이름(`pnpm` · `my-npm`)은 뺀다.
# npm or npx invocations, absolute paths included; a dot-folder or another tool's name does not count.
_NPM_CALL = re.compile(r"(?<![\w.-])(npm|npx)\b((?:\s+-\S+)*)([^\n&|;]*)")
# 레지스트리에서 받지 않는 npm 하위 명령 — 잠금 파일 설치 · 스크립트 실행 · 캐시 정리.
# 🔴 받아 오는 하위 명령을 나열하지 않고 이것만 면제한다: 모르는 하위 명령(update · exec · link …)과 npx 는
#    인자가 전부 정확한 버전이어야 통과한다 — 목록 밖이 조용히 지나가지 않고 red 가 된다.
# npm subcommands that never fetch from the registry. Everything else (and npx) must pin exactly.
_NPM_NON_FETCHING = frozenset({"ci", "run", "run-script", "cache"})


def _npm_fetches(text: str) -> list[tuple[str, str]]:
    """레지스트리에서 받는 npm · npx 호출의 (패키지, 버전 표기) — 버전 없는 패키지는 표기가 ''. 플래그 · 꼬리 주석은 뺀다."""
    text = re.sub(r"\\\s*\n\s*", " ", text)
    out = []
    for tool, _flags, rest in _NPM_CALL.findall(text):
        words = [w for w in shlex.split(rest, comments=True) if not w.startswith("-")]
        if tool == "npm":
            if not words or words[0] in _NPM_NON_FETCHING:
                continue
            words = words[1:]
        for word in words:
            name, _, spec = word.lstrip("@").partition("@")
            out.append((("@" if word.startswith("@") else "") + name, spec))
    return out


def _inexact(text: str) -> list[str]:
    """정확한 버전이 아닌 설치 — 범위 · 메이저만 · 버전 없음. node 는 메이저 고정이 설계라 뺀다."""
    bad = {f"{tool}={spec}" for tool, spec in _pins(text).items()
           if tool != "node" and not _EXACT.fullmatch(spec)}
    bad |= {f"{name}={spec}" if spec else f"{name}(버전 없음)"
            for name, spec in _npm_fetches(text) if not _EXACT.fullmatch(spec)}
    return sorted(bad)


def _image_run_text(dockerfile: str) -> str:
    """Dockerfile RUN 인자를 셸 문장으로 — exec 형(`RUN ["npm", …]`)은 argv 를, 셸 감싸기(`["sh", "-c", …]`)는
    그 스크립트를 되돌린다."""
    out = []
    for args in run_steps(dockerfile):
        if args.startswith("["):
            try:
                argv = json.loads(args)
                args = shell_script(argv) or shlex.join(argv)
            except (ValueError, TypeError):
                pass
        out.append(args)
    return "\n".join(out)


def _ci_run_text(workflow: str) -> str:
    """워크플로 `run:` 스크립트를 YAML 이 푼 그대로 — 접힌 블록(`>`)에서 줄이 나뉜 명령도 한 명령이다."""
    jobs = (yaml.safe_load(workflow) or {}).get("jobs") or {}
    return "\n".join(step["run"] for job in jobs.values() for step in job.get("steps") or []
                     if isinstance(step, dict) and isinstance(step.get("run"), str))


def test_inexact_reader_on_planted_text():
    """판정식 뒤집기 — 정확한 핀은 통과하고, 범위 · 메이저만 · 버전 없음은 표기와 별칭에 상관없이 잡힌다."""
    assert _inexact("npm install -g eslint@9.39.5 typescript@6.0.3\n"
                    "gem install rubocop -v 1.57.2 --no-document\n"
                    'node-version: "20"\nnpm ci --ignore-scripts\nnpm run build\nnpm cache clean --force\n'
                    "npm --version\nRUN --mount=type=cache,target=/root/.npm npm i -g eslint@9.39.5\n") == []
    assert _inexact("npm install -g eslint@9 @typescript-eslint/parser\n"
                    "npm install -g 'typescript@>=6.0.3 <6.1.0'\n") == [
        "@typescript-eslint/parser(버전 없음)", "eslint=9", "typescript=>=6.0.3 <6.1.0"]
    assert _inexact("npm i -g eslint\nnpm --global add prettier@^3.0.0  # 꼬리 주석\n") == [
        "eslint(버전 없음)", "prettier=^3.0.0"]
    assert _inexact("sudo /usr/bin/npm install -g eslint@latest\n") == ["eslint=latest"]


# witness-corpus: npm CLI 문서에서 레지스트리 패키지를 받는 명령 중 install 이 아닌 것 — update · exec · npx · link · install-test
_FETCHING_NPM_COMMANDS = [
    "npm update -g eslint",
    "npm exec --package=eslint@9 -- eslint --version",
    "npx eslint@9 --version",
    "npm link eslint",
    "npm install-test eslint@9",
]


@pytest.mark.parametrize("command", _FETCHING_NPM_COMMANDS)
def test_fetching_npm_commands_beyond_install_are_red(command):
    """🔴 install 이 아닌 받아 오는 명령도 정확한 버전이 아니면 red 다 — 하위 명령을 나열하지 않으니 비켜 가지 못한다."""
    assert _inexact(command + "\n"), f"{command!r} 가 판정을 비켜 갔다"


def test_install_text_readers_on_planted_files():
    """exec 형 RUN 과 접힌 YAML 블록도 셸 명령으로 읽힌다 — 접힌 블록을 날 글로 읽으면 위 판정을 비켜 간다."""
    dockerfile = ('FROM x\nRUN ["npm", "install", "-g", "eslint"]\nRUN npm i -g prettier@3.3.3\n'
                  'RUN ["/bin/sh", "-c", "npm install -g typescript@6"]\n')
    assert _inexact(_image_run_text(dockerfile)) == ["eslint(버전 없음)", "typescript=6"]
    workflow = "jobs:\n  a:\n    steps:\n      - run: >-\n          npm install -g\n          eslint@9\n"
    assert _inexact(_ci_run_text(workflow)) == ["eslint=9"]
    assert _inexact(workflow) == []


@pytest.mark.parametrize("name", ["Dockerfile", "ci.yml"])
def test_every_analyzer_install_names_an_exact_version(name):
    """🔴 운영 이미지와 CI 의 분석기 설치는 전부 정확한 버전이다 — Dockerfile «전부 버전 핀» 의 기계 검증."""
    text = (_ci_run_text(_ci_text()) if name == "ci.yml"
            else _image_run_text(DOCKERFILE.read_text(encoding="utf-8")))
    assert _pins(text) and _npm_fetches(text), f"{name} 에서 설치를 못 읽었다 — 이 검사가 공허하다"
    assert _inexact(text) == [], (
        f"{name} 에 정확한 버전이 아닌 분석기 설치가 있다: {_inexact(text)} — 지금 운영이 쓰는 판"
        "(`npm view <패키지>@<범위> version` 의 마지막 값)으로 고정하고, 두 파일을 같은 커밋에서 고칠 것."
    )
