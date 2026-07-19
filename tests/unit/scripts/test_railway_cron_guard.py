"""railway.toml cron 재도입 차단 가드 (2026-07-19 P0 — 5종 전부 미실행 사고).

🔴 사고 / Incident: `[[deploy.cronJobs]]` 는 **Railway 스키마에 존재하지 않는 키**라 조용히
무시됐다. Railway cron 은 서비스당 **단일** `deploy.cronSchedule`(또는 대시보드 Cron Schedule)
이며 배열을 지원하지 않는다. 실측: SCAManager `cronSchedule=null`·`nextCronRunAt=null` →
weekly/trend/retry/orphan/retention 5종이 **한 번도 실행되지 않았다**.
결정적 증거 = 20:00 UTC 스윕 3.5시간 경과 후에도 만료 캐시 8건 잔존(`purge_expired` 는
`expires_at < now` 를 지우므로 실행됐다면 0이어야 함).
`[[deploy.cronJobs]]` is not a Railway key — silently ignored; all 5 jobs never ran.

🔴 이 가드의 역할 전환: 이전 버전은 cron **명령의 따옴표·`-f`** 를 검사했다(따옴표 결함은
실재했으나 명령 자체가 실행되지 않아 무의미했다). 이제는 **무효 키의 재도입 자체를 차단**하고,
대체 기전(인앱 스케줄러)이 살아 있는지 단언한다.
Role change: previously validated cron command quoting; now blocks reintroduction of the inert
key and asserts the replacement mechanism (in-app scheduler) is present.
"""
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY_TOML = _ROOT / "railway.toml"


def _railway_config():
    return tomllib.loads(_RAILWAY_TOML.read_text(encoding="utf-8"))


def test_inert_cronjobs_key_not_reintroduced():
    """🔴 `[[deploy.cronJobs]]` 재도입 차단 — Railway 가 인식하지 않는 키다.

    이 키를 다시 넣으면 "cron 을 설정했다"는 착각만 남고 아무것도 실행되지 않는다
    (정확히 이번 사고의 형태 — 설정은 존재했고, 실행은 0이었다).
    """
    deploy = _railway_config().get("deploy", {})
    assert "cronJobs" not in deploy, (
        "railway.toml 에 `[[deploy.cronJobs]]` 재도입됨 — Railway 스키마에 없는 키라 무시된다.\n"
        "주기 작업은 src/scheduler.py (인앱 스케줄러)에 등록하세요."
    )


def test_no_localhost_curl_cron_pattern_in_config():
    """🔴 `curl http://localhost:$PORT` 자기호출 패턴 재도입 차단.

    Railway cron 서비스는 start command 를 **대신** 실행하므로, 그 컨테이너에는 웹서버가
    떠 있지 않다 — 자기 자신에게 curl 하는 구조는 성립할 수 없다.
    """
    raw = _RAILWAY_TOML.read_text(encoding="utf-8")
    # 주석(설명)은 허용, 실제 설정 라인만 검사 / comments are fine; check config lines only
    config_lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    offending = [ln for ln in config_lines if "localhost:$PORT" in ln and "curl" in ln]
    assert not offending, f"자기호출 curl cron 패턴 재도입: {offending}"


def test_scheduler_module_exists_as_replacement():
    """🔴 대체 기전이 실재 — 무효 설정만 지우고 대체를 안 만들면 기능이 사라진다."""
    assert (_ROOT / "src" / "scheduler.py").is_file(), (
        "src/scheduler.py 부재 — railway.toml cron 제거의 대체 기전이 없다"
    )


def test_startcommand_still_present():
    """대조군 — 유효한 deploy 키는 그대로 (제거가 과했는지 확인)."""
    deploy = _railway_config().get("deploy", {})
    assert deploy.get("startCommand"), "startCommand 소실 — cron 블록 제거가 과했다"
    assert deploy.get("preDeployCommand"), "preDeployCommand 소실"
