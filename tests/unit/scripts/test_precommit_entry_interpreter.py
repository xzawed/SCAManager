"""`.pre-commit-config.yaml` 훅이 **실제로 실행될 수 있는가** — 죽은 인터프리터 차단 (backlog R56).

## 사고 (2026-08-06 5+1 회고 P0 · 실행 실측)

pre-commit 이 이 머신에 **한 번도 설치된 적이 없어** 16 훅이 19 PR 내내 0회 실행됐다.
그래서 그 안에 있던 결함도 **함께 보이지 않았다**: 문서·가드 훅 7종이

    language: system
    entry: python scripts/check_X.py

였는데, `language: system` 은 pre-commit 이 **PATH 를 전혀 손대지 않는** 모드다. 이 개발
머신에서 bare `python` 은 Microsoft Store 스텁이라 스크립트를 실행하지 않고 `Python` 한 줄만
찍고 죽는다.

🔴 **실행 실측 (2026-08-06, 동일 스크립트·동일 entry 로 language 만 바꿔 비교)**

| language | 결과 |
|---|---|
| `system` | **Failed, exit code 9009** — 출력 `Python` (스텁이 인자를 무시) |
| `python` | **Passed** |

즉 설치만 했다면 7 훅이 **커밋마다 무의미하게 차단**했을 것이고, 그 마찰은 `--no-verify`
습관으로 이어졌을 것이다 — 계층을 살리려는 조치가 계층을 죽이는 형태다.

## 이 파일이 닫는 축 (그리고 닫지 못하는 축)

- ✅ **`language: system` + bare 인터프리터 entry** 조합의 재도입 — 이 저장소가 이미
  `settings.json` 에서 겪은 exit 49 클래스(`test_hook_interpreter_liveness.py`)의 **두 번째 표면**.
  그 파일은 `.claude/settings.json` 만 본다 — pre-commit 표면에는 관측자가 **0개**였다.
- ✅ entry 가 가리키는 스크립트가 **실재**하는가(이름이 바뀌면 커밋 시점에야 터진다).
- ✅ `pre-push` 타입 자동 설치 금지(이 리포의 6-step ② 게이트를 밀어낸다).
- ❌ 훅 본문의 정확성 · pre-commit 이 이 머신에 **실제로 설치돼 있는지**
  (그 축은 `check_precommit_installed.py` 와 그 테스트가 맡는다).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_CONFIG = _ROOT / ".pre-commit-config.yaml"

# 주변 PATH 로 해소되는 인터프리터 이름 — `language: system` 과 조합되면 죽은 스텁을 만난다.
# Interpreter names resolved from the ambient PATH; deadly when combined with `language: system`.
_BARE_INTERPRETERS = {"python", "python3", "py", "node", "ruby", "perl", "bash", "sh"}


def _config() -> dict:
    return yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))


def _local_hooks() -> list[dict]:
    """`repo: local` 훅 전부 — 이 저장소가 직접 저술한 것만 대상으로 한다."""
    return [h for r in _config()["repos"] if r.get("repo") == "local" for h in r.get("hooks", [])]


def _entry_tokens(hook: dict) -> list[str]:
    """entry 를 공백으로 쪼갠 토큰.

    🔴 `shlex.split` 을 쓰지 않는다 — `language: pygrep` 훅의 entry 는 **명령이 아니라
    정규식**이고(`[^${'"\\s]{10,}` 등) 따옴표가 균형 잡혀 있지 않아 `shlex` 가
    `ValueError: No closing quotation` 으로 죽는다(실측: 초판이 수집 단계에서 전건 error).
    첫 토큰만 필요하므로 단순 분할로 충분하고, 정규식 entry 는 인터프리터 이름과
    일치하지 않아 자연히 제외된다.
    """
    return hook.get("entry", "").split()


# ── ① 죽은 인터프리터 조합 차단 ─────────────────────────────────────────


def test_no_system_hook_invokes_a_bare_interpreter():
    """🔴 `language: system` + `entry: python …` = 주변 PATH 도박.

    실측한 defeat 그대로다 — 이 머신에서 그 조합은 exit 9009 로 커밋을 막고,
    스크립트는 **한 줄도 실행되지 않는다**.
    """
    offenders = [
        f"{h.get('id')}: language=system entry={h.get('entry')!r}"
        for h in _local_hooks()
        if h.get("language") == "system"
        and (t := _entry_tokens(h))
        and t[0] in _BARE_INTERPRETERS
    ]
    assert not offenders, (
        "`language: system` 훅이 주변 PATH 의 인터프리터를 부른다 — Windows Store 스텁이면\n"
        "스크립트를 실행하지 않고 커밋만 막는다(실측 exit 9009).\n"
        "→ `language: python` 으로 바꿀 것(pre-commit 이 venv bin 을 PATH 앞에 붙인다).\n  "
        + "\n  ".join(offenders)
    )


def test_the_script_hooks_are_actually_present():
    """🔴 대조군 — 위 단언은 **대상이 0개여도 통과**한다(공허한 초록).

    실제로 인터프리터를 부르는 로컬 훅이 존재하는지 여기서 고정한다. 훅을 전부 지우거나
    `repo: local` 블록을 없애면 이 테스트가 red 가 되어 위 가드의 공허화를 막는다.
    """
    script_hooks = [h for h in _local_hooks()
                    if (t := _entry_tokens(h)) and t[0] in _BARE_INTERPRETERS]
    assert len(script_hooks) >= 7, (
        f"인터프리터를 부르는 로컬 훅이 {len(script_hooks)}개뿐이다 — "
        "검사 범위가 줄었다면 이 하한을 같은 PR 에서 갱신할 것"
    )


@pytest.mark.parametrize(
    "hook_id,script",
    [
        (h["id"], _entry_tokens(h)[1])
        for h in _local_hooks()
        if len(_entry_tokens(h)) >= 2 and _entry_tokens(h)[0] in _BARE_INTERPRETERS
    ],
)
def test_hook_entry_script_exists(hook_id: str, script: str):
    """entry 가 가리키는 스크립트가 실재해야 한다 — 이름이 바뀌면 커밋 시점에야 터진다."""
    assert (_ROOT / script).is_file(), f"{hook_id} 의 entry 가 없는 파일을 가리킨다: {script}"


# ── ② 설치 타입 계약 ────────────────────────────────────────────────────


def test_commit_msg_type_is_installed_by_default():
    """🔴 `--hook-type commit-msg` 를 빠뜨리면 **실제 토큰 유출 사고로 만들어진 훅**만 죽는다.

    나머지가 정상 설치되므로 겉보기에는 "설치 완료" 다 — 가장 흔한 실수이자 가장 조용한 실패.
    """
    types = _config().get("default_install_hook_types") or []
    assert "commit-msg" in types, (
        "default_install_hook_types 에 commit-msg 가 없다 — "
        "`stages: [commit-msg]` 훅이 설치되지 않은 채 '설치 완료' 로 보인다"
    )
    assert "pre-commit" in types


def test_pre_push_type_is_never_installed_by_default():
    """🔴 pre-commit 이 `.git/hooks/pre-push` 를 `pre-push.legacy` 로 **밀어낸다**.

    그 자리에는 이 저장소의 6-step ② 게이트 러너가 있다 — 밀리면 push 전 전체 검증이
    통째로, 조용히 사라진다.
    """
    types = _config().get("default_install_hook_types") or []
    assert "pre-push" not in types, (
        "pre-push 타입을 자동 설치하면 이 리포의 push 게이트(.git/hooks/pre-push)가 밀려난다"
    )


def test_commit_msg_stage_hook_still_exists():
    """대조군 — 위 계약은 commit-msg 훅이 하나도 없어도 통과한다."""
    staged = [h["id"] for h in _local_hooks() if "commit-msg" in (h.get("stages") or [])]
    assert staged, "commit-msg 단계 훅이 사라졌다 — 설치 타입 계약이 무의미해진다"


# ── ③ 자동 수정 훅의 파괴 반경 ──────────────────────────────────────────

_PROTECTED = ("alembic/versions/", "src/static/vendor/")


@pytest.mark.parametrize("hook_id", ["trailing-whitespace", "end-of-file-fixer"])
def test_autofixers_exclude_records_and_vendored_files(hook_id: str):
    """🔴 자동 수정 훅은 **vendor·수정금지 파일**을 재작성하면 안 된다.

    `alembic/versions/**` 는 CLAUDE.md 수정 금지 파일 · `src/static/vendor/**` 는
    외부 산출물이다.
    """
    hooks = [h for r in _config()["repos"] for h in r.get("hooks", []) if h.get("id") == hook_id]
    assert hooks, f"{hook_id} 훅이 없다 — 이 가드가 공허해졌다"
    exclude = hooks[0].get("exclude", "")
    missing = [p for p in _PROTECTED if p not in exclude]
    assert not missing, (
        f"{hook_id} 가 보호 대상 경로를 제외하지 않는다: {missing}\n"
        "→ vendor·수정금지 파일을 자동 재작성하게 된다"
    )
    assert "docs/_archive/" not in exclude, (
        "퇴역한 이력 트리가 exclude 에 남아 있다 — 분모가 빈 경로를 센다"
    )
