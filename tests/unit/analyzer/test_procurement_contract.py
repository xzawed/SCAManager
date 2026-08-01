"""조달 계약 ↔ 실제 조달 파일 대조 — `PROVISIONED_ANALYZERS` 가 산문이 되지 않게.

## 왜 (backlog R21, 사용자 결정 2026-08-01 — 옵션 C)

`unavailable_tools`(바이너리 부재)를 무조건 `incomplete` 로 올리면, 배포 이미지가 **애초에
설치하지 않는** 도구의 언어는 auto-merge 가 **영구 불가**가 된다. 실측: 등록 25 분석기 중
**9종**(clippy·dart_analyze·dotnet_format·phpstan·psscriptanalyzer·stylelint·swiftlint·
buf_lint·htmlhint)이 조달 파일 어디에도 없다 → rust·dart·C#·php·powershell·css/scss·
swift·protobuf·html 리포는 손댈 수 없는 이유로 차단됐다.

그래서 **조달 계약**(`PROVISIONED_ANALYZERS`)으로 갈라친다:
  · 계약 안 도구가 없다 → 실제 배포 회귀 → 차단 (fail-closed 보존)
  · 계약 밖 도구가 없다 → 제품 미제공 → 가시화만

## 🔴 이 파일이 막는 것

계약이 **실제 조달과 갈라지는 것**. 두 방향 다 해롭다:
  (a) 조달했는데 계약 미등재 → 그 도구가 사라져도 **아무도 모른다**(회귀 미탐)
  (b) 미조달인데 계약 등재 → **영구 차단 재발**(R21 이 고친 그것)

기대값을 손으로 적지 않고 **실제 조달 파일에서 파싱**한다 — 손유지 목록끼리 대조하면
조달이 바뀌어도 영원히 초록이다(이 저장소가 반복해 온 observer-lie).
Cross-checks the procurement contract against the real provisioning files, parsed from disk.
"""
import re
from pathlib import Path

import pytest

import src.analyzer.io.static as static
from src.analyzer.pure.registry import REGISTRY

_ROOT = Path(__file__).resolve().parents[3]

# 조달 흔적을 찾는 파일들 — 하나라도 사라지면 파서가 공허해지므로 존재를 단언한다.
# Files that carry procurement evidence; their existence is asserted so the parser can't go vacuous.
_PROVISION_FILES = (
    "nixpacks.toml",       # aptPkgs
    "railway.toml",        # buildCommand 직접 설치
    "requirements.txt",    # Python 도구
    "package.json",        # npm 도구
)

# 분석기 이름 ↔ 조달 파일에 실제로 나타나는 토큰 (이름이 그대로 안 나오는 경우만).
# Analyzer name → the token that actually appears in provisioning files, when they differ.
_PROVISION_ALIAS = {
    "rubocop": "ruby-full",       # nixpacks aptPkgs 가 루비 런타임을 깐다
    "tsc": "typescript",          # npm 패키지명
    "slither": "slither-analyzer",  # PyPI 배포명
}


def provisioning_text() -> str:
    parts = []
    for rel in _PROVISION_FILES:
        path = _ROOT / rel
        assert path.exists(), f"조달 파일이 사라졌다 — 이 테스트가 공허해진다: {rel}"
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _mentioned(tool: str, text: str) -> bool:
    token = _PROVISION_ALIAS.get(tool, tool)
    # `_` ↔ `-` 표기 흔들림 허용 (buf_lint ↔ buf-lint 등)
    variants = {token, token.replace("_", "-"), token.replace("-", "_")}
    return any(re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", text) for v in variants)


# ── 계약이 공허하지 않은지 ────────────────────────────────────────────────


def test_contract_is_not_empty_and_not_everything():
    """🔴 대조군 — 계약이 비면 전부 가시화(차단 0), 전부면 R21 이 되돌아온다."""
    registered = {a.name for a in REGISTRY}
    assert registered, "레지스트리가 비었다 — import 부작용 확인"
    assert 0 < len(static.PROVISIONED_ANALYZERS) < len(registered), (
        f"계약 {len(static.PROVISIONED_ANALYZERS)} / 등록 {len(registered)} — "
        "계약이 전부이거나 전무하면 이 축이 아무 구분도 하지 않는다"
    )


def test_contract_has_no_unknown_analyzer():
    """계약에 등록되지 않은 이름이 있으면 오타이고, 그 항목은 영원히 무의미하다."""
    registered = {a.name for a in REGISTRY}
    unknown = static.PROVISIONED_ANALYZERS - registered
    assert not unknown, f"계약에 있으나 레지스트리에 없는 분석기(오타?): {sorted(unknown)}"


# ── 계약 ↔ 실제 조달 양방향 대조 ──────────────────────────────────────────


@pytest.mark.parametrize("tool", sorted(static.PROVISIONED_ANALYZERS))
def test_every_contracted_tool_is_actually_provisioned(tool):
    """🔴 (b) 방향 — 미조달인데 계약에 있으면 **영구 차단이 재발**한다(R21 그 자체)."""
    assert _mentioned(tool, provisioning_text()), (
        f"`{tool}` 이 조달 계약에 있으나 {list(_PROVISION_FILES)} 어디에도 없다.\n"
        "→ 조달을 추가하거나, PROVISIONED_ANALYZERS 에서 빼라. 그대로 두면 그 언어 리포는 "
        "auto-merge 가 영구 차단된다."
    )


def test_uncontracted_tools_are_genuinely_absent_from_provisioning():
    """🔴 (a) 방향 — 조달했는데 계약에 없으면 **그 도구가 사라져도 아무도 모른다**.

    조달 파일에 이름이 보이는데 계약에 없는 분석기를 열거한다. 오탐이 생기면
    `_PROVISION_ALIAS` 로 표기를 맞추거나 계약에 추가하는 것이 정답이다.
    """
    text = provisioning_text()
    registered = {a.name for a in REGISTRY}
    leaked = sorted(
        t for t in registered - static.PROVISIONED_ANALYZERS if _mentioned(t, text)
    )
    assert not leaked, (
        f"조달 파일에 흔적이 있는데 계약에 없는 분석기: {leaked}\n"
        "→ 실제로 조달된다면 PROVISIONED_ANALYZERS 에 추가할 것(없어지면 차단해야 하므로)."
    )
