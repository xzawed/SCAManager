"""path-scoped rules 커버리지 · runbook 색인의 **대응 관계** 불변식.

## 사고 (2026-07-19 회고 P2)

1. 🔴 **credential 리댁션 필터를 호스팅하는 파일이 어떤 보안 규칙에도 안 걸렸다.**
   `src/logging_config.py` 는 `_RedactSecretsFilter`(#1109 봉인 — 봇 토큰·웹훅 URL 평문
   유출 차단)를 정의하는데, `.claude/rules/security.md` 의 `paths:` 에 없었다. 즉 **그
   파일을 편집하는 세션은 보안 규칙을 로드하지 않는다** — 통제를 지탱하는 코드가 통제를
   설명하는 문서와 연결되지 않은 상태.

2. **runbook 3건이 색인에서 누락됐다** — `ai-collaboration.md`(정책 19 가 **단일 출처**로
   지목) · `owed-verification.md`(SessionStart 훅이 매 세션 읽는 원장) · `cost-controls.md`.
   색인만 보는 세션에게 미등재 문서는 존재하지 않는 것과 같다.

3. CLAUDE.md 의 9영역 매트릭스와 각 규칙 파일의 `paths:` frontmatter 는 **같은 사실의
   두 사본**이라 조용히 갈라질 수 있다.

## 🔴 왜 이 방향만 검사하는가

매트릭스가 frontmatter 에 **없는** 경로를 나열하면 = 자동 로드된다고 **거짓 약속**한다.
반대(frontmatter 가 더 많음)는 매트릭스가 `등` 으로 축약한 정상 상태다(deploy·testing 실측).
따라서 `매트릭스 ⊆ frontmatter` 단방향만 강제한다 — 양방향 강제는 축약 표기를 금지해
정책 17(안정성 > 권장 규격)에 반한다.
Only the dangerous direction is enforced: a documented path that does NOT actually auto-load.
"""
import ast
import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_RULES = _ROOT / ".claude" / "rules"
_CLAUDE_MD = _ROOT / "CLAUDE.md"
_DOCS_README = _ROOT / "docs" / "README.md"
_RUNBOOKS = _ROOT / "docs" / "runbooks"


def rule_paths(area: str) -> set:
    """`.claude/rules/<area>.md` frontmatter 의 `paths:` 집합 — 실제 자동 로드 기준."""
    text = (_RULES / f"{area}.md").read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    return set((yaml.safe_load(m.group(1)) or {}).get("paths", [])) if m else set()


def _areas() -> list:
    return sorted(p.stem for p in _RULES.glob("*.md"))


# ── 1. 보안 통제 코드는 보안 규칙에 걸려야 한다 ──────────────────────────


def _modules_defining_logging_filters() -> list:
    """`logging.Filter` 를 상속하는 클래스를 정의한 `src/` 모듈 — AST 로 판정.

    🔴 문자열 검색이면 "필터를 붙일 것" 이라고 쓴 주석이 검사를 통과시킨다.
    """
    out = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {getattr(b, "attr", None) or getattr(b, "id", None) for b in node.bases}
            if "Filter" in bases:
                out.append(path.relative_to(_ROOT).as_posix())
                break
    return out


def test_log_redaction_modules_are_covered_by_security_rules():
    """🔴 로그 리댁션 필터를 정의하는 모듈은 `security.md` paths 에 있어야 한다.

    비밀을 지우는 코드를 편집하면서 보안 규칙을 못 읽는 상태를 금지한다.
    실측 사고: `src/logging_config.py`(`_RedactSecretsFilter`)가 미등재였다.
    """
    modules = _modules_defining_logging_filters()
    assert modules, "logging.Filter 정의 모듈이 0개 — 이 가드의 전제가 사라졌다"
    paths = rule_paths("security")
    uncovered = [
        m for m in modules
        if not any(_glob_covers(g, m) for g in paths)
    ]
    assert not uncovered, (
        f"보안 규칙 paths 에 없는 리댁션 모듈: {uncovered}\n"
        "→ `.claude/rules/security.md` frontmatter `paths:` + CLAUDE.md 9영역 매트릭스에\n"
        "   **양쪽 다** 추가할 것(둘은 같은 사실의 두 사본)."
    )


def _glob_covers(pattern: str, path: str) -> bool:
    """`src/**` 형태 glob 이 경로를 덮는가 — `Path.match` 는 `**` 를 다르게 다룬다."""
    if pattern == path:
        return True
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    return Path(path).match(pattern)


# ── 2. 매트릭스 ⊆ frontmatter (거짓 약속 금지) ───────────────────────────


def test_claude_md_matrix_never_promises_an_unloaded_path():
    """🔴 CLAUDE.md 매트릭스가 frontmatter 에 없는 경로를 나열하면 거짓 약속이다.

    "이 경로를 건드리면 규칙이 자동 로드된다" 고 읽히지만 실제로는 안 된다.
    반대 방향(frontmatter 가 더 많음)은 매트릭스의 `등` 축약이라 정상 — 강제하지 않는다.
    """
    claude = _CLAUDE_MD.read_text(encoding="utf-8")
    bad = {}
    for area in _areas():
        m = re.search(rf"{area}\.md \(([^)]*)\)", claude)
        if not m:
            continue
        promised = set(re.findall(r"`([^`]+)`", m.group(1)))
        extra = sorted(promised - rule_paths(area))
        if extra:
            bad[area] = extra
    assert not bad, (
        f"매트릭스가 약속했으나 frontmatter 에 없는 경로: {bad}\n"
        "→ 해당 `.claude/rules/<area>.md` 의 `paths:` 에 추가하거나 매트릭스에서 뺄 것."
    )


def test_every_rules_file_declares_paths():
    """대조군 — `paths:` 가 비면 그 규칙은 **영원히 로드되지 않는다**(조용한 무력화)."""
    empty = [a for a in _areas() if not rule_paths(a)]
    assert not empty, f"`paths:` 가 비어 자동 로드되지 않는 규칙 파일: {empty}"


# ── 3. runbook 색인 전단사 ───────────────────────────────────────────────


def _indexed_runbooks() -> set:
    return set(re.findall(r"runbooks/([\w.-]+\.md)", _DOCS_README.read_text(encoding="utf-8")))


def test_every_runbook_is_indexed():
    """🔴 `docs/runbooks/` 의 모든 문서는 `docs/README.md` 에 등재돼야 한다.

    실측 누락 3건 중 둘이 특히 아팠다 — `ai-collaboration.md` 는 정책 19 가 **단일 출처**로
    지목한 프로토콜이고, `owed-verification.md` 는 SessionStart 훅이 매 세션 읽는 원장이다.
    """
    disk = {p.name for p in _RUNBOOKS.glob("*.md")}
    missing = sorted(disk - _indexed_runbooks())
    assert not missing, (
        f"`docs/README.md` 에 미등재된 runbook: {missing}\n"
        "→ runbook 을 추가한 **같은 커밋**에서 색인 행도 추가할 것."
    )


def test_index_has_no_dangling_runbook_links():
    """역방향 — 색인이 없는 runbook 을 가리키면 죽은 링크다."""
    disk = {p.name for p in _RUNBOOKS.glob("*.md")}
    dangling = sorted(_indexed_runbooks() - disk)
    assert not dangling, f"색인이 존재하지 않는 runbook 을 가리킨다: {dangling}"


# ── 탐지력 자가 검증 / self-verification ─────────────────────────────────


def test_glob_matcher_handles_the_shapes_actually_used():
    """`_glob_covers` 경계 고정 — 여기가 틀리면 커버리지 단언이 조용히 무의미해진다."""
    assert _glob_covers("src/auth/**", "src/auth/oauth.py")
    assert _glob_covers("src/logging_config.py", "src/logging_config.py")
    assert not _glob_covers("src/auth/**", "src/logging_config.py")
    assert not _glob_covers("src/crypto.py", "src/logging_config.py")


def test_discovery_helpers_are_not_vacuous():
    """대조군 — 탐색이 0건이면 위 단언들이 공허하게 통과한다."""
    assert len(_areas()) >= 9, f"규칙 영역이 {len(_areas())}개 — 9개 미만이면 확인 필요"
    assert len(_indexed_runbooks()) > 10, "runbook 색인 추출이 사실상 비었다"
