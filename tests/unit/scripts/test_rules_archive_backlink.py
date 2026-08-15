"""밀도 압축이 아카이브로 옮긴 **서사에 규칙 파일이 도달 가능한지** 를 잰다.

이 가드는 도달성(역링크·앵커·절 존재)을 잰다. 서사 보존을 재지 않는다.
공동화된 아카이브는 통과한다.

## 사고 배경 (2026-08-12 밀도 압축)

`.claude/rules/` 7파일에서 사고 재현·측정 로그를 걷어내 **101,544 → 37,761자(−63%)** 로
줄이고, 걷어낸 원문을 `docs/_archive/rules-incident-log.md` 에 두었다.

## 이 가드가 재는 축 / what this measures

1. 규칙 파일 → 아카이브 **역링크 존재**
2. 그 링크의 **앵커가 아카이브에 실재**(끊긴 앵커 = 조용한 사각)
3. 아카이브의 각 영역 절이 **헤딩만은 아님**(길이 하한 — 빈 절 차단. 채움 문자열은 통과한다)
4. 아카이브가 **실행 대상이 아님**을 자기 선언
5. 아카이브 파일 크기가 압축된 규칙 합계보다 큼 (크기 비교. 서사 동일성은 보지 않는다)

## 이 가드가 재지 **않는** 축 — 보존 축은 내렸다 (R81 옵션 b, 2026-08-15)

이 가드는 도달성을 잰다. 서사 보존을 재지 않는다. 공동화된 아카이브는 통과한다.

보존 축(리터럴 지문 + 인용 다양성 하한 25)을 내린 이유: 그 축이 있다고 단언한
문장 *"채움 문자열은 둘 다 통과하지 못한다"* 는 실측으로 거짓이었다.

독립 재현 2회:
- 2026-08-13 이 리포 회고: 서사 100% 제거 + 지문·인용 채움 + 필러 → **38/38 green**
- 2026-08-14 Grok `01a00061` 격리 worktree: 아카이브 **101,380 → 40,191자**(≈60% 공동화)
  → **38/38 green**

그래서 2026-08-15 사용자 결정 옵션 (b) 가 보존 축을 제거하고, 문서의 보존 주장을
철회했다. 아카이브가 내용을 유지하는지를 기계가 재는 장치는 이제 없다.

This guard measures reachability (backlinks, anchors, section presence). It does
not measure narrative preservation. A hollowed archive passes by design.
"""
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_RULES = _ROOT / ".claude" / "rules"
_ARCHIVE = _ROOT / "docs" / "_archive" / "rules-incident-log.md"

# 🔴 압축 대상 7영역을 **리터럴로 못박는다** — 규칙 디렉토리에서 유도하면 파일을
# 지웠을 때 루프가 안 돌아 초록이 된다(자기참조 공허화, guards.md 기록 클래스).
# Pinned literally: deriving this from the rules dir would go green when a file is deleted.
_COMPRESSED_AREAS = ("ui", "pipeline", "api", "db", "testing", "deploy", "i18n")

# 헤딩만 남기는 우회를 막는 길이 하한. 채움 문자열·필러도 통과한다 — 서사 보존
# 검사가 아니다 (R81: 2000자 `X` 패딩이 이 축을 통과한 것이 실측).
# Length floor against heading-only sections. Filler still passes; this is not
# a narrative-preservation check.
_MIN_SECTION_CHARS = 2000


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _archive_sections() -> dict:
    """아카이브의 `## <area>` 절 → 본문. / archive area sections."""
    text = _read(_ARCHIVE)
    out = {}
    marks = [(m.group(1).strip(), m.start(), m.end()) for m in re.finditer(r"^## (\S+)\s*$", text, re.M)]
    for i, (name, _start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out[name] = text[end:stop]
    return out


def test_archive_file_exists() -> None:
    """아카이브가 사라지면 7 규칙 파일의 '왜' 가 통째로 사라진다."""
    assert _ARCHIVE.exists(), (
        f"{_ARCHIVE.relative_to(_ROOT)} 가 없다 — 압축된 rules 의 서사가 도달 불가다."
    )


@pytest.mark.parametrize("area", _COMPRESSED_AREAS)
def test_compressed_rules_file_links_back_to_the_archive(area: str) -> None:
    """각 압축 규칙 파일은 자기 영역 아카이브 앵커를 가리켜야 한다."""
    body = _read(_RULES / f"{area}.md")
    anchor = f"rules-incident-log.md#{area}"
    assert anchor in body, (
        f".claude/rules/{area}.md 에 아카이브 역링크(`{anchor}`)가 없다 — "
        "규칙을 완화하려는 세션이 그 규칙의 근거를 찾을 길이 끊긴다."
    )


@pytest.mark.parametrize("area", _COMPRESSED_AREAS)
def test_archive_anchor_resolves_to_a_real_section(area: str) -> None:
    """역링크의 앵커가 아카이브에 실재하는 절이어야 한다 (끊긴 앵커 차단)."""
    sections = _archive_sections()
    assert area in sections, (
        f"아카이브에 `## {area}` 절이 없다 — .claude/rules/{area}.md 의 역링크가 끊겼다. "
        f"실재 절: {sorted(sections)}"
    )


@pytest.mark.parametrize("area", _COMPRESSED_AREAS)
def test_archive_section_is_not_just_a_heading(area: str) -> None:
    """비보존 검사 — 헤딩만 남기는 우회를 막는다. 채움 문자열은 통과한다.

    Not a preservation check: filler of this length still passes (R81).
    """
    section = _archive_sections().get(area, "")
    assert len(section) >= _MIN_SECTION_CHARS, (
        f"아카이브 `## {area}` 절이 {len(section)}자뿐이다(하한 {_MIN_SECTION_CHARS}). "
        "헤딩만 남기고 본문을 비운 상태다."
    )


def test_archive_declares_itself_non_executable() -> None:
    """아카이브는 규칙 원문이라 실행 지시 어휘를 그대로 담는다 — 자기 선언이 필수다.

    `test_plans_are_not_executable` 의 `guard-cue-quote` 면제와 짝이다.
    """
    head = _read(_ARCHIVE)[:1200]
    assert re.search(r"<!--\s*guard-cue-quote:\s*\S[^>]{10,}?-->", head), (
        "아카이브 최상단에 `guard-cue-quote:` 면제 주석이 없다 — "
        "원문의 실행 지시 어휘가 활성 지시로 오독된다."
    )
    assert "실행 대상이 아닙니다" in head, (
        "아카이브가 자신이 실행 대상이 아님을 본문으로 선언하지 않는다 — "
        "사람 독자가 옛 규칙을 현행으로 읽는다."
    )


def test_archive_is_larger_than_the_rules_it_replaced() -> None:
    """비보존 검사 — 크기 비교만. 서사 동일성은 보지 않는다.

    Grok `01a00061` 의 60% 공동화(101,380 → 40,191)도 이 축은 green 이었다.
    Not a preservation check: size only, not narrative identity.
    """
    archive_size = len(_read(_ARCHIVE))
    rules_size = sum(len(_read(_RULES / f"{a}.md")) for a in _COMPRESSED_AREAS)
    assert archive_size > rules_size, (
        f"아카이브({archive_size:,}자)가 압축본 합계({rules_size:,}자)보다 작다 — "
        "옮긴 분량이 압축본보다 짧다(도달 대상이 요약본 크기다)."
    )
