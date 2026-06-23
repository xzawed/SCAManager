#!/usr/bin/env python3
"""
cycle-history TOC 앵커 정합 점검 — 목차 `](#anchor)` 링크가 실제 `##` 헤딩 slug 과 일치하는지.
cycle-history TOC anchor checker — verify each TOC `](#anchor)` resolves to a real heading slug.

GitHub 자동 생성 slug(소문자화·비단어문자 제거·공백→하이픈·중복 헤딩 -1/-2 접미)를 재계산해
목차의 끊긴 앵커를 turn-0(pre-commit)에서 차단한다(과거 #958 더블하이픈 슬러그 사후 수정 이력).
em-dash(—)는 공백 사이에서 제거돼 `--` 더블하이픈 slug 를 만드므로 본 체커가 정확히 모사한다.
stdlib 전용. 끊긴 앵커 0건이면 exit 0.
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TARGET = Path("docs") / "cycle-history.md"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
# 인라인 코드/링크 안에 있을 수 있으나, TOC 링크는 단순히 마지막 `](#...)` 형태
_TOC_LINK = re.compile(r"\]\(#([^)]+)\)")
_SLUG_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)


def github_slug(heading_text: str, seen: dict[str, int]) -> str:
    """GitHub 헤딩 slug 계산 (중복 시 -1/-2 접미). seen 으로 중복 카운트 추적.

    Compute a GitHub heading slug (with -1/-2 suffix on duplicates), tracking counts in `seen`.
    """
    base = _SLUG_STRIP.sub("", heading_text.lower()).replace(" ", "-")
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def _toc_region(md_text: str) -> str:
    """'## 목차' 헤딩부터 다음 '## ' 헤딩 직전까지(목차 블록)만 반환.

    Return only the TOC block (from '## 목차' to the next '## ' heading). 본문 섹션의
    인라인 코드 예시(예: `](#...)` 설명)나 cross-link 을 앵커 검사 대상에서 제외해 오탐 방지.
    목차 헤딩이 없으면 전체 텍스트 반환(fallback).
    """
    lines = md_text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^##\s+목차\s*$", ln):
            start = i + 1
            break
    if start is None:
        return md_text
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r"^##\s+", lines[j]):
            end = j
            break
    return "\n".join(lines[start:end])


def check_anchors(md_text: str) -> tuple[bool, list[str]]:
    """헤딩 slug 집합(문서 전체)을 만들고 목차 블록의 앵커가 전부 매칭되는지 검사."""
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    for m in _HEADING.finditer(md_text):
        slugs.add(github_slug(m.group(2), seen))

    # 목차 블록의 `](#...)` 앵커만 검사 — 본문 인라인 코드/cross-link 오탐 제외
    anchors = [m.group(1) for m in _TOC_LINK.finditer(_toc_region(md_text))]
    broken = [a for a in anchors if a not in slugs]
    msgs = [f"❌ 끊긴 앵커: #{a} (일치하는 헤딩 slug 없음)" for a in broken]
    return (not broken), msgs


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    target = project_root / TARGET
    if not target.exists():
        print(f"❌ 대상 파일 없음: {TARGET}")
        return 1
    ok, msgs = check_anchors(target.read_text(encoding="utf-8"))
    print("=== cycle-history TOC 앵커 점검 / TOC Anchor Check ===\n")
    if ok:
        print(f"✅ {TARGET.as_posix()} 의 모든 `](#...)` 앵커가 헤딩 slug 과 일치")
        return 0
    for m in msgs:
        print(m)
    print("\n해결: 헤딩 텍스트의 GitHub slug(소문자·비단어 제거·공백→하이픈·중복 -1)로 앵커 정정.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
