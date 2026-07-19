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
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY_TOML = _ROOT / "railway.toml"
_SCHEDULER = _ROOT / "src" / "scheduler.py"

# 분산 잠금 표지 — scheduler.py docstring 이 지목하는 해법(`DB 잠금(advisory lock) 도입 의무`).
# Marker for the distributed lock the scheduler docstring prescribes.
_LOCK_MARKER = "advisory"


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
    if _LOCK_MARKER in scheduler_src.lower():
        return None
    return (
        f"multiRegionConfig 총 replica={total} 인데 src/scheduler.py 에 분산 잠금"
        f"(`{_LOCK_MARKER}`)이 없다 — weekly 리포트가 **replica 수만큼 중복 발송**된다.\n"
        "→ 수평 확장 전 DB advisory lock 을 먼저 도입할 것 (scheduler.py docstring §한계)."
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


def test_guard_detects_scale_up_without_lock():
    """replica 2 + 잠금 없음 = 위반으로 탐지되는가."""
    scaled = {"deploy": {"multiRegionConfig": {"us-west2": {"numReplicas": 2}}}}
    assert _scale_without_lock_violation(scaled, "no lock here") is not None


def test_guard_allows_scale_up_when_lock_present():
    """replica 2 + advisory lock 있음 = 통과 — 막기만 하지 않고 해야 할 일로 유도한다."""
    scaled = {"deploy": {"multiRegionConfig": {"us-west2": {"numReplicas": 2}}}}
    assert _scale_without_lock_violation(scaled, "pg_advisory_lock(...)") is None


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
