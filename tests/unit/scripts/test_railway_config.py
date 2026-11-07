"""`scripts/railway_config.py` — 배포 설정을 «변수 값 없이» 읽는 계기의 판정 시험.
Tests for the safe Railway deploy-config reader: values must never be printed.

계기를 뒤집어 본다(verify.md 「판정식을 쓸 때」 4).

- claimed(이름이 약속하는 것): 서비스 `variables` · 최상위 `sharedVariables` 의 값은 출력에 없다.
  서비스마다 `deploy` · `build` 는 그대로 나온다. 못 읽으면(JSON 아님 · CLI 실패 · 서비스 없음) red.
- cheap(첫 출력만 보고 적은 가장 싼 과정): «최상위 `variables` 키 하나를 지운다».
  - claimed \\ cheap → 서비스 안 `variables` 와 최상위 `sharedVariables` 에 심은 값 — 반드시 사라져야 한다.
  - cheap \\ claimed → «아무것도 안 찍기» 도 값은 안 샌다 — 그래서 `deploy` 값이 **남는지** 함께 본다.

이 파일의 심는 값은 실제 비밀이 아니라 고유 표지 문자열이다(`_PLANT_*`).
Planted strings are unique markers, never real secrets.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import railway_config  # noqa: E402  # pylint: disable=wrong-import-position,import-error

_PLANT_SERVICE = "PLANT-service-variable-value-7f3a"
_PLANT_SHARED = "PLANT-shared-variable-value-91c2"
_PLANT_RAW = "PLANT-raw-non-json-output-55e0"
_PLANT_NESTED = "PLANT-nested-under-deploy-0b6d"

_DEPLOY = {
    "startCommand": "",
    "preDeployCommand": ["alembic upgrade head"],
    "healthcheckPath": "/health",
    "healthcheckTimeout": 60,
    "multiRegionConfig": {"us-east4-eqdc4a": {"numReplicas": 1}},
}
_BUILD = {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"}


def _config_json() -> str:
    return json.dumps({
        "services": {
            "svc-1": {
                "deploy": _DEPLOY,
                "build": _BUILD,
                "variables": {"API_KEY": {"value": _PLANT_SERVICE, "isSealed": False}},
                "networking": {"serviceDomains": {}},
            },
        },
        "sharedVariables": {"SHARED_KEY": {"value": _PLANT_SHARED}},
    })


def _fake_run(stdout: str, returncode: int = 0, stderr: str = ""):
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    return run, calls


_FAKE_EXE = "/fake/bin/railway"


def _main(monkeypatch, capsys, stdout: str, argv=(), returncode: int = 0, stderr: str = ""):
    run, calls = _fake_run(stdout, returncode, stderr)
    monkeypatch.setattr(railway_config.shutil, "which", lambda name: _FAKE_EXE)
    monkeypatch.setattr(railway_config.subprocess, "run", run)
    code = railway_config.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err, calls


def test_variable_values_never_reach_the_output(monkeypatch, capsys):
    """🔴 claimed \\ cheap — 서비스 안 variables 와 최상위 sharedVariables 의 값이 둘 다 사라진다."""
    code, out, err, _ = _main(monkeypatch, capsys, _config_json())
    assert code == 0, err
    assert _PLANT_SERVICE not in out + err, "서비스 변수 값이 출력에 남았다"
    assert _PLANT_SHARED not in out + err, "공유 변수 값이 출력에 남았다"


def test_deploy_and_build_survive_unchanged(monkeypatch, capsys):
    """🔴 cheap \\ claimed — 아무것도 안 찍어도 값은 안 샌다. 그래서 비교에 쓰는 값이 남는지 본다."""
    code, out, _, _ = _main(monkeypatch, capsys, _config_json())
    assert code == 0
    shown = json.loads(out)
    assert shown == {"services": {"svc-1": {"deploy": _DEPLOY, "build": _BUILD}}}


def test_it_asks_the_cli_for_the_same_config_the_docs_compare(monkeypatch, capsys):
    """CLI 에 묻는 명령은 문서가 대조하던 바로 그 설정이다 — `--environment` 는 그대로 넘긴다."""
    _, _, _, calls = _main(monkeypatch, capsys, _config_json(), argv=["--environment", "production"])
    assert [cmd for cmd, _ in calls] == [
        [_FAKE_EXE, "environment", "config", "--json", "--environment", "production"],
    ]


def test_cli_is_resolved_through_path_lookup(monkeypatch, capsys):
    """Windows 의 npm shim(`railway.cmd`)은 확장자 없는 이름으로 실행되지 않는다 — PATH 해석 결과를 쓴다."""
    seen = []
    monkeypatch.setattr(railway_config.shutil, "which", lambda name: seen.append(name) or _FAKE_EXE)
    run, calls = _fake_run(_config_json())
    monkeypatch.setattr(railway_config.subprocess, "run", run)
    assert railway_config.main([]) == 0
    capsys.readouterr()
    assert seen == ["railway"]
    assert calls[0][0][0] == _FAKE_EXE


def test_non_json_output_is_red_and_never_echoed(monkeypatch, capsys):
    """🔴 못 읽으면 red — 원문에는 값이 들어 있을 수 있으니 에러에도 싣지 않는다."""
    code, out, err, _ = _main(monkeypatch, capsys, f"oops {_PLANT_RAW}")
    assert code != 0
    assert _PLANT_RAW not in out + err


@pytest.mark.parametrize("stdout", [None, ""], ids=["none", "empty"])
def test_missing_stdout_is_red_without_raising(monkeypatch, capsys, stdout):
    """stdout 이 비거나 None 이어도 예외 없이 red (Grok G3 지적 — json.loads 의 TypeError)."""
    code, _, _, _ = _main(monkeypatch, capsys, stdout)
    assert code != 0


def test_cli_failure_is_red_without_echoing_either_stream(monkeypatch, capsys):
    """CLI 가 실패하면 red — 그때 나온 stdout·stderr 어느 쪽도 싣지 않는다."""
    code, out, err, _ = _main(monkeypatch, capsys, _PLANT_RAW, returncode=1,
                              stderr=f"error near {_PLANT_SERVICE}")
    assert code != 0
    assert _PLANT_RAW not in out + err
    assert _PLANT_SERVICE not in out + err


def test_missing_cli_is_red(monkeypatch, capsys):
    """railway CLI 가 없으면 red — «안 쟀음» 을 «통과» 로 접지 않는다."""
    monkeypatch.setattr(railway_config.shutil, "which", lambda name: None)
    assert railway_config.main([]) != 0


def test_cli_vanishing_between_lookup_and_run_is_red(monkeypatch, capsys):
    """찾은 뒤 실행 직전에 사라져도 red — 예외로 죽지 않는다."""
    def run(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(railway_config.shutil, "which", lambda name: _FAKE_EXE)
    monkeypatch.setattr(railway_config.subprocess, "run", run)
    assert railway_config.main([]) != 0


@pytest.mark.parametrize("payload", [
    pytest.param({"sharedVariables": {}}, id="no-services-key"),
    pytest.param({"services": {}}, id="empty-services"),
    pytest.param({"services": []}, id="services-not-a-map"),
    pytest.param([], id="top-level-not-a-map"),
])
def test_nothing_to_show_is_red(monkeypatch, capsys, payload):
    """서비스를 하나도 못 읽으면 red — 빈 출력이 «설정 없음» 으로 읽히면 안 된다."""
    code, _, _, _ = _main(monkeypatch, capsys, json.dumps(payload))
    assert code != 0


def test_service_without_kept_sections_is_not_shown(monkeypatch, capsys):
    """남길 절이 없는 서비스는 빈 객체로도 찍지 않는다 — 하나도 없으면 red (Grok G3 반례)."""
    only_vars = {"services": {"svc-1": {"variables": {"X": {"value": "{}"}}}}}
    code, out, err, _ = _main(monkeypatch, capsys, json.dumps(only_vars))
    assert code != 0
    assert out == ""
    mixed = json.loads(_config_json())
    mixed["services"]["svc-2"] = {"variables": {"Y": {"value": _PLANT_SERVICE}}}
    code, out, _, _ = _main(monkeypatch, capsys, json.dumps(mixed))
    assert code == 0
    assert list(json.loads(out)["services"]) == ["svc-1"]


def test_values_nested_under_kept_sections_are_refused(monkeypatch, capsys):
    """🔴 CLI 가 나중에 deploy 안에 variables 를 실어도 새지 않는다 — 남길 절 안에서 다시 보고 거절한다."""
    leaky = json.loads(_config_json())
    leaky["services"]["svc-1"]["deploy"] = dict(_DEPLOY, variables={"K": {"value": _PLANT_NESTED}})
    code, out, err, _ = _main(monkeypatch, capsys, json.dumps(leaky))
    assert code != 0
    assert _PLANT_NESTED not in out + err
