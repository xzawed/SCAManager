"""문서의 "게이트" 주장 ↔ `Makefile` 실제 내용 대조 — 5지점 drift 재발 차단.

## 사고 (2026-08-01 Grok 시스템 감사 `019fbccf`)

"로컬 게이트가 무엇인가" 라는 **하나의 사실**이 5곳에 **서로 다르게** 적혀 있었다:

| 위치 | 주장 | 사실 |
|---|---|---|
| `CLAUDE.md` | `pre_push_gate` (make 부재 명시) | ✅ 2026-08-01 정정됨 |
| `AGENTS.md` | "`make gate` … **실제 게이트**" | 🔴 Grok 진입점이 거짓을 읽었다 |
| `docs/runbooks/new-machine-setup.md` | "정적 게이트 (**CI 동일 기준**) \| `make gate`" | 🔴 CLAUDE.md 만 고치고 남긴 사본 |
| `docs/agents-index.md` | "pytest + pylint + **flake8** + bandit" | 🔴 Makefile 이 flake8 을 **명시적으로 제외** |
| `.github/PULL_REQUEST_TEMPLATE.md` | "`make gate` 통과" 체크박스 | 🔴 `make` 없는 머신에선 정직하게 체크 불가 |

🔴 **한 사본만 고치면 나머지가 확실히 거짓이 된다.** 실제로 그 일이 일어났다 — CLAUDE.md 를
정정한 바로 그 세션이 4 사본을 남겼고, drift 가 줄지 않고 **커졌다**.

## 이 파일이 강제하는 것

기대값을 손으로 적지 않고 **`Makefile` 의 `gate:` 타깃에서 파싱**한다. Makefile 이 바뀌면
문서 주장도 따라와야 하고, 안 따라오면 여기서 깨진다.

Cross-checks every doc claim about the local gate against the Makefile's actual gate target;
expectations are parsed from the Makefile, never hand-copied.
"""
import re
import subprocess  # nosec B404 — 리포 자신의 파일 목록만 읽는다
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _ROOT / "Makefile"

# 로컬 게이트의 **정본 이름** — 문서가 "로컬 게이트" 를 말할 때 가리켜야 하는 것.
_CANONICAL_GATE = "scripts/pre_push_gate.py"

# `make gate` 가 실제로 부르지 **않는** 도구. 문서가 부른다고 하면 거짓이다.
_LINTERS = ("flake8", "pylint", "bandit", "mypy", "ruff")

# 부정 표지 — 이 표현이 같은 줄에 있으면 "거짓 주장" 이 아니라 **정정문**이다.
# 🔴 한글 활용형을 전부 적는다: `아니다`·`아닙니다`·`아니라`·`않는다`·`않습니다`.
#    `아니` 만으로는 `아닙니다`(아·닙·니·다)를 못 잡는다 — 실측으로 두 번 오탐했다.
# Negation markers; Korean inflections are enumerated because 아닙니다 does not contain 아니.
# 절 구분자 — 부정 표지는 **도구가 들어 있는 절 안에서만** 인정한다.
# 🔴 문자 창(±N)으로는 정밀하지 않았다: 25자면 참인 문장("`flake8` 은 … `make gate` 에서
#    제외돼")을 오탐하고, 40자로 늘리면 거짓 문장("게이트가 아니다 — … flake8 …")을 면제해
#    준다. 둘을 가르는 것은 거리가 아니라 **절 경계**다(실측 후 전환).
# Clause boundaries: a negation only excuses a claim inside the SAME clause. A character window
# could not separate the true sentence from the false one; the clause boundary can.
_CLAUSE_SPLIT = re.compile(r"[|—\-]{1,2}|[,()]|\. ")

_NEGATED = re.compile(
    r"아니다|아닙니다|아니라|아닌|않는다|않습니다|대체가|거짓|미포함|제외|"
    r"not the same|not a gate|exclud|never"
)


def gate_target_body() -> str:
    """`Makefile` 의 `gate:` 타깃 본문 (다음 top-level 타깃 직전까지)."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^gate:\s*$", text, re.MULTILINE)
    assert match, "Makefile 에 `gate:` 타깃이 없다 — 이 테스트가 공허해진다"
    rest = text[match.end():]
    nxt = re.search(r"^[a-zA-Z][\w-]*:", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def tools_make_gate_runs() -> set:
    """`make gate` 가 실제로 실행하는 린터 이름 집합 (주석 줄 제외)."""
    body = "\n".join(
        line for line in gate_target_body().splitlines()
        if not line.lstrip().startswith("#")
    )
    return {t for t in _LINTERS if re.search(rf"(?<![\w-]){t}(?![\w-])", body)}


def tracked_docs() -> list:
    out = subprocess.run(  # nosec B603 B607
        ["git", "ls-files", "*.md"], cwd=str(_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.split()
    return [f for f in out if "_archive" not in f]


# ── 파서가 공허하지 않은지 ────────────────────────────────────────────────


def test_makefile_gate_target_is_parseable():
    """🔴 대조군 — 파서가 고장 나면 아래 단언이 전부 통과해 버린다."""
    body = gate_target_body()
    assert "pytest" in body, f"gate 타깃에서 pytest 를 못 찾았다 — 파서 확인:\n{body[:200]}"
    tools = tools_make_gate_runs()
    assert tools, "gate 타깃에서 린터를 하나도 못 찾았다 — 파서 확인"


def test_flake8_is_genuinely_excluded_from_make_gate():
    """전제 고정 — Makefile 이 flake8 을 **의도적으로 제외**한다(주석이 사유를 적고 있다).

    이 전제가 바뀌면(= flake8 이 gate 에 들어가면) 아래 문서 단언의 의미도 달라지므로
    여기서 먼저 깨져야 한다.
    """
    assert "flake8" not in tools_make_gate_runs(), (
        "Makefile `gate:` 가 이제 flake8 을 부른다 — 문서 주장과 이 테스트를 함께 재검토할 것"
    )


# ── 핵심 불변식: 문서가 `make gate` 에 대해 거짓말하지 않는다 ──────────────


def _claim_lines(path: Path) -> list:
    """`make gate` 를 언급하는 줄 (번호, 내용). 주석·코드펜스 구분 없이 전부 본다."""
    return [
        (i, line) for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "make gate" in line
    ]


@pytest.mark.parametrize("doc", tracked_docs())
def test_no_doc_claims_make_gate_runs_a_tool_it_does_not(doc):
    """🔴 문서가 `make gate` 를 언급하면서 **실행하지 않는 도구**를 나열하면 거짓이다.

    실측 사고: `docs/agents-index.md` 가 "pytest + pylint + **flake8** + bandit" 이라 적었는데
    Makefile 은 flake8 을 명시적으로 제외한다.
    """
    absent = set(_LINTERS) - tools_make_gate_runs()
    for lineno, line in _claim_lines(_ROOT / doc):
        for tool in absent:
            if not re.search(rf"(?<![\w-]){tool}(?![\w-])", line):
                continue
            # 🔴 부정 표지는 **그 도구가 들어 있는 절 안에서만** 인정한다. 줄 전체를 보면
            #    "게이트가 아니다 — … pytest + pylint + flake8 + bandit" 처럼 **다른 것에 대한
            #    부정**이 거짓 주장을 면제해 준다(실측: 뮤테이션 M2 가 GREEN 이었다).
            # A negation only excuses the claim when it sits in the same clause as the tool.
            clauses = [c for c in _CLAUSE_SPLIT.split(line)
                       if re.search(rf"(?<![\w-]){tool}(?![\w-])", c)]
            if any(_NEGATED.search(c) for c in clauses):
                continue
            pytest.fail(
                f"{doc}:{lineno} 가 `make gate` 가 {tool!r} 을 실행한다고 읽힌다.\n"
                f"  줄: {line.strip()[:160]}\n"
                f"  Makefile `gate:` 실제 실행: {sorted(tools_make_gate_runs())}\n"
                "→ 문서를 고치거나, 부정 표지(미포함/제외)를 명시할 것."
            )


@pytest.mark.parametrize("doc", tracked_docs())
def test_no_doc_calls_make_gate_the_real_or_ci_equivalent_gate(doc):
    """🔴 `make gate` 를 "실제 게이트"·"CI 동일 기준" 이라 부르면 안 된다 — 둘 다 거짓이다.

    그 타깃은 CI 가 강제하는 repo-integrity 9종 + PR-diff 4종을 **하나도** 돌리지 않고,
    이 개발 머신에는 `make` 자체가 없다(backlog R29).
    """
    bad = ("실제 게이트", "CI 동일 기준", "CI 와 동일 기준")
    for lineno, line in _claim_lines(_ROOT / doc):
        for phrase in bad:
            # 🔴 한글 활용형 주의 — `아니다`의 존댓말은 `아닙니다`라 **`아니` 가 부분문자열이 아니다**
            #    (아·닙·니·다). 이 가드의 초판이 정확히 그 이유로 참인 문장을 두 번 오탐했다.
            #    활용형을 정규식으로 명시한다.
            # Korean inflection: 아닙니다 does not contain 아니 as a substring; enumerate the forms.
            if phrase in line and not _NEGATED.search(line):
                pytest.fail(
                    f"{doc}:{lineno} 가 `make gate` 를 {phrase!r} 로 부른다.\n"
                    f"  줄: {line.strip()[:160]}\n"
                    f"→ 로컬 게이트의 정본은 `{_CANONICAL_GATE}` 다."
                )


def test_the_canonical_gate_is_named_where_agents_enter():
    """🔴 진입 문서 3종이 **정본 게이트 이름**을 담아야 한다.

    Grok 은 `AGENTS.md` 로 들어오고, Claude 는 `CLAUDE.md` 로, 기여자는 PR 템플릿으로 들어온다.
    한 곳이라도 빠지면 그 경로로 들어온 행위자는 정본을 모른 채 작업한다.
    """
    for entry in ("AGENTS.md", "CLAUDE.md", ".github/PULL_REQUEST_TEMPLATE.md"):
        text = (_ROOT / entry).read_text(encoding="utf-8")
        assert _CANONICAL_GATE in text, (
            f"{entry} 에 정본 게이트 `{_CANONICAL_GATE}` 가 없다 — "
            "이 경로로 들어온 행위자는 무엇을 돌려야 하는지 모른다."
        )


def test_canonical_gate_script_exists():
    """정본 이름이 실재하는 파일을 가리켜야 한다 — 죽은 이름을 강제하면 더 나쁘다."""
    assert (_ROOT / _CANONICAL_GATE).is_file(), f"{_CANONICAL_GATE} 가 없다"
