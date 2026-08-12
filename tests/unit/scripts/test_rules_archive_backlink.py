"""밀도 압축이 아카이브로 옮긴 **서사가 실제로 도달 가능한지** 를 집행한다.

## 사고 배경 (2026-08-12 밀도 압축)

`.claude/rules/` 7파일에서 사고 재현·측정 로그를 걷어내 **101,544 → 37,761자(−63%)** 로
줄이고, 걷어낸 원문을 `docs/_archive/rules-incident-log.md` 에 보존했다.

🔴 **이 압축은 하나의 단언 위에 서 있다** — *"규칙문은 남고 서사는 아카이브에 보존됐다."*
그런데 그 단언에는 집행자가 없었다. 아카이브를 지우거나 앵커를 바꿔도 규칙 파일은
멀쩡해 보이고, 규칙을 **완화하려는 다음 세션은 그 규칙이 왜 생겼는지 읽을 길을 잃는다**.
서사가 없으면 규칙은 *과하다* 고 판단되기 쉽다 — 압축의 가장 큰 역효과가 그것이다.

## 이 가드가 닫는 축 / what this closes

1. 규칙 파일 → 아카이브 **역링크 존재**
2. 그 링크의 **앵커가 아카이브에 실재**(끊긴 앵커 = 조용한 사각)
3. 아카이브의 각 영역 절이 **비어 있지 않음**(지우고 헤딩만 남기는 우회 차단)
4. 아카이브가 **실행 대상이 아님**을 자기 선언(원문에 실행 지시 어휘가 그대로 들어 있다)

5. 각 절의 **내용 충실도** — 리터럴 지문 + 인용 다양성 하한

🔴 **5축은 Grok claim-review `019ff591` 이 이 가드의 초판을 WEAKENED 로 판정해 추가됐다.**
초판은 1~4축뿐이었고, 지적된 반례가 실제로 성립했다: *"각 `## <area>` 절 본문을
2000자짜리 `X` 로 갈아치우고 전체 길이만 패딩하면 전건 green"*. 즉 **서사를 통째로
공동화해도 관측자가 참으로 보였다** — 이 저장소가 반복해 온 observer-lie 그 자체다.
그래서 절마다 그 영역에만 있는 식별자를 **테스트 쪽에 리터럴로 못박고**, 백틱 인용의
**서로 다른 개수**에 하한을 둔다. 채움 문자열은 둘 다 통과하지 못한다.

## 이 가드가 닫지 **않는** 축 (정직 기준)

내용이 *옳은지* 는 여전히 보지 않는다. 지문이 남아 있는 채로 문장을 다시 쓰면 통과한다 —
5축이 올린 것은 "공동화 비용" 이지 "서사 진위" 가 아니다. 그 축은 claim-review 가 방어한다.

This guard enforces that the compressed rules keep a live path back to the
narrative that justifies them; it does not judge that narrative's correctness.
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

# 아카이브 영역 절의 최소 분량. 압축 전 원문이라 가장 작은 절(i18n)도 8천자를 넘는다 —
# 2000 은 "헤딩만 남기고 본문을 비우는" 우회를 막는 하한이지 품질 기준이 아니다.
_MIN_SECTION_CHARS = 2000

# 🔴 **분량만으로는 공동화를 막지 못한다** (Grok `019ff591` 반례: 2000자 `X` 로 통과).
# 그래서 절마다 **그 영역에만 있는 식별자**를 테스트 쪽에 리터럴로 못박는다.
# 🔴 아카이브에서 **유도하지 않는다** — 유도하면 지우는 순간 기대값도 같이 사라져 초록이 된다
# (guards.md §기대값을 피검사 모듈에서 유도하지 말 것).
# Pinned literally on the test side; deriving them from the archive would go green when gutted.
_SECTION_FINGERPRINTS = {
    "ui": ("landing.html", "setApproveMode", "ai_review_enabled"),
    "pipeline": ("_BACKGROUND_MODULES", "run_gate_check", "AutoMergeAction"),
    "api": ("approve_mode", "auto_approve_threshold", "run_gate_check"),
    "db": ("effective_migration_url", "_REGISTERED_MODELS", "alembic/env.py"),
    "testing": ("DATABASE_URL_TEST_POSTGRES", "e2e/pytest.ini", "asyncio_mode"),
    "deploy": ("numReplicas", "preDeployCommand", "cronSchedule"),
    "i18n": ("i18n_args", "RepoConfig.notification_language", "review_guides/"),
}

# 서로 다른 백틱 인용의 최소 개수 — 지문을 남긴 채 나머지를 채움 문자열로 바꾸는 것을 막는다.
# 실측 최소 절(i18n)이 60종을 넘으므로 25 는 여유 있는 하한이다.
_MIN_DISTINCT_CITATIONS = 25
_INLINE = re.compile(r"`([^`\n]+)`")


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
def test_archive_section_is_not_hollowed_out(area: str) -> None:
    """절이 존재하되 **비어 있으면** 보존이 아니다 — 헤딩만 남기는 우회를 막는다."""
    section = _archive_sections().get(area, "")
    assert len(section) >= _MIN_SECTION_CHARS, (
        f"아카이브 `## {area}` 절이 {len(section)}자뿐이다(하한 {_MIN_SECTION_CHARS}). "
        "압축 전 원문 보존이 아니라 껍데기다."
    )


@pytest.mark.parametrize("area", _COMPRESSED_AREAS)
def test_archive_section_keeps_its_pinned_fingerprints(area: str) -> None:
    """🔴 분량 하한을 채움 문자열로 통과하는 공동화를 막는다 (Grok `019ff591` 반례)."""
    section = _archive_sections().get(area, "")
    missing = [f for f in _SECTION_FINGERPRINTS[area] if f not in section]
    assert not missing, (
        f"아카이브 `## {area}` 절에서 지문 {missing} 이 사라졌다 — "
        "분량은 남아도 원문 서사가 아니다(채움/재작성 의심). "
        "정당하게 원문이 바뀌었다면 이 테스트의 리터럴 지문을 같은 PR 에서 갱신할 것."
    )


@pytest.mark.parametrize("area", _COMPRESSED_AREAS)
def test_archive_section_keeps_citation_diversity(area: str) -> None:
    """지문만 남기고 나머지를 채움으로 바꾸는 우회를 막는다 — 인용 다양성 하한."""
    section = _archive_sections().get(area, "")
    distinct = {m.group(1).strip() for m in _INLINE.finditer(section) if m.group(1).strip()}
    assert len(distinct) >= _MIN_DISTINCT_CITATIONS, (
        f"아카이브 `## {area}` 절의 서로 다른 인용이 {len(distinct)}종뿐이다"
        f"(하한 {_MIN_DISTINCT_CITATIONS}) — 사고 재현 로그가 아니라 요약본이다."
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
    """아카이브는 압축분(≈63,783자)을 담아야 한다 — 요약본으로 바뀌면 보존이 아니다."""
    archive_size = len(_read(_ARCHIVE))
    rules_size = sum(len(_read(_RULES / f"{a}.md")) for a in _COMPRESSED_AREAS)
    assert archive_size > rules_size, (
        f"아카이브({archive_size:,}자)가 압축본 합계({rules_size:,}자)보다 작다 — "
        "걷어낸 서사가 보존되지 않았다."
    )
