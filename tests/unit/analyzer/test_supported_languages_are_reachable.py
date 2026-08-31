"""어댑터가 선언한 언어가 **실제로 도달 가능한가** — 선언≠도달 가능 (#1577).

`detect_language()` 가 정본이다. 어댑터가 그 치역 **밖의** 이름을 선언하면 그 이름은
프로덕션에서 결코 발생하지 않는다 — 선언에만 있고 동작에는 없는 죽은 이름이다.

실측(2026-08-30): `stylelint` 이 `"scss"` 를, `tflint` 가 `"hcl"` 을 선언했는데
정본은 그 확장자를 **의도적으로 접는다**:

    detect_language("a.scss") -> "css"        (`.sass`·`.less` 도 같이 css 로)
    detect_language("a.hcl")  -> "terraform"  (`.tf` 와 같이)

두 어댑터 어디에도 그 이름을 다르게 다루는 분기가 없었다. 그런데 **초록 테스트 2건이**
언어 문자열을 손으로 먹여 그 도달 불가 상태를 지키고 있었다 — `detect_language` 를 거치지
않으므로 프로덕션에서 결코 발생하지 않는 입력을 단언한 것이다.

「부분문자열≠상태」의 사촌이다: **선언≠도달 가능.** 선언 집합을 언어로 세는 코드는 매번
2개를 부풀렸고, `#1521` 의 「대체 관측면 없는 언어 6개」가 정확히 그렇게 생겼다(실제 4개).

## 이 파일이 하는 것

1. 선언한 어댑터의 `SUPPORTED_LANGUAGES` 가 `detect_language()` **치역의 부분집합**이다.
2. 등록된 어댑터 **전원**이 그 치역에서 최소 한 언어를 지원한다 — 아무도 도달 못 하는
   어댑터가 없다는 뜻이다.

🔴 2 를 「미선언 어댑터 이름 == {pylint, flake8, bandit}」 같은 **스냅샷 집합**으로 쓰지
않는다. 그러면 누가 python 어댑터에 `SUPPORTED_LANGUAGES` 를 **정당하게 추가**하는 순간
red 가 된다 — 개선을 벌하는 가드다. 속성 유무와 무관한 **행동 파생**(`supports()`)으로 묻는다.

Declared is not reachable: a language name outside `detect_language()`'s range can never occur
in production, and tests that hand-feed the string keep that dead state green.
"""
from __future__ import annotations

import pytest

# 🔴 등록은 import 부작용이다 — `static` 을 들여와야 REGISTRY 가 찬다.
#    `# noqa: F401` 단독은 flake8 전용이라 CodeQL `py/unused-import` 가 발화하고,
#    정의만 두면 `py/unused-global-variable` 로 옮겨갈 뿐이다. 정본은 튜플-참조
#    **두 줄**(정의 + 소실 시 loud-fail) — `docs/workflow/verify.md::### side-effect-only ORM import`.
import src.analyzer.io.static as _adapter_registration
from src.analyzer.pure import language as _language
from src.analyzer.pure.registry import REGISTRY, AnalyzeContext

_SIDE_EFFECT_MODULES = (_adapter_registration,)
if not REGISTRY:
    raise RuntimeError(
        f"side-effect import 소실 — {[m.__name__ for m in _SIDE_EFFECT_MODULES]} 를 "
        "들여왔는데 어댑터 REGISTRY 가 비었다"
    )


def _detectable_languages() -> frozenset[str]:
    """`detect_language()` 의 치역 — **손으로 나열하지 않는다.**

    정본의 네 맵에서 파생한다. 나열하면 맵이 바뀔 때 이 가드가 조용히 낡는다.
    """
    return frozenset().union(*(
        set(m.values()) for m in (
            _language._EXTENSION_MAP,        # noqa: SLF001
            _language._FILENAME_MAP,         # noqa: SLF001
            _language._FILENAME_PREFIX_MAP,  # noqa: SLF001
            _language._SHEBANG_MAP,          # noqa: SLF001
        )
    ))


def _ctx(language: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename="probe", content="", language=language, is_test=False, tmp_path="probe",
    )


def test_the_range_and_the_registry_are_not_empty():
    """🔴 둘 중 하나가 비면 아래 두 시험이 통째로 공허하다."""
    assert _detectable_languages(), "detect_language 치역이 비었다 — 정본 맵을 못 읽었다"
    assert REGISTRY, "등록 어댑터가 0개 — import 부작용이 안 돌았다"


def test_declared_languages_are_all_reachable():
    """🔴 선언한 언어는 전부 `detect_language()` 가 **실제로 내는** 이름이어야 한다.

    치역 밖 이름은 프로덕션에서 발생하지 않는다 — 선언에만 있는 죽은 이름이다.
    """
    reachable = _detectable_languages()
    offenders = {
        analyzer.name: sorted(set(analyzer.SUPPORTED_LANGUAGES) - reachable)
        for analyzer in REGISTRY
        if hasattr(analyzer, "SUPPORTED_LANGUAGES")
        and set(analyzer.SUPPORTED_LANGUAGES) - reachable
    }
    assert not offenders, (
        f"`detect_language()` 가 결코 내지 않는 언어를 선언한 어댑터: {offenders}\n"
        "  그 이름은 프로덕션에서 발생하지 않는다 — 선언에서 지워라.\n"
        "  정말 그 언어를 따로 다뤄야 한다면 `src/analyzer/pure/language.py` 의 맵을\n"
        "  먼저 고쳐라(제품 결정이다 — `.sass`·`.less` 도 `css` 로 접혀 있다)."
    )


@pytest.mark.parametrize("analyzer", REGISTRY, ids=lambda a: a.name)
def test_every_registered_analyzer_is_reachable_by_some_language(analyzer):
    """🔴 등록된 어댑터는 치역 안의 어떤 언어로든 도달 가능해야 한다.

    🔴 **행동 파생이다** — `SUPPORTED_LANGUAGES` 속성 유무를 묻지 않고 `supports()` 를 부른다.
    속성으로 물으면 미선언 어댑터(`pylint`·`flake8`·`bandit`)가 검사에서 빠지고,
    「미선언 이름 == {…}」 스냅샷으로 물으면 정당한 선언 추가가 red 가 된다.
    """
    hit = sorted(lang for lang in _detectable_languages() if analyzer.supports(_ctx(lang)))
    assert hit, (
        f"`{analyzer.name}` 은 `detect_language()` 치역의 어떤 언어로도 도달할 수 없다 — "
        "등록돼 있지만 프로덕션에서 결코 실행되지 않는다."
    )
