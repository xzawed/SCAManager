"""설정값으로 «숨는» 표면이 스윕에 자리가 있는가 — 양방향 등식.

🔴 `settings.html` 은 블록을 설정값으로 숨긴다:

    <div id="mergeThresholdRow" class="{% if not config.auto_merge %}is-hidden{% endif %}">

기본값은 `auto_merge=False`·`approve_mode="disabled"`(`src/models/repo_config.py`)라
그 블록들은 **기본 상태에서 전부 `display:none`** 이다. 그 안에 range 슬라이더·숫자 입력·
임계값 라벨이 있는데 어떤 스윕도 그 글자를 본 적이 없었다(#1639 W12-b).

🔴 이 부류는 「참 팔이 새 클래스를 내놓는가」로는 **못 찾는다.** 참 팔이 내놓는 것은
   공유 클래스 `is-hidden` 이고, 봐야 할 UI 는 **거짓 팔**이다. 양쪽 팔을 다 봐야 보인다
   (Grok `01a090cd` 가 내 단방향 판정을 BROKEN 으로 반증).

## 분업

- **닫힘**은 여기다. 템플릿에서 «설정으로 숨는 블록» 을 파생해, 그 블록을 여는 설정을
  e2e 시드가 실제로 만드는지 대조한다. 새 블록이 생기면 red 다.
- **행동 판정**은 e2e 가 한다
  (`e2e/test_theme_mobile_guards.py::test_token_text_meets_aa_in_settings_gate_blocks`).
"""
import ast
import re

from ._contrast import ROOT

SETTINGS = ROOT / "src" / "templates" / "settings.html"
E2E_CONFTEST = ROOT / "e2e" / "conftest.py"
E2E_SWEEP = ROOT / "e2e" / "test_theme_mobile_guards.py"

# `class="{% if <조건> %}is-hidden{% endif %}"` — 조건이 참일 때 숨는다.
_HIDDEN_IF_RE = re.compile(r"\{%-?\s*if\s+(.+?)\s*-?%\}\s*is-hidden\s*\{%-?\s*endif\s*-?%\}")


def config_gated_conditions() -> list[str]:
    """설정으로 숨는 블록의 «조건식» — 손 목록이 아니라 템플릿에서 판다."""
    src = SETTINGS.read_text(encoding="utf-8")
    found = [m.group(1).strip() for m in _HIDDEN_IF_RE.finditer(src)]
    assert found, (
        "`is-hidden` 을 설정으로 거는 블록이 0개 — 관용구가 바뀌었다. "
        "0이면 이 파일 전체가 공허한 초록이 된다."
    )
    return found


def _seeded_gate_config() -> dict[str, object]:
    """e2e 시드가 «게이트 리포» 에 세우는 설정 — AST 로 딴다(문자열 검색 아님)."""
    tree = ast.parse(E2E_CONFTEST.read_text(encoding="utf-8"))
    out: dict[str, object] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "_seed_gated_repo"):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Assign)
                    and len(sub.targets) == 1
                    and isinstance(sub.targets[0], ast.Attribute)
                    and isinstance(sub.value, ast.Constant)):
                out[sub.targets[0].attr] = sub.value.value
    assert out, "`_seed_gated_repo` 에서 설정 대입을 하나도 못 읽었다 — 이름이 바뀌었다"
    return out


def _condition_is_opened_by(cond: str, cfg: dict[str, object]) -> bool:
    """그 조건이 «거짓» 이 되어 블록이 열리는가.

    🔴 부분문자열로 판정하지 않는다 — 조건식 형태를 정확히 맞춘다. 모르는 형태는
       «열린다» 고 넘기지 않고 False 로 둬서 red 가 되게 한다(fail-closed).
    """
    if m := re.fullmatch(r"not\s+config\.(\w+)", cond):
        return bool(cfg.get(m.group(1))) is True
    if m := re.fullmatch(r"config\.(\w+)\s*==\s*'([^']*)'", cond):
        return cfg.get(m.group(1)) != m.group(2)
    if m := re.fullmatch(r"config\.(\w+)\s*!=\s*'([^']*)'", cond):
        return cfg.get(m.group(1)) == m.group(2)
    return False


def test_every_config_gated_block_has_a_seed_that_opens_it():
    """🔴 설정으로 숨는 블록 전건에 «그것을 여는» 시드가 있어야 한다 — 닫힘.

    red 로 만드는 뮤테이션: `settings.html` 에 새 블록
    `{% if not config.pr_review_comment %}is-hidden{% endif %}` 을 넣으면 red
    (그 설정을 여는 시드가 없으므로). 반대로 시드에서 `auto_merge` 대입을 지워도 red.
    """
    cfg = _seeded_gate_config()
    unopened = [c for c in config_gated_conditions() if not _condition_is_opened_by(c, cfg)]
    assert not unopened, (
        "설정으로 숨는 블록인데 그것을 여는 e2e 시드가 없다 — 그 안의 글자는 "
        f"아무도 재지 않는다(시드 설정 {cfg}):\n  " + "\n  ".join(sorted(set(unopened)))
    )


def test_the_sweep_actually_visits_the_gated_repo():
    """토큰만 세우고 «열지» 않으면 화면은 그대로다 — 배선을 따로 잰다."""
    sweep = E2E_SWEEP.read_text(encoding="utf-8")
    assert "gated_settings_repo" in sweep, (
        "게이트 설정 리포를 쓰는 스윕이 없다 — 시드만 만들고 아무도 방문하지 않는다"
    )
    assert "_assert_gate_blocks_were_measured" in sweep, (
        "«실제로 열렸는지» 되짚는 단언이 없다 — 숨은 채로 0을 재고 초록이 된다"
    )


def test_the_condition_parser_is_fail_closed():
    """🔴 모르는 조건 형태를 «열린다» 로 흘려보내지 않는다.

    이 자기 시험이 없으면, 새로운 조건 표현이 등장했을 때 가드가 조용히 통과시킨다.
    """
    cfg = {"auto_merge": True, "approve_mode": "semi-auto"}
    assert _condition_is_opened_by("not config.auto_merge", cfg)
    assert _condition_is_opened_by("config.approve_mode == 'disabled'", cfg)
    assert _condition_is_opened_by("config.approve_mode != 'semi-auto'", cfg)
    # 열리지 않는 경우
    assert not _condition_is_opened_by("not config.auto_merge", {"auto_merge": False})
    assert not _condition_is_opened_by("config.approve_mode == 'semi-auto'", cfg)
    # 🔴 모르는 형태 = 열리지 않음(fail-closed)
    assert not _condition_is_opened_by("config.a and config.b", cfg), (
        "모르는 조건 형태를 «열린다» 로 판정한다 — fail-open 이다"
    )


def test_the_template_scan_is_not_vacuous():
    """관측 하한 — 조건을 못 찾으면 위 단언이 조용히 공허해진다."""
    conds = config_gated_conditions()
    assert len(conds) >= 3, f"설정 게이트 조건을 {len(conds)}개만 찾았다: {conds}"
