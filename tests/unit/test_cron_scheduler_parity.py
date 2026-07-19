"""cron 엔드포인트 ↔ 인앱 스케줄러 job 파리티 가드 (2026-07-19 회고 P1).
Parity guard between the internal cron endpoints and the in-app scheduler's JOBS.

🔴 갭 (실측, 2026-07-19): `src/api/internal_cron.py` 는 cron 엔드포인트 **6종**을 노출하는데
`src/scheduler.py::JOBS` 는 **5종**만 등록한다. 빠진 것은 `scan-security`(GHAS 폴링,
`scan_all_repos`) — 즉 **출시 이래 주기 실행 0회**다. 그런데 `docs/reference/env-vars.md` 의
`INTERNAL_CRON_API_KEY` 행은 6종을 열거하며 "주기 실행은 인앱 스케줄러가 서비스 함수를 직접
호출하므로 이 키가 없어도 스케줄 작업은 동작한다" 고 단언한다 — `scan-security` 에 대해 **거짓**.
Measured gap: 6 cron endpoints vs 5 scheduler jobs; scan-security has never run periodically,
while the docs claim all 6 are covered by the in-app scheduler.

🔴 이 가드가 막는 것 / what this seals:
  (1) **신규 cron 엔드포인트를 추가하면서 job 등록도 예외 등재도 하지 않으면 CI FAIL.**
      이번 사고의 형태 — "설정/배선이 어긋나도 아무도 모른다" — 를 코드 안에서 반복하지 않는다.
  (2) 반대 방향(유령 job): JOBS 에 있는데 대응 엔드포인트가 없는 항목도 FAIL.
  (3) 예외 목록의 stale 항목(이미 사라진 엔드포인트)도 FAIL.

🔴 활성화 여부는 **사용자 결정 영역**(정책 15 High tier — GitHub API 쿼터 소모 + 알림 발생)이라
이 가드는 `scan-security` 를 스케줄에 넣지 않는다. 대신 **갭이 조용히 숨지 못하게** 고정한다:
미스케줄 경로는 `src/scheduler.py::UNSCHEDULED_CRON_PATHS` 에 **사유와 함께** 명시돼야 한다.
Enabling it is the user's call; this guard only makes the gap explicit and non-silent.

🔴 산문 grep 금지 — 이 파일은 소스 텍스트를 문자열로 뒤지지 않는다. FastAPI `router.routes` 를
**실제로 열거**하고 `JOBS` 를 **실제로 참조**한다. 하드코딩 6/5 카운트도 두지 않는다
(카운트를 박으면 엔드포인트 추가 시 카운트만 고쳐 통과시키는 우회가 생긴다).
No prose assertions: routes are enumerated from the real router and JOBS is the real registry.
"""
from fastapi.routing import APIRoute

from src.api.internal_cron import router as cron_router
from src.scheduler import CRON_PATH_TO_JOB, JOBS, UNSCHEDULED_CRON_PATHS

# 이 파일이 공허해지는 것을 막는 앵커 — 라우터 열거가 깨지면(빈 집합) 아래 단언들이 전부
# 공허하게 통과한다. `_ANCHOR_PATH` 존재 단언이 그 순간 FAIL 한다.
# Anchor against vacuous passes: if route enumeration silently returns nothing, every parity
# assertion below would pass trivially — the anchor test fails at that moment instead.
_ANCHOR_PATH = "weekly"


def _cron_endpoint_paths() -> set[str]:
    """cron 라우터의 경로 suffix 집합 — 실제 `router.routes` 열거 (하드코딩 금지).
    The set of cron path suffixes, enumerated from the real router.

    `router.prefix`(`/api/internal/cron`) 를 벗겨 `weekly` · `scan-security` 같은 suffix 만 남긴다.
    Strips the router prefix so only the endpoint suffix remains.
    """
    prefix = cron_router.prefix
    paths = set()
    for route in cron_router.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        # 접두사 계약이 깨지면(라우터 재구성 등) 조용히 빈 집합이 되지 않도록 loud-fail.
        # Loud-fail rather than silently yielding an empty set if the prefix contract changes.
        assert path.startswith(prefix), f"cron 라우트가 prefix 밖에 있음: {path!r}"
        paths.add(path[len(prefix):].strip("/"))
    return paths


def _job_names() -> set[str]:
    """스케줄러에 실제 등록된 job 이름 집합 / the real registered job names."""
    return {job.name for job in JOBS}


# --------------------------------------------------------------------------------------
# 앵커 (공허한 통과 차단) / anchor — keeps every assertion below non-vacuous
# --------------------------------------------------------------------------------------

def test_router_enumeration_yields_real_cron_paths():
    """🔴 라우터 열거가 실제로 동작한다 — 빈 집합이면 아래 파리티 단언이 전부 공허해진다."""
    paths = _cron_endpoint_paths()
    assert paths, (
        "cron 라우터에서 경로를 하나도 열거하지 못했다 — `router.routes` 열거 방식이 깨졌다. "
        "이 파일의 파리티 단언이 전부 공허하게 통과하는 상태다."
    )
    assert _ANCHOR_PATH in paths, (
        f"앵커 경로 {_ANCHOR_PATH!r} 가 열거 결과에 없다 (열거 결과: {sorted(paths)}) — "
        "경로 suffix 추출(prefix 제거)이 잘못됐거나 엔드포인트가 사라졌다."
    )


# --------------------------------------------------------------------------------------
# 정방향: 엔드포인트 → job 또는 명시 예외 / forward: endpoint must map to a job or an exception
# --------------------------------------------------------------------------------------

def test_every_cron_endpoint_has_job_or_documented_exception():
    """🔴 모든 cron 엔드포인트는 스케줄 job 을 갖거나 사유와 함께 예외 등재돼야 한다.

    이 가드의 존재 이유 — 신규 cron 엔드포인트를 추가하면서 `JOBS` 등록도 `UNSCHEDULED_CRON_PATHS`
    등재도 하지 않으면 **여기서 CI 가 막는다**. (2026-07-19: 그 상태로 `scan-security` 가
    출시 이래 한 번도 주기 실행되지 않았다.)
    """
    unaccounted = sorted(
        _cron_endpoint_paths() - set(CRON_PATH_TO_JOB) - set(UNSCHEDULED_CRON_PATHS)
    )
    assert not unaccounted, (
        f"스케줄에도 예외 목록에도 없는 cron 엔드포인트: {unaccounted}\n"
        "→ 주기 실행이 필요하면 src/scheduler.py 의 JOBS + CRON_PATH_TO_JOB 에 등록하고,\n"
        "  의도적으로 수동/외부 트리거 전용이면 UNSCHEDULED_CRON_PATHS 에 **사유와 함께** 등재할 것.\n"
        "  (등재 없이 방치하면 엔드포인트만 있고 아무도 부르지 않는 dead cron 이 된다.)"
    )


def test_mapped_job_names_exist_in_registry():
    """🔴 매핑이 가리키는 job 이름이 JOBS 에 실재한다 — 오타 매핑은 dead 배선이다."""
    missing = sorted(set(CRON_PATH_TO_JOB.values()) - _job_names())
    assert not missing, (
        f"CRON_PATH_TO_JOB 이 가리키는 job 이 JOBS 에 없음: {missing} "
        f"(등록된 job: {sorted(_job_names())}) — 이름 오타이거나 job 이 제거됐다."
    )


def test_mapping_keys_are_real_endpoints():
    """매핑 key 가 실제 엔드포인트 — 엔드포인트 제거 후 남은 stale 매핑을 잡는다."""
    stale = sorted(set(CRON_PATH_TO_JOB) - _cron_endpoint_paths())
    assert not stale, (
        f"CRON_PATH_TO_JOB 에 실존하지 않는 엔드포인트 경로가 있음: {stale} — "
        "엔드포인트가 제거됐는데 매핑이 남았다."
    )


# --------------------------------------------------------------------------------------
# 역방향: job → 엔드포인트 (유령 job 차단) / reverse: no ghost jobs
# --------------------------------------------------------------------------------------

def test_no_ghost_job_without_matching_endpoint():
    """🔴 대응 엔드포인트가 없는 유령 job 이 없다 — 수동 트리거 불가한 job 은 운영에서 손댈 수 없다.

    주기 job 은 장애 시 운영자가 즉시 1회 수동 실행할 수 있어야 한다
    (`POST /api/internal/cron/<path>`). 엔드포인트 없는 job 은 그 경로를 잃는다.
    """
    ghosts = sorted(_job_names() - set(CRON_PATH_TO_JOB.values()))
    assert not ghosts, (
        f"대응 cron 엔드포인트가 없는 job: {ghosts} — "
        "src/api/internal_cron.py 에 수동 트리거 엔드포인트를 추가하고 "
        "CRON_PATH_TO_JOB 에 매핑할 것."
    )


# --------------------------------------------------------------------------------------
# 예외 목록의 위생 / hygiene of the exception list
# --------------------------------------------------------------------------------------

def test_unscheduled_paths_are_real_endpoints():
    """예외 목록에 stale 항목이 없다 — 사라진 엔드포인트의 면제가 남으면 갭 판단이 흐려진다."""
    stale = sorted(set(UNSCHEDULED_CRON_PATHS) - _cron_endpoint_paths())
    assert not stale, (
        f"UNSCHEDULED_CRON_PATHS 에 실존하지 않는 엔드포인트가 남아있음: {stale} — "
        "엔드포인트 제거 시 예외 등재도 함께 제거할 것."
    )


def test_unscheduled_and_scheduled_are_disjoint():
    """한 경로가 스케줄과 예외에 동시 등재될 수 없다 — 의도가 모호해진다."""
    both = sorted(set(UNSCHEDULED_CRON_PATHS) & set(CRON_PATH_TO_JOB))
    assert not both, (
        f"스케줄 매핑과 예외 목록에 동시 등재된 경로: {both} — "
        "주기 실행하거나(CRON_PATH_TO_JOB) 안 하거나(UNSCHEDULED_CRON_PATHS) 둘 중 하나여야 한다."
    )


def test_every_unscheduled_path_documents_its_reason():
    """🔴 미스케줄 사유가 기계 검증 가능한 형태로 남아있다 — "그냥 빠뜨림" 과 구별되어야 한다.

    사유를 주석이 아니라 **값**으로 두는 이유: 주석은 검증할 수 없어서 시간이 지나면
    "왜 빠져 있는지 아무도 모르는 항목" 으로 퇴화한다.
    """
    for path, reason in UNSCHEDULED_CRON_PATHS.items():
        assert isinstance(reason, str) and len(reason.strip()) >= 20, (
            f"{path!r} 의 미스케줄 사유가 비었거나 너무 짧다 ({reason!r}) — "
            "왜 주기 실행하지 않는지(비용·쿼터·사용자 결정 대기 등)를 서술할 것."
        )


def test_no_cron_endpoint_is_currently_unscheduled():
    """🔴 현재 상태 고정 — 미스케줄 예외가 **하나도 없다** (6종 전부 스케줄).

    2026-07-19 사용자 결정으로 `scan-security` 가 활성화되면서 예외 목록이 비었다.
    예외가 조용히 늘어나면 "cron 엔드포인트는 있는데 아무도 안 부른다" 가 다시 정상처럼
    보인다 — 항목 추가는 이 단언을 **의도적으로** 고쳐야만 가능하게 만들어 PR 검토를 강제한다.
    Pins the empty exception list: adding one requires a deliberate edit here.
    """
    assert set(UNSCHEDULED_CRON_PATHS) == set(), (
        f"미스케줄 예외가 생겼다: {sorted(UNSCHEDULED_CRON_PATHS)}\n"
        "→ 정말 주기 실행이 불필요한지 PR 에서 검토하고, 사유를 값으로 남길 것."
    )
