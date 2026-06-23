#!/usr/bin/env python3
"""
이중언어 주석 점검 (보수적) — staged 신규 주석 라인 중 한글-only(영어 병행 없음) 탐지.
Bilingual-comment checker (conservative) — flag added comment lines that are Korean-only.

CLAUDE.md 이중언어 주석 규칙(한+영 병행)을 commit-time 보조. 오탐 최소화: (1) staged 추가 라인
한정 (2) `# TODO/FIXME/type:/noqa/pylint:` 단어태그 면제 (3) 블록(연속 주석) 단위로 영어 동반
여부 판정 (4) pre-commit only(CI 제외). stdlib 전용.
Supplements CLAUDE.md bilingual-comment rule at commit time. Minimizes false positives: (1) staged
added lines only (2) word-tag exemptions (3) block-level English co-occurrence check (4) pre-commit
only (not CI). stdlib only.
"""
import io
import re
import subprocess  # nosec B404 — git diff 읽기 전용 / read-only git diff
import sys

# Windows cp949 출력 보호 — UTF-8 강제
# Protect output on Windows cp949 — force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 한글 유니코드 범위 정규식 / Hangul unicode range regex
_HANGUL = re.compile(r"[가-힣]")

# 3자 이상 연속 라틴 문자 = 영어 단어 추정 / 3+ consecutive Latin chars = likely English word
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")

# 순수 주석 라인 패턴 (들여쓰기 허용) / Pure comment line pattern (indentation allowed)
_COMMENT = re.compile(r"^\s*#\s?(.*)$")

# 면제 단어태그 패턴 (TODO/FIXME/type:/noqa 등)
# Exempt word-tag pattern (TODO/FIXME/type:/noqa etc.)
_EXEMPT_TAG = re.compile(r"^\s*#\s*(TODO|FIXME|NOTE|XXX|type:|noqa|pylint:|nosec|pragma)", re.I)


def _has_hangul(s: str) -> bool:
    """문자열에 한글이 포함되어 있는지 검사.
    Check if the string contains Hangul characters.
    """
    return bool(_HANGUL.search(s))


def _has_latin_word(s: str) -> bool:
    """문자열에 3자 이상 영어 단어가 포함되어 있는지 검사.
    Check if the string contains a Latin word of 3+ characters.
    """
    return bool(_LATIN_WORD.search(s))


def _is_exempt(line: str) -> bool:
    """단어태그(TODO/FIXME/type:/noqa 등) 라인인지 판별 — 면제 대상.
    Determine if the line is a word-tag comment (exempt from bilingual requirement).
    """
    return bool(_EXEMPT_TAG.match(line))


def check_lines(added_comment_lines: list[str]) -> tuple[bool, list[str]]:
    """추가된 라인 목록에서 한글-only 주석 위반을 보수적으로 탐지.
    Conservatively detect Korean-only comment violations among added lines.

    블록(연속 주석 라인)에 영어 단어 동반 라인이 하나라도 있으면 통과(병행 간주).
    A block passes if any line in the consecutive comment block contains a Latin word.

    보수성 원칙: 면제 태그 라인은 블록을 끊지 않고 건너뜀 — 면제 라인이 한글-영어
    블록 사이에 끼어도 블록 단위 판정이 유지됨.
    Conservative principle: exempt tag lines skip without breaking the block — block-level
    judgment is preserved even when exempt lines appear between Korean and English lines.
    """
    msgs: list[str] = []
    # 현재 블록(비면제 연속 주석)과 영어 동반 여부 추적
    # Track current block (non-exempt consecutive comments) and whether it has English
    block: list[str] = []
    block_has_latin = False

    def _flush_block() -> None:
        """현재 블록을 평가하고 상태 초기화 (block + block_has_latin 모두 리셋).
        Evaluate the current block and reset all state (block and block_has_latin).
        """
        nonlocal block_has_latin
        # 블록에 영어 라인이 없을 때만 한글-only 위반 검사
        # Only flag Korean-only violations when no English line exists in the block
        if block and not block_has_latin:
            for ln in block:
                if _has_hangul(ln) and not _has_latin_word(ln):
                    msgs.append(f"❌ 한글-only 주석(영어 병행 없음): {ln.strip()}")
        block.clear()
        # 블록 플래그 초기화 — _flush_block 내부에서 일괄 리셋 (외부 중복 불필요)
        # Reset block flag here so callers don't need to repeat it
        block_has_latin = False

    for line in added_comment_lines:
        m = _COMMENT.match(line)
        if not m:
            # 주석 아닌 라인 — 블록 경계로 처리
            # Non-comment line — treat as block boundary
            _flush_block()
            continue
        if _is_exempt(line):
            # 면제 태그 라인 — 블록을 끊지 않고 건너뜀 (보수성)
            # Exempt tag line — skip without breaking the block (conservative)
            continue
        block.append(line)
        # 주석 내용(# 이후)에 영어 단어가 있으면 블록 플래그 설정
        # Set block flag if the comment body contains a Latin word
        if _has_latin_word(m.group(1)):
            block_has_latin = True

    # 마지막 블록 평가
    # Evaluate the final block
    _flush_block()
    return (not msgs), msgs


def _added_comment_lines(files: list[str]) -> list[str]:
    """git diff --cached 에서 추가된(+) 주석 라인 추출 (파일 목록 한정).
    Extract added (+) comment lines from git diff --cached (limited to given files).
    """
    if not files:
        return []
    # staged diff에서 추가 라인만 수집
    # Collect only added lines from staged diff
    out = subprocess.run(  # nosec B603 B607
        ["git", "diff", "--cached", "--unified=0", "--", *files],
        capture_output=True, text=True, check=False,
    ).stdout
    added = []
    for ln in out.splitlines():
        # '+' 로 시작하되 '+++' (파일 헤더) 제외
        # Lines starting with '+' but not '+++' (file header)
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
    return added


def main() -> int:
    """CLI 진입점 — pre-commit 이 전달한 .py 파일의 staged 추가 주석만 검사.
    CLI entry point — check only staged added comments in .py files passed by pre-commit.
    """
    # .py 파일만 대상 (pre-commit이 전달한 인수 필터링)
    # Target .py files only (filter args passed by pre-commit)
    files = [a for a in sys.argv[1:] if a.endswith(".py")]
    ok, msgs = check_lines(_added_comment_lines(files))
    print("=== 이중언어 주석 점검 / Bilingual Comment Check ===\n")
    if ok:
        print("✅ 추가 주석 라인에 한글-only(영어 병행 없음) 위반 없음")
        print("✅ No Korean-only (without English) comment violations in added lines")
        return 0
    for m in msgs:
        print(m)
    print(
        "\n해결: 한국어 주석 다음 줄에 영어 병행 추가 (CLAUDE.md 이중언어 규칙). 단어태그는 자동 면제."
    )
    print(
        "Fix: Add an English translation on the next line after Korean comments "
        "(CLAUDE.md bilingual rule). Word-tags are automatically exempt."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
