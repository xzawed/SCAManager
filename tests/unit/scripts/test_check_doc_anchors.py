"""문서 코드 앵커 가드의 자기검증.

🔴 이 가드가 막으려는 것은 **조용한 거짓**이다. 2026-08-26 실측: 영역 문서의
`file:line` 참조 93건 중 24건이 틀려 있었고, 깨진 시점은 하루 전 머지 3건이었으며
그때 red 가 된 게이트는 0건이었다. 그래서 여기서 재는 것은 두 가지다:

  1. 앵커가 사라지면 **정말 red 가 되는가** (가드가 발화하는가)
  2. 줄번호 참조가 남아 있으면 **정말 red 가 되는가** (구 형식이 되살아나지 않는가)

둘 중 하나라도 못 재면 이 가드는 거짓 집행자다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

_SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "check_doc_anchors.py"


def _load():
    """스크립트를 모듈로 적재 — `scripts/` 는 패키지가 아니다."""
    spec = importlib.util.spec_from_file_location("check_doc_anchors", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_anchors"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_exists():
    """가드 파일 자체가 있어야 한다 — 없으면 나머지 단언이 전부 공허하다."""
    assert _SCRIPT.is_file(), f"{_SCRIPT} 가 없다"


def test_anchor_regex_matches_the_documented_form():
    """`path::anchor` 를 잡고, 앵커에 공백·괄호가 들어가도 잡는다."""
    mod = _load()
    m = mod._ANCHOR.search("보안 헤더는 `src/main.py::class SecurityHeadersMiddleware` 다")
    assert m, "표준 앵커 형식을 못 잡았다"
    assert m.group(1) == "src/main.py"
    assert m.group(2) == "class SecurityHeadersMiddleware"

    m2 = mod._ANCHOR.search("`railway.toml::[deploy.multiRegionConfig]`")
    assert m2 and m2.group(2) == "[deploy.multiRegionConfig]", "괄호가 든 앵커를 못 잡았다"


def test_line_ref_regex_still_catches_the_old_form():
    """구 형식 `path:123` 을 잡아야 한다 — 못 잡으면 되살아나도 초록이다."""
    mod = _load()
    assert mod._LINE_REF.search("`src/main.py:74`"), "`path:NNN` 을 못 잡았다"
    assert mod._LINE_REF.search("`src/config.py:248-254`"), "범위 형식을 못 잡았다"
    assert mod._BARE_REF.search("메타 추출(`:377`)"), "맨 `:NNN` 을 못 잡았다"


def test_line_ref_detector_does_not_enumerate_the_tail():
    """🔴 콜론 뒤 숫자면 줄번호다 — 꼬리 형태를 열거하면 열거 밖에 눈먼다.

    초판은 `` `path:123` `` 과 `` `path:123-456` `` 만 알았고 실제 문서에 있던
    `:51,150`(쉼표) · `:34~41`(물결) · `` `gitleaks`:30 ``(백틱 밖) · `(:48)`(괄호) ·
    `` `x` :5 ``(공백) 을 놓쳤다. 실측: 꼬리 열거를 버리자 70 -> 79 -> 최종 7건이 더 드러났다.
    이 파일이 막으려는 실패를 가드 자신이 저지르고 있었다.
    """
    mod = _load()
    assert mod._LINE_REF.search("`tests/unit/test_migration_completeness.py:51,150`"), "쉼표 꼬리"
    assert mod._LINE_REF.search("`base.html:34~41`"), "물결 범위"
    assert mod._BARE_REF.search("`check-secrets-in-diff`:56"), "백틱 밖 줄번호"
    assert mod._BARE_REF.search("`fastapi==0.141.1` :5"), "공백 낀 줄번호"
    assert mod._PAREN_REF.search("`_PROVENANCE`(:48)"), "괄호 줄번호"
    assert mod._SINGLE_COLON.search("`src/gate/actions/approve.py:_run_semi_auto`"), "단일 콜론+식별자"
    # 앵커 형식은 어느 축에도 걸리면 안 된다 — 걸리면 전 문서가 영구 red 다.
    ok = "`src/main.py::def _run_semi_auto`"
    for rx in (mod._LINE_REF, mod._BARE_REF, mod._PAREN_REF, mod._SINGLE_COLON):
        assert not rx.search(ok), f"정상 앵커가 {rx.pattern} 에 걸린다"


def test_anchor_must_be_unique_not_merely_present():
    """🔴 이 가드의 전부 — 존재만 보면 거짓 집행자다 (Grok 반증 01a0402e).

    존재만 검사하면 `result_dict["static_analysis_incomplete"]` 대입을 지워도 그 이름을
    언급하는 **주석 두 줄이 남아** 초록이다. 사라진 코드를 가리키며 ✅ 를 인쇄하는 것은
    줄번호보다 나쁘다. 그래서 count == 1 을 강제한다.
    """
    mod = _load()
    tracked = mod.tracked_files()
    # 리포에 여러 번 나타나는 문자열을 앵커로 쓰면 red 여야 한다.
    body = mod.file_text("src/worker/pipeline.py")
    assert body.count("def ") > 1, "전제가 깨졌다 — 다중 일치 문자열이 필요하다"
    bad = mod._check_anchor("x.md", 1, "src/worker/pipeline.py", "def ", tracked, "`x`")
    assert bad and "특정하지 못한다" in bad, f"다중 일치를 통과시켰다: {bad}"


def test_anchor_must_not_be_trivially_short():
    """`src/main.py::a` 같은 한 글자 앵커는 아무 데나 맞는다 — 자기면제 차단."""
    mod = _load()
    bad = mod._check_anchor("x.md", 1, "src/main.py", "a", mod.tracked_files(), "`x`")
    assert bad and "미만" in bad, f"짧은 앵커를 통과시켰다: {bad}"


def test_markdown_targets_are_parsed():
    """🔴 `_EXTS` 에 `md` 가 빠져 있던 동안 `docs/architecture.md::tools/` 는
    **앵커로 파싱조차 되지 않아** 문자열이 사라져도 초록이었다(Grok 지적).
    """
    mod = _load()
    m = mod._ANCHOR.search("`docs/architecture.md::REGISTRY 8`")
    assert m and m.group(1) == "docs/architecture.md", "md 대상이 앵커로 안 잡힌다"


def test_anchor_and_line_ref_do_not_overlap():
    """🔴 `path::anchor` 가 구 형식으로도 잡히면 전 문서가 영구 red 다.

    `::` 뒤가 숫자로 시작하는 앵커(`src/main.py::42번째 규칙`)에서 실제로 겹칠 수 있다.
    """
    mod = _load()
    text = "`src/main.py::42_RULES`"
    assert mod._ANCHOR.search(text), "앵커로 안 잡혔다"
    assert not mod._LINE_REF.search(text), (
        "숫자로 시작하는 앵커가 줄번호 참조로도 잡힌다 — 전 문서가 영구 red 가 된다"
    )


def test_base_anchor_needs_a_declared_base_file():
    """🔴 `::anchor` 는 기준 선언이 있을 때만 해석된다 — 없으면 red 여야 한다.

    조용히 통과시키면 「검증된 것처럼 보이는 미검증 참조」가 생긴다. 그건 줄번호보다 나쁘다.
    """
    mod = _load()
    assert mod._BASE_ANCHOR.search("채점(`::def calculate_score`)"), "기준-파일 앵커를 못 잡았다"
    # 기준 선언이 없는 문서를 흉내낸다 — scan 은 문서를 읽으므로 여기서는 정규식만 확인하고,
    # 「기준 없음 -> dead」 경로는 리포 전체 통과 테스트가 실사용으로 덮는다.
    assert not mod._ANCHOR.search("`::def calculate_score`"), (
        "경로 없는 앵커가 경로 있는 앵커로도 잡힌다 — 두 축이 겹치면 이중 계수된다"
    )


def test_the_repo_itself_passes():
    """리포 문서 전체가 이 규약을 지킨다 — 이 가드의 실사용 축이다."""
    mod = _load()
    tracked = mod.tracked_files()
    dead, line_refs, checked = mod.scan(tracked)
    assert not dead, f"앵커가 실재하지 않는다: {dead[:5]}"
    assert not line_refs, f"줄번호 참조가 남아 있다 ({len(line_refs)}건): {line_refs[:5]}"
    assert checked > 0, "앵커를 0건 검사했다 — 이 테스트가 공허하다"
