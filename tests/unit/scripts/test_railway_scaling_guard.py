"""인앱 스케줄러의 **단일 인스턴스 전제**를 railway.toml 수준에서 지키는 가드.

## 왜 필요한가 / Why

`src/scheduler.py` 는 단일 인스턴스를 전제한다(docstring §한계). replica 가 2개 이상이면
**weekly 리포트가 중복 발송**되고 GHAS 폴링이 쿼터를 2배 소모한다(retry 큐는 `FOR UPDATE
SKIP LOCKED`, sweep/retention 은 멱등이라 안전). 그런데 그 전제는 **저장소 밖 대시보드 설정**에
있어 조용히 깨질 수 있다 — 2026-07-19 P0(`[[deploy.cronJobs]]` 가 Railway 스키마에 없는 키라
무시돼 cron 5종이 한 번도 실행 안 됨)와 **같은 실패 모드**다.
The scheduler assumes a single instance; scaling up silently double-fires weekly reports.

## 🔴 이 파일이 막는 진짜 덫 / The actual trap this blocks

`docs/backlog.md` B2 는 이 문제의 해법으로 **"`railway.toml` 에 `numReplicas = 1` 명시 핀"** 을
지시했다. **그 지시대로 하면 P0 를 그대로 재현한다** — Railway 공식 config-as-code 레퍼런스
(`docs.railway.com/config-as-code/reference`) 의 `[deploy]` 유효 키는

    startCommand · preDeployCommand · multiRegionConfig · healthcheckPath ·
    healthcheckTimeout · restartPolicyType · restartPolicyMaxRetries ·
    cronSchedule · overlapSeconds · drainingSeconds

이고 **`numReplicas` 는 없다**. replica 수는 오직 `multiRegionConfig.<region>.numReplicas` 로만
지정된다. 즉 `[deploy] numReplicas = 1` 은 **조용히 무시되고**, 저장소에는 "핀했다" 는 흔적만
남아 다음 사람이 보호받고 있다고 **오인**한다 — 무효 설정 + 거짓 안심, P0 와 동형이다.
`numReplicas` is NOT a valid top-level `[deploy]` key — writing it yields inert config plus
false assurance, exactly the 2026-07-19 cron failure mode.

## 이 가드의 두 축 / Two assertions

1. **무효 키 차단** — `deploy.numReplicas` 가 나타나면 즉시 실패시켜 위 덫을 봉인한다.
2. **조건부 상향** — `multiRegionConfig` 로 실제 replica 를 2 이상 올리면 `scheduler.py` 에
   분산 잠금(advisory lock)이 있어야 통과한다. 막기만 하는 게 아니라 **해야 할 일로 유도**한다.

각 축은 합성 위반 입력으로 탐지력을 자가 검증한다(가드가 통과만 하고 아무것도 안 잡는 사고 차단).
"""
import ast
import textwrap
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY_TOML = _ROOT / "railway.toml"
_SCHEDULER = _ROOT / "src" / "scheduler.py"

# 🔴 분산 잠금 탐지는 **AST 호출**로 한다 — 문자열 검색 금지 (2026-07-19 회고 P1).
#
# 구 구현은 `"advisory" in scheduler_src.lower()` 였고, `scheduler.py` docstring 의
# **"수평 확장 시 DB 잠금(advisory lock) 도입 의무"** — 즉 *해야 할 일을 적어둔 처방 산문* —
# 이 그 검사를 만족시켰다. 결과: 이 축은 **한 번도 발화한 적이 없다**.
# 실측: `numReplicas = 5` 로 올려도 8 passed(가드가 막아야 할 바로 그 상황).
#
# 🔴 교훈: "잠금을 도입하라"고 **쓴 글**이 "잠금이 있다"는 **검사**를 통과시킨다.
#    처방을 구현으로 오인하는 것이 observer-lie 의 전형이다.
# The old substring check was satisfied by the docstring that PRESCRIBES the lock.
# Detect an actual call, never a mention.
_LOCK_CALLEES = frozenset({"pg_advisory_lock", "pg_try_advisory_lock", "pg_advisory_xact_lock"})


def _callee_name(node: ast.Call) -> str:
    """호출 대상 이름 — `f()` 와 `obj.f()` 양쪽 지원."""
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _has_lock_call(source: str) -> bool:
    """소스에 분산 잠금 **호출**이 실재하는가 — 주석·docstring·문자열은 세지 않는다.

    Whether the source actually CALLS a lock API; mentions in prose/strings do not count.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        isinstance(n, ast.Call) and _callee_name(n) in _LOCK_CALLEES
        for n in ast.walk(tree)
    )


def _railway_config() -> dict:
    return tomllib.loads(_RAILWAY_TOML.read_text(encoding="utf-8"))


def _bare_num_replicas_violation(config: dict) -> str | None:
    """`[deploy] numReplicas` (무효 키) 사용 여부 — 위반 시 사유 문자열 반환.

    Return a reason when the inert top-level `deploy.numReplicas` key is present.
    """
    if "numReplicas" in config.get("deploy", {}):
        return (
            "railway.toml 에 `[deploy] numReplicas` 가 있다 — Railway config-as-code 레퍼런스의 "
            "`[deploy]` 유효 키가 아니라 **조용히 무시된다**. 핀했다는 착각만 남는다.\n"
            "→ replica 를 지정하려면 `[deploy.multiRegionConfig.<region>] numReplicas = N` 형식만 유효."
        )
    return None


def _configured_replicas(config: dict) -> int:
    """multiRegionConfig 기준 총 replica 수 (미설정 시 Railway 기본 1)."""
    regions = config.get("deploy", {}).get("multiRegionConfig") or {}
    if not regions:
        return 1
    return sum(int(r.get("numReplicas", 1)) for r in regions.values())


def _scale_without_lock_violation(config: dict, scheduler_src: str) -> str | None:
    """replica ≥ 2 인데 분산 잠금이 없으면 사유 반환.

    Return a reason when replicas are scaled up without a distributed lock.
    """
    total = _configured_replicas(config)
    if total <= 1:
        return None
    if _has_lock_call(scheduler_src):
        return None
    return (
        f"multiRegionConfig 총 replica={total} 인데 src/scheduler.py 에 분산 잠금 **호출**이 없다 "
        f"— weekly 리포트가 **replica 수만큼 중복 발송**된다.\n"
        f"→ 수평 확장 전 {sorted(_LOCK_CALLEES)} 중 하나를 실제로 호출할 것.\n"
        "🔴 docstring 에 '도입 의무' 라고 적는 것만으로는 통과하지 않는다(구 구현의 결함)."
    )


# ── 현재 저장소 상태 / current repo state ────────────────────────────────


def test_bare_num_replicas_key_is_not_used():
    """🔴 `[deploy] numReplicas` 무효 키 차단 — backlog B2 가 지시한 덫을 봉인한다.

    이 키는 Railway 가 인식하지 않아 무시되며, 저장소에는 보호받고 있다는 **거짓 흔적**만 남는다.
    """
    violation = _bare_num_replicas_violation(_railway_config())
    assert violation is None, violation


def test_current_config_does_not_scale_without_a_lock():
    """현재 설정이 잠금 없이 replica 를 올리고 있지 않은지 — 실제 저장소 상태 단언."""
    violation = _scale_without_lock_violation(
        _railway_config(), _SCHEDULER.read_text(encoding="utf-8")
    )
    assert violation is None, violation


def test_scheduler_still_documents_the_single_instance_limit():
    """대조군 — 단일 인스턴스 전제가 scheduler.py 에 **명시**돼 있어야 한다.

    이 가드의 존재 이유가 그 전제이므로, 전제 설명이 사라지면 가드도 재검토 대상이다.
    """
    src = _SCHEDULER.read_text(encoding="utf-8")
    assert "다중 인스턴스" in src, (
        "scheduler.py 에서 다중 인스턴스 한계 설명이 사라졌다 — 전제가 바뀐 것인지 확인하고, "
        "분산 잠금이 도입됐다면 이 가드도 함께 갱신할 것"
    )


# ── 탐지력 자가 검증 (합성 위반) / self-verification with synthetic input ──


def test_guard_detects_bare_num_replicas():
    """🔴 무효 키를 실제로 잡는가 — 통과만 하고 아무것도 안 잡는 가드 차단."""
    assert _bare_num_replicas_violation({"deploy": {"numReplicas": 1}}) is not None


def test_guard_allows_valid_multi_region_form():
    """유효 형식(`multiRegionConfig`)은 무효 키 검사에 걸리지 않아야 한다 — 부정 통제."""
    valid = {"deploy": {"multiRegionConfig": {"us-west2": {"numReplicas": 1}}}}
    assert _bare_num_replicas_violation(valid) is None


# ── FIX-1 freeze 3종 (2026-07-19 회고 P1 — 죽은 축을 되살린 뒤 봉인) ──────
#
# 🔴 구 테스트는 **합성 문자열**(`"no lock here"` / `"pg_advisory_lock(...)"`)로만 검증해
# 통과했다. 그래서 실제 `scheduler.py` 의 docstring 이 마커를 만족시키는 것을 못 봤다.
# 이제 **실파일**로 검증한다 — 합성 입력만 쓰는 뮤테이션은 A2 를 명목상 충족하되 무의미하다.
# The old tests used only synthetic sources, so the real docstring's false-positive was invisible.


def test_scaling_up_the_real_repo_now_fails_without_a_lock():
    """🔴 freeze ①: **실제 저장소** replica 를 올리면 이 축이 반드시 발화한다.

    구 구현은 여기서 통과했다(실측: `numReplicas = 5` → 8 passed). 즉 이 단언이
    이 가드가 살아 있는지 여부를 결정한다.
    """
    scaled = {"deploy": {"multiRegionConfig": {"us-east4-eqdc4a": {"numReplicas": 5}}}}
    violation = _scale_without_lock_violation(scaled, _SCHEDULER.read_text(encoding="utf-8"))
    assert violation is not None, (
        "실제 scheduler.py 로 replica 5 를 올렸는데 통과했다 — 축이 죽어 있다. "
        "구 구현이 docstring 의 'advisory lock 도입 의무' 산문에 매칭되던 결함의 재발."
    )


def test_prose_only_mention_does_not_satisfy_the_lock_check():
    """🔴 freeze ②: 주석·docstring·문자열 안의 API 이름은 **잠금이 아니다**.

    구 결함의 정확한 형태다 — 처방을 구현으로 오인하지 않는지 직접 단언한다.
    """
    prose = textwrap.dedent(
        '''
        """수평 확장 시 pg_advisory_lock 도입 의무."""
        # TODO: pg_try_advisory_lock 을 붙일 것
        SQL_RECIPE = "SELECT pg_advisory_lock(1)"
        '''
    )
    scaled = {"deploy": {"multiRegionConfig": {"us-west2": {"numReplicas": 2}}}}
    assert _scale_without_lock_violation(scaled, prose) is not None, (
        "산문/문자열 언급이 잠금 검사를 통과시켰다 — 구 substring 결함 재발"
    )


def test_actual_lock_call_satisfies_the_check():
    """🔴 freeze ③: **실제 호출**이면 통과 — 막기만 하지 않고 해야 할 일로 유도한다.

    이게 없으면 가드가 영구 차단기가 되어 수평 확장 자체가 불가능해진다.
    """
    impl = textwrap.dedent(
        """
        def acquire(db):
            return db.execute(pg_advisory_lock(42))
        """
    )
    scaled = {"deploy": {"multiRegionConfig": {"us-west2": {"numReplicas": 2}}}}
    assert _scale_without_lock_violation(scaled, impl) is None, (
        "실제 잠금 호출이 있는데도 차단했다 — 가드가 확장을 영구 봉쇄한다"
    )


def test_guard_sums_replicas_across_regions():
    """다중 region 합산 — 각 region 이 1이어도 합이 2면 중복 실행이다."""
    two_regions = {
        "deploy": {
            "multiRegionConfig": {
                "us-west2": {"numReplicas": 1},
                "europe-west4-drams3a": {"numReplicas": 1},
            }
        }
    }
    assert _configured_replicas(two_regions) == 2
    assert _scale_without_lock_violation(two_regions, "no lock") is not None


# ── C 클러스터: 핀 자체와 TOML 구조를 지키는 단언 (2026-07-19 회고 P1) ────
#
# 🔴 위 가드들은 "replica 를 올렸을 때" 를 막지만, **핀을 통째로 지우는 것**은 못 막았다.
# 실측: `[deploy.multiRegionConfig...]` 섹션을 삭제해도 9 passed —
# `_configured_replicas` 가 미설정 시 Railway 기본 1 을 반환하므로 위반이 안 잡힌다.
# 즉 #1125 가 넣은 핀은 **어떤 테스트도 지키지 않는 상태**였다.
# The guards above block scaling UP but not deleting the pin outright (default-1 fallback).


def test_replica_pin_is_present_and_explicit():
    """🔴 핀이 **실재**해야 한다 — 지워도 green 이던 것 봉인.

    `_configured_replicas` 는 미설정 시 Railway 기본값 1 을 돌려주므로 "위반 없음" 으로
    보인다. 그래서 핀 삭제가 조용히 통과했다. 존재 자체를 단언한다.
    """
    deploy = _railway_config().get("deploy", {})
    regions = deploy.get("multiRegionConfig")
    assert regions, (
        "`[deploy.multiRegionConfig.<region>]` 핀이 없다 — 대시보드 스케일업을 설정으로 막지 못한다.\n"
        "🔴 `_configured_replicas` 의 기본값 1 fallback 때문에 다른 가드는 이걸 못 잡는다."
    )
    total = sum(int(r.get("numReplicas", 1)) for r in regions.values())
    assert total == 1, f"핀된 총 replica={total} — 단일 인스턴스 전제와 불일치"


def test_deploy_level_keys_are_not_absorbed_by_the_region_table():
    """🔴 TOML 테이블 섹션이 **뒤따르는 key 를 흡수**하는 결함 회귀 차단 (#1125 자백분).

    `[deploy.multiRegionConfig.X]` 를 `[deploy]` 중간에 두면 그 아래 key 들이 region
    블록으로 빨려 들어간다. 실측으로 `restartPolicyMaxRetries = 10` 이 사라졌었고,
    deploy 레벨 재시작 정책이 **조용히 증발**했다. 파싱 결과로 소속을 단언한다.
    A TOML table absorbs following keys; the pin section must stay last so [deploy] keys remain.
    """
    deploy = _railway_config().get("deploy", {})
    for key in ("startCommand", "preDeployCommand", "healthcheckPath",
                "healthcheckTimeout", "restartPolicyType", "restartPolicyMaxRetries"):
        assert key in deploy, (
            f"`[deploy] {key}` 가 사라졌다 — region 테이블이 흡수했을 가능성.\n"
            "🔴 `[deploy.multiRegionConfig.*]` 섹션은 **파일 맨 끝**에 두어야 한다."
        )
    # region 블록이 deploy 레벨 키를 삼키지 않았는지 직접 확인
    for region, body in (deploy.get("multiRegionConfig") or {}).items():
        stray = set(body) - {"numReplicas"}
        assert not stray, (
            f"region `{region}` 블록이 deploy 레벨 키를 흡수했다: {sorted(stray)}"
        )
