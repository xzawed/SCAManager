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
