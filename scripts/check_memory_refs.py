#!/usr/bin/env python3
"""
메모리 슬러그 교차 점검 스크립트.
Memory slug cross-checker script.

CLAUDE.md / .claude/policies/active.md / history.md 에서 참조된 메모리 슬러그와
실제 메모리 디렉토리 파일 목록을 비교해 누락·스테일 어노테이션·미참조 파일을 보고한다.

Compares memory slugs referenced in project docs against actual files in the memory
directory, reporting: missing files, stale "(현재 미생성)" annotations, unreferenced files.
"""
import io
import os
import re
import sys
from pathlib import Path

# Windows cp949 환경에서 한글/이모지 출력 오류 방지
# Prevent encoding errors on Windows cp949 for Korean/emoji output.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECTS_ROOT = Path.home() / ".claude" / "projects"
# 🔴 스캔 범위 = **처방적(prescriptive) 표면** — 미래 세션의 *행동을 지시*하는 문서.
# 2026-08-05 문서 감사 이전에는 아래 3개 리터럴뿐이었다(전체 188 md 중 **1.6%**). 범위가
# 좁으면 `.claude/rules/*.md` 나 runbook 이 죽은 슬러그를 가리켜도 가드가 **"✅ 전부 존재"**
# 를 인쇄한다 — 빈/좁은 범위 위의 초록은 fail-open 이다(이 리포가 반복해 고쳐 온 클래스).
#
# 스캔 = 처방 표면만. 2026-08-16 이력 퇴역 후 `docs/_archive/**` · `docs/cycle-history.md`
# 는 디스크에 없다 — 제외 목록이 아니라 **글롭에 처음부터 안 넣는다**.
# 캠페인 런북 6건도 같은 날 삭제됐다. `docs/runbooks/*.md` 분모가 그만큼 줄었다
# (글롭은 존재하는 파일만 돌려준다 — 아래 리터럴과 달리 부재를 못 본다).
# Scope = prescriptive docs only. Retired history trees are gone, so they are not
# in the globs. The runbooks glob shrank when six campaign records were deleted.
#
# 🔴 2026-08-26 (감사 B7, #1519): 범위가 **13파일**뿐이라 그 안에서 인용이 0건이었고,
# 가드는 「아무것도 검증하지 않았다」를 인쇄하며 통과했다. 그런데 **범위 밖에 진짜
# 인용이 4건, 그중 1건이 dangling** 이었다(`.github/dependabot.yml` 의
# feedback-log-first-debugging.md — 파일 없음). 위 주석이 예고한 fail-open 이
# 그대로 일어난 것이다.
#
# 그래서 «슬러그를 인용할 수 있는 곳» 전부로 넓힌다 — 테스트·워크플로 설정도
# 메모리를 근거로 인용한다. 좁히면 `test_scan_scope_covers_where_slugs_actually_appear`
# 가 red 다.
# Widened after an out-of-scope dangling reference slipped through.
_DOC_GLOBS = (
    "docs/**/*.md",
    ".github/**/*.yml",
    ".github/**/*.yaml",
    ".claude/**/*.md",
    "tests/**/*.py",
    "scripts/**/*.py",
)
# 🔴 리터럴은 `.is_file()` 로 걸러내지 않는다. 걸러내면 파일이 사라진 순간 스코프가
#    조용히 줄어들고, `main()` 의 부재 검사가 그 이름을 보지 못해 초록이 된다.
#    글롭은 존재하는 파일만 돌려주는 것이 글롭의 정의라 그대로 둔다.
# Literals stay in the list even when missing so main() can fail loudly; globs only
# match existing files (that is what a glob is).
_DOC_LITERALS = ("CLAUDE.md",)


def _doc_files(project_root: Path) -> list[str]:
    """스캔 대상 문서 목록 — 리터럴은 부재여도 남긴다. / Literals stay even if missing."""
    files = list(_DOC_LITERALS)
    for pattern in _DOC_GLOBS:
        files += sorted(p.relative_to(project_root).as_posix()
                        for p in project_root.glob(pattern))
    return files


# 하위 호환 — 모듈 로드 시점의 리포 기준 목록(테스트·기존 호출부가 참조).
# Kept for compatibility; computed against the repo root at import time.
DOC_FILES = _doc_files(Path(__file__).resolve().parents[1])
# 백틱으로 감싼 파일명 표기 — 하이픈·언더스코어 구분자 양쪽을 받는다.
# 🔴 이 주석에 예시 슬러그를 백틱으로 적으면 이 파일 자신이 dangling 참조로 잡힌다(실측).
# Backtick-quoted filename, hyphen or underscore separated. Deliberately no inline example:
# a backticked sample slug here would make this very file a dangling reference.
SLUG_PATTERN = re.compile(r"`((?:feedback|project|user)[-_][\w-]+\.md)`")
# 🔴 wiki-link 표기(이중 대괄호) — 현행 메모리 규약의 링크 형식인데 이전 판은 보지 않았다.
# Wiki-link form, the current memory convention; the previous version ignored it entirely.
WIKI_PATTERN = re.compile(r"\[\[((?:feedback|project|user)[-_][\w-]+)\]\]")
STALE_PATTERN = re.compile(
    r"`((?:feedback|project|user)[-_][\w-]+\.md)`\s*\(현재 미생성[^)]*\)"
)


def normalize(slug: str) -> str:
    """슬러그 비교 정규화 — 하이픈/언더스코어 표기 차이를 흡수한다.

    🔴 실측(2026-07-31): 문서는 하이픈(`feedback-stale-blocker-policy.md`), 실제 파일은
    언더스코어(`feedback_test_patterns.md`)를 쓴다. 정규화 없이는 **표기 불일치만으로**
    전건 오탐(모든 참조가 '누락')·전건 미탐(모든 파일이 '미참조')이 갈린다.
    Docs use hyphens while files use underscores; without normalisation every reference
    reads as missing and every file as unreferenced.
    """
    return slug.lower().replace("-", "_")


def repo_slug(project_root: Path) -> str:
    """리포 절대경로 → Claude Code 프로젝트 디렉토리 슬러그.

    `f:\\DEVELOPMENT\\SOURCE\\CLAUDE\\SCAManager` → `f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager`
    (드라이브 콜론과 경로 구분자를 각각 `-` 로 치환하므로 `f:` + `\\` 가 `--` 가 된다).
    Maps the absolute repo path to the slug Claude Code uses for its project directory.
    """
    return re.sub(r"[\\/:]", "-", str(project_root))


def resolve_memory_dir(project_root: Path) -> Path | None:
    """이 머신의 메모리 디렉토리 — env 우선, 없으면 리포 경로에서 유도.

    🔴 이전 판은 `~/.claude/projects/d--Source-SCAManager/memory` 를 **하드코딩**했다(구 PC
    `D:\\Source\\SCAManager` 슬러그). PC 를 옮긴 뒤 그 경로는 존재하지 않으므로 부재-skip 분기가
    **항상** 타서 이 가드는 이 머신에서 한 번도 검사한 적이 없다(회고 2026-07-31 P0-6).
    Was hardcoded to the previous machine's slug, so the absent-dir skip always fired.
    """
    env = os.environ.get("CLAUDE_PROJECT_MEMORY_DIR")
    if env:
        return Path(env)
    if not PROJECTS_ROOT.is_dir():
        return None
    want = repo_slug(project_root).lower()
    dirs = [d for d in PROJECTS_ROOT.iterdir() if (d / "memory").is_dir()]
    exact = [d for d in dirs if d.name.lower() == want]
    return exact[0] / "memory" if exact else None


def near_miss_slugs(project_root: Path) -> list[str]:
    """리포 이름으로 끝나지만 **정확히 일치하지 않는** 후보 — 오류 메시지 힌트용.

    🔴 초판은 이걸 fallback 으로 **자동 해결**했다. Grok claim-review(2026-07-31, F2)가 반증:
    드라이브 문자나 상위 경로가 바뀐 경우는 **정확히 우리가 loud 로 잡아야 할 drift** 인데,
    fallback 이 그것을 조용히 봉합해 무관한 프로젝트의 메모리를 검사할 수 있었다(실측 재현).
    이제 해결하지 않고 **힌트로만** 보여준다 — 자동 추측보다 사람이 한 번 보는 편이 안전하다.
    Grok refuted the auto-fallback: a changed drive letter is precisely the drift we must shout
    about, and the fallback could silently bind an unrelated project's memory.
    """
    if not PROJECTS_ROOT.is_dir():
        return []
    suffix = f"-{project_root.name}".lower()
    want = repo_slug(project_root).lower()
    return sorted(
        d.name for d in PROJECTS_ROOT.iterdir()
        if (d / "memory").is_dir() and d.name.lower().endswith(suffix) and d.name.lower() != want
    )


def collect_referenced(project_root: Path) -> dict[str, list[str]]:
    """각 문서에서 메모리 슬러그 참조를 수집한다. / Collect memory slug references from each doc."""
    referenced: dict[str, list[str]] = {}
    for rel_path in DOC_FILES:
        full_path = project_root / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        for match in SLUG_PATTERN.finditer(content):
            referenced.setdefault(match.group(1), []).append(rel_path)
        # wiki-link 는 확장자가 없으므로 붙여서 동일 키 공간에 넣는다.
        # Wiki-links carry no extension; append one so both forms share a key space.
        for match in WIKI_PATTERN.finditer(content):
            referenced.setdefault(f"{match.group(1)}.md", []).append(rel_path)
    return referenced


def collect_stale(project_root: Path, actual: set[str]) -> list[tuple[str, str]]:
    """파일은 생성됐으나 '(현재 미생성)' 어노테이션이 잔존하는 항목 탐지.
    Detect slugs where the file exists but a '(현재 미생성)' annotation still remains."""
    stale: list[tuple[str, str]] = []
    for rel_path in DOC_FILES:
        full_path = project_root / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        # 🔴 정규화 후 대조 — 초판은 여기만 exact `slug in actual` 이라 표기가 엇갈리면
        #   stale 어노테이션을 놓쳤다(Grok claim-review F5, 실측 재현).
        # Normalised comparison: the first version used exact membership here only, so a
        # hyphen/underscore mismatch silently hid stale annotations.
        actual_norm = {normalize(a) for a in actual}
        for match in STALE_PATTERN.finditer(content):
            slug = match.group(1)
            if normalize(slug) in actual_norm:
                stale.append((rel_path, slug))
    return stale


def print_report(
    referenced: dict[str, list[str]],
    actual: set[str],
    stale: list[tuple[str, str]],
) -> bool:
    """결과를 출력하고 문제가 없으면 True를 반환한다. / Print report; return True when clean."""
    # 🔴 표기 정규화 후 대조 — 하이픈/언더스코어 차이가 전건 오탐/미탐을 만들던 것을 흡수.
    # Compare on normalised slugs so the hyphen/underscore split doesn't flip every verdict.
    actual_norm = {normalize(a) for a in actual}
    referenced_norm = {normalize(s) for s in referenced}
    missing = {slug for slug in referenced if normalize(slug) not in actual_norm}
    extra = {a for a in actual if normalize(a) not in referenced_norm}

    print("=== SCAManager 메모리 슬러그 점검 / Memory Slug Check ===\n")
    print(f"참조된 슬러그: {len(referenced)}개")
    print(f"실제 파일:     {len(actual)}개")

    ok = True

    if missing:
        ok = False
        print(f"\n❌ 누락 파일 ({len(missing)}개 — 문서 참조 O, 파일 X):")
        for slug in sorted(missing):
            refs = ", ".join(referenced[slug])
            print(f"  {slug}  ← {refs}")
    elif not referenced:
        # 🔴 분자가 0 이면 `missing` 은 필연적으로 공집합이다 — 그 위의 ✅ 는 «통과» 가 아니라
        #    «안 쟀음» 이다. 2026-08-17 문서 개편이 슬러그를 인용하던 문서를 전부 지워
        #    실제로 이 상태가 됐고, 그 EXIT 0 이 「기능 손실 0」의 근거로 인용됐다.
        #    advisory 스크립트라 exit 는 0 으로 두되 **판정을 인쇄에서 분리**한다.
        # A zero numerator makes `missing` empty by construction: that is "not measured", not "pass".
        print("\n⚠️  이 축은 **아무것도 검증하지 않았다** — 스캔 범위에서 슬러그 인용 0건.")
        print("    초록이 아니라 '안 쟀음' 이다. 참조를 되살리거나 이 축을 폐기할 것.")
    else:
        print(f"\n✅ 참조 슬러그 {len(referenced)}개 전건에 실제 파일 존재")

    if stale:
        ok = False
        print(f"\n⚠️  스테일 어노테이션 ({len(stale)}건 — 파일 생성 후 '(현재 미생성)' 잔존):")
        for doc, slug in stale:
            print(f"  {doc}: `{slug}` (현재 미생성) → 어노테이션 제거 필요")
    else:
        print("✅ 스테일 '(현재 미생성)' 어노테이션 없음")

    if extra:
        print(f"\nℹ️  미참조 파일 ({len(extra)}개 — 문서 참조 X, 파일 O):")
        for slug in sorted(extra):
            print(f"  {slug}")

    return ok


def main(project_root: Path | None = None) -> int:
    # 리포 루트는 주입 가능 — 테스트가 전역 `Path.resolve` 를 패치하지 않아도 되게 한다.
    # Injectable so tests need not monkeypatch Path.resolve globally.
    project_root = project_root or Path(__file__).resolve().parents[1]

    # 🔴 '부재' 와 '경로 drift' 를 구별한다 (회고 2026-07-31 P0-6 처방).
    #  - projects 루트 자체가 없다 = Claude Code 머신이 아니다(CI·타 개발자) → skip(0).
    #  - 루트는 있는데 이 리포에 대응하는 후보가 없다 = **경로 drift** → loud + exit 1.
    # 이전 판은 둘을 합쳐 '부재=정상' 으로 처리했고, 그래서 PC 이전 후 영구 무동작이 됐다.
    # Distinguish "not a Claude Code machine" (skip) from "slug drift" (loud failure); the old
    # version collapsed both into a silent pass, which is how it went dead after the PC move.
    # 🔴 env 는 프로젝트 루트 유무보다 **먼저** 본다 (Grok claim-review F1, 실측 재현).
    #   초판은 루트 부재 skip 이 먼저라, env 를 지정해도 exit 0 으로 빠졌다 — 즉 문서가 광고한
    #   "env 가 최우선" 이 진입점에서 거짓이었다. 탈출구가 진입점에서 막혀 있으면 탈출구가 아니다.
    # Env must win before the root check; otherwise the advertised escape hatch is unreachable.
    if not os.environ.get("CLAUDE_PROJECT_MEMORY_DIR") and not PROJECTS_ROOT.is_dir():
        print(f"⏭️  Claude 프로젝트 루트 없음 — 점검 skip (CI/타 환경 정상): {PROJECTS_ROOT}")
        return 0

    memory_dir = resolve_memory_dir(project_root)
    if memory_dir is None or not memory_dir.is_dir():
        hints = near_miss_slugs(project_root)
        print(
            "🔴 메모리 디렉토리를 찾지 못했습니다 — 이 머신에 프로젝트 루트는 있는데 대응 후보가 없습니다.\n"
            "   Memory dir unresolved though the Claude projects root exists (slug drift).\n"
            f"   기대 슬러그 / expected slug : {repo_slug(project_root)}\n"
            f"   탐색 위치 / searched        : {PROJECTS_ROOT}\n"
            + (f"   🔎 이름은 비슷한 후보 / near-miss: {', '.join(hints)}\n"
               "      (자동 채택하지 않습니다 — 드라이브·상위 경로가 바뀐 drift 일 수 있어 사람이 확인해야 합니다)\n"
               if hints else "")
            + "   해결 / Fix: `CLAUDE_PROJECT_MEMORY_DIR` 로 실경로를 지정하거나 디렉토리명을 맞추세요.\n"
            "   🔴 여기서 조용히 통과시키면 이 가드는 '초록인데 아무것도 검사하지 않는' 상태가 됩니다.",
            file=sys.stderr,
        )
        return 1

    # 🔴 검사 대상 문서가 실재하는지 먼저 확인 (Grok claim-review F3, 실측 재현).
    #   초판은 부재 문서를 조용히 건너뛰어, 전부 없으면 "참조 0건 → 모든 참조 존재" 로 exit 0 이었다.
    #   입력이 비었는데 성공을 보고하는 것이 이 회고가 명명한 "관측자가 자기 범위를 관측하지 않는다".
    # Verify the scanned docs exist: skipping them silently made an empty input report success.
    # 🔴 빈 목록도 실패다 — `DOC_FILES = []` 는 "부재 0건" 이라 부재 검사를 **통과**한다.
    #   스코프를 비우면 통과하는 검사는 그 자체로 fail-open 이다(실측: 이 테스트를 쓰다 발견).
    # An empty list also fails: it trivially satisfies an "any missing?" check.
    absent = [d for d in DOC_FILES if not (project_root / d).is_file()]
    if not DOC_FILES or absent:
        print(
            "🔴 점검 대상 문서가 없습니다 — 스코프가 비면 이 검사는 공허합니다.\n"
            "   Scanned documents are missing; an empty scope makes this check vacuous.\n"
            f"   부재 / missing: {', '.join(absent) or '(DOC_FILES 자체가 비어 있음)'}\n"
            "   해결 / Fix: 문서를 복구하거나 `DOC_FILES` 를 실제 경로로 갱신하세요.",
            file=sys.stderr,
        )
        return 1

    referenced = collect_referenced(project_root)
    actual = {f.name for f in memory_dir.glob("*.md") if f.name != "MEMORY.md"}
    stale = collect_stale(project_root, actual)

    print(f"메모리 디렉토리 / memory dir: {memory_dir}\n")
    return 0 if print_report(referenced, actual, stale) else 1


if __name__ == "__main__":
    sys.exit(main())
