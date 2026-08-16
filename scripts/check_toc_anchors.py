#!/usr/bin/env python3
"""
TOC 앵커 정합 점검 — 목차 `](#anchor)` 링크가 실제 `##` 헤딩 slug 과 일치하는지.
TOC anchor checker — verify each TOC `](#anchor)` resolves to a real heading slug.

대상은 `## 목차` 를 가진 **활성** 문서 목록(`TARGETS`)이다. `docs/cycle-history.md` 는
원장 퇴역 캠페인으로 이 목록에서 빠진다 — 그 파일의 목차를 이 가드가 더 이상 지키지 않는다.

GitHub 자동 생성 slug(소문자화·비단어문자 제거·공백→하이픈·중복 헤딩 -1/-2 접미)를 재계산해
목차의 끊긴 앵커를 turn-0(pre-commit)에서 차단한다(과거 #958 더블하이픈 슬러그 사후 수정 이력).
em-dash(—)는 공백 사이에서 제거돼 `--` 더블하이픈 slug 를 만드므로 본 체커가 정확히 모사한다.
stdlib 전용. 끊긴 앵커 0건이면 exit 0.

🔴 TARGETS 가 비거나 항목 파일이 없으면 exit 1 — 빈 범위 위의 초록은 공허다.
Empty TARGETS or a missing listed file is exit 1; a vacant scope must not report success.
"""
import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 리포에서 `## 목차` 를 가진 활성 문서 (2026-08-16 grep 실측).
# `docs/cycle-history.md` 는 의도적으로 제외 — 원장 삭제 캠페인의 대상이라 이 가드가
# 그 파일에 묶여 있으면 삭제가 이 가드를 공허하게 만들거나 영구 red 로 남긴다.
# Live documents that have a `## 목차` heading. cycle-history is omitted on purpose.
TARGETS: tuple[Path, ...] = (
    Path("CONTRIBUTING.ko.md"),
    Path("docs") / "runbooks" / "github-integration-guide.md",
    Path("docs") / "runbooks" / "onpremise-migration-guide.md",
)

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
    print("=== TOC 앵커 점검 / TOC Anchor Check ===\n")
    # 🔴 빈 목록은 "검사할 것이 없어 성공" 이 아니다 — 스코프 붕괴다.
    # An empty list is a collapsed scope, not a successful check of zero anchors.
    if not TARGETS:
        print("❌ TARGETS 가 비어 있다 — 스코프가 비면 이 검사는 공허하다.")
        return 1

    any_fail = False
    for rel in TARGETS:
        target = project_root / rel
        if not target.is_file():
            print(f"❌ 대상 파일 없음: {rel.as_posix()}")
            any_fail = True
            continue
        ok, msgs = check_anchors(target.read_text(encoding="utf-8"))
        if ok:
            print(f"✅ {rel.as_posix()} 의 모든 `](#...)` 앵커가 헤딩 slug 과 일치")
        else:
            any_fail = True
            print(f"❌ {rel.as_posix()}")
            for msg in msgs:
                print(f"   {msg}")
    if any_fail:
        print("\n해결: 헤딩 텍스트의 GitHub slug(소문자·비단어 제거·공백→하이픈·중복 -1)로 앵커 정정.")
        print("      대상 파일이 없으면 TARGETS 를 갱신할 것.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
