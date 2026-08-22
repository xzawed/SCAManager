"""repo-integrity 체커 스크립트 회귀 가드 — check_docs_sync.

현재 repo 에서 통과(pre-commit 이 현 상태를 막지 않음) + 합성 위반 적발(실제 drift 차단)을
양방향 고정한다. WF-2(docs 수치 정합) 자동화의 회귀 가드.
"""
import ast
import re
import sys
from pathlib import Path

# 스크립트 임포트 경로 설정 / Script import path setup (기존 test_extract_design_tokens 패턴)
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_docs_sync  # noqa: E402


# --- check_docs_sync (WF-2) ---

def test_docs_sync_passes_on_current_repo():
    ok, msgs = check_docs_sync.check_consistency(_ROOT)
    assert ok, msgs


def test_docs_sync_flags_count_mismatch(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STATE.md").write_text(
        "**종합 수치**: 전체 **5196** 수집 (단위 **5042** + 통합 154)\n"
        "| 전체 테스트 | **5196 수집** *(...)* | 단위 5042 + 통합 154 (현재). 이력 → 아래 절\n"
        # 이력 절은 이제 **필수**다(fail-closed) — 없으면 그 자체로 red 라 픽스처도 갖춘다.
        # The history section is now mandatory (fail-closed), so the fixture carries one.
        "\n## 테스트 수 추적 이력\n\n"
        "- **시드 항목** (5000→**5042** 단위 — 통합 154 = **5196** 수집).\n",
        encoding="utf-8",
    )
    # README 배지가 STATE 와 다른 수치(5195/5041) → 불일치 적발
    badge = "Tests-5195%2B_total_(5041_unit_%2B_154_integration)"
    (tmp_path / "README.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    (tmp_path / "README.ko.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    ok, msgs = check_docs_sync.check_consistency(tmp_path)
    assert not ok
    assert any("불일치" in m for m in msgs)


# --- 추적 이력 **꼬리** 축 (2026-08-05 — 구 가드가 원리적으로 못 보던 축) ---
#
# 🔴 왜 필요한가: 이력은 append-only 라 최신값이 꼬리에 있는데 가드는 `_first()` 로 머리만
# 읽었다. 그래서 "꼬리만 갱신하고 머리를 빠뜨림"(실제 발생)도, 그 반대도 탐지 대상이 아니었다.
# 아래 뮤테이션은 **실 리포 파일**을 복사해 마지막 이력 항목만 깨뜨린다(가드 3-불변식 ②).

def _count_fixture(tmp_path: Path) -> Path:
    """수치 검사가 읽는 3개 파일을 실 리포에서 그대로 복사."""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATE.md").write_text(
        (_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8"), encoding="utf-8")
    for rel in ("README.md", "README.ko.md"):
        (tmp_path / rel).write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_docs_sync_flags_stale_history_tail(tmp_path):
    """이력 **마지막** 항목만 어긋나도 red — 머리 4곳은 전부 정상인 상태에서.

    구 가드(`_first` 단독)는 이 상태를 초록으로 통과시켰다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    # 이력 절 마지막 줄의 누계만 깨뜨린다 (표 머리·README 배지는 손대지 않는다)
    last = re.findall(r"=\s*\*\*(\d+)\*\* 수집", text)
    assert last, "이력 꼬리 패턴 미발견 — 형식이 바뀌었으면 가드도 함께 갱신할 것"
    tail = f"= **{last[-1]}** 수집"
    idx = text.rindex(tail)
    state.write_text(text[:idx] + "= **99999** 수집" + text[idx + len(tail):], encoding="utf-8")

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "이력 꼬리가 어긋났는데 통과했다 — 꼬리 축이 관측되지 않는다"
    assert any("이력 마지막" in m for m in msgs), msgs


def test_apply_fix_derives_every_sink_from_the_history_tail(tmp_path):
    """파생 5지점을 전부 훼손해도 `--fix` 가 **이력 꼬리 하나**로부터 복원한다.

    🔴 이것이 P0-3 의 계약이다 — 손으로 유지하는 지점을 5 → 1 로 줄인다.
    복원 결과가 **원본과 바이트 동일**해야 한다: 아니면 파생이 결정적이지 않다는 뜻이고,
    그러면 `--fix` 를 돌릴 때마다 값이 흔들려 가드가 무의미해진다.
    """
    root = _count_fixture(tmp_path)
    before = {n: (root / n).read_text(encoding="utf-8")
              for n in ("docs/STATE.md", "README.md", "README.ko.md")}

    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    text = re.sub(r"전체 \*\*\d+\*\* 수집 \(단위 \*\*\d+\*\*", "전체 **1111** 수집 (단위 **2222**", text, count=1)
    text = re.sub(r"\| 전체 테스트 \| \*\*\d+ 수집\*\*", "| 전체 테스트 | **3333 수집**", text, count=1)
    text = re.sub(r"단위 \d+ \+ (통합 \d+ \(현재\))", r"단위 4444 + \1", text, count=1)
    state.write_text(text, encoding="utf-8")
    for name in ("README.md", "README.ko.md"):
        path = root / name
        path.write_text(
            re.sub(r"Tests-\d+%2B_total_\(\d+_unit", "Tests-5555%2B_total_(6666_unit",
                   path.read_text(encoding="utf-8"), count=1),
            encoding="utf-8")

    assert not check_docs_sync.check_consistency(root)[0], "훼손이 red 가 아니면 이 테스트는 무의미"

    ok, msgs = check_docs_sync.apply_fix(root)
    assert ok, msgs
    for name, original in before.items():
        assert (root / name).read_text(encoding="utf-8") == original, (
            f"{name} 이 원본과 다르다 — 파생이 결정적이지 않다")
    assert check_docs_sync.check_consistency(root)[0]


def test_apply_fix_refuses_when_the_ssot_itself_is_malformed(tmp_path):
    """SSOT(이력 꼬리)가 형식을 안 갖추면 **고치지 않고 거부**한다.

    형식 없는 꼬리에서 값을 추측해 파생을 쓰면, 틀린 값을 5곳에 **자동으로 퍼뜨리게** 된다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    state.write_text(state.read_text(encoding="utf-8").rstrip("\n") + "\n- 수치 없는 항목\n",
                     encoding="utf-8")
    before = state.read_text(encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    assert not ok
    assert any("형식" in m for m in msgs), msgs
    assert state.read_text(encoding="utf-8") == before, "거부했는데 파일을 건드렸다"


def test_docs_sync_fails_when_history_section_is_deleted(tmp_path):
    """이력 절을 **통째로 지우면** red — 초판은 `None → 대조 제외` 라 초록이었다.

    🔴 *보호 장치를 삭제해도 여전히 참으로 보이는 것* 의 정확한 사례였고,
    Grok claim-review 가 실측으로 적발했다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    assert check_docs_sync._STATE_HIST_HEADING in text
    state.write_text(text.split(check_docs_sync._STATE_HIST_HEADING)[0], encoding="utf-8")

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "이력 절이 사라졌는데 통과했다 — 가드를 지우면 초록이 되는 fail-open"
    assert any("절이 없다" in m for m in msgs), msgs


def test_docs_sync_fails_when_tail_entry_has_no_numbers(tmp_path):
    """수치 없는 항목을 꼬리에 덧붙이면 red — 초판은 직전 값이 계속 last 라 초록이었다.

    형식 계약이 곧 append 계약이다: 새 항목은 누계와 단위를 모두 적어야 한다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    state.write_text(orig.rstrip("\n") + "\n- 세션N 임시 메모(수치 없음)\n", encoding="utf-8")
    assert state.read_text(encoding="utf-8") != orig  # 뮤테이션 유효성 (불변식 2)

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "수치 없는 꼬리 항목이 통과했다 — 꼬리 축이 형식을 강제하지 않는다"
    assert any("형식을 갖추지 않았다" in m for m in msgs), msgs


def test_docs_sync_history_tail_is_not_the_head(tmp_path):
    """꼬리 검사가 머리를 다시 읽는 것이 아님을 증명 — 머리만 깨면 꼬리는 정상으로 보고된다.

    두 축이 같은 값을 두 번 읽는 것이라면 이 가드는 축이 하나뿐인 것과 같다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    _mutate(state, "| 전체 테스트 | **", "| 전체 테스트 | **9")  # 머리만 훼손

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok
    joined = " ".join(msgs)
    assert "STATE 추적셀(전체)=9" in joined, joined     # 머리는 훼손값
    assert "STATE 이력 마지막(전체)=9" not in joined, joined  # 꼬리는 원값 — 독립 축


# --- P0-1: `_STATE_CELL_TOTAL` 전역 첫-매치가 원장을 덮어쓴다 ---
#
# 실측 재현 (사본, 원본 무수정): §현재 수치 line 27 `**7421 수집**` 을 `**7421**` 로
# 바꾸면 apply_fix 가 line 253 원장 항목 `**5365 수집**` 을 `**7421 수집**` 으로 덮고
# ok=True + 재검증 True. 원장은 append-only 라 그 쓰기는 기록을 거짓으로 만든다.


def test_apply_fix_does_not_rewrite_ledger_when_current_cell_pattern_vanishes(tmp_path):
    """현재 영역의 `**N 수집**` 이 사라지면 apply_fix 는 원장에 쓰지 않고 거부한다.

    구 코드는 파일 전역 첫-매치라 원장 `**5365 수집**` 을 덮고 ok=True 였다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    heading = check_docs_sync._STATE_HIST_HEADING
    assert orig.count(heading) == 1
    current, _, hist = orig.partition(heading)
    cell = check_docs_sync._STATE_CELL_TOTAL.search(current)
    assert cell is not None, "현재 영역에 **N 수집** 이 없다 — 픽스처 전제 붕괴"
    # `**7421 수집**` → `**7421**` (패턴 소실). 숫자만 남기면 전역 첫-매치가 원장으로 미끄러진다.
    # Drop the 수집 token so the global first-match slides into the ledger.
    mutated = current[: cell.start()] + f"**{cell.group(1)}**" + current[cell.end() :]
    mutated = mutated + heading + hist
    assert mutated != orig
    state.write_text(mutated, encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    after = state.read_text(encoding="utf-8")
    _, _, after_hist = after.partition(heading)
    assert after_hist == hist, (
        "apply_fix 가 원장 절을 바꿨다 — 전역 첫-매치가 이력 항목을 덮어썼다. "
        f"msgs={msgs}"
    )
    assert not ok, (
        "현재 영역 패턴 소실인데 apply_fix 가 ok=True — 원장으로 미끄러진 채 재검증이 초록이다"
    )
    joined = " ".join(msgs)
    assert any(tok in joined for tok in ("못 찾", "미발견", "범위 붕괴", "영역")), msgs


def test_check_consistency_does_not_read_ledger_as_the_current_cell(tmp_path):
    """현재 영역에서 패턴이 없으면 '원장 첫 매치와 헤더 불일치'가 아니라 범위 붕괴로 red.

    전역 첫-매치는 원장 `**5365 수집**` 을 추적셀로 읽어 불일치 메시지를 낸다.
    그건 원장을 검사 대상으로 삼는 것이라 fail-closed 가 아니다 — 영역을 못 찾은 것이다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    heading = check_docs_sync._STATE_HIST_HEADING
    current, _, hist = orig.partition(heading)
    cell = check_docs_sync._STATE_CELL_TOTAL.search(current)
    assert cell is not None
    mutated = current[: cell.start()] + f"**{cell.group(1)}**" + current[cell.end() :]
    state.write_text(mutated + heading + hist, encoding="utf-8")
    assert state.read_text(encoding="utf-8") != orig

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok
    joined = " ".join(msgs)
    # 원장 값(5365)을 추적셀로 인용하면 전역 첫-매치가 아직 살아있는 것이다.
    # Citing the ledger value as the tracking cell means the global first-match is still live.
    assert "5365" not in joined, (
        f"추적셀 판정이 원장 항목으로 미끄러졌다: {msgs}"
    )
    assert any(tok in joined for tok in ("미발견", "못 찾", "범위 붕괴")), msgs


def test_apply_fix_refuses_decoy_full_pair_on_the_last_bullet(tmp_path):
    """마지막 불릿 앞에 산술 유효 decoy 쌍을 붙이면 apply_fix 는 쓰지 않는다.

    구 `_first(TOTAL)`/`_first(UNIT)` 는 total=1171 unit=1000 을 SSOT 로 읽어
    §현재 수치와 README 2곳에 퍼뜨렸다 (claim-review 01a00434).
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    heading = check_docs_sync._STATE_HIST_HEADING
    current, sep, hist = orig.partition(heading)
    lines = hist.splitlines(keepends=True)
    last_i = max(i for i, ln in enumerate(lines) if ln.startswith("- "))
    decoy = "(0000→**1000** 단위 = **1171** 수집) "
    lines[last_i] = lines[last_i][:2] + decoy + lines[last_i][2:]
    mutated = current + sep + "".join(lines)
    assert mutated != orig
    state.write_text(mutated, encoding="utf-8")
    before_readme = (root / "README.md").read_text(encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    after = state.read_text(encoding="utf-8")
    after_cur = after.split(heading, 1)[0]
    cell = check_docs_sync._STATE_CELL_TOTAL.search(after_cur)
    assert not ok, msgs
    assert cell is not None and cell.group(1) != "1171", cell.group(0) if cell else None
    assert (root / "README.md").read_text(encoding="utf-8") == before_readme
    assert any("모호" in m or "형식 쌍" in m for m in msgs), msgs


def test_apply_fix_refuses_readme_badge_decoy(tmp_path):
    """README 선두 decoy 배지에 apply_fix 가 쓰지 않는다. 파일은 그대로."""
    root = _count_fixture(tmp_path)
    readme = root / "README.md"
    decoy = "Tests-1111%2B_total_(2222_unit_%2B_0_integration)"
    orig = readme.read_text(encoding="utf-8")
    readme.write_text(decoy + "\n" + orig, encoding="utf-8")
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    state.write_text(
        re.sub(
            r"\| 전체 테스트 \| \*\*\d+ 수집\*\*",
            "| 전체 테스트 | **3333 수집**",
            text,
            count=1,
        ),
        encoding="utf-8",
    )
    before_readme = readme.read_text(encoding="utf-8")
    before_state = state.read_text(encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    assert not ok, msgs
    assert readme.read_text(encoding="utf-8") == before_readme
    assert state.read_text(encoding="utf-8") == before_state
    assert before_readme.startswith(decoy)
    assert any("배지 매치" in m or "1개" in m for m in msgs), msgs


def test_check_consistency_flags_duplicate_readme_badge(tmp_path):
    """배지가 2개면 불일치 숫자가 아니라 개수 붕괴로 red."""
    root = _count_fixture(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        "Tests-1111%2B_total_(2222_unit_%2B_0_integration)\n"
        + readme.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok
    joined = " ".join(msgs)
    assert "1111" not in joined, f"decoy 수치를 배지로 읽었다: {msgs}"
    assert any("매치" in m and "2" in m for m in msgs), msgs


def test_apply_fix_happy_path_leaves_history_bytes_unchanged(tmp_path):
    """정상 `--fix` 도 원장 절 바이트를 건드리지 않는다 (파생은 현재 영역만)."""
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    heading = check_docs_sync._STATE_HIST_HEADING
    orig_hist = orig.split(heading, 1)[1]
    # 현재 영역 숫자만 훼손 — 기존 파생 테스트와 같은 축, 원장 불변만 추가로 단언.
    text = re.sub(
        r"\| 전체 테스트 \| \*\*\d+ 수집\*\*",
        "| 전체 테스트 | **3333 수집**",
        orig,
        count=1,
    )
    assert text != orig
    state.write_text(text, encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    assert ok, msgs
    after_hist = state.read_text(encoding="utf-8").split(heading, 1)[1]
    assert after_hist == orig_hist


def _apply_fix_ast() -> ast.FunctionDef:
    src = (_ROOT / "scripts" / "check_docs_sync.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "apply_fix":
            return node
    raise AssertionError("apply_fix 가 없다")


def _history_tail_ast() -> ast.FunctionDef:
    src = (_ROOT / "scripts" / "check_docs_sync.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_history_tail":
            return node
    raise AssertionError("_history_tail 이 없다")


def test_apply_fix_cell_total_sub_targets_new_current_only():
    """M1a — `_STATE_CELL_TOTAL.sub` 의 대상은 `new_current` 뿐.

    sub 만 전역 `new_state` 로 되돌려도 조기 검사가 막아서 행동 테스트는
    4 passed 였다. 호출 대상을 AST 로 고정한다.
    """
    fn = _apply_fix_ast()
    targets: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "sub"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "_STATE_CELL_TOTAL"):
            continue
        assert len(node.args) >= 2, ast.dump(node)
        target = node.args[1]
        assert isinstance(target, ast.Name), ast.dump(target)
        targets.append(target.id)
    assert targets, "_STATE_CELL_TOTAL.sub 호출이 없다"
    assert all(name == "new_current" for name in targets), targets


def test_apply_fix_hist_bytes_assertion_is_live():
    """M3 — `orig_hist != new_hist` 가 살아 있는 if 조건이어야 한다.

    `if False and orig_hist != new_hist` 는 행동 테스트 4 passed 였다.
    """
    fn = _apply_fix_ast()
    live = False
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.BoolOp)
            and isinstance(test.op, ast.And)
            and any(isinstance(v, ast.Constant) and v.value is False for v in test.values)
        ):
            continue
        names: set[str] = set()
        for child in ast.walk(test):
            if isinstance(child, ast.Name):
                names.add(child.id)
        if {"orig_hist", "new_hist"} <= names:
            live = True
    assert live, "orig_hist != new_hist 가 살아 있는 if 조건이 아니다"


def test_formal_pairs_does_not_cross_assemble_a_decoy():
    """한 줄에 쌍이 둘이면 각 쌍의 C 는 자기 구간에만 있다 — 첫 C + 첫 B 조립 금지."""
    line = (
        "(0000→**1000** 단위 = **1171** 수집) "
        "(7230→**7250** 단위 = **7421** 수집)"
    )
    pairs = check_docs_sync.formal_pairs(line)
    assert pairs == [(0, 1000, 1171), (7230, 7250, 7421)]
    assert check_docs_sync.full_pairs(line) == [(0, 1000, 1171), (7230, 7250, 7421)]


def test_history_tail_uses_full_pairs_not_independent_first():
    """읽기 규약 통일 — `_history_tail` 은 `full_pairs` 를 호출하고
    누계·단위를 **따로** 첫-매치하지 않는다.

    ## 2026-08-17 강화 — 이름 열거를 버리고 **형태**로 잰다

    초판은 `_first(_STATE_HIST_TOTAL)` / `_first(_STATE_HIST_UNIT)` 이라는 **특정 이름**만
    금지했다. 그런데 그 두 상수는 아무도 쓰지 않는 채 남아 CodeQL
    `py/unused-global-variable`(alert 581·582)로 잡혔고, 삭제하는 순간 이 단언은
    **영원히 참**이 된다 — 이름이 없으니 AST 에서 찾힐 리가 없다(A4 자기참조 공허화).

    그래서 두 축으로 바꾼다:
      ① `_history_tail` 이 `_first(<모듈 전역 정규식>)` 을 **어떤 이름으로도** 부르지 않는다
         — 새 상수를 다른 이름으로 만들어 되살려도 잡힌다.
      ② 문제의 두 이름이 모듈에 **다시 생기지 않았다** — 되살리면 그 사고의 도구가 돌아온다.

    ## 왜 이 규약인가 (원 사고)

    누계와 단위를 따로 첫-매치하면 한 불릿 안의 decoy 쌍이 틀린 (C, B) 를 조립한다.
    실측: 1171 이 파생 3지점에 퍼졌다.
    Shape-based, not name-based: deleting the constants would make a name-based assertion
    vacuously true forever.
    """
    fn = _history_tail_ast()
    called_full = False
    independent_first: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "full_pairs":
            called_full = True
        if isinstance(func, ast.Name) and func.id == "_first" and node.args:
            arg0 = node.args[0]
            # 🔴 이름을 열거하지 않는다 — `_first(<Name>)` 형태 자체가 금지다.
            # Any Name argument is the forbidden shape, whatever it is called.
            if isinstance(arg0, ast.Name):
                independent_first.append(arg0.id)

    assert called_full, "_history_tail 이 full_pairs 를 호출하지 않는다"
    assert not independent_first, (
        f"_history_tail 이 전역 정규식을 독립 _first 한다: {independent_first} — "
        "누계·단위를 따로 읽으면 decoy 쌍이 틀린 (C, B) 를 조립한다"
    )

    for gone in ("_STATE_HIST_TOTAL", "_STATE_HIST_UNIT"):
        assert not hasattr(check_docs_sync, gone), (
            f"{gone} 이 되살아났다 — 2026-08-17 에 CodeQL 지적(py/unused-global-variable)으로 "
            "지운 것이고, 되살리면 독립 첫-매치 사고의 도구가 돌아온다. "
            "읽기는 full_pairs() 하나로 통일한다"
        )


# --- check_docs_sync 의존성 핀 축 (backlog R15 — ground truth 대조) ---
#
# 아래 뮤테이션은 합성 문자열이 아니라 **실 리포 파일 내용**을 복사해 깨뜨린다(가드 3-불변식 ②).
# 기대값은 테스트에 하드코딩하지 않고 현재 핀에서 유도한다 — bump 마다 테스트가 같이 썩지 않도록.
# Mutations copy the real repo files and break them; expectations derive from the current pin.

def _pin_fixture(tmp_path: Path) -> Path:
    """핀 검사가 읽는 4개 파일을 실 리포에서 그대로 복사. / Copy the 4 real files the check reads."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    for rel in ("requirements.txt", "README.md", "README.ko.md"):
        (tmp_path / rel).write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _mutate(path: Path, old: str, new: str) -> None:
    """실파일 치환 + 실제로 바뀌었는지 단언 (no-op 뮤테이션은 아무것도 증명하지 않는다)."""
    orig = path.read_text(encoding="utf-8")
    mutated = orig.replace(old, new)
    assert mutated != orig, f"뮤테이션 무효 — {path.name} 에 {old!r} 없음"
    path.write_text(mutated, encoding="utf-8")


def test_dependency_pins_pass_on_current_repo():
    ok, msgs = check_docs_sync.check_dependency_pins(_ROOT)
    assert ok, msgs


def test_dependency_pins_flag_badge_drift(tmp_path):
    """README 배지만 구버전으로 남으면 red — R15 가 두 번 재발한 바로 그 형태."""
    root = _pin_fixture(tmp_path)
    badge = re.search(r"FastAPI-(\d+\.\d+)-", (root / "README.md").read_text(encoding="utf-8"))
    _mutate(root / "README.md", f"FastAPI-{badge.group(1)}-", "FastAPI-0.1-")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("README.md FastAPI 배지" in m for m in msgs)


def test_dependency_pins_flag_missing_ground_truth(tmp_path):
    """기준이 되는 requirements 핀 자체가 사라지면 red — 기대값 소실을 통과로 읽지 않는다."""
    root = _pin_fixture(tmp_path)
    pin = re.search(r"^fastapi==(\S+)$", (root / "requirements.txt").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)
    _mutate(root / "requirements.txt", f"fastapi=={pin}", "fastapi")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("핀 미발견" in m for m in msgs)


def test_dependency_pins_flag_korean_readme_badge_drift(tmp_path):
    """README.ko.md 도 검사 대상 — 한쪽만 고치고 넘어가는 실수를 막는다."""
    root = _pin_fixture(tmp_path)
    badge = re.search(r"FastAPI-(\d+\.\d+)-", (root / "README.ko.md").read_text(encoding="utf-8"))
    _mutate(root / "README.ko.md", f"FastAPI-{badge.group(1)}-", "FastAPI-0.1-")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("README.ko.md FastAPI 배지" in m for m in msgs)


def test_docs_sync_main_fails_when_only_pin_axis_fails(monkeypatch, capsys):
    """🔴 집계 배선 — 수치 축이 통과해도 핀 축이 실패하면 exit 1 이어야 한다.

    Grok claim-review `019fccd5` 가 지적한 구멍: 신규 테스트가 전부
    `check_dependency_pins` 를 **직접** 호출해서, `main()` 이 `return 0 if ok else 1` 로
    퇴화해 핀 축 실패를 삼켜도 전건 green 이었다(live probe 로 실증). 이 테스트가 그 축이다.
    """
    monkeypatch.setattr(check_docs_sync, "check_consistency", lambda _root: (True, []))
    monkeypatch.setattr(
        check_docs_sync, "check_dependency_pins", lambda _root: (False, ["❌ 핀 축 실패"])
    )
    assert check_docs_sync.main() == 1
    assert "핀 축 실패" in capsys.readouterr().out


def test_precommit_hook_watches_every_file_the_check_reads():
    """🔴 배선 — pre-commit `files` 패턴이 스크립트가 읽는 파일 전건을 덮는가.

    좁은 패턴은 훅을 **조용히 안 돌게** 한다(핀만 바꾼 커밋에서 미발화). 산문 대조가 아니라
    실제 `files` 정규식을 뽑아 각 입력 경로에 매칭시킨다.
    """
    config = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = config.split("- id: check-docs-sync", 1)[1]
    pattern = re.search(r'^\s*files:\s*"(.+)"\s*$', block, re.MULTILINE).group(1)
    compiled = re.compile(pattern.replace("\\\\", "\\"))
    for path in ("docs/STATE.md", "README.md", "README.ko.md",
                 "requirements.txt"):
        assert compiled.match(path), f"pre-commit files 패턴이 {path} 를 놓친다"


def test_apply_fix_accepts_a_changed_integration_count_from_the_ssot_alone(tmp_path):
    """🔴 통합 수가 바뀌어도 **이력 꼬리 한 줄만** 고치면 `--fix` 가 통과한다.

    ## 이 축이 없어서 무엇이 깨져 있었나 (실측 2026-08-22)

    `apply_fix` 는 전체·단위를 SSOT 불릿에서 읽으면서 **통합만** 자기가 곧 덮어쓸
    추적셀(`통합 N (현재)`)에서 읽었다. 그래서 통합 수가 바뀐 커밋에서는 SSOT 불릿을
    아무리 정확히 적어도 산술 검사가 **옛 통합값**과 대조돼 항상 거부됐다:

        ❌ 이력 SSOT 가 산술적으로 불가능하다 — 전체 7244 ≠ 단위 7060 + 통합 182

    즉 `apply_fix` docstring 이 약속한 *"작성자는 이력에 항목 한 줄만 적고 이걸 돌린다"*
    가 통합 축에서만 **원리적으로 불가능**했고, 통합만 손으로 먼저 고쳐야 통과했다 —
    이 스크립트가 없애려던 손 동기화가 바로 그 자리에 남아 있었다.

    기존 `test_apply_fix_derives_every_sink_from_the_history_tail` 은 통합 수를
    **바꾸지 않은 채** 파생만 훼손하므로 이 경로를 지나가지 않는다.

    The fix path read the integration count from the sink it was about to overwrite, so any
    commit that changed it could never satisfy the arithmetic check. The existing sink test
    never varies that number, so it does not cover this path.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")

    tail, errs = check_docs_sync._history_tail_bullet(text)  # pylint: disable=protected-access
    assert not errs and tail, errs

    unit = int(re.search(r"→\s*\*\*(\d+)\*\*\s*단위", tail).group(1))
    integ = int(re.search(r"통합 (\d+)", tail).group(1))
    total = int(re.search(r"=\s*\*\*(\d+)\*\*\s*수집", tail).group(1))
    assert total == unit + integ, f"픽스처 SSOT 가 이미 산술 불일치: {tail!r}"

    # 통합 테스트 2건이 늘었다고 가정 — **이력 불릿만** 고친다(파생은 손대지 않는다).
    new_integ, new_total = integ + 2, total + 2
    new_tail = (
        tail.replace(f"통합 {integ}", f"통합 {new_integ}")
        .replace(f"= **{total}** 수집", f"= **{new_total}** 수집")
    )
    assert new_tail != tail, "불릿 치환이 적용되지 않았다 — 형식이 바뀌었으면 이 테스트도 갱신할 것"
    state.write_text(text.replace(tail, new_tail, 1), encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    assert ok, (
        "통합 수만 바뀌었는데 --fix 가 거부했다 — 통합을 파생 셀에서 읽고 있다는 신호:\n"
        + "\n".join(msgs)
    )

    # 새 통합값이 **파생 지점까지** 전파돼야 한다 — 거부하지 않은 것만으로는 부족하다.
    after = state.read_text(encoding="utf-8")
    assert f"통합 {new_integ} (현재)" in after, (
        f"추적셀이 옛 통합값을 유지한다 — 전파 실패: {re.findall(r'통합 [0-9]+ [(]현재[)]', after)}"
    )
    assert f"전체 **{new_total}** 수집 (단위 **{unit}** + 통합 {new_integ})" in after, (
        "종합 수치 줄이 새 값을 담지 않았다"
    )
    for name in ("README.md", "README.ko.md"):
        badge = (root / name).read_text(encoding="utf-8")
        assert f"{new_total}%2B_total_({unit}_unit_%2B_{new_integ}_integration)" in badge, (
            f"{name} 배지가 갱신되지 않았다"
        )

    assert check_docs_sync.check_consistency(root)[0], "전파 후에도 정합 검사가 red"
