"""H2 이중언어 주석 체커 — 추가 주석 라인의 한글-only(영어 병행 없음) 보수적 탐지."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_bilingual_comments as mod  # noqa: E402


def test_korean_only_comment_flagged():
    ok, msgs = mod.check_lines(["    # 레이트 리밋 초과 시 재시도"])
    assert not ok
    assert msgs


def test_bilingual_comment_passes():
    ok, _ = mod.check_lines([
        "    # 레이트 리밋 초과 시 재시도",
        "    # Retry on rate limit exceeded",
    ])
    # 같은 블록에 영어 동반 라인이 있으면 통과 (블록 단위 판정)
    assert ok


def test_english_only_comment_passes():
    ok, _ = mod.check_lines(["    # retry on rate limit"])
    assert ok


def test_word_tag_exempt():
    ok, _ = mod.check_lines(["    # TODO: 재시도 추가", "    # type: ignore"])
    assert ok  # 단어태그 라인은 면제


def test_non_comment_line_ignored():
    ok, _ = mod.check_lines(['    x = "한글 문자열"  # noqa'])
    assert ok  # 코드 라인의 한글 리터럴은 주석 아님


def test_same_line_bilingual_passes():
    """동일 라인에 한글+영어가 함께 있으면 통과.
    A single line containing both Hangul and Latin words should pass.
    """
    # "재시도" = Hangul, "retry" = Latin word → 동일 라인 병행 통과
    # "재시도" = Hangul, "retry" = Latin word → same-line bilingual passes
    ok, _ = mod.check_lines(["    # 재시도 retry"])
    assert ok


def test_exempt_in_middle_preserves_block():
    """면제 태그 라인이 블록 중간에 있어도 블록 판정이 유지됨 (보수성).
    An exempt tag line mid-block must not break the block — conservative behavior.
    """
    # 한글 라인 → 면제(TODO) → 영어 라인 순서: 면제가 블록을 끊으면 한글 라인이 위반으로
    # 잘못 보고됨. 보수적 skip 시 블록이 유지되어 영어 동반으로 통과해야 함.
    # Korean line → exempt (TODO) → English line: if exempt breaks the block the Korean
    # line would be wrongly flagged. With conservative skip the block is preserved → pass.
    ok, _ = mod.check_lines([
        "    # 레이트 리밋 초과 시 재시도",
        "    # TODO: 나중에 개선",
        "    # Retry on rate limit exceeded",
    ])
    assert ok
