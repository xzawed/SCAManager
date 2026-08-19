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
import re
from pathlib import Path

import pytest

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
# 🔴 hadolint·ktlint·tflint 세 도구만 `releases/latest/download/` 였다. 형제는 전부 핀이다
#    (rubocop 1.57.2 · rubocop-ast 1.36.2 · golangci-lint v1.55.2 · typescript 6.0.x).
#    계약 도구는 부재·오작동이 `incomplete` 로 승격해 auto-merge 를 막으므로,
#    상류 릴리스 하나가 **리포 변경 0줄로** 파이프라인을 세울 수 있었다.
#    그리고 CI 와 Railway 가 `latest` 를 **서로 다른 시점에** 해석하므로 둘이 조용히 갈렸다.

_RAILWAY = _ROOT / "railway.toml"
_PINNED_TOOLS = ("hadolint", "ktlint", "tflint")
_RELEASE_PIN = re.compile(
    r"(hadolint|ktlint|tflint)/releases/download/([^/]+)/"
)


def _release_pins(text: str) -> dict:
    """`<tool>/releases/download/<ver>/` 에서 (도구 → 버전)."""
    return {tool: ver for tool, ver in _RELEASE_PIN.findall(text)}


def test_no_procurement_installs_from_the_latest_tag():
    """🔴 `releases/latest` 재발 차단 — 두 파일 모두.

    이 문자열이 하나라도 살아나면 그 도구는 다시 상류 시점에 묶인다.
    """
    for path in (_CI, _RAILWAY):
        text = path.read_text(encoding="utf-8")
        assert text.strip(), f"{path.name} 이 비었다 — 이 검사가 공허하다"
        assert "releases/latest" not in text, (
            f"{path.name} 이 `releases/latest` 로 설치한다 — 버전을 고정할 것. "
            "고정 후 tests/integration/test_contracted_analyzers_real_binary.py 로 파서를 다시 잰다."
        )


def test_ci_and_railway_pin_the_same_versions():
    """🔴 두 환경이 **같은 바이너리**를 쓴다 — 갈리면 CI 초록이 운영을 보증하지 못한다."""
    ci = _release_pins(_CI.read_text(encoding="utf-8"))
    railway = _release_pins(_RAILWAY.read_text(encoding="utf-8"))

    assert ci, "ci.yml 에서 버전 핀을 하나도 못 읽었다 — 이 테스트가 공허하다"
    assert railway, "railway.toml 에서 버전 핀을 하나도 못 읽었다 — 이 테스트가 공허하다"
    for tool in _PINNED_TOOLS:
        assert tool in ci, f"ci.yml 에 `{tool}` 핀이 없다"
        assert tool in railway, f"railway.toml 에 `{tool}` 핀이 없다"
        assert ci[tool] == railway[tool], (
            f"`{tool}` 버전이 갈렸다 — CI {ci[tool]} vs Railway {railway[tool]}. "
            "두 파일을 같은 커밋에서 고칠 것."
        )
