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


# --- cp949 인코딩 크래시 회귀 가드 (Windows 한국어 .py 주석 커밋 차단 버그) ---
# Regression guards for the cp949 crash (blocked committing Korean .py comments on Windows).

def test_git_diff_subprocess_specifies_utf8():
    """git diff subprocess 가 encoding='utf-8' 명시 — bare text=True 는 Windows cp949 로
    디코딩해 한국어 UTF-8 diff 에서 UnicodeDecodeError 크래시(스테이지 한국어 .py 주석 커밋 불가)."""
    import re
    src = (_ROOT / "scripts" / "check_bilingual_comments.py").read_text(encoding="utf-8")
    m = re.search(r"subprocess\.run\(.*?\)\.stdout", src, re.DOTALL)
    assert m, "subprocess.run(...).stdout 호출 미발견"
    call = m.group(0)
    assert 'encoding="utf-8"' in call or "encoding='utf-8'" in call, \
        "git diff subprocess 에 encoding='utf-8' 누락 (cp949 한국어 크래시 회귀)"


def test_added_comment_lines_survives_none_stdout(monkeypatch):
    """subprocess.stdout 가 None(디코드 실패 등)이어도 크래시 없이 [] 반환 (`or \"\"` 견고화)."""
    class _R:
        stdout = None
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _R())
    assert mod._added_comment_lines(["x.py"]) == []
