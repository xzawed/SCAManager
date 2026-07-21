"""등록된 **모든 analyzer** 가 바이너리 조달 출처를 선언하도록 강제한다.

## 왜 이 파일이 따로 있나 (2026-07-19 회고 P1)

`test_build_command_deps.py`(#1119)는 **buildCommand 가 호출하는 명령**의 조달 출처를 강제한다
— `unzip` 부재로 tflint 가 죽은 클래스를 잡는 가드다. 그런데 그 방향만으로는
**"등록은 됐는데 바이너리가 아예 조달되지 않는 analyzer"** 를 구조적으로 볼 수 없다.
buildCommand 에 언급조차 없으면 검사 대상에 들어오지 않기 때문이다.

실측(2026-07-19): `src/analyzer/io/static.py` 가 **23종**을 register 하는데 그중 **9종**의
바이너리가 buildCommand·aptPkgs·requirements 어디에도 없다 — tflint 실패 모드의 **9배 일반화**다.
`#1119` 는 이 클래스를 "봉인했다" 고 선언했으나 1/10 만 고친 상태였다.

Measured: 23 analyzers registered, 9 with no provisioning anywhere — #1119 sealed 1 of 10.

## 🔴 두 축을 **모두** 유지한다 (Grok 적대 검증 결론)

이 파일로 `test_build_command_deps.py` 를 대체하지 **않는다**. 축을 갈아끼우면
`#1119` 의 원래 결함(설치 단계가 부르는 헬퍼 명령이 없는 경우)이 다시 열린다.

- **축 A** (`test_build_command_deps.py`): buildCommand 가 **호출하는 명령** ⊆ 조달 출처
- **축 B** (이 파일): **등록된 analyzer** → 조달 모드 전단사(bijection)

## `optional_absent_ok` 가 도피처가 되지 않도록

`#1119` 는 이 클래스를 한 번 "봉인" 이라 선언하고 틀렸다. 그래서 optional 에 통제를 건다:
1. 모드는 **닫힌 집합** — 자유 문자열 금지
2. optional 은 **사유 문자열 의무**
3. buildCommand/apt/pip 에 **실제로 있는** 바이너리를 optional 로 표기 금지(모순)
4. **전부 optional 로 표기 금지** — 실제 조달되는 analyzer 가 다수여야 한다
"""
import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY = _ROOT / "railway.toml"
_NIXPACKS = _ROOT / "nixpacks.toml"
_REQUIREMENTS = _ROOT / "requirements.txt"
_STATIC = _ROOT / "src" / "analyzer" / "io" / "static.py"

# 조달 모드 — 닫힌 집합 / closed set of provisioning modes
BUILD, APT, PIP, SETUP, OPTIONAL = "build_install", "apt", "pip", "nixpacks_setup", "optional_absent_ok"
_MODES = frozenset({BUILD, APT, PIP, SETUP, OPTIONAL})

# analyzer 모듈 → (요구 바이너리, 조달 모드, optional 사유)
# 🔴 신규 analyzer 추가 시 여기 등재 의무 — 미등재는 CI FAIL (이 클래스의 재발 차단).
_PROVENANCE = {
    "buf_lint": ("buf", OPTIONAL, "Protobuf 툴체인 미탑재 — Railway 이미지에 buf 없음"),
    "clippy": ("cargo", OPTIONAL, "Rust 툴체인 미탑재 — cargo 설치 시 이미지 크게 증가"),
    "cppcheck": ("cppcheck", APT, ""),
    "dart_analyze": ("dart", OPTIONAL, "Dart SDK 미탑재"),
    "dotnet_format": ("dotnet", OPTIONAL, ".NET SDK 미탑재 — 이미지 크기 부담"),
    "eslint": ("eslint", BUILD, ""),
    "golangci_lint": ("golangci-lint", BUILD, ""),
    "hadolint": ("hadolint", BUILD, ""),
    # 🔴 htmlhint·stylelint 는 위 7종(언어 툴체인 부재)과 성격이 다르다 — **npm 패키지**이고
    #   buildCommand 는 이미 `npm install -g` 를 3회 돌린다. 즉 못 넣은 게 아니라 빠진 것으로
    #   보이며, 의도 미확인 상태다. 사용자 결정 전까지 optional 로 두되 사유에 그 사실을 남긴다.
    "htmlhint": ("htmlhint", OPTIONAL, "npm 설치 가능하나 미설치 — 의도 미확인(사용자 결정 대기)"),
    "stylelint": ("stylelint", OPTIONAL, "npm 설치 가능하나 미설치 — 의도 미확인(사용자 결정 대기)"),
    "ktlint": ("ktlint", BUILD, ""),
    "phpstan": ("phpstan", OPTIONAL, "PHP/composer 툴체인 미탑재"),
    "psscriptanalyzer": ("pwsh", OPTIONAL, "PowerShell 미탑재"),
    "python": ("pylint", PIP, ""),
    "rubocop": ("rubocop", BUILD, ""),
    "semgrep": ("semgrep", PIP, ""),
    "shellcheck": ("shellcheck", APT, ""),
    "slither": ("slither", BUILD, ""),
    "sqlfluff": ("sqlfluff", PIP, ""),
    "swiftlint": ("swiftlint", OPTIONAL, "Swift 툴체인 미탑재(주로 macOS)"),
    "tflint": ("tflint", BUILD, ""),
    "tsc": ("tsc", BUILD, ""),
    "yamllint": ("yamllint", PIP, ""),
}


def _registered_modules() -> set:
    """`static.py` 가 import 해 자동 등록하는 tool 모듈명 전수."""
    src = _STATIC.read_text(encoding="utf-8")
    return set(re.findall(r"import src\.analyzer\.io\.tools\.(\w+)", src))


def _build_command() -> str:
    return tomllib.loads(_RAILWAY.read_text(encoding="utf-8"))["build"]["buildCommand"]


# echo 인용 산문 제거용 — `echo '...'` / `echo "..."` 세그먼트를 통째로 지운다.
# Strip `echo '...'`/`echo "..."` segments so their prose can't satisfy a substring check.
_ECHO_PROSE = re.compile(r"""echo\s+(['"])[^'"]*\1""")


def _build_command_installs_only() -> str:
    """🔴 buildCommand 에서 **echo 경고 산문을 제거**한 실제 설치 명령만.

    ## 2026-07-20 세션5 회고 P1

    `_is_actually_provisioned` 이 `binary in _build_command()` 로 전체 문자열을 봐서,
    `echo 'WARNING: tsc install failed — tsc analyzer will be disabled'` 같은 **경고 산문**이
    검사를 통과시켰다. 즉 실제 설치가 사라져도 echo 문구만 남으면 "조달됨" 으로 오판된다 —
    tflint 를 잡으려던 가드가 정확히 tflint 형 결함(설정 존재·실행 0)을 산문으로 눈감았다.
    이 세션이 반복해 만난 '산문이 코드 검사를 만족' 클래스의 재현.
    The echo warning prose contained the binary name, so removed real installs still "passed".
    """
    return _ECHO_PROSE.sub(" ", _build_command())


# 🔴 바이너리명 ≠ 설치 패키지명 매핑 — 이게 없으면 echo 산문 제거 후 오탐(false-fail)이 된다.
#   실측: `tsc` 는 npm `typescript` 가, `slither` 는 pip `slither-analyzer` 가 제공한다.
#   버그가 아니라 사실이므로 명시 매핑으로 조달을 인정하되, **echo 산문이 아닌 실제 설치 토큰**에
#   대해서만 매칭한다.
# Binary→provider package: tsc←typescript(npm), slither←slither-analyzer(pip).
_PROVIDER_PACKAGE = {
    "tsc": "typescript",
    "slither": "slither-analyzer",
}


def _apt_packages() -> list:
    return tomllib.loads(_NIXPACKS.read_text(encoding="utf-8"))["phases"]["setup"]["aptPkgs"]


def _setup_cmds() -> str:
    return "\n".join(tomllib.loads(_NIXPACKS.read_text(encoding="utf-8"))["phases"]["setup"]["cmds"])


def _is_actually_provisioned(binary: str) -> bool:
    """이 바이너리가 어딘가에서 **실제로** 조달되는가 (모드 선언과 무관한 사실 확인).

    🔴 buildCommand 는 **echo 경고 산문을 제거한** 실제 설치 명령만 본다(위 함수 참조).
    바이너리명과 설치 패키지명이 다르면 `_PROVIDER_PACKAGE` 로 실제 설치 토큰을 매칭한다.
    """
    # 바이너리명 + 알려진 제공자 패키지명 — 둘 중 하나라도 실제로 조달되면 인정.
    tokens = [binary]
    if binary in _PROVIDER_PACKAGE:
        tokens.append(_PROVIDER_PACKAGE[binary])

    build = _build_command_installs_only()  # 🔴 echo 산문 제거본
    reqs = _REQUIREMENTS.read_text(encoding="utf-8")
    apt = _apt_packages()
    setup = _setup_cmds()

    for tok in tokens:
        # 🔴 하이픈·`@`·단어 이웃을 제외한 엄격 경계 — `\b` 는 `@typescript-eslint/parser` 의
        #   "typescript" 에 걸려 tsc 를 오탐(false-pass)시킨다(그 패키지는 tsc 를 안 준다).
        #   실측: 이 경계가 없으면 `npm install -g typescript` 제거해도 guard 가 통과했다.
        # Strict boundary excluding hyphen/@/word neighbours; \b would match @typescript-eslint.
        if re.search(rf"(?<![-@\w]){re.escape(tok)}(?![-\w])", build):
            return True
        if any(tok == p or tok in p for p in apt):
            return True
        if tok in setup:
            return True
        if re.search(rf"^{re.escape(tok)}[=<>\[]", reqs, re.M | re.I):
            return True
    return False


# ── 축 B: 등록 analyzer ↔ 조달 모드 전단사 ────────────────────────────────


def test_every_registered_analyzer_declares_provenance():
    """🔴 등록된 analyzer 는 **전부** 조달 모드를 선언해야 한다 — 미등재 = CI FAIL.

    이게 없으면 신규 analyzer 가 조용히 무동작 상태로 출시된다(tflint 가 그랬다).
    """
    missing = sorted(_registered_modules() - set(_PROVENANCE))
    assert not missing, (
        f"조달 모드 미선언 analyzer: {missing}\n"
        "→ _PROVENANCE 에 (바이너리, 모드, 사유) 를 등재할 것. "
        "모드 미선언은 '등록은 됐는데 바이너리가 없다' 를 조용히 허용한다."
    )


def test_provenance_table_has_no_stale_entries():
    """대조군 — 등록되지 않은 모듈이 표에 남아 있으면 dead 등재다."""
    stale = sorted(set(_PROVENANCE) - _registered_modules())
    assert not stale, f"등록되지 않은 analyzer 가 표에 있다(제거 필요): {stale}"


def test_declared_modes_are_from_the_closed_set():
    """모드는 닫힌 집합 — 자유 문자열은 taxonomy 를 무의미하게 만든다."""
    bad = {m: v[1] for m, v in _PROVENANCE.items() if v[1] not in _MODES}
    assert not bad, f"미정의 모드: {bad} (허용: {sorted(_MODES)})"


def test_non_optional_analyzers_are_actually_provisioned():
    """🔴 optional 이 아니라고 선언했으면 **실제로** 조달돼야 한다.

    선언만 하고 실물이 없으면 표 자체가 observer-lie 가 된다.
    """
    broken = {
        mod: binary
        for mod, (binary, mode, _) in _PROVENANCE.items()
        if mode != OPTIONAL and not _is_actually_provisioned(binary)
    }
    assert not broken, (
        f"조달된다고 선언했으나 실제 출처가 없는 analyzer: {broken}\n"
        "→ buildCommand/aptPkgs/requirements 중 한 곳에 추가하거나 optional 로 재분류할 것."
    )


# ── optional 도피처 차단 (Grok 지정 통제 3종) ────────────────────────────


def test_optional_entries_carry_a_reason():
    """optional 은 **사유 의무** — 사유 없는 optional 은 '검토 안 했다' 와 구별되지 않는다."""
    silent = [mod for mod, (_, mode, why) in _PROVENANCE.items() if mode == OPTIONAL and not why.strip()]
    assert not silent, f"사유 없는 optional: {silent}"


def test_optional_is_not_claimed_for_actually_provisioned_binaries():
    """🔴 실제로 조달되는 바이너리를 optional 로 표기 금지 — 표와 사실의 모순.

    이 방향의 거짓은 "어차피 없는 것" 이라는 오해를 만들어 진짜 부재를 가린다.
    """
    contradictory = {
        mod: binary
        for mod, (binary, mode, _) in _PROVENANCE.items()
        if mode == OPTIONAL and _is_actually_provisioned(binary)
    }
    assert not contradictory, (
        f"실제 조달되는데 optional 로 표기됨: {contradictory} → 올바른 모드로 정정할 것"
    )


def test_not_everything_is_optional():
    """🔴 전부 optional 로 표기하면 이 가드는 무의미해진다 — 과반은 실제 조달이어야 한다.

    optional 이 도피처가 되는 것을 산술로 막는다(#1119 가 '봉인' 을 잘못 선언한 전례).
    """
    total = len(_PROVENANCE)
    optional = sum(1 for _, mode, _ in _PROVENANCE.values() if mode == OPTIONAL)
    assert optional < total / 2, (
        f"optional 이 {optional}/{total} — 과반이 '없어도 된다' 면 analyzer 세트 자체를 재검토할 것"
    )


# ── 탐지력 자가 검증 ─────────────────────────────────────────────────────


def test_guard_detects_unregistered_new_analyzer():
    """신규 analyzer 미등재를 실제로 잡는가 — 합성 입력."""
    fake_registered = _registered_modules() | {"brand_new_tool"}
    assert sorted(fake_registered - set(_PROVENANCE)) == ["brand_new_tool"]


def test_provisioning_detector_distinguishes_present_and_absent():
    """조달 탐지기 양성/음성 통제 — 항상 True/False 를 뱉으면 위 단언이 전부 무의미하다."""
    assert _is_actually_provisioned("tflint") is True, "buildCommand 설치분을 못 본다"
    assert _is_actually_provisioned("cppcheck") is True, "aptPkgs 를 못 본다"
    assert _is_actually_provisioned("pylint") is True, "requirements 를 못 본다"
    assert _is_actually_provisioned("definitely-not-a-real-binary-xyz") is False, "항상 True 를 뱉는다"
