"""🔴 예산제의 계약 (P4).

## 왜 (2026-08-08 진단)

사용자 관찰 *"규칙이 반복 발화되는데 지켜지지 않는다"* 는 실측으로 옳았다.
원인은 **총량이 아니라 집행 비율**이다:

| 축 | 값 |
|---|---|
| 🔴 규칙(줄 기준) | **290** |
| 집행자 동반 | **67 (23.1%)** |
| **무집행** | **223** |

실측 준수율 **0/42**(정책 13) · **발화율 100% / 이행률 0%**(R43)인 규칙이 있다.
규칙이 도달해도 지켜지지 않으니 **규칙을 더 쓰는 것은 처방이 아니다.**

🔴 **문서를 줄이는 것도 아니다** — 두 번 시도해 두 번 다 순손실이었다
(`#1296` 축소 → Grok BROKEN: 행동 규칙 8건 소실 / R54 파생화 → 틀린 값 4지점 자동 전파).

그래서 이 게이트는 바이트를 재지 않고 **하나만** 묻는다:
*집행자 없는 🔴 이 이 PR 에서 늘었는가?*

## 고정하는 계약

| 상황 | 기대 |
|---|---|
| 무집행 🔴 증가 | **exit 1** ← 본체 |
| 집행자를 **함께** 만든 🔴 | exit 0 |
| 참조한 가드 파일이 **없음**(dangling) | 집행자로 치지 않음 |
| 면제 마커 있음 | exit 0 + job summary 계수 |
| base 산출 실패 | **exit 1** (판정 불가) |
| PR env 부재 | exit 0 (현황만 인쇄) |

## ⚠️ 프록시임을 숨기지 않는다

블록에 가드 이름이 있는 것과 그 가드가 그 규칙을 **실제로 집행**하는 것은 다르다.
이 게이트가 재는 것은 *"저자가 집행자를 함께 만들었는가"* 라는 **습관**이다.
"""
from __future__ import annotations

from pathlib import Path

import scripts.check_red_budget as gate

_ROOT = Path(__file__).resolve().parents[3]
_MOD = "scripts.check_red_budget"


def _surface(root: Path, body: str) -> Path:
    """합성 표면 — 실제 판정부가 읽는 위치에 만든다."""
    d = root / ".claude" / "rules"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "probe.md"
    f.write_text(body, encoding="utf-8")
    return f


# ── ① 산식 — 결정론적이고 재현 가능해야 한다 ────────────────────────────


def test_rule_block_is_one_red_line_plus_continuation():
    """🔴 규칙 1건 = 🔴 를 포함한 **줄 1개**. 블록은 뒤따르는 연속 줄까지."""
    text = "머리말\n🔴 규칙 A\n  이어지는 설명\n\n평범한 줄\n🔴 규칙 B\n"
    blocks = gate.rule_blocks(text)
    assert len(blocks) == 2, f"🔴 줄 2개인데 {len(blocks)}블록"
    assert "이어지는 설명" in blocks[0], "연속 줄이 블록에 안 들어왔다"
    assert "평범한 줄" not in blocks[0], "빈 줄 뒤까지 삼켰다"


def test_consecutive_red_lines_are_separate_rules():
    """연속한 🔴 줄은 각각 별개 규칙 — 하나로 뭉치면 개수가 과소가 된다."""
    assert len(gate.rule_blocks("🔴 A\n🔴 B\n🔴 C\n")) == 3


def test_enforcer_must_actually_exist(tmp_path):
    """🔴 **dangling 참조는 집행자가 아니다** — 이름만 적고 파일이 없으면 집행이 없다."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_real.py").write_text("x = 1\n", encoding="utf-8")
    assert gate.has_enforcer("🔴 규칙 — `scripts/check_real.py` 가 집행", tmp_path) is True
    assert gate.has_enforcer("🔴 규칙 — `scripts/check_ghost.py` 가 집행", tmp_path) is False


def test_prose_without_a_guard_name_is_unenforced(tmp_path):
    """대조군 — 가드 이름이 없으면 아무리 강조해도 집행자 없음."""
    assert gate.has_enforcer("🔴 **반드시** 지킬 것. 예외 없음.", tmp_path) is False


def test_current_ratio_is_reproducible():
    """🔴 산식이 이 저장소에서 **재현**돼야 한다 — 22%/29% 가 공존하던 것을 고정한다.

    판단자가 채택 조건으로 요구한 축이다. 값이 크게 흔들리면 산식이 결정론적이지 않다.
    """
    unenforced, total = gate.unenforced_count(_ROOT)
    assert total >= 200, f"🔴 규칙을 {total}건만 찾았다 — 파서 확인(공허 방지)"
    ratio = (total - unenforced) / total
    assert 0.10 <= ratio <= 0.60, (
        f"집행자 동반 비율 {ratio:.1%} — 산식이 흔들렸는지 확인할 것 "
        f"(2026-08-08 실측 23.1%: {total - unenforced}/{total})"
    )


# ── ② 증감 판정 (실행 관측) ─────────────────────────────────────────────


def test_unenforced_increase_is_blocked(tmp_path, monkeypatch, capsys):
    """🔴 이 게이트의 본체 — 집행자 없는 🔴 이 늘면 실패.

    통제 실험으로도 실증했다: 실제 리포에서 `.claude/rules/docs.md` 에 집행자 없는
    🔴 한 줄을 넣었더니 exit 1 이었고, 실재하는 가드 이름을 넣으니 exit 0 이었다.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 새 규칙 — 집행자 없음\n")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: (0, set()))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.delenv("PR_BODY", raising=False)
    assert gate.main() == 1
    err = capsys.readouterr().err
    assert "늘었다" in err, f"이유를 설명하지 않았다: {err!r}"


def test_no_increase_passes(tmp_path, monkeypatch, capsys):
    """대조군 — 늘지 않으면 통과한다(무조건 red 면 가드 자살)."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 새 규칙 — 집행자 없음\n")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: (1, set()))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    assert gate.main() == 0
    assert "늘지 않았다" in capsys.readouterr().out


def test_adding_a_rule_with_its_guard_passes(tmp_path, monkeypatch):
    """🔴 규칙을 **늘리는 것 자체는 막지 않는다** — 집행자를 함께 만들면 통과다.

    이 게이트가 "문서를 줄여라" 가 아니라 "집행과 함께 늘려라" 인 이유다.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "check_new.py").write_text("x = 1\n", encoding="utf-8")
    _surface(tmp_path, "🔴 새 규칙 — `scripts/check_new.py` 가 집행한다\n")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: (0, set()))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    assert gate.main() == 0


def test_baseline_uses_a_worktree_not_the_current_tree(monkeypatch):
    """🔴 base 는 **worktree 로 꺼내서** 세야 한다.

    `git show` 로 파일만 읽으면 '파일 실재' 판정이 **현재 트리**를 보게 되어,
    이 PR 이 추가한 가드가 base 계산에도 반영된다 → base 과대평가 → **증가를 놓친다**.
    """
    seen = []

    def fake_run(args, cwd, timeout=300):
        seen.append(args)

        class R:
            returncode = 1        # worktree 실패로 만들어 조기 종료
            stdout = stderr = ""
        return R()

    monkeypatch.setattr(f"{_MOD}._run", fake_run)
    assert gate.baseline_unenforced("abc", _ROOT) is None
    assert any("worktree" in a for a in seen[0]), f"worktree 를 쓰지 않았다: {seen}"


def test_undecidable_baseline_fails_closed(tmp_path, monkeypatch, capsys):
    """base 산출 실패는 **통과가 아니라 실패** — 조용한 0 은 초록과 구별되지 않는다."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 규칙\n")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: None)
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    assert gate.main() == 1
    assert "판정 불가" in capsys.readouterr().err


def test_no_pr_env_only_reports(tmp_path, monkeypatch, capsys):
    """PR env 가 없으면 현황만 인쇄하고 쉰다 — 로컬 게이트를 영구 red 로 만들지 않는다."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 규칙\n")
    monkeypatch.delenv("PR_BASE_SHA", raising=False)
    assert gate.main() == 0
    assert "무집행" in capsys.readouterr().out


# ── ③ 면제 마커 ─────────────────────────────────────────────────────────


def test_exemption_requires_a_substantive_reason():
    assert gate._EXEMPT.search("red-budget-exempt: 지금은 집행 가드를 만들 수 없는 규칙입니다")
    assert not gate._EXEMPT.search("red-budget-exempt: x")


def test_documenting_the_marker_does_not_self_exempt():
    """마커를 **설명하는 문장**이 면제로 오인되면 안 된다(정책 19 실사고와 같은 클래스)."""
    assert not gate._EXEMPT.search(
        "집행 불가면 `red-budget-exempt: <사유>` 를 본문에 적으세요.")


def test_exemption_is_recorded_in_the_job_summary(tmp_path, monkeypatch):
    """면제는 **사람이 보는 자리**에 누적된다 — `::notice` 는 로그 안쪽이라 안 본다."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 규칙\n")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.setenv("PR_BODY", "red-budget-exempt: 외부 계약이라 지금 집행할 수 없습니다")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: (0, set()))
    assert gate.main() == 0
    assert "예산 면제" in summary.read_text(encoding="utf-8")


# ── ④ 표면 목록·배선 ────────────────────────────────────────────────────


def test_surface_list_covers_every_rule_home():
    """🔴 표면을 빠뜨리면 거기서 늘어나는 🔴 은 영원히 안 보인다. 리터럴로 못박는다."""
    for required in ("CLAUDE.md", "AGENTS.md", ".claude/rules/*.md", ".claude/policies/*.md"):
        assert required in gate.SURFACE_GLOBS, f"표면 목록에서 빠졌다: {required}"


def test_surfaces_resolve_in_this_repo():
    """대조군 — glob 이 0개를 반환하면 위 단언이 공허해진다."""
    found = gate.surfaces(_ROOT)
    assert len(found) >= 12, f"표면을 {len(found)}개만 찾았다 — glob 확인"


def test_wired_into_ci():
    """정의 ≠ 배선 — CI 가 실제로 실행하는지."""
    from tests.unit.scripts._wiring_shape import surface_invokes

    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert surface_invokes(ci, "scripts/check_red_budget.py"), "CI 미배선 — dead code"


def test_ci_passes_base_sha_and_body():
    """🔴 env 2종이 load-bearing — 빠지면 게이트가 조용히 쉰다."""
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    blocks = [b for b in ci.split("- name:") if "check_red_budget.py" in b]
    assert blocks, "step 을 못 찾았다"
    for var in ("PR_BASE_SHA", "PR_BODY"):
        assert var in blocks[0], f"{var} 를 넘기지 않는다 — 그 축이 죽는다"


# ── 🔴 표면 삭제는 '개선' 이 아니다 (2026-08-13 회고 P0) ──────────────────


def test_surface_names_is_relative_and_stable(tmp_path):
    """`surface_names` 는 **루트 상대 경로 집합**이어야 base↔head 대조가 성립한다.

    절대 경로를 돌려주면 base worktree(임시 디렉토리)와 head(리포)가 영원히 다른
    집합이 되어, 대조가 *모든 파일이 사라졌다* 로 오작동한다.
    """
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text("x\n", encoding="utf-8")
    (tmp_path / ".claude" / "rules" / "a.md").write_text("x\n", encoding="utf-8")

    names = gate.surface_names(tmp_path)

    assert names == {"CLAUDE.md", ".claude/rules/a.md"}, names
    assert all(not n.startswith(str(tmp_path)) for n in names), "절대 경로가 샜다"


def test_missing_surfaces_reports_deletions_only(tmp_path):
    """base 에 있고 head 에 없는 것만 보고한다 — 신규 추가는 결함이 아니다."""
    base, head = tmp_path / "b", tmp_path / "h"
    for root in (base, head):
        (root / ".claude" / "rules").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("x\n", encoding="utf-8")
    (base / ".claude" / "rules" / "guards.md").write_text("x\n", encoding="utf-8")
    (base / ".claude" / "rules" / "docs.md").write_text("x\n", encoding="utf-8")
    (head / ".claude" / "rules" / "new.md").write_text("x\n", encoding="utf-8")

    missing = gate.missing_surfaces(base, head)

    assert missing == [".claude/rules/docs.md", ".claude/rules/guards.md"], missing


def test_no_deletion_reports_nothing(tmp_path):
    """🔴 과교정 대조군 — 삭제가 없으면 빈 목록이어야 한다.

    이게 없으면 '항상 red' 로 고쳐도 위 테스트가 통과해 가드가 곧 꺼진다(정책 17).
    """
    base, head = tmp_path / "b", tmp_path / "h"
    for root in (base, head):
        (root / ".claude" / "rules").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("x\n", encoding="utf-8")
        (root / ".claude" / "rules" / "guards.md").write_text("x\n", encoding="utf-8")

    assert gate.missing_surfaces(base, head) == []


def test_deletion_is_not_offset_by_a_lower_unenforced_count():
    """🔴 이 가드의 존재 이유 — 삭제로 무집행 🔴 이 **줄어도** 통과하면 안 된다.

    ## 사고 (2026-08-13 회고 P0, 실경로 재현)

    `.claude/rules/guards.md`(49 🔴) + `docs.md` 를 삭제하면 무집행 🔴 이
    **221 → 171 (Δ −50)** 이 되고, 게이트가 `✅ 무집행 🔴 이 늘지 않았다` 로 **EXIT 0** 을
    냈다. 즉 **가드 저술 규칙을 통째로 지우는 것이 이 리포에서 가장 값싼 '집행률 개선'
    수단**이었다. delta 만 보는 판정은 분모가 사라지는 경우를 원리적으로 못 본다.

    Deleting the rules that *author guards* lowered the unenforced count and the gate
    called it an improvement. A delta-only verdict cannot see the denominator vanishing.
    """
    src = (_ROOT / "scripts" / "check_red_budget.py").read_text(encoding="utf-8")

    assert "missing_surfaces" in src, "표면 삭제 축이 스크립트에 없다"
    # 🔴 정의만으로는 부족하다 — main() 이 실제로 호출하고 그 결과로 실패해야 한다.
    body = src.split("def main(")[1]
    assert "missing_surfaces" in body, "main() 이 호출하지 않는다 — 정의≠배선"


def test_deletion_axis_is_not_exemptible_by_the_red_budget_marker():
    """🔴 `red-budget-exempt:` 는 **증가**를 명시화하는 마커다 — 삭제 면제로 전용되면 안 된다.

    삭제까지 그 마커로 통과시키면 '가드를 지우고 한 줄 적으면 끝' 이 되어
    이 축이 처음부터 없는 것과 같아진다.
    """
    src = (_ROOT / "scripts" / "check_red_budget.py").read_text(encoding="utf-8")
    body = src.split("def main(")[1]
    deletion_block = body.split("missing_surfaces")[1].split("return")[0]

    assert "_EXEMPT" not in deletion_block, (
        "삭제 축이 red-budget-exempt 로 면제된다 — 마커 한 줄로 가드를 지울 수 있다"
    )
