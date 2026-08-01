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
_CROSS_AREA_RULES = (
    ("WorkerSessionLocal", "src/gate/engine.py"),
    ("WorkerSessionLocal", "src/worker/pipeline.py"),
    ("WorkerSessionLocal", "src/api/hook.py"),
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
    """규칙이 지배한다고 적은 경로가 실재해야 한다 — 죽은 경로면 이 단언이 공허하다."""
    assert (_ROOT / src_path).is_file(), f"{src_path} 가 없다 — _CROSS_AREA_RULES 갱신 필요"


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
