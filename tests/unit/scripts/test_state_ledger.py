"""`scripts/check_state_ledger.py` — STATE §추적 이력의 조용한 손실을 명시 결정으로 승격.

## 왜 (단위 2 P0-2)

조사 실측: 원장 항목을 173→1 로 줄여도 전 가드가 초록이었다. 그래서 *"줄였다"* ·
*"보존했다"* 는 기계로 검증 불가능한 주장이었다. 이 가드는 감축을 **금지하지 않는다** —
baseline 을 같은 PR 에서 낮추면 통과한다. 목적은 조용한 손실을 diff 에 보이게 하는 것
(`check_lint_js_nonvacuous` 의 baseline 관용구).

## 계약

1. 항목 수(`- ` 불릿)가 커밋된 `min_items` 미만이면 red.
2. 절 문자 수가 커밋된 `min_chars` 미만이면 red.
3. 인접 항목의 `→ **B** 단위` 가 다음 `(A→` 와 같아야 한다.
   알려진 예외는 baseline `known_breaks` 에 사유와 함께 등재.
   새 단절 · 쓰이지 않는 예외 둘 다 red.

## 못 막는 것 (정직 기준)

- 같은 PR 이 baseline 을 함께 낮추면 통과한다 (의도 — 명시 결정).
- 항목 수·문자 수를 유지한 채 본문을 `X` 로 채우고 공백으로 패딩하면 통과한다.
  문자 하한은 R81(아카이브 공동화)의 *짧은* 공동화만 잡는다. 등가 길이 필러는
  이 축의 밖이다.
- `→**B** 단위` / `(A→` 형식이 없는 초기 항목은 사슬 검사 대상이 아니다.

Expectations are literals in this file or the committed JSON — never imported from
the module under test (A4).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


from tests.unit.scripts._wiring_shape import surface_invokes

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_state_ledger as ledger  # noqa: E402

_STATE = _ROOT / "docs" / "STATE.md"
_BASELINE = _ROOT / "scripts" / "state_ledger_baseline.json"
# 리터럴 — 피검사 모듈에서 유도하지 않는다. 사슬 실측 (단위 2 착수, 형식 있는 항목만).
# Literals, not derived from the module. Measured on formal-pattern items only.
_KNOWN_BREAK = (6819, 6821)
_MIN_ITEMS_FLOOR = 179
# 리터럴 = 커밋된 baseline 과 동일. 43000 여유는 같은 PR 에서 min_chars 를
# 785자 내려도 이 핀이 통과하게 해, 다음 PR 의 짧은 공동화가 안 보였다.
# Literal equals the committed floor. Slack hid the next hollowing.
_MIN_CHARS_FLOOR = 44_710
_MAX_KNOWN_BREAKS = 1


def _copy_state(tmp_path: Path) -> Path:
    """실 STATE.md 를 tmp 로 복사. / Copy the real ledger into tmp."""
    dest = tmp_path / "docs"
    dest.mkdir()
    target = dest / "STATE.md"
    target.write_text(_STATE.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _section_of(text: str) -> str:
    heading = ledger.HIST_HEADING
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _bullets(section: str) -> list[str]:
    return [ln for ln in section.splitlines() if ln.startswith("- ")]


# ── 현재 리포는 통과 (대조군) ───────────────────────────────────────────


def test_current_repo_passes():
    """커밋된 STATE + baseline 은 통과해야 한다. 아니면 가드 자신이 상시 red."""
    ok, msgs = ledger.check_ledger(_STATE.read_text(encoding="utf-8"), _BASELINE)
    assert ok, msgs


def test_baseline_pins_the_known_break_literally():
    """알려진 예외는 테스트 리터럴 **집합**과 같아야 한다 — 부분집합 금지.

    `in` 만 보면 junk 예외를 추가해도 통과한다. 등재 비용은 이 핀 + 상한이다.
    Exact set, not a subset. Adding a junk exception must turn this red.
    """
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    breaks = {(int(b["prev_end"]), int(b["next_start"])) for b in data["known_breaks"]}
    assert breaks == {_KNOWN_BREAK}
    assert data["min_items"] == _MIN_ITEMS_FLOOR
    assert data["min_chars"] == _MIN_CHARS_FLOOR
    assert ledger.MAX_KNOWN_BREAKS == _MAX_KNOWN_BREAKS


# ── 항목 수 · 문자 수 하한 ─────────────────────────────────────────────


def _split_hist(text: str) -> tuple[str, str, str, str, str]:
    heading = ledger.HIST_HEADING
    current, sep, rest = text.partition(heading)
    section, mid, tail = rest.partition("\n## ")
    return current, sep, section, mid, tail


def _join_hist(current: str, sep: str, section: str, mid: str, tail: str) -> str:
    return current + sep + section + (mid + tail if mid else "")


def test_item_axis_alone_is_red(tmp_path):
    """비형식 항목 1개만 제거하고 문자·사슬은 유지 — 항목 축만 red.

    예전의 `assert "항목" in joined` 는 문자 축 메시지(`항목만 남기고`)에 기생해
    `n_items < 1` 로 항목 축을 죽여도 GREEN 이었다.
    Drop one informal bullet, pad chars, keep the chain. Only axis `items`.
    """
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    current, sep, section, mid, tail = _split_hist(orig)
    dropped = None
    kept: list[str] = []
    for ln in section.splitlines():
        if dropped is None and ln.startswith("- ") and not ledger.formal_pairs(ln):
            dropped = ln
            continue
        kept.append(ln)
    assert dropped is not None, "비형식 항목이 없다 — 격리 픽스처 전제 붕괴"
    new_section = "\n".join(kept)
    if section.endswith("\n"):
        new_section += "\n"
    pad = len(section) - len(new_section)
    assert pad > 0
    new_section = new_section + (" " * pad)
    assert len(new_section) == len(section)
    mutated = _join_hist(current, sep, new_section, mid, tail)
    assert mutated != orig
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok
    axes = {v.axis for v in verdict.violations}
    assert axes == {"items"}, verdict.violations
    assert any(v.kind == "below_floor" for v in verdict.violations)


def test_char_axis_alone_is_red(tmp_path):
    """머리말 산문만 줄인다 — 항목 수·사슬은 유지. 문자 축만 red."""
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    current, sep, section, mid, tail = _split_hist(orig)
    lines = section.splitlines()
    cut = False
    for i, ln in enumerate(lines):
        if not ln.startswith("- ") and len(ln) > 80:
            lines[i] = ln[: len(ln) - 40]
            cut = True
            break
    assert cut, "자를 산문 줄이 없다 — 격리 픽스처 전제 붕괴"
    new_section = "\n".join(lines)
    if section.endswith("\n"):
        new_section += "\n"
    assert len(new_section) < len(section)
    assert _bullets(new_section) == _bullets(section)
    mutated = _join_hist(current, sep, new_section, mid, tail)
    assert mutated != orig
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok
    axes = {v.axis for v in verdict.violations}
    assert axes == {"chars"}, verdict.violations
    assert any(v.kind == "below_floor" for v in verdict.violations)


def test_chain_axis_alone_is_red(tmp_path):
    """같은 길이로 꼬리 A 만 바꾼다 — 항목·문자 유지. 새 단절만 red.

    `assert "단절" in joined` 는 stale 예외 문구의 `단절` 에 기생해
    `observed_breaks → []` 여도 GREEN 이었다.
    Same-length A edit. Only `new_break` on the chain axis.
    """
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    mutated = orig.replace("(7230→**7250** 단위", "(7231→**7250** 단위", 1)
    assert mutated != orig
    assert len(mutated) == len(orig)
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok
    axes = {v.axis for v in verdict.violations}
    assert axes == {"chain"}, verdict.violations
    assert any(
        v.kind == "new_break" and v.data == (7230, 7231)
        for v in verdict.violations
    ), verdict.violations


def test_shrinking_ledger_to_one_item_is_red(tmp_path):
    """원장을 173→1 로 줄이면 red. 다중 축이 같이 깨져도 items 축은 있어야 한다."""
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    current, sep, section, mid, tail = _split_hist(orig)
    bullets = _bullets(section)
    assert len(bullets) >= _MIN_ITEMS_FLOOR, "실원장 항목 수가 하한보다 작다 — 전제 붕괴"
    kept = bullets[-1]
    prefix = "\n".join(ln for ln in section.splitlines() if not ln.startswith("- "))
    new_section = prefix + "\n" + kept + "\n"
    mutated = current + sep + new_section + (mid + tail if mid else "")
    assert mutated != orig
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok
    assert any(v.axis == "items" and v.kind == "below_floor" for v in verdict.violations), (
        verdict.violations
    )


def test_hollowing_item_bodies_to_x_is_red(tmp_path):
    """항목 본문을 `X` 한 글자로 바꾸면 문자 축이 red 여야 한다."""
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    current, sep, section, mid, tail = _split_hist(orig)
    bullets = _bullets(section)
    hollow = "\n".join("- X" for _ in bullets)
    prefix = "\n".join(ln for ln in section.splitlines() if not ln.startswith("- "))
    mutated = current + sep + prefix + "\n" + hollow + "\n" + (mid + tail if mid else "")
    assert mutated != orig
    assert len(mutated) < len(orig)
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok
    assert any(v.axis == "chars" and v.kind == "below_floor" for v in verdict.violations), (
        verdict.violations
    )


def test_lowering_baseline_in_the_same_tree_is_green(tmp_path):
    """baseline 을 함께 낮추면 통과 — 감축 금지가 아님을 고정하는 대조군."""
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    heading = ledger.HIST_HEADING
    current, sep, rest = orig.partition(heading)
    section, mid, tail = rest.partition("\n## ")
    bullets = _bullets(section)
    kept = bullets[-1]
    prefix = "\n".join(ln for ln in section.splitlines() if not ln.startswith("- "))
    new_section = prefix + "\n" + kept + "\n"
    path.write_text(current + sep + new_section + (mid + tail if mid else ""), encoding="utf-8")

    baseline = tmp_path / "baseline.json"
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    data["min_items"] = 1
    data["min_chars"] = 1
    # 항목이 1개면 사슬 단절이 관측되지 않으므로 예외도 비운다.
    data["known_breaks"] = []
    baseline.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok, msgs = ledger.check_ledger(path.read_text(encoding="utf-8"), baseline)
    assert ok, msgs


# ── 수치 사슬 ──────────────────────────────────────────────────────────


def test_new_chain_break_is_red(tmp_path):
    """알려진 예외가 아닌 새 단절은 red — kind/data 로 단언 (문구 `단절` 금지)."""
    path = _copy_state(tmp_path)
    orig = path.read_text(encoding="utf-8")
    mutated = orig.replace("(7230→**7250** 단위", "(9999→**7250** 단위", 1)
    assert mutated != orig
    path.write_text(mutated, encoding="utf-8")

    verdict = ledger.evaluate_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not verdict.ok, "새 사슬 단절이 통과했다"
    assert any(
        v.axis == "chain" and v.kind == "new_break" and v.data == (7230, 9999)
        for v in verdict.violations
    ), verdict.violations


def test_known_break_6819_to_6821_is_not_reported(tmp_path):
    """기존 단절 6819→6821 은 예외로 등재돼 있어 그것만으로는 red 가 아니다."""
    text = _STATE.read_text(encoding="utf-8")
    pairs = ledger.parse_chain(_bullets(_section_of(text)))
    # 리터럴 단절이 실제로 파일에 있어야 예외 등재가 공허하지 않다.
    ends_starts = [(p[1], nxt[0]) for p, nxt in zip(pairs, pairs[1:]) if p[1] != nxt[0]]
    assert _KNOWN_BREAK in ends_starts, (
        f"파일에 6819→6821 단절이 없다 — 예외가 stale 이거나 파서가 다르다: {ends_starts}"
    )
    ok, msgs = ledger.check_ledger(text, _BASELINE)
    assert ok, msgs


def test_stale_known_break_is_red(tmp_path):
    """등재된 예외가 더 이상 단절이 아니면 red — 개수는 상한 안, 값만 위조."""
    baseline = tmp_path / "baseline.json"
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    data["known_breaks"] = [{
        "prev_end": 1,
        "next_start": 2,
        "reason": "존재하지 않는 단절을 예외로 심는 뮤테이션",
    }]
    baseline.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict = ledger.evaluate_ledger(_STATE.read_text(encoding="utf-8"), baseline)
    assert not verdict.ok
    assert any(
        v.axis == "chain" and v.kind == "stale_break" and v.data == (1, 2)
        for v in verdict.violations
    ), verdict.violations


def test_second_known_break_hits_the_cap(tmp_path):
    """예외를 하나 더 넣으면 상한 red — 사유 길이가 아니라 개수가 비용이다."""
    baseline = tmp_path / "baseline.json"
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    data["known_breaks"].append({
        "prev_end": 7230,
        "next_start": 9999,
        "reason": "xxxxxxxxxxxxxxxx",
    })
    baseline.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict = ledger.evaluate_ledger(_STATE.read_text(encoding="utf-8"), baseline)
    assert not verdict.ok
    assert any(v.axis == "known_breaks" and v.kind == "over_cap" for v in verdict.violations), (
        verdict.violations
    )


def test_known_break_without_reason_is_red(tmp_path):
    """예외에 사유가 없으면 red — 빈 사유는 등재가 아니다."""
    baseline = tmp_path / "baseline.json"
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    data["known_breaks"] = [{"prev_end": 6819, "next_start": 6821, "reason": ""}]
    baseline.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict = ledger.evaluate_ledger(_STATE.read_text(encoding="utf-8"), baseline)
    assert not verdict.ok
    assert any(v.axis == "known_breaks" and v.kind == "no_reason" for v in verdict.violations), (
        verdict.violations
    )


# ── fail-closed 범위 붕괴 ──────────────────────────────────────────────


def test_missing_history_section_is_red(tmp_path):
    path = _copy_state(tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.split(ledger.HIST_HEADING, 1)[0], encoding="utf-8")
    assert path.read_text(encoding="utf-8") != text
    ok, msgs = ledger.check_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not ok
    assert any("절이 없다" in m or "없다" in m for m in msgs), msgs


def test_missing_baseline_is_red(tmp_path):
    """파일 부재는 baseline/missing 축이다. 사슬 문구의 `baseline` 단어에 기생 금지.

    로더가 0/0/[] 를 돌려도 이 단언은 red 여야 한다 — 그때는 이 축이 사라진다.
    """
    missing = tmp_path / "no-such-baseline.json"
    verdict = ledger.evaluate_ledger(_STATE.read_text(encoding="utf-8"), missing)
    assert not verdict.ok
    assert any(
        v.axis == "baseline" and v.kind == "missing" for v in verdict.violations
    ), verdict.violations
    assert not any(v.axis == "chain" for v in verdict.violations), verdict.violations


def test_duplicate_history_heading_is_red(tmp_path):
    path = _copy_state(tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text + "\n" + ledger.HIST_HEADING + "\n", encoding="utf-8")
    ok, msgs = ledger.check_ledger(path.read_text(encoding="utf-8"), _BASELINE)
    assert not ok
    assert any("2개" in m or "하나" in m for m in msgs), msgs


# ── 배선 (불변식 3) ────────────────────────────────────────────────────


def test_ledger_guard_is_invoked_from_ci():
    """CI repo-integrity 가 실제 호출한다 — `echo scripts/check_state_ledger.py` 는 불통."""
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert surface_invokes(ci, "scripts/check_state_ledger.py")


def test_ledger_guard_is_invoked_from_pre_push_gate():
    """로컬 러너 목록에 있다. CI 에만 있고 러너가 모르면 로컬 초록이 거짓이다."""
    sys.path.insert(0, str(_ROOT / "scripts"))
    import pre_push_gate as gate  # noqa: E402
    listed = list(gate._INTEGRITY) + list(gate._DIFF_SCOPED)
    listed += [name for name, _ in gate._INTEGRITY_WITH_ARGS]
    # 파일명 목록이 아니라, 러너가 그 파일을 실행 대상으로 들고 있는지를 본다.
    # Not a substring of a command blob — the runner's own inventory.
    assert "check_state_ledger.py" in listed


def test_ledger_guard_is_invoked_from_precommit():
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert surface_invokes(pc, "scripts/check_state_ledger.py")


def test_thin_body_edit_workflow_also_invokes_the_ledger_guard():
    """같은 required check 이름을 쓰므로 step 집합이 갈라지면 본문 편집 경로가 세탁된다."""
    thin = (_ROOT / ".github" / "workflows" / "claim-review-on-body-edit.yml").read_text(
        encoding="utf-8"
    )
    assert surface_invokes(thin, "scripts/check_state_ledger.py")


def test_precommit_files_cover_state_and_baseline():
    """훅 files 가 STATE 또는 baseline 만 바꿔도 발화해야 한다."""
    import re
    config = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "- id: check-state-ledger" in config
    block = config.split("- id: check-state-ledger", 1)[1]
    pattern = re.search(r'^\s*files:\s*"(.+)"\s*$', block, re.MULTILINE).group(1)
    compiled = re.compile(pattern.replace("\\\\", "\\"))
    for path in ("docs/STATE.md", "scripts/state_ledger_baseline.json"):
        assert compiled.match(path), f"pre-commit files 가 {path} 를 놓친다"


# ── 파서 자가 검증 ─────────────────────────────────────────────────────


def test_parser_finds_formal_pairs_on_the_real_file():
    """파서가 0건이면 사슬 축이 공허하다. 이어 붙인 줄은 쌍마다 한 홉."""
    pairs = ledger.parse_chain(_bullets(_section_of(_STATE.read_text(encoding="utf-8"))))
    assert len(pairs) >= 50, f"형식 있는 사슬 홉이 {len(pairs)}건 — 파서 확인"


def test_formal_pairs_does_not_cross_assemble_a_decoy():
    """한 줄에 쌍이 둘이면 각 쌍의 C 는 자기 구간에만 있다 — 첫 C + 첫 B 조립 금지."""
    line = (
        "(0000→**1000** 단위 = **1171** 수집) "
        "(7230→**7250** 단위 = **7421** 수집)"
    )
    pairs = ledger.formal_pairs(line)
    assert pairs == [(0, 1000, 1171), (7230, 7250, 7421)]
    assert ledger.full_pairs(line) == [(0, 1000, 1171), (7230, 7250, 7421)]


def test_main_returns_zero_on_the_current_repo(capsys):
    """진입점 배선 — `main()` 이 evaluate_ledger 에 실제로 도달하고 한계를 인쇄한다."""
    assert ledger.main([]) == 0
    out = capsys.readouterr().out
    assert "하한" in out
    assert "필러" in out
