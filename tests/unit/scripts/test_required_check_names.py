"""required status check 이름의 **불변성** 가드 (backlog R64).

## 왜 (2026-08-06)

`E2E (Playwright)` 를 main 브랜치 보호의 required status check 로 승격했다
(9 → 10, `enforce_admins: true` 유지). 승격 근거는 안정성 실측이다:

| 구간 | e2e job 성공률 |
|---|---|
| `#1294`(CSP + CSS 빌드) 이전 | **2 / 17** |
| 그 이후 | **16 / 16** |

즉 빨강의 원인은 플레이크가 아니라 **원인이 밝혀진 결함**이었고, 그것이 닫힌 뒤로는
한 번도 실패하지 않았다.

## 🔴 이 파일이 닫는 축 — 그리고 닫지 **못하는** 축

required check 는 **(SHA, 이름)** 으로 식별된다(`.claude/rules/guards.md`).
그래서 `ci.yml` 의 job `name:` 을 바꾸면 GitHub 이 기다리는 이름의 체크는
**영원히 보고되지 않는다** — 설정은 그대로인데 게이트가 조용히 의미를 잃는다.
이 파일은 그 **이름 drift** 만 막는다.

❌ **라이브 설정은 보지 못한다.** GitHub 에서 `E2E (Playwright)` 를 required 목록에서
빼도 이 테스트는 초록이다. 그것을 관측하려면 `Administration: read` 권한 토큰이 필요하고,
그 자격증명을 리포 시크릿에 두면 같은 리포의 어떤 워크플로에서도 읽을 수 있어
**containment 가 성립하지 않는다**(Environment 스코프가 필요). 그래서 만들지 않았다 —
없는 관측을 있는 것처럼 보이게 하는 파일을 두는 것이 더 나쁘다.

정본 목록과 롤백 절차는 `docs/runbooks/branch-protection.md` 가 기록한다.
"""
from __future__ import annotations

import pathlib

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
_CI = _REPO / ".github" / "workflows" / "ci.yml"

# 🔴 리터럴로 못박는다 — `ci.yml` 에서 유도하면 이름을 바꿔도 초록이 된다(자기참조 공허화).
#    이 문자열은 GitHub 브랜치 보호에 등록된 값과 **한 글자도** 달라선 안 된다.
_REQUIRED_JOB_NAMES = (
    "E2E (Playwright)",
    "pytest + Codecov + SonarCloud",
    "Repo integrity guards (stdlib backstop)",
    "Static analysis gate (pylint + bandit on src/)",
    "TruffleHog secret scan",
    "Lint changed test files (F401/F841 — C1)",
    "PG-only tests (SKIP LOCKED + migration round-trip)",
    "pip-audit (SCA — 의존성 취약점 게이트)",
    "lint-js 공허화 차단 (검사 범위 비면 fail)",
    "Dockerfile build + analyzer contract",
)
# `Analyze (python)` 은 `codeql.yml` 소속이라 이 파일이 보지 않는다.
# `Analyze (python)` lives in `codeql.yml`, outside this file's view.

# 승격하며 `if:` 부재를 실측한 job — 색이 코드 결함만 따라야 한다(아래 가드).
# `Lint changed test files` 는 `if: pull_request` 라 뺐다 — PR 에선 항상 참이다.
# Promoted jobs verified to have no `if:`; their colour must track code defects only.
_PROMOTED_JOB_NAMES = (
    "E2E (Playwright)",
    "Dockerfile build + analyzer contract",
)


def _jobs() -> dict[str, dict]:
    data = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    return {k: j for k, j in data.get("jobs", {}).items() if isinstance(j, dict)}


def _job_names() -> set[str]:
    return {j.get("name") for j in _jobs().values()}


def _needs(job: dict) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def test_ci_defines_every_required_job_name():
    """🔴 이름이 바뀌면 GitHub 이 기다리는 체크가 **영원히 보고되지 않는다**.

    설정은 그대로인데 게이트만 조용히 죽는 형태다 — required check 는 (SHA, 이름)으로
    식별되기 때문이다.
    """
    names = _job_names()
    missing = [n for n in _REQUIRED_JOB_NAMES if n not in names]
    assert not missing, (
        "브랜치 보호가 required 로 지정한 이름이 ci.yml 에 없다 — 그 체크는 영원히 pending 이다:\n  "
        + "\n  ".join(missing)
        + "\n→ job 이름을 바꿨다면 **같은 PR 에서** 브랜치 보호 설정도 갱신할 것"
        + " (`docs/runbooks/branch-protection.md`)."
    )


def test_the_pinned_list_is_not_vacuous():
    """대조군 — 목록이 비면 위 단언은 항상 통과한다."""
    assert len(_REQUIRED_JOB_NAMES) >= 10
    assert len(_PROMOTED_JOB_NAMES) >= 2


def test_promoted_jobs_colour_tracks_only_the_code():
    """🔴 승격한 job 의 색은 코드 결함만 따라야 한다 — 세 경로를 닫는다.

    1. 자기 `if:` — skip 은 성공으로 취급돼 빨간 required check 를 **세탁**한다.
    2. `needs:` 선행의 skip — 선행이 skip 되면 이 job 도 skip 이다. 그래서 선행 사슬 전체가
       `if:` 없는 required 여야 한다 — 그래야 선행의 빨강이 직접 머지를 막는다.
    3. 캐시 export — gha 캐시 서비스 429·503 이 빌드와 무관하게 job 을 red 로 만든다.
       `ignore-error=true` 는 그 export 만 삼킨다. **부분문자열이 아니라 속성으로** 읽는다
       (`scope=ignore-error=true` 는 속성이 아니다).
    """
    jobs = _jobs()
    by_name = {j.get("name"): k for k, j in jobs.items()}
    caches = []
    for name in _PROMOTED_JOB_NAMES:
        assert name in by_name, f"{name!r} job 을 못 찾았다 — 이름이 바뀌었으면 위 가드가 먼저 red 다"
        chain, todo = [], [by_name[name]]
        while todo:
            key = todo.pop()
            if key not in chain:
                chain.append(key)
                todo.extend(_needs(jobs[key]))
        for key in chain:
            assert "if" not in jobs[key] and jobs[key].get("name") in _REQUIRED_JOB_NAMES, (
                f"{name!r} 의 skip 경로: job {key!r} 에 `if:` 가 있거나 required 가 아니다 — "
                "skip 은 성공으로 취급돼 빨간 required check 를 세탁할 수 있다"
            )
        for step in jobs[by_name[name]].get("steps", []):
            for line in str((step.get("with") or {}).get("cache-to", "")).splitlines():
                if line.strip():
                    attrs = dict(kv.split("=", 1) for kv in line.strip().split(",") if "=" in kv)
                    caches.append((name, line.strip(), attrs.get("ignore-error")))
    assert caches, "승격 job 에서 `cache-to` 를 하나도 못 읽었다 — 3번 단언이 공허하다"
    bad = [(n, line) for n, line, flag in caches if flag != "true"]
    assert not bad, (
        f"캐시 export 실패가 required job 을 red 로 만든다 — `ignore-error=true` 없음: {bad}"
    )
