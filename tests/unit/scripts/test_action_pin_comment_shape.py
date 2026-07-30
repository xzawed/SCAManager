"""SHA-핀 action 의 버전 주석이 **dependabot 이 갱신할 수 있는 형태**임을 강제한다 (#1239).

Force SHA-pinned action comments into the shape dependabot can rewrite.

## 왜 필요한가 (실측 사고)

`.github/workflows/ci.yml` 의 trufflehog 핀은 SHA 옆 주석이 `# v3.95.7 (SHA 핀 — 공급망 무결성,
@main 가변 태그 위험 차단)` 형태였다. dependabot 은 SHA 를 올렸지만 **주석은 갱신하지 않았고**,
그 결과 SHA 가 실제로는 v3.96.0 을 가리키는데 주석은 v3.95.7 을 주장했다 — 핀을 감사하는 사람에게
거짓을 보여주는 observer-lie.

🔴 **근본 원인 = 주석 형식**. dependabot-core `GithubActions::FileUpdater#updated_version_comment`
는 `comment.end_with?(previous_version)` 일 때만 주석을 재작성한다. 버전 뒤에 설명이 붙으면
재작성이 **skip** 되고 SHA 만 올라간다. 즉 이 drift 는 **앞으로도 자동으로 벌어진다**.

## 이 가드가 강제하는 것

SHA 로 핀된 모든 `uses:` 는 주석이 **버전 문자열로 끝나야** 한다. 설명은 별도 줄에 쓴다.
산문 규약(주석에 "이렇게 쓰세요")은 이미 한 번 실패했으므로 기계로 강제한다.

## 잡지 못하는 것 (정직 기준)

주석의 버전이 **실제 SHA 가 가리키는 태그와 같은지**는 네트워크 조회가 필요해 검사하지 않는다
(오프라인 CI 안정성 우선). 이 가드는 **형식**만 보증한다 — 형식이 맞으면 dependabot 이 값을
맞춰 주므로, 형식 강제가 값 정합의 필요조건이다.
"""
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# `uses: owner/repo@<40-hex>` + 같은 줄 주석
_SHA_PINNED = re.compile(
    r"^\s*uses:\s*(?P<action>[\w.-]+/[\w.-]+(?:/[\w.-]+)*)@(?P<sha>[0-9a-f]{40})\s*(?P<rest>.*)$"
)
# dependabot 이 재작성 가능한 형태 = 주석이 버전으로 **끝난다**
_ENDS_WITH_VERSION = re.compile(r"#\s*v?\d+\.\d+\.\d+\s*$")


def _pinned_uses() -> list[tuple[Path, int, str, str]]:
    """(파일, 줄번호, action, 줄 전체) — SHA 로 핀된 모든 uses."""
    found = []
    for wf in sorted(_WORKFLOWS.glob("*.yml")):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = _SHA_PINNED.match(line)
            if m:
                found.append((wf, i, m.group("action"), line))
    return found


def test_there_is_at_least_one_sha_pinned_action():
    """전제 고정 — 핀이 하나도 없으면 이 가드는 아무것도 지키지 않는다(공허 통과 방지)."""
    assert _pinned_uses(), "SHA 로 핀된 action 이 없다 — 이 가드의 전제가 사라졌다"


def test_sha_pinned_actions_carry_a_dependabot_rewritable_version_comment():
    """🔴 SHA 핀 주석은 **버전으로 끝나야** dependabot 이 SHA 범프 시 함께 갱신한다.

    설명을 버전 뒤에 붙이면 `comment.end_with?(previous_version)` 판정이 실패해 주석만 stale 로
    남는다 — #1239 가 정확히 그 형태였다. 설명은 `uses:` **위 줄**에 쓴다.
    """
    violations = [
        f"{wf.name}:{ln} ({action}) — {line.strip()[:110]}"
        for wf, ln, action, line in _pinned_uses()
        if not _ENDS_WITH_VERSION.search(line)
    ]
    assert not violations, (
        "SHA 핀 주석이 버전으로 끝나지 않는다 → dependabot 이 갱신을 skip 해 주석이 stale 로 남는다.\n"
        "설명은 `uses:` 위 줄로 옮기고 주석은 `# vX.Y.Z` 로 끝낼 것 (#1239):\n  "
        + "\n  ".join(violations)
    )


def test_trufflehog_does_not_claim_to_pin_the_scanner():
    """🔴 주장 범위 제한 — action SHA 는 **스캐너 바이너리를 핀하지 않는다**.

    action 의 `version` 입력 기본값이 `latest` 라 실제 스캐너는 `ghcr.io/...:latest` 가변 태그에서
    온다. `with: version:` 없이 "가변 태그 차단" 을 주장하면 그 주석 자체가 새 observer-lie 다.
    스캐너를 진짜 핀했다면(= `version:` 이 있다면) 이 검사는 해당 없음으로 통과한다.
    """
    ci = _WORKFLOWS / "ci.yml"
    text = ci.read_text(encoding="utf-8")
    if "trufflesecurity/trufflehog@" not in text:
        pytest.skip("trufflehog 미사용 — 해당 없음")

    has_version_input = re.search(r"^\s+version:\s*\S", text, re.MULTILINE) is not None
    if has_version_input:
        return  # 스캐너를 실제로 핀했다면 주장해도 된다

    # 스캐너 미핀 상태에서 "가변 태그 차단" 류 주장을 하고 있으면 fail
    overclaims = [
        (i, ln.strip()[:110])
        for i, ln in enumerate(text.splitlines(), 1)
        if "trufflehog" in ln.lower() and re.search(r"가변\s*태그.*차단|mutable tag.*block", ln)
    ]
    assert not overclaims, (
        "`with: version:` 없이 스캐너 핀을 주장한다 — 실제 스캐너는 `:latest` 가변 태그에서 온다 "
        "(#1239). 주장을 축소하거나 version 을 명시할 것:\n  "
        + "\n  ".join(f"ci.yml:{i} — {t}" for i, t in overclaims)
    )
