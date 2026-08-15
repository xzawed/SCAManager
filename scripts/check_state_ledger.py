#!/usr/bin/env python3
"""STATE.md §테스트 수 추적 이력 — 조용한 손실을 명시 결정으로 승격.

## 왜 필요한가 (단위 2 P0-2)

조사 실측: 원장 항목을 173건 → 1건으로 줄여도 전 가드가 초록이었다. 그래서
*"줄였다"* · *"보존했다"* 는 기계로 검증 불가능한 주장이었다. 다음 세션이
원장을 통째로 날려도 아무도 모른다.

이 가드는 감축을 **금지하지 않는다**. baseline 을 같은 PR 에서 낮추면 통과한다.
목적은 조용한 손실을 리뷰 가능한 diff 로 승격하는 것
(`check_lint_js_nonvacuous` 의 baseline 관용구와 같다).

## 계약

- `min_items` — `- ` 불릿 수가 커밋된 하한 미만이면 red.
- `min_chars` — 절 문자 수가 커밋된 하한 미만이면 red.
- 수치 사슬 — 형식 있는 항목의 `→ **B** 단위` 가 다음 `(A→` 와 같아야 한다.
  알려진 예외는 baseline `known_breaks` 에 **사유와 함께** 등재.
  새 단절 · 쓰이지 않는 예외 둘 다 red.

## 못 막는 것 (정직 기준)

- 같은 PR 이 baseline 을 함께 고치면 통과한다 (의도).
- 항목 수와 문자 수를 유지한 채 본문을 `X` 로 채우고 공백으로 패딩하면 통과한다.
  문자 하한은 *짧은* 공동화(R81)만 잡는다. 등가 길이 필러는 이 축의 밖이다.
  성공 배너에도 이 한계를 인쇄한다 — 초록이 "내용이 살아 있다"가 아니다.
- `→**B** 단위` / `(A→` 형식이 없는 초기 항목은 사슬 검사 대상이 아니다.
- 항목을 합치거나 나누되 수·문자·사슬을 지키면 내용 손실을 못 본다.
- `known_breaks` 사유의 *의미* 진위는 정적 검사가 원리적으로 못 본다.
  길이·어휘는 연극이다. 대신 예외 개수 상한(코드 상수)과 테스트의 리터럴
  집합 핀이 등재를 비싸게 만든다. 상한을 올리고 핀을 같은 PR 에서 바꾸면 통과한다.

Promotes silent ledger loss to an explicit baseline diff. Does not forbid
reduction; a same-PR baseline edit still passes. Equal-length filler is out of
scope and the success banner says so.
"""
from __future__ import annotations

import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]
_STATE = _ROOT / "docs" / "STATE.md"
_BASELINE = _ROOT / "scripts" / "state_ledger_baseline.json"

HIST_HEADING = "## 테스트 수 추적 이력"
# 형식 쌍의 열림. C(`= **N** 수집`)는 다음 열림 앞 구간에서만 찾는다.
# Pair opener. C (`= **N** 수집`) is taken only from the span before the next opener.
# 초판은 `_first(TOTAL)` 과 `_first(UNIT)` 를 따로 써서 불릿 안 첫 매치가
# 서로 다른 쌍의 숫자로 SSOT 를 조립했다 (claim-review 01a00434).
# Independent _first(TOTAL)/_first(UNIT) assembled a pair from two different matches.
_UNIT_OPEN = re.compile(r"\((\d+)\s*→\s*\*\*(\d+)\*\*\s*단위")
_FULL_TOTAL = re.compile(r"=\s*\*\*(\d+)\*\*\s*수집")
# 하위 호환 별칭 — 외부 테스트가 예전에 쓰던 이름. 신규 코드는 formal_pairs 만.
# Aliases for older tests. New code goes through formal_pairs only.
_START = re.compile(r"\((\d+)\s*→")
_END = re.compile(r"→\s*\*\*(\d+)\*\*\s*단위")
_REASON_MIN = 16
# 예외 상한. 늘리려면 이 숫자와 테스트 리터럴 집합을 같은 PR 에서 바꿔야 한다.
# Cap on exceptions. Raising it is a two-file, reviewable change.
MAX_KNOWN_BREAKS = 1


@dataclass(frozen=True)
class Violation:
    """한 축의 위반. 메시지가 아니라 axis/kind/data 로 단언한다.

    One finding. Tests assert axis/kind/data, not message substrings.
    """

    axis: str
    kind: str
    message: str
    data: tuple = ()


@dataclass
class LedgerVerdict:
    """원장 판정. / Structured ledger verdict."""

    ok: bool
    violations: list[Violation]

    @property
    def msgs(self) -> list[str]:
        return [v.message for v in self.violations]


def history_section(state: str) -> tuple[str | None, list[str]]:
    """이력 절 본문. 절이 없거나 둘이면 fail-closed."""
    count = state.count(HIST_HEADING)
    if count == 0:
        return None, [f"❌ STATE.md 에 `{HIST_HEADING}` 절이 없다 — 원장 검사 불가"]
    if count > 1:
        return None, [
            f"❌ `{HIST_HEADING}` 절이 {count}개다 — 원장 SSOT 는 **하나**여야 한다"
        ]
    section = state.split(HIST_HEADING, 1)[1].split("\n## ", 1)[0]
    return section, []


def ledger_items(section: str) -> list[str]:
    """`- ` 로 시작하는 항목. / Bullets that start with `- `."""
    return [ln for ln in section.splitlines() if ln.startswith("- ")]


def formal_pairs(line: str) -> list[tuple[int, int, int | None]]:
    """한 줄의 형식 쌍. `_history_tail` 과 `parse_chain` 의 **단일 읽기 규약**.

    각 쌍은 `(A→**B** 단위` 로 시작한다. `= **C** 수집` 은 그 시작부터
    **다음** `(A→**B** 단위` 앞까지만 본다. 그래서 한 불릿에  decoy 쌍을
    앞에 붙여도 첫 C 와 첫 B 가 다른 쌍에서 조립되지 않는다.

    선택 (claim-review 01a00434 처방):
    - 마지막 매치: decoy 를 뒤에 붙이면 그대로 뚫린다.
    - 불릿당 1개 강제(전 항목): 원장 line 128 이 이어 붙인 2쌍이라 live 가 red.
    - **이 파서 + 마지막 불릿의 full pair(C 있는 쌍) 가 정확히 1개** — 문법 통일,
      역사적 이어 붙임은 사슬 홉으로 살리고, SSOT 만 모호하면 red.

    One grammar for both consumers. C is scoped to the span before the next opener.
    """
    opens = list(_UNIT_OPEN.finditer(line))
    out: list[tuple[int, int, int | None]] = []
    for i, match in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(line)
        segment = line[match.end() : end]
        total = _FULL_TOTAL.search(segment)
        out.append((
            int(match.group(1)),
            int(match.group(2)),
            int(total.group(1)) if total else None,
        ))
    return out


def full_pairs(line: str) -> list[tuple[int, int, int]]:
    """C 가 있는 형식 쌍만. SSOT 는 이 목록이 마지막 불릿에서 길이 1 이어야 한다.

    Full pairs only (C present). The last bullet must have exactly one.
    """
    return [(a, b, c) for a, b, c in formal_pairs(line) if c is not None]


def parse_chain(items: list[str]) -> list[tuple[int, int]]:
    """형식 있는 항목의 (시작 A, 끝 B). `formal_pairs` 와 같은 문법.

    한 줄에 쌍이 여럿이면(이어 붙임) **각 쌍이 한 홉**이다. 예전처럼
    첫 A·마지막 B 로 한 홉을 만들지 않는다 — 그건 `_history_tail` 의
    독립 `_first` 와 규약이 갈렸다.
    Same grammar as formal_pairs. Concatenated bullets emit one hop per pair.
    """
    pairs: list[tuple[int, int]] = []
    for line in items:
        for start, end, _total in formal_pairs(line):
            pairs.append((start, end))
    return pairs


def load_baseline(path: Path) -> tuple[dict | None, list[str]]:
    """baseline JSON. 없거나 형식이 아니면 None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"❌ baseline 을 읽지 못했다 ({path}) — {exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"❌ baseline JSON 파싱 실패 ({path}) — {exc}"]
    if not isinstance(data, dict):
        return None, ["❌ baseline 이 object 가 아니다 — 검사 범위 붕괴"]
    missing = [k for k in ("min_items", "min_chars", "known_breaks") if k not in data]
    if missing:
        return None, [f"❌ baseline 키 누락: {missing} — 검사 범위 붕괴"]
    try:
        data["min_items"] = int(data["min_items"])
        data["min_chars"] = int(data["min_chars"])
    except (TypeError, ValueError):
        return None, ["❌ baseline min_items/min_chars 가 정수가 아니다"]
    if not isinstance(data["known_breaks"], list):
        return None, ["❌ baseline known_breaks 가 배열이 아니다"]
    return data, []


def _known_pairs(raw: list) -> tuple[set[tuple[int, int]], list[str]]:
    """known_breaks 를 (prev_end, next_start) 집합으로. 사유 없는 항목은 red."""
    pairs: set[tuple[int, int]] = set()
    errs: list[str] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            errs.append(f"❌ known_breaks[{i}] 가 object 가 아니다")
            continue
        reason = str(row.get("reason") or "").strip()
        if len(reason) < _REASON_MIN:
            errs.append(
                f"❌ known_breaks[{i}] 사유가 {_REASON_MIN}자 미만이다 "
                f"({len(reason)}자) — 빈 사유는 등재가 아니다"
            )
            continue
        try:
            pairs.add((int(row["prev_end"]), int(row["next_start"])))
        except (KeyError, TypeError, ValueError):
            errs.append(f"❌ known_breaks[{i}] 에 prev_end/next_start 정수가 없다")
    return pairs, errs


def observed_breaks(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """인접 형식 항목에서 prev_end != next_start 인 단절."""
    out: list[tuple[int, int]] = []
    for prev, cur in zip(pairs, pairs[1:]):
        if prev[1] != cur[0]:
            out.append((prev[1], cur[0]))
    return out


def evaluate_ledger(state: str, baseline_path: Path) -> LedgerVerdict:
    """원장 판정 — 축이 식별 가능한 Violation 목록.

    `check_ledger` 는 이 결과의 (ok, msgs) 뷰다. 테스트는 여기를 직접 본다.
    Structured verdict; check_ledger is the (ok, msgs) view for the CLI.
    """
    violations: list[Violation] = []
    section, errs = history_section(state)
    if errs:
        kind = "ambiguous" if "개다" in (errs[0] if errs else "") else "missing"
        return LedgerVerdict(False, [
            Violation("section", kind, m) for m in errs
        ])
    assert section is not None

    baseline, berr = load_baseline(baseline_path)
    if berr:
        kind = "missing" if not baseline_path.exists() else "invalid"
        return LedgerVerdict(False, [
            Violation("baseline", kind, m) for m in berr
        ])
    assert baseline is not None

    items = ledger_items(section)
    n_items = len(items)
    n_chars = len(section)
    if n_items < baseline["min_items"]:
        violations.append(Violation(
            "items",
            "below_floor",
            f"❌ 원장 항목 수 {n_items} < baseline min_items {baseline['min_items']} "
            "— 감소는 같은 PR 에서 baseline 을 낮추는 명시 결정이어야 한다",
            (n_items, baseline["min_items"]),
        ))
    if n_chars < baseline["min_chars"]:
        violations.append(Violation(
            "chars",
            "below_floor",
            f"❌ 원장 문자 수 {n_chars} < baseline min_chars {baseline['min_chars']} "
            "— 짧은 공동화(항목만 남기고 본문을 비움)를 막는다",
            (n_chars, baseline["min_chars"]),
        ))

    raw_breaks = baseline["known_breaks"]
    if len(raw_breaks) > MAX_KNOWN_BREAKS:
        violations.append(Violation(
            "known_breaks",
            "over_cap",
            f"❌ known_breaks {len(raw_breaks)}개 > 상한 {MAX_KNOWN_BREAKS} — "
            "상한을 올리려면 코드 상수와 테스트 리터럴 집합을 같은 PR 에서 바꿔야 한다",
            (len(raw_breaks), MAX_KNOWN_BREAKS),
        ))

    known, kerr = _known_pairs(raw_breaks)
    for msg in kerr:
        violations.append(Violation("known_breaks", "no_reason", msg))
    pairs = parse_chain(items)
    observed = set(observed_breaks(pairs))
    for prev_end, next_start in sorted(observed - known):
        violations.append(Violation(
            "chain",
            "new_break",
            f"❌ 새 사슬 단절 {prev_end}→{next_start} — "
            "기존 예외가 아니면 baseline known_breaks 에 사유와 함께 등재할 것",
            (prev_end, next_start),
        ))
    for prev_end, next_start in sorted(known - observed):
        violations.append(Violation(
            "chain",
            "stale_break",
            f"❌ 쓰이지 않는 예외 {prev_end}→{next_start} — "
            "단절이 사라졌으면 known_breaks 에서 제거할 것",
            (prev_end, next_start),
        ))
    return LedgerVerdict(not violations, violations)


def check_ledger(state: str, baseline_path: Path) -> tuple[bool, list[str]]:
    """CLI/기존 호출자용 (ok, msgs) 뷰. 테스트는 evaluate_ledger 를 쓴다."""
    verdict = evaluate_ledger(state, baseline_path)
    return verdict.ok, verdict.msgs


def write_baseline(state: str, baseline_path: Path) -> tuple[int, list[str]]:
    """min_items/min_chars 만 갱신. 새 단절이 있으면 쓰지 않는다.

    known_breaks 는 자동 감지하지 않는다 — 예외는 사람이 사유를 적어야 한다.
    Floors only. New breaks refuse the write; exceptions stay hand-authored.
    """
    existing, berr = load_baseline(baseline_path)
    known_raw = existing["known_breaks"] if existing and not berr else []
    # 기존 파일이 없어도 갱신은 가능하다 — 예외는 빈 배열로 시작한다.
    # A missing file can still be created; exceptions start empty.
    if existing is None:
        known_raw = []

    section, errs = history_section(state)
    if errs:
        return 1, errs
    assert section is not None
    items = ledger_items(section)
    pairs = parse_chain(items)
    known, kerr = _known_pairs(known_raw) if known_raw else (set(), [])
    if kerr:
        return 1, kerr + ["→ 예외 사유를 고친 뒤에 --update-baseline 을 다시 돌릴 것"]
    new = sorted(set(observed_breaks(pairs)) - known)
    if new:
        return 1, [
            f"❌ 새 단절이 있어 baseline 을 쓰지 않았다: {new}",
            "→ known_breaks 에 사유와 함께 등재한 뒤 다시 --update-baseline.",
        ]
    payload = {
        "min_items": len(items),
        "min_chars": len(section),
        "known_breaks": known_raw,
    }
    old_items = existing["min_items"] if existing else None
    old_chars = existing["min_chars"] if existing else None
    baseline_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    di = (
        f"{old_items}→{payload['min_items']} "
        f"({payload['min_items'] - old_items:+})"
        if old_items is not None
        else f"(new) {payload['min_items']}"
    )
    dc = (
        f"{old_chars}→{payload['min_chars']} "
        f"({payload['min_chars'] - old_chars:+})"
        if old_chars is not None
        else f"(new) {payload['min_chars']}"
    )
    return 0, [
        f"baseline 갱신: items {di} · chars {dc} · breaks={len(known_raw)}"
    ]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    state_text = _STATE.read_text(encoding="utf-8")
    if "--update-baseline" in args:
        code, msgs = write_baseline(state_text, _BASELINE)
        for m in msgs:
            print(m)
        return code
    print("=== STATE 원장 하한 / State ledger floor ===\n")
    ok, msgs = check_ledger(state_text, _BASELINE)
    if ok:
        section, _ = history_section(state_text)
        items = ledger_items(section or "")
        baseline, _ = load_baseline(_BASELINE)
        n_items = len(items)
        n_chars = len(section or "")
        floor_i = baseline["min_items"] if baseline else "?"
        floor_c = baseline["min_chars"] if baseline else "?"
        delta_i = f"{n_items - floor_i:+}" if isinstance(floor_i, int) else "?"
        delta_c = f"{n_chars - floor_c:+}" if isinstance(floor_c, int) else "?"
        print(
            f"✅ 원장 항목 {n_items} (하한 {floor_i}, {delta_i}) · "
            f"문자 {n_chars} (하한 {floor_c}, {delta_c})"
        )
        print(
            "   사슬 단절은 등재분뿐. "
            "등가 길이 필러(본문 X + 같은 문자 수 패딩)는 이 축이 못 막는다."
        )
        return 0
    for m in msgs:
        print(m)
    print(
        "\n해결: 의도한 감축이면 `py -3 scripts/check_state_ledger.py --update-baseline` "
        "결과를 **같은 PR 에** 포함하고, 새 단절이면 known_breaks 에 사유를 적는다."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
