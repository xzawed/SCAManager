"""path-scoped 규칙이 **필요한 순간에 도달하는가** — 경로 매칭 ≠ 소비자 목록.

## 사고 (2026-08-01 Grok 시스템 감사 `019fbccf`)

`.claude/rules/<area>.md` 는 frontmatter 의 `paths:` 가 매칭될 때만 Claude 컨텍스트에 자동
주입된다. 그런데 규칙 **본문**은 종종 다른 경로의 파일을 지배한다.

실측: `db.md` 의 **`WorkerSessionLocal` 세션 라우팅 규칙**은 background 진입점 17 모듈
(`gate/engine`·`worker/pipeline`·`webhook/*`·`notifier/*`·`api/*` 등)에 **alias 를 의무화**하는데,
`db.md` 의 `paths:` 는 `alembic/**`·`src/models/**`·`src/database.py`·`src/repositories/**` 뿐이다.
→ **그 17 모듈을 편집할 때 규칙이 자동으로 오지 않는다.**

사후 가드(`test_worker_session_routing.py`)가 위반을 잡지만, 작성 시점에 규칙을 못 보면
틀린 코드를 먼저 쓰게 된다. "가드가 있으니 됐다" 는 이 저장소가 반복해 온 오답이다.

## 이 파일이 강제하는 것

규칙 본문이 **어떤 소스 경로를 지배한다고 말하면**, 그 경로를 `paths:` 로 갖는 규칙 파일에도
최소한 **포인터**가 있어야 한다. 기대값을 손으로 적지 않고 **rules frontmatter 에서 파싱**한다.

Path-scoped rules only load on path match; this guard asserts that a rule governing modules
outside its own path set is at least pointed at from the rule files those modules DO load.
"""
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_RULES_DIR = _ROOT / ".claude" / "rules"

# 🔴 "이 심볼을 의무화하는 규칙" ↔ "그 의무가 적용되는 대표 소스 경로".
#    기대값을 여기 고정하는 이유: rules 본문에서 소비자 목록을 파싱하면 서술 형식에 의존해
#    깨지기 쉽다. 대신 **경로는 실재해야** 하고(아래 대조군), 규칙 파일 매칭은 실측한다.
# 🔴 **하드코딩 3핀은 등록 침묵을 만든다** — 새 cross-area 규칙을 추가해도 아무도 알려주지
#    않고 스위트는 초록으로 남는다(Grok claim-review `019fbd1e` 적발). 그래서 대상 경로를
#    **디스크에서 유도**한다: `WorkerSessionLocal` 을 실제로 쓰는 소스 파일 전부가 대상이다.
#    규칙이 지배하는 파일이 늘면 검사 대상도 자동으로 는다.
# Derived from disk, not pinned: every source file that actually uses the symbol is a target,
# so adding a consumer automatically widens the check instead of silently passing.
_CROSS_AREA_SYMBOLS = ("WorkerSessionLocal",)


def _consumers(symbol: str) -> list:
    """이 심볼을 실제로 쓰는 `src/` 파일들 (정의 파일 `database.py` 는 제외)."""
    out = []
    for f in sorted((_ROOT / "src").rglob("*.py")):
        rel = f.relative_to(_ROOT).as_posix()
        if rel == "src/database.py":
            continue
        if symbol in f.read_text(encoding="utf-8", errors="replace"):
            out.append(rel)
    return out


_CROSS_AREA_RULES = tuple(
    (sym, path) for sym in _CROSS_AREA_SYMBOLS for path in _consumers(sym)
)


def rule_paths(rule_file: Path) -> list:
    """규칙 파일 frontmatter 의 `paths:` 목록."""
    text = rule_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return []
    end = text.index("\n---", 3)
    block = text[:end]
    match = re.search(r"^paths:\s*$", block, re.MULTILINE)
    if not match:
        return []
    return re.findall(r'^\s*-\s*"([^"]+)"', block[match.end():], re.MULTILINE)


def _matches(pattern: str, path: str) -> bool:
    """`src/gate/**` 같은 glob 을 경로에 대조 (fnmatch 는 `**` 를 `/` 넘어 매칭 못 함)."""
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, path) is not None


def rules_loaded_for(path: str) -> list:
    """이 소스 경로를 편집할 때 자동 로드되는 규칙 파일들."""
    return [
        f for f in sorted(_RULES_DIR.glob("*.md"))
        if any(_matches(p, path) for p in rule_paths(f))
    ]


# ── 파서가 공허하지 않은지 ────────────────────────────────────────────────


def test_rule_frontmatter_is_parseable():
    """🔴 대조군 — frontmatter 파싱이 깨지면 아래 단언이 전부 공허해진다."""
    files = sorted(_RULES_DIR.glob("*.md"))
    assert len(files) >= 8, f"규칙 파일 {len(files)}개 — 경로 확인"
    with_paths = [f for f in files if rule_paths(f)]
    assert len(with_paths) >= 8, (
        f"`paths:` 를 읽어낸 규칙이 {len(with_paths)}개뿐 — 파서 확인"
    )


def test_glob_matcher_is_not_vacuous():
    """🔴 매처가 항상 True/False 면 이 파일 전체가 무의미하다."""
    assert _matches("src/gate/**", "src/gate/engine.py") is True
    assert _matches("src/gate/**", "src/worker/pipeline.py") is False
    assert _matches("src/database.py", "src/database.py") is True
    assert _matches("src/models/**", "src/database.py") is False


@pytest.mark.parametrize(("_symbol", "src_path"), _CROSS_AREA_RULES)
def test_governed_paths_exist(_symbol, src_path):
    """유도된 경로가 실재해야 한다 — 파서가 고장 나면 이 단언이 먼저 깨진다."""
    assert (_ROOT / src_path).is_file(), f"{src_path} 가 없다 — 유도 로직 확인"


def test_consumer_derivation_is_not_vacuous():
    """🔴 대조군 — 소비자를 하나도 못 찾으면 아래 단언 전체가 공허하다."""
    found = _consumers("WorkerSessionLocal")
    assert len(found) >= 8, f"소비자를 {len(found)}개만 찾았다 — 유도 로직 확인: {found}"


# ── 핵심 불변식 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(("symbol", "src_path"), _CROSS_AREA_RULES)
def test_cross_area_rule_reaches_the_files_it_governs(symbol, src_path):
    """🔴 규칙이 지배하는 파일을 편집할 때 그 규칙이 **자동 로드되는 규칙 파일에 있어야** 한다.

    본문이 다른 파일에 있어도 좋다 — 포인터 한 줄이면 충분하다. 없으면 그 규칙은
    "있는데 안 보이는" 상태이고, 그건 이 저장소의 지배적 결함 형태다.
    """
    loaded = rules_loaded_for(src_path)
    assert loaded, f"{src_path} 편집 시 로드되는 규칙이 하나도 없다 — paths 매트릭스 확인"

    mentions = [f.name for f in loaded if symbol in f.read_text(encoding="utf-8")]
    assert mentions, (
        f"`{symbol}` 규칙이 {src_path} 를 지배하는데, 그 파일 편집 시 로드되는 규칙\n"
        f"  {[f.name for f in loaded]}\n"
        f"어디에도 그 이름이 없다 — 작성 시점에 규칙이 보이지 않는다.\n"
        "→ 해당 규칙 파일에 **포인터 한 줄**을 넣을 것(본문 복제 불필요)."
    )


def test_claude_md_path_matrix_matches_the_real_rule_files():
    """🔴 `CLAUDE.md` 의 path 매트릭스가 실제 규칙 파일과 일치해야 한다.

    매트릭스가 stale 하면 Grok(= auto-load 없음)이 그 표를 보고 **없는 파일을 열거나
    있는 파일을 놓친다**.
    """
    claude = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    on_disk = {f.stem for f in _RULES_DIR.glob("*.md")}
    assert on_disk, "규칙 파일을 못 찾았다"
    missing = [
        name for name in sorted(on_disk)
        if f".claude/rules/{name}.md" not in claude
    ]
    assert not missing, (
        f"CLAUDE.md 가 언급하지 않는 규칙 파일: {missing}\n"
        "→ Grok 은 auto-load 가 없어 이 목록만 보고 움직인다."
    )


def test_agents_md_carries_the_path_table_for_grok():
    """🔴 Grok 은 auto-load 가 **없다** — `AGENTS.md` 에 경로별 표가 있어야 한다.

    표가 없으면 Grok 은 "grep 해서 찾아라" 만 듣고, 시간 압박 아래 규칙을 건너뛴다.
    """
    agents = (_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for needle in ("src/gate/**", "src/worker/pipeline.py", "tests/**", "scripts/**"):
        assert needle in agents, (
            f"AGENTS.md 의 경로 표에 {needle!r} 가 없다 — Grok 이 그 영역 규칙을 못 찾는다"
        )
    assert "WorkerSessionLocal" in agents, (
        "AGENTS.md 가 path 매칭이 안 되는 cross-area 규칙을 경고하지 않는다"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 `AGENTS.md` 경로 표 ↔ rules frontmatter 정합 (Grok `019fbd1e` 적발: 24 경로 누락)
#
# Grok 은 auto-load 가 **없어서** 이 표만 보고 움직인다. 표가 frontmatter 와 갈라지면
# **없는 규칙을 열거나 있는 규칙을 놓친다** — 틀린 표는 표가 없는 것보다 나쁘다.
#
# 다만 표는 사람이 읽는 문서라 축약 표기를 쓴다(`requirements*.txt`,
# `src/shared/{log_safety,ssrf,secure_compare}.py`). 그래서 **문자 일치가 아니라
# 축약을 인정하는 대조**를 한다 — 안 그러면 이 가드가 정당한 표기를 거부한다(가드 자살).
# ──────────────────────────────────────────────────────────────────────────────

def _covered_by_table(path: str, table: str) -> bool:
    """frontmatter 경로가 표에 (축약 표기 포함) 나타나는가."""
    if path in table:
        return True
    # `requirements-dev.txt` ← `requirements*.txt`
    # 🔴 접두사만 뽑는다 — `[-.\w]+\.txt$` 는 문자열 전체를 삼켜 빈 stem 을 냈다(실측).
    m = re.fullmatch(r"([A-Za-z_]+)[-.].*\.txt", path)
    if m and f"{m.group(1)}*.txt" in table:
        return True
    # `src/shared/ssrf.py` ← `src/shared/{log_safety,ssrf,secure_compare}.py`
    m = re.fullmatch(r"(.*/)(\w+)\.py", path)
    if m and re.search(rf"{re.escape(m.group(1))}\{{[^}}]*\b{re.escape(m.group(2))}\b[^}}]*\}}\.py", table):
        return True
    # `tests/unit/hooks/**` ← `tests/unit/{scripts,hooks}/**`
    m = re.fullmatch(r"(.*/)(\w+)/\*\*", path)
    if m and re.search(rf"{re.escape(m.group(1))}\{{[^}}]*\b{re.escape(m.group(2))}\b[^}}]*\}}/\*\*", table):
        return True
    return False


def test_shorthand_matcher_is_not_vacuous():
    """🔴 축약 매처가 항상 True 면 아래 단언 전체가 무의미하다."""
    table = "`requirements*.txt` · `src/shared/{log_safety,ssrf}.py` · `tests/unit/{scripts,hooks}/**`"
    assert _covered_by_table("requirements-dev.txt", table) is True
    assert _covered_by_table("src/shared/ssrf.py", table) is True
    assert _covered_by_table("tests/unit/hooks/**", table) is True
    assert _covered_by_table("src/gate/**", table) is False, "매처가 아무거나 통과시킨다"
    assert _covered_by_table("src/shared/nope.py", table) is False


def test_agents_path_table_covers_every_rule_frontmatter_path():
    """🔴 표가 frontmatter 를 **전부** 덮어야 한다 — Grok 은 이 표만 본다."""
    table = (_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    missing = [
        (f.stem, p)
        for f in sorted(_RULES_DIR.glob("*.md"))
        for p in rule_paths(f)
        if not _covered_by_table(p, table)
    ]
    assert not missing, (
        "AGENTS.md 경로 표가 덮지 않는 rules frontmatter 경로:\n  "
        + "\n  ".join(f"{s}: {p}" for s, p in missing)
        + "\n→ Grok 은 auto-load 가 없어 이 표만 보고 움직인다. 표를 갱신하거나 축약 표기를 맞출 것."
    )
