"""문서가 드는 **구별값**을 코드에서 파생해 대조한다.

## 왜 — 형식 검사 셋을 다 통과하고도 거짓이었다 (실측)

문서 감사에서 세 계기가 전부 초록이었다:

    경로 실재      89/89        앵커 유일 실재   114/114
    명령 도구 실재   91/91        기존 doc 가드    7종 EXIT 0

그런데 코드에서 파생해 대조하니 **구별값 8개 중 3개가 거짓**이었다:

    docs/workflow/db.md    현재 head `0045`   ->  실제 0047
    docs/STATE.md          등록 분석기 25종     ->  실제 24
    README.ko.md           모두 25종           ->  실제 24

🔴 `0045` 는 파일이 실재하고(경로 검사 통과) 문자열도 실재하며(앵커 검사 통과) 어떤 가드도
그 그래프를 걷지 않는다(가드 EXIT 0). **경로 실재는 문장을 참으로 만들지 않는다.**

그 문장을 믿고 `down_revision = "0045"` 를 쓰면 DAG 가 분기한다. 실측: 분기를 심어도
`tests/unit/migrations` + `test_migration_completeness.py` 는 **229 passed** 다.
잡는 곳은 `e2e/conftest.py::def _get_alembic_head` 하나뿐이고 `pre_push_gate.py` 는 e2e 를 돌리지 않는다 —
로컬 push 는 통과하고 CI e2e 나 Railway pre-deploy 에서야 터진다.

## 이 파일이 강제하는 것

문서에 적힌 구별값이 **코드에서 파생한 값과 같다.** 손으로 적은 기대값을 두지 않는다 —
그러면 이 파일이 세 번째 SSOT 가 되고 그것이 늙는 순간 같은 결함이 돌아온다.

A path existing does not make a sentence true: these are the values no existing guard derives.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("SESSION_SECRET", "0123456789abcdef0123456789abcdef")

from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]

def _alembic_heads() -> list[str]:
    """head 를 **alembic 자신에게** 묻는다 — 정규식으로 파일을 훑지 않는다.

    🔴 첫 판은 `revision =`·`down_revision =` 을 정규식으로 긁어 `set(revs) - set(downs)` 를
    head 라 불렀다. 그것은 alembic 이 계산하는 것과 **다르다**(Grok claim-review `01a057fd`):
    머지 리비전의 튜플 `down_revision`, 리터럴이 아닌 `revision`, 다른 형태의 타입 주석이
    전부 **조용히 통과**한다. alembic 은 모듈을 exec 하고 나는 텍스트만 봤다.
    Ask alembic, not a regex fork: tuple down_revisions and non-literal revisions slip past text.
    """
    from alembic.config import Config  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from alembic.script import ScriptDirectory  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    return list(ScriptDirectory.from_config(cfg).get_heads())


def test_the_migration_dag_has_exactly_one_head():
    """🔴 head 가 둘이면 `alembic upgrade head` 가 운영 pre-deploy 에서 실패한다.

    실측: 분기를 심어도 기존 마이그레이션 단위 시험 229개가 **전부 통과**한다.
    잡는 곳은 `e2e/conftest.py::def _get_alembic_head` 뿐이고 `pre_push_gate.py` 는 e2e 를 돌리지
    않는다 — 그래서 로컬에서 잡을 관측면이 여기 필요하다.
    """
    heads = sorted(_alembic_heads())
    assert heads, "head 를 하나도 못 읽었다 — 이 시험이 공허하다"
    assert len(heads) == 1, (
        f"alembic head 가 {len(heads)}개다: {heads}\n"
        "  분기다. 새 리비전의 `down_revision` 은 **직전 head** 여야 한다 —\n"
        "  `py -3 -m alembic heads` 로 확인하고 적어라(문서에 적힌 숫자를 믿지 마라)."
    )


def test_db_workflow_does_not_pin_a_head_number():
    """🔴 문서에 head 번호를 **적지 않는다** — 적는 순간 다음 리비전에서 낡는다.

    `0045`→`0047` 로 고치는 것은 처방이 아니다. `0048` 에서 같은 거짓이 된다.
    절차는 「직전 head 를 조회해서 쓴다」여야 한다.
    """
    db_md = (_ROOT / "docs" / "workflow" / "db.md").read_text(encoding="utf-8")
    # 🔴 문구를 잠그지 않는다 — 「현재 head `0047`」만 막으면 「직전 head 는 `0048`」이 통과한다.
    #    지난 사고의 지문을 외우는 것은 가드가 아니다. **파생값 자체**가 문서에 박혀 있는지 본다.
    #    (첫 판은 `현재 head \w+` 정규식이었다 — Grok claim-review `01a057fd` 가 theatre 라 짚었다.)
    # Derive, don't phrase-lock: the last incident's wording is not the invariant.
    pinned = [h for h in _alembic_heads() if h in db_md]
    assert not pinned, (
        f"db.md 에 현재 head 값이 박혀 있다: {pinned}. 다음 리비전에서 거짓이 된다 — "
        "번호 대신 `py -3 -m alembic heads` 를 적어라."
    )


def _registry_size() -> int:
    """등록 어댑터 수 — import 부작용으로 채워진 정본 레지스트리에서 읽는다."""
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    importlib.import_module("src.analyzer.io.static")  # 등록 부작용
    return len(importlib.import_module("src.analyzer.pure.registry").REGISTRY)


def test_state_analyzer_count_is_derived():
    """🔴 `docs/STATE.md` 의 등록 분석기 수가 실제 레지스트리와 같다.

    `check_docs_sync.py` 는 **stdlib 백스톱**이라 `src` 를 임포트할 수 없다 — 그래서 이 값을
    파생하지 못하고, 어댑터를 지워도 초록이었다(실측: 25종 표기 · 실제 24).
    """
    state = (_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8")
    m = re.search(r"등록 분석기 (\d+)종", state)
    assert m, "STATE.md 에서 등록 분석기 수를 못 찾았다 — 표기가 바뀌었으면 이 시험도 고쳐라"
    assert int(m.group(1)) == _registry_size(), (
        f"STATE.md 는 {m.group(1)}종이라 적는데 레지스트리는 {_registry_size()}개다"
    )


def test_both_readmes_carry_the_derived_analyzer_count():
    """🔴 같은 값이 **두 README** 에 있다 — 한쪽만 고치면 다른 쪽이 늙는다.

    첫 판은 `README.ko.md` 만 봤고, 그 사이 영문 `README.md` 는 계속 25 라고 적고 있었다
    (Grok claim-review `01a057fd`) — 이 파일이 죽이겠다는 바로 그 부류를 스스로 남겼다.
    """
    size = _registry_size()
    checked = 0
    for name, pattern in (
        ("README.ko.md", r"모두 \*\*(\d+)종\*\*"),
        ("README.md", r"There are \*\*(\d+) registered analyzers\*\*"),
    ):
        text = (_ROOT / name).read_text(encoding="utf-8")
        m = re.search(pattern, text)
        assert m, f"{name} 에서 분석기 수 문장을 못 찾았다 — 표기가 바뀌었으면 이 시험도 고쳐라"
        assert int(m.group(1)) == size, (
            f"{name} 는 {m.group(1)}종이라 적는데 레지스트리는 {size}개다"
        )
        checked += 1
    assert checked == 2, "두 README 를 다 재지 못했다 — 공허화"


def test_readme_ko_provisioned_count_is_derived():
    """부정 통제 — 같은 문장의 **조달 수**는 다른 축이다. 둘을 섞으면 한쪽이 조용히 맞는다."""
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    provisioned = importlib.import_module("src.analyzer.io.static").PROVISIONED_ANALYZERS
    readme = (_ROOT / "README.ko.md").read_text(encoding="utf-8")
    m = re.search(r"모두 \*\*(\d+)종\*\*이고, 그중 \*\*(\d+)종\*\*", readme)
    assert m and int(m.group(2)) == len(provisioned), (
        f"README.ko 필수 설치 수가 조달 계약({len(provisioned)}종)과 다르다"
    )
