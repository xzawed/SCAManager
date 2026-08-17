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
_CLAUSE_SPLIT = re.compile(r"[|—\-]{1,2}|[,;()]|\. ")

_NEGATED = re.compile(
    r"아니다|아닙니다|아니라|아닌|않는다|않습니다|대체가|거짓|미포함|제외|"
    r"not the same|not a gate|exclud|never"
)


def _quoted_spans(line: str) -> list:
    """따옴표로 감싼 구간 목록 — `"…"` · `“…”` · `'…'`.

    🔴 **인용은 주장이 아니다.** 이 저장소는 거짓 주장을 *인용해서 정정하는* 기록을 많이 남긴다
    (`STATE.md`·`backlog.md`·`cycle-history.md` 의 사고 서사, `CLAUDE.md` 의 정정문). 그 인용을
    거짓 주장으로 세면 **정정 기록을 쓸 수 없게 되고**, 그건 이 저장소가 가장 중요하게 여기는
    "무엇이 왜 틀렸는지 남기기" 를 가드가 막는 것이다(Grok claim-review `019fbd1e` 후 실측 4건).
    Quoting a falsehood in order to correct it is not asserting it.
    """
    spans, quote, start = [], None, 0
    pairs = {'"': '"', "“": "”", "'": "'"}
    for i, ch in enumerate(line):
        if quote is None and ch in pairs:
            quote, start = pairs[ch], i
        elif quote is not None and ch == quote:
            spans.append((start, i))
            quote = None
    return spans


def _is_citation(line: str, pos: int) -> bool:
    """그 위치가 인용 구간 안인가. / Is this position inside a quotation?"""
    return any(lo <= pos <= hi for lo, hi in _quoted_spans(line))


def _mentions(tool: str, text: str) -> bool:
    """단어 경계로 도구 이름을 찾는다. / Word-boundary match for a tool name."""
    return re.search(rf"(?<![\w-]){re.escape(tool)}(?![\w-])", text) is not None


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


def tracked_docs(root: Path | None = None) -> list:
    """추적 중인 `.md` 목록 — 경로 하나당 **정확히 한 번**.

    ## 사고 (2026-08-08 회고 N-P0-3 — main CI 12시간 49분 red 의 실기전)

    `git ls-files` 는 **머지 충돌 중인 경로를 stage 1/2/3 로 3번** 출력한다(실측). 이 함수가
    수집 시점에 호출되고 그 결과가 `parametrize` **2곳**(`:149`·`:188`)에 쓰이므로,
    충돌 `.md` 1건당 collected 가 **+4** 된다. 즉 충돌 중에 `--collect-only` 를 돌리면
    계기가 **트리에 없는 테스트 수**를 보고한다.

    실제로 그 일이 일어났다 — 배치-PR 충돌 4건 상태에서 잰 `6824 + 4×4 = 6840` 이
    STATE 4지점에 전파됐고, 충돌이 풀린 뒤 CI 가 6824 를 재서 main 이 12h49m red 였다.
    당시 이것은 *"사람의 수치 오판독"* 으로 기록됐다. 아니었다 — **계기가 거짓을 냈고
    사람은 그 값을 정확히 읽었다.** 관측자가 거짓말하는 이 리포의 지배 결함 그대로다.

    `--deduplicate` 플래그(git ≥2.31)에 의존하지 않고 **파이썬에서 순서 보존 dedupe** 한다 —
    구버전 git 에서 조용히 옛 동작으로 돌아가지 않게 하기 위해서다.

    🔴 **정직 기준** (Grok claim-review `019fe026`): 이 함수는 여전히 **인덱스**를 읽는다
    (`git ls-files` 가 그렇다). 닫은 것은 *"한 경로가 여러 번 나와 수가 부푸는"* 축 하나다.
    스테이지되었으나 미커밋인 `.md` 는 여전히 목록에 들어온다 — 그건 별개 축이고,
    수집 수를 **부풀리지는** 않으므로 6840 사고의 기전이 아니다.

    `-z` 로 NUL 구분해 읽는다 — 공백이 든 파일명이 `split()` 에 두 조각으로 쪼개져
    유령 항목 2개가 되던 것도 같은 부류의 계기 거짓말이기 때문이다(현재 해당 파일 0건).

    Returns each tracked ``.md`` exactly once. ``git ls-files`` emits a conflicted path once
    per merge stage, which silently inflated the collected-test count and shipped a wrong
    number to four sinks. NUL-separated so spaces in names cannot split one path into two.
    """
    base = root or _ROOT
    out = subprocess.run(  # nosec B603 B607
        ["git", "ls-files", "-z", "*.md"], cwd=str(base),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.split("\0")
    # 🔴 dict.fromkeys = 순서 보존 dedupe. set() 는 parametrize 순서를 비결정적으로 만든다.
    # dict.fromkeys keeps order; set() would make the parametrize order nondeterministic.
    # 🔴 인덱스는 있는데 워킹트리가 없는 경로(삭제 실험·반쯤 체크아웃)는 건너뛴다.
    #    이 테스트는 문서 **주장**을 읽는 것이지 파일 존재를 재는 것이 아니다.
    #    존재 축은 각 문서의 전용 가드가 진다. 인덱스만 보고 read_text 하면
    #    퇴역 예정 파일을 지우자마자 여기가 FileNotFoundError 로 죽는다.
    # Skip tracked-but-missing paths: this test reads claims, not file presence.
    return list(dict.fromkeys(
        f for f in out
        if f and "_archive" not in f and (base / f).is_file()
    ))


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
    runs = tools_make_gate_runs()
    absent = set(_LINTERS) - runs
    for lineno, line in _claim_lines(_ROOT / doc):
        for tool in absent:
            if not _mentions(tool, line):
                continue
            # 🔴 **열거 문맥**으로 판정한다 — 부정어 탐색은 양방향으로 취약했다:
            #    줄 전체를 보면 다른 것에 대한 부정이 거짓 주장을 면제했고(M2 GREEN),
            #    문자 창으로 좁히니 참인 문장을 오탐했고, 절 단위로 좁혀도
            #    "Unlike flake8, make gate only runs pylint and bandit" 같은 **참인 문장**을
            #    거부했다(Grok claim-review `019fbd1e` 가 6형태 실증).
            #    거짓 주장은 항상 **"make gate 가 돌리는 것들" 의 열거**로 나타난다:
            #    `pytest + pylint + flake8 + bandit`. 그러니 그 도구가 **실제로 도는 도구와
            #    같은 절에 나열돼 있을 때만** 거짓으로 본다. 단순하고, 양방향 오류가 없다.
            # Enumeration context, not negation hunting: a false claim always lists the absent
            # tool alongside tools make gate DOES run. Negation scanning failed both ways.
            enumerating = [
                c for c in _CLAUSE_SPLIT.split(line)
                if _mentions(tool, c) and any(_mentions(r, c) for r in runs)
            ]
            if not enumerating:
                continue
            if any(_NEGATED.search(c) for c in enumerating):
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

    그 타깃은 CI 가 강제하는 repo-integrity 가드와 PR-diff 한정 가드를 **하나도** 돌리지 않고,
    이 개발 머신에는 `make` 자체가 없다(backlog R29).

    2026-08-17 정정 — 여기 «9종 + 4종» 이라 적혀 있었다. 실측은 13 + 4 다
    (`pre_push_gate._INTEGRITY` 12 + `_INTEGRITY_WITH_ARGS` 1 · `_DIFF_SCOPED` 3 + flake8).
    같은 개수가 리포 8지점에 복사돼 7 · 9 · 13 세 값으로 갈려 있었다.
    """
    bad = ("실제 게이트", "CI 동일 기준", "CI 와 동일 기준")
    for lineno, line in _claim_lines(_ROOT / doc):
        for phrase in bad:
            # 🔴 한글 활용형 주의 — `아니다`의 존댓말은 `아닙니다`라 **`아니` 가 부분문자열이 아니다**
            #    (아·닙·니·다). 이 가드의 초판이 정확히 그 이유로 참인 문장을 두 번 오탐했다.
            #    활용형을 정규식으로 명시한다.
            # Korean inflection: 아닙니다 does not contain 아니 as a substring; enumerate the forms.
            # 🔴 형제 단언도 **절 단위**로 본다 — 초판은 줄 전체를 봐서
            #    "make gate 는 실제 게이트다 — lint 는 대체가 아니다" 가 면제됐다
            #    (Grok `019fbd1e` 적발: tool 축만 고치고 이 축에 같은 구멍을 남겼다).
            # Clause-scoped here too; the first version left this sibling hole line-wide.
            if phrase not in line:
                continue
            # 인용문 안이면 주장이 아니라 **정정 기록**이다(위 `_is_citation` 주석).
            if _is_citation(line, line.index(phrase)):
                continue
            owning = [c for c in _CLAUSE_SPLIT.split(line) if phrase in c]
            if not any(_NEGATED.search(c) for c in owning):
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


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 판정기 자체의 양방향 정밀도 (Grok claim-review `019fbd1e` 가 6형태 실증)
#
# 이 가드는 설계를 **세 번** 바꿨다:
#   1. 줄 전체 부정어 탐색 → 다른 것에 대한 부정이 거짓 주장을 면제(뮤테이션 M2 GREEN)
#   2. 문자 창 ±25 → 참인 문장("`flake8` 은 … `make gate` 에서 제외돼")을 오탐
#   3. 절 단위 → "Unlike flake8, make gate only runs pylint and bandit" 같은 **참인 문장**을 거부
#   4. **열거 문맥**(현행) → 거짓 주장은 항상 "make gate 가 돌리는 것들" 의 열거로 나타난다
#
# 아래는 그 실측 형태들이다. 판정기를 다시 좁히거나 넓히면 여기서 깨진다.
# ──────────────────────────────────────────────────────────────────────────────

def _tool_claim_fails(line: str) -> bool:
    """한 줄이 '거짓 도구 주장' 으로 판정되는가 — 위 단언과 같은 로직."""
    runs = tools_make_gate_runs()
    for tool in set(_LINTERS) - runs:
        if not _mentions(tool, line):
            continue
        enumerating = [
            c for c in _CLAUSE_SPLIT.split(line)
            if _mentions(tool, c) and any(_mentions(r, c) for r in runs)
        ]
        if enumerating and not any(_NEGATED.search(c) for c in enumerating):
            return True
    return False


@pytest.mark.parametrize("line", [
    # 🔴 전부 **참인 문장**이다 — 거부하면 가드 자살이다.
    "make gate (see also flake8 elsewhere for unused imports)",
    "make gate and the CI flake8 job are separate concerns",
    "Unlike flake8, make gate only runs pylint and bandit",
    "make gate runs pytest; also flake8 is in CI only",
    "See `make gate` vs `flake8` in CI",
    "flake8 is not run by make gate on purpose",
    "`flake8` 은 의도적으로 `make gate` 에서 제외돼 있습니다",
    "make gate 는 pytest + pylint + bandit 3종뿐 (flake8 미포함)",
])
def test_true_sentences_are_not_flagged(line):
    assert not _tool_claim_fails(line), f"참인 문장을 거짓 주장으로 오판 — 가드 자살: {line!r}"


@pytest.mark.parametrize("line", [
    # 🔴 전부 **거짓 주장**이다 — 통과시키면 fail-open 이다.
    "| `make gate` | Phase 게이트 — pytest + pylint + flake8 + bandit |",
    "make gate runs pytest + pylint + flake8 + bandit",
    "🔴 **Phase 완료 게이트가 아니다** — pytest + pylint + flake8 + bandit",
])
def test_false_claims_are_flagged(line):
    assert _tool_claim_fails(line), f"거짓 주장을 통과 — fail-open: {line!r}"


@pytest.mark.parametrize(("line", "flagged"), [
    # 인용은 주장이 아니다 — 정정 기록을 쓸 수 있어야 한다.
    ('CLAUDE.md 의 *"로컬 사전 확인은 `make gate`(CI 와 동일 기준)"* 는 **거짓**이었다', False),
    ('⚠️ **`make gate` 는 "CI 와 동일 기준" 이 아니었다**(2026-08-01 정정)', False),
    # 인용 없이 그대로 주장하면 거짓이다.
    ("로컬 사전 확인은 `make gate` — CI 와 동일 기준이다", True),
])
def test_citation_is_not_an_assertion(line, flagged):
    owning = [c for c in _CLAUSE_SPLIT.split(line) if "CI 와 동일 기준" in c]
    cited = _is_citation(line, line.index("CI 와 동일 기준"))
    hit = (not cited) and owning and not any(_NEGATED.search(c) for c in owning)
    assert bool(hit) is flagged, f"인용/주장 구분 오판: {line!r}"
