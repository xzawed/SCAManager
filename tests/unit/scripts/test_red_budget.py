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


def test_every_red_rule_now_has_an_enforcer():
    """🔴 **집행자 없는 🔴 은 0이어야 한다** (2026-08-13 사용자 결정 이후의 계약).

    ## 왜 하한이 아니라 0인가

    초판은 *"비율이 10~60% 사이인가"* 를 봤다 — 산식이 결정론적인지만 재는 축이었고,
    실측 23.1%(2026-08-08) → 28.0%(2026-08-13) 를 그대로 통과시켰다. 즉 **무집행 🔴 이
    221건 쌓이는 동안 이 테스트는 계속 초록**이었다.

    사용자 결정(2026-08-13): *"룰과 규칙은 최소한의 기준으로 남기고, 핵심 이외는 필요 없다."*
    그래서 집행자 없는 🔴 **221개를 전량 제거**했다(규칙문은 보존 — 🔴 마커만 뗐다).
    🔴 는 이제 *"과거 사고로 검증됐고 기계가 지킨다"* 는 뜻이며, 그렇지 않으면 붙이지 않는다.

    실측 근거: 이 세션에서 실수를 막은 것은 기계 가드 12회 · 함정 기억 7회 ·
    외부 적대 검증 4회였고 **룰 텍스트는 ≈0회**였다.

    Every 🔴 must now carry a machine enforcer; the old ratio-band test stayed green
    while 221 unenforced rules accumulated.
    """
    unenforced, total = gate.unenforced_count(_ROOT)

    assert total >= 50, f"🔴 규칙을 {total}건만 찾았다 — 파서 확인(공허 방지)"
    assert unenforced == 0, (
        f"집행자 없는 🔴 이 {unenforced}건이다 (전체 {total}). "
        "🔴 을 새로 붙이려면 같은 PR 에서 그것을 집행하는 가드를 만들 것 — "
        "집행할 수 없는 규칙이면 🔴 없이 평문으로 적고, 실패 기전이라면 "
        "`.claude/traps.md` 에 넣는다."
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
    """🔴 표면을 빠뜨리면 거기서 늘어나는 🔴 은 영원히 안 보인다. 리터럴로 못박는다.

    ## 2026-08-14 확대 — 이름이 'every rule home' 인데 새 rule home 을 안 요구했다

    회고(`wf_2b615d5e-8c5`) P0-A: `#1345` 가 `docs/process/**`·`.claude/traps.md` 를
    **지시문 층으로 신설**했는데 이 목록이 넷으로 고정돼 있어 카운터가 두 층을 한 번도
    읽지 않았다 — 그 안에 무집행 마커 **27건**. *"무집행 0건 · 100%"* 는 그 27건을
    **뺀 값**이었다. 테스트 이름은 옳았고 내용이 이름을 따라가지 못했다.

    The list is literal on purpose (deriving it would let an empty source pass), so it
    must be widened by hand whenever a new rule-authoring surface is created.
    """
    for required in (
        "CLAUDE.md",
        "AGENTS.md",
        ".claude/rules/*.md",
        ".claude/policies/*.md",
        ".claude/traps.md",
        "docs/process/*.md",
    ):
        assert required in gate.SURFACE_GLOBS, f"표면 목록에서 빠졌다: {required}"


def test_new_layers_are_actually_counted(tmp_path):
    """🔴 목록에 있다 ≠ 계수된다 — 두 신설 층에서 실제로 블록이 잡히는지 본다.

    위 테스트는 **문자열 존재**만 본다. glob 이 0개를 반환하거나 파일이 사라지면
    단언은 통과하는데 계수는 0이다(A4 자기참조 공허화의 사촌). 실제 파일에서
    마커 블록이 나오는지 실행으로 확인한다.
    """
    names = {p.relative_to(_ROOT).as_posix() for p in gate.surfaces(_ROOT)}
    assert ".claude/traps.md" in names, "traps.md 가 표면으로 해소되지 않는다"
    assert any(n.startswith("docs/process/") for n in names), "docs/process/ 가 비었다"

    counted = sum(
        len(gate.rule_blocks((_ROOT / n).read_text(encoding="utf-8")))
        for n in names if n.startswith("docs/process/") or n == ".claude/traps.md"
    )
    assert counted >= 3, f"신설 층에서 마커 블록을 {counted}개만 찾았다 — 계수가 공허하다"


def test_marker_inside_code_is_a_mention_not_a_rule():
    """🔴 인용 배제 — 코드 스팬·펜스 안의 마커는 **설명**이지 규칙 표시가 아니다.

    이 배제가 없으면 저자가 마커 제도 자체를 문서로 설명할 수 없다
    (`*"무집행 🔴 이 늘었는가"*` 같은 문장이 무집행 규칙으로 잡힌다).
    traps B5 · 메모리 `feedback-prose-guard-both-ways` 의 *"인용 면제 필수"* 축이다.
    """
    inline = "규칙은 집행자가 지킨다(`🔴` = 집행자 동반).\n"
    fenced = "```\n# 🔴 예외 없음\n```\n"
    assert gate.rule_blocks(inline) == []
    assert gate.rule_blocks(fenced) == []
    # 대조군 — 인용이 아닌 실제 마커는 그대로 잡혀야 한다(과교정 방지).
    assert len(gate.rule_blocks("🔴 **집행자 없는 진짜 규칙**\n")) == 1


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


def test_deleting_a_surface_blocks_even_when_unenforced_dropped(tmp_path, monkeypatch, capsys):
    """🔴 이 가드의 존재 이유 — **실행 관측**으로 봉인한다 (2026-08-13 회고 P0).

    ## 사고 (실경로 재현)

    `.claude/rules/guards.md`(49 🔴) + `docs.md` 를 삭제하면 무집행 🔴 이 **221 → 171
    (Δ −50)** 이 되고, 게이트가 `✅ 무집행 🔴 이 늘지 않았다` 로 **EXIT 0** 을 냈다.
    **가드 저술 규칙을 통째로 지우는 것이 가장 값싼 '집행률 개선' 수단**이었다.

    🔴 **초판 테스트는 `"missing_surfaces" in main_body` 산문 검사였다** — 주석이나
    버려진 호출로도 통과하고, main() 을 실행하지도 exit 1 을 단언하지도 않았다.
    Grok claim-review `019ffadc` 가 *"보호 장치를 지워도 초록"* 으로 BROKEN 판정했다.
    fail-open 을 고치면서 fail-open 인 테스트를 쓴 셈이라, 실행 관측으로 교체했다.

    Executes main(): base had a surface that head lacks, and the unenforced count DROPPED.
    A delta-only verdict would print success; this must exit 1.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 남은 규칙 — 집행자 없음\n")
    # base 에는 head 에 없는 표면이 있었다 + 무집행 🔴 은 **줄었다**(50 → 현재 1)
    monkeypatch.setattr(
        f"{_MOD}.baseline_unenforced",
        lambda _s, _r: (50, {".claude/rules/guards.md", ".claude/rules/docs.md"}),
    )
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.delenv("PR_BODY", raising=False)

    assert gate.main() == 1, "표면이 사라졌는데 통과했다 — 삭제가 개선으로 채점된다"

    out = capsys.readouterr().out
    assert "사라졌다" in out, f"이유를 설명하지 않았다: {out!r}"
    assert ".claude/rules/guards.md" in out, "사라진 파일을 이름으로 지목하지 않았다"


def test_deletion_is_not_exemptible_by_the_red_budget_marker(tmp_path, monkeypatch):
    """🔴 `red-budget-exempt:` 는 **증가**를 명시화하는 마커다 — 삭제 면제로 전용 금지.

    삭제까지 그 마커로 통과시키면 *"가드를 지우고 한 줄 적으면 끝"* 이 되어 축이 무의미해진다.
    🔴 초판은 소스 슬라이싱(`body.split("missing_surfaces")[1].split("return")[0]`)이라
    `return` 줄의 `_EXEMPT` 를 못 봤다(Grok `019ffadc` #8). 실제로 마커를 넣고 돌린다.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 남은 규칙 — 집행자 없음\n")
    monkeypatch.setattr(
        f"{_MOD}.baseline_unenforced", lambda _s, _r: (50, {".claude/rules/guards.md"}))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.setenv(
        "PR_BODY", "red-budget-exempt: 이 규칙은 지금 집행할 수 없어서 지웁니다\n")

    assert gate.main() == 1, "면제 마커 한 줄로 표면 삭제가 통과했다"


def test_a_rename_is_not_a_deletion(tmp_path, monkeypatch):
    """🔴 과교정 차단 — **내용이 같은 파일이 다른 이름으로 있으면** 삭제가 아니다.

    Grok `019ffadc` C2: `git mv .claude/rules/services.md …` 같은 정상 rename 이
    면제 경로 없이 hard-block 됐다. 문서가 처방한 *"같은 PR 에서 SURFACE_GLOBS 를 고쳐라"*
    는 **fiction** 이다 — 그 상수는 glob 튜플이고 단위 테스트가 그 문자열을 pin 한다.
    그래서 내용 해시로 rename 을 식별해 통과시킨다.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    body = "🔴 남은 규칙 — 집행자 없음\n"
    (tmp_path / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "rules" / "renamed.md").write_text(body, encoding="utf-8")
    monkeypatch.setattr(
        f"{_MOD}.baseline_unenforced",
        lambda _s, _r: (1, {".claude/rules/guards.md"}),
    )
    # base 의 guards.md 내용 = head 의 renamed.md 내용 (rename 신호)
    monkeypatch.setattr(f"{_MOD}.base_blob", lambda _sha, _name, _root: body)
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.delenv("PR_BODY", raising=False)

    assert gate.main() == 0, "정상 rename 을 삭제로 오판했다 — 가드가 곧 꺼진다"


def test_a_deletion_is_not_disguised_as_a_rename(tmp_path, monkeypatch):
    """🔴 rename 예외의 대조군 — 내용이 어디에도 없으면 그냥 삭제다."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 전혀 다른 내용\n")
    monkeypatch.setattr(
        f"{_MOD}.baseline_unenforced", lambda _s, _r: (50, {".claude/rules/guards.md"}))
    monkeypatch.setattr(
        f"{_MOD}.base_blob", lambda _sha, _name, _root: "🔴 삭제된 원본 내용\n")
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.delenv("PR_BODY", raising=False)

    assert gate.main() == 1, "rename 예외가 삭제까지 통과시킨다"


# ── ⑥ 마커 위장 · 로컬 배너 정직성 (2026-08-13 Grok claim-review `019ffb93`) ──
#
# 적대 검토가 CLAIM 1("무집행 🔴 은 0이고 기계가 강제한다")을 **BROKEN** 으로 판정했다.
# 실경로 뮤테이션 2건이 초록으로 살아남았다:
#   (e) `.claude/rules/` 에 **🛑** 로 표시한 집행자 없는 필수 규칙 → 25 passed
#   (d) 🔴 표면 파일 하나를 통째로 삭제 → 25 passed · 스크립트 EXIT 0 · `100.0%` 배너
# 아래 4 테스트가 그 두 축을 고정한다. (b) 프록시 축은 **닫지 않는다** — 아래 마지막 참조.


def test_lookalike_red_markers_are_counted_too(tmp_path):
    """🔴 **빨강 계열 위장 마커도 필수 규칙으로 센다** — 반례 하나가 아니라 클래스를 닫는다.

    Grok 반례 (e): 카운터가 `"🔴" in line` 이던 시절, 독자에게는 빨간 필수 마커로
    보이는 **🛑** 줄이 카운터에는 존재하지 않았다. *"무집행 🔴 = 0"* 이 참인 채로
    집행자 없는 필수 규칙을 무한히 쌓을 수 있었다(A5 = 거짓 집행자).

    AGENTS.md §불변식 2-b 에 따라 받은 인스턴스(🛑)만 막지 않고 **클래스 전체**를
    리터럴 집합으로 못박는다. 집합은 여기서 리터럴로 재확인한다 — 피검사 모듈에서
    유도하면 원천을 비워도 초록이다(A4).
    """
    for marker in ("🔴", "🛑", "🟥", "⛔", "🚨", "🚫", "🔺", "‼", "🆘"):
        blocks = gate.rule_blocks(f"{marker} 집행자 없는 필수 규칙\n")
        assert len(blocks) == 1, f"{marker} 가 규칙 마커로 인식되지 않는다 — 위장 통로"
        assert not gate.has_enforcer(blocks[0], tmp_path)


def test_caution_and_bad_example_glyphs_are_not_rule_markers():
    """대조군 — ⚠/❌ 까지 세면 '한계 고지'·'나쁜 예시' 가 규칙으로 둔갑한다.

    과교정 방지축이다. 이 둘을 넣으면 기존 33 occurrence 가 무집행 규칙으로 잡혀
    저자가 **한계를 적는 것 자체에 벌점**을 받는다 — 이 리포가 지키려는 것의 정반대다.
    """
    assert gate.rule_blocks("⚠️ 이 축은 X 를 보지 못한다\n") == []
    assert gate.rule_blocks("❌ `binary in build_text` — echo 로 통과\n") == []


def test_lookalike_marker_makes_the_repo_gate_red(tmp_path, monkeypatch):
    """실행 관측 — 위장 마커로 무집행 규칙을 늘리면 `main()` 이 1을 낸다."""
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🛑 집행자 없는 필수 규칙\n")
    monkeypatch.setattr(f"{_MOD}.baseline_unenforced", lambda _s, _r: (0, set()))
    monkeypatch.setenv("PR_BASE_SHA", "deadbeef")
    monkeypatch.delenv("PR_BODY", raising=False)

    assert gate.main() == 1, "🛑 로 쓴 무집행 규칙이 증가로 잡히지 않는다"


def test_local_run_says_the_denominator_axis_was_not_measured(
        tmp_path, monkeypatch, capsys):
    """🔴 PR env 없는 실행의 EXIT 0 은 **'통과' 가 아니라 '안 쟀음'** 이라고 말해야 한다.

    Grok 반례 (d): 🔴 표면 파일을 삭제한 상태에서 env 없이 돌리면 출력이
    `100.0% · 무집행 0건` + EXIT 0 이었다 — 분모가 줄어든 것이 **개선으로 읽힌다**.
    `deleted_not_renamed` 는 `PR_BASE_SHA` 분기에만 살아서 로컬은 그 축을 한 번도
    돌리지 않는다. 로컬에서 판정을 만들 수는 없으니(base 가 없다) **배너가 봉인처럼
    읽히지 않게** 하는 것이 할 수 있는 전부다.

    통과 조건을 문자열 존재로 두면 A1(산문 통과)이 되므로, 배너가 **분모 축과
    증감 축 둘 다** 미측정으로 명시하는지를 본다.
    """
    monkeypatch.setattr(f"{_MOD}._ROOT", tmp_path)
    _surface(tmp_path, "🔴 규칙 `scripts/check_red_budget.py`\n")
    monkeypatch.delenv("PR_BASE_SHA", raising=False)

    assert gate.main() == 0
    out = capsys.readouterr().out
    assert "안 쟀다" in out, "EXIT 0 이 '통과' 로 읽힌다 — 미측정임을 말하지 않는다"
    assert "분모" in out, "분모 축(표면 삭제) 미측정 고지가 없다"
    assert "증감" in out, "증감 축 미측정 고지가 없다"


def test_the_proxy_ceiling_is_documented_not_claimed_closed():
    """이 게이트가 **닫지 못하는** 축을 문서가 인정하고 있는가.

    Grok 반례 (b): DB 규칙 옆에 `scripts/check_toc_anchors.py`(실재하지만 그 규칙과
    무관)를 적으면 `unenforced == 0` 이 유지된다 — **25 passed**. 이 축은 정적으로
    닫을 수 없다(어떤 가드가 어떤 규칙을 집행하는지는 의미 판정이다).

    그래서 봉인하지 않고 **한계를 명시**한다. 이 리포가 값을 치른 것은 못 한 것이
    아니라 한 것보다 크게 말한 것이었다(traps A5 · docs/process/claim-and-verify.md §3).
    한계 문장이 사라지면 다음 세션이 이 게이트를 봉인으로 읽는다.
    """
    doc = (_ROOT / "scripts" / "check_red_budget.py").read_text(encoding="utf-8")
    assert "이것은 프록시다" in doc
    assert "집행하는 것은 다르다" in doc


def test_claude_md_discloses_all_three_ceilings():
    """🔴 **한계 고지 3축이 `CLAUDE.md` 에서 살아 있어야 한다** — 지우면 봉인으로 읽힌다.

    ## 왜 (2026-08-14 회고 P0-A)

    2026-08-13 판 `CLAUDE.md` 는 한계를 **둘만** 밝혔다(프록시 · 표면 삭제 축 CI 전용).
    밝히지 않은 세 번째가 **계수 범위**였고, 그 침묵 위에서 «무집행 0건 · 100%» 이
    조건 없이 단언됐다. 회고 실측: 계수 안 92 vs 계수 밖 505 — 그리고 그 선언을 한
    바로 그 커밋이 계수 밖에 마커 30개를 새로 만들었다.

    한계 고지는 **본문에 있을 때만** 작동한다(읽히지 않으면 0이다). 고지가 조용히
    사라지는 것을 막는 유일한 방법은 그 생존을 기계로 고정하는 것이다 —
    이 리포가 traps A5 로 이름 붙인 *"거짓 집행자가 무집행보다 나쁘다"* 의 예방판이다.

    Three ceilings must stay disclosed in CLAUDE.md; silently dropping one turns the gate
    into a perceived seal.
    """
    body = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    # 축 1 — 프록시(가드가 그 규칙을 집행하는지는 판정하지 않는다)
    assert "프록시" in body and "무관한 가드 이름을 적어도 통과한다" in body, (
        "프록시 한계 고지가 CLAUDE.md 에서 사라졌다"
    )
    # 축 2 — 표면 삭제 축은 CI 전용(로컬 EXIT 0 은 '안 쟀음')
    assert "안 쟀음" in body, "로컬 EXIT 0 의 의미 고지가 사라졌다"
    # 축 3 — 계수 범위(2026-08-14 신설. 이것이 빠진 채 100% 를 단언한 것이 P0-A 였다)
    assert "계수 범위가 리포 전체가 아니다" in body, (
        "계수 범위 한계 고지가 사라졌다 — 이 축의 침묵이 P0-A 의 직접 원인이었다"
    )
    assert "SURFACE_GLOBS" in body, "범위 한계가 어느 상수를 가리키는지 없다"
