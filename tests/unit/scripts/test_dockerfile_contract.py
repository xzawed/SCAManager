"""배포 빌드 정본 = 루트 `Dockerfile` — 기동·빌더·빌드 컨텍스트 계약.

The root Dockerfile is the build source: start command, builder and build-context contract.

## 왜 (Railway 문서, 2026-09-28 확인)

- Config as Code(`railway.toml`)는 폐기 예정이고 **2026-12-01** 부터 읽히지 않는다.
  그 뒤에는 대시보드 값이 적용된다. Nixpacks 도 폐기 예정이다.
- 루트 `Dockerfile` 은 매 배포 자동 감지된다 — 컷오프 뒤에도 남는 유일한 저장소 내 빌드 정의다.
- 🔴 Dockerfile 빌드의 시작 명령은 **exec 형**이라 `$PORT` 를 확장하지 않는다. 문서 처방:
  `/bin/sh -c "exec python main.py --port $PORT"`. 대시보드 Start Command 는 지금 확장되지 않는
  `uvicorn … --port $PORT` 를 들고 있으므로, `railway.toml` 이 `startCommand` 를 빼면 그 값이
  적용돼 기동이 깨진다 — 그래서 `railway.toml` 은 셸 래핑 형태를 **유지**한다.

Exec-form start commands do not expand `$PORT`; the dashboard still holds the raw command,
so railway.toml keeps a shell-wrapped startCommand until the file is retired.
"""
import fnmatch
import re
import shlex
import tomllib

import pytest

from tests.unit.scripts._dockerfile import (
    DOCKERFILE,
    DOCKERIGNORE,
    RAILWAY_TOML,
    dockerignore_patterns,
    instructions,
    serves_injected_port,
    start_argv,
    uvicorn_argv,
    without_port_value,
)


def _dockerfile() -> str:
    assert DOCKERFILE.is_file(), "루트 Dockerfile 이 없다 — Railway 가 Dockerfile 빌드를 할 수 없다"
    return DOCKERFILE.read_text(encoding="utf-8")


def _railway() -> dict:
    return tomllib.loads(RAILWAY_TOML.read_text(encoding="utf-8"))


# ── 판정식 자기검증 — 심은 입력으로 뒤집어 본다 ───────────────────────────


@pytest.mark.parametrize("dockerfile, expected", [
    # 🔴 exec 형 + $PORT = 글자 그대로 전달 — 이 PR 이 막으려는 형태
    ('CMD ["uvicorn", "src.main:app", "--port", "$PORT"]', False),
    # 셸 형은 Docker 가 /bin/sh -c 로 감싼다
    ("CMD exec uvicorn src.main:app --port ${PORT:-8000}", True),
    # exec 형이라도 명시 셸 래핑이면 확장된다
    ('CMD ["/bin/sh", "-c", "exec uvicorn src.main:app --port $PORT"]', True),
    # 🔴 셸 형이지만 포트가 고정 — 「셸 형인가」만 보는 싼 판정은 통과시킨다
    ("CMD exec uvicorn src.main:app --port 8000", False),
    # 🔴 주석 속 올바른 CMD 는 무시돼야 한다 — 실제 CMD 는 exec 형 $PORT
    ('# CMD exec uvicorn src.main:app --port $PORT\nCMD ["uvicorn", "--port", "$PORT"]', False),
    # 🔴 마지막 CMD 만 유효하다
    ('CMD exec uvicorn a:b --port $PORT\nCMD ["uvicorn", "a:b", "--port", "$PORT"]', False),
    # SHELL 지시어 뒤 셸 형은 그 셸로 감싼다
    ('SHELL ["/bin/bash", "-o", "pipefail", "-c"]\nCMD exec uvicorn a:b --port ${PORT:-8000}', True),
])
def test_port_judgement_on_planted_dockerfiles(dockerfile, expected):
    assert serves_injected_port(start_argv(dockerfile)) is expected


@pytest.mark.parametrize("start, expected", [
    ("uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers", False),
    ('/bin/sh -c "exec uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers"', True),
    # 🔴 따옴표 없는 래핑 — `-c` 스크립트가 `exec` 한 단어가 된다. 접두사만 보는 판정은 통과시킨다
    ("/bin/sh -c exec uvicorn src.main:app --port $PORT", False),
])
def test_port_judgement_on_planted_start_commands(start, expected):
    assert serves_injected_port(shlex.split(start)) is expected


# ── 이미지 기동 ────────────────────────────────────────────────────────────


def test_image_start_command_serves_the_injected_port():
    """🔴 이미지 CMD 가 `$PORT` 를 확장한다 — 대시보드 Start Command 를 비우면 이것이 적용된다."""
    argv = start_argv(_dockerfile())
    assert argv, "Dockerfile 에 CMD 가 없다"
    assert serves_injected_port(argv), (
        f"CMD 가 $PORT 를 확장하지 않는다: {argv}\n"
        "→ shell 형 `CMD exec uvicorn … --port ${PORT:-8000} …` 또는 `sh -c` 래핑으로 쓸 것."
    )


def test_image_has_no_entrypoint():
    """ENTRYPOINT 가 있으면 Railway Start Command 가 그 **인자**가 될지 대체할지 문서에 없다."""
    assert all(keyword != "ENTRYPOINT" for keyword, _ in instructions(_dockerfile()))


def test_image_puts_the_venv_on_path():
    """🔴 pre-deploy `alembic upgrade head` 는 exec 형이다 — venv bin 이 PATH 에 있어야 풀린다."""
    text = _dockerfile()
    venvs = re.findall(r"-m venv (\S+)", " ".join(a for k, a in instructions(text) if k == "RUN"))
    assert len(venvs) == 1, f"venv 생성 단계가 정확히 하나여야 한다: {venvs}"
    path_env = " ".join(a for k, a in instructions(text) if k == "ENV")
    assert f"PATH={venvs[0]}/bin:" in path_env, (
        f"ENV PATH 가 venv bin({venvs[0]}/bin)을 앞에 두지 않는다 — alembic·uvicorn 이 안 풀린다"
    )


def test_image_does_not_run_as_root():
    """분석기는 PR 의 신뢰할 수 없는 코드를 돈다 — 마지막 USER 는 root 가 아니어야 한다."""
    users = [args for keyword, args in instructions(_dockerfile()) if keyword == "USER"]
    assert users, "USER 지시어가 없다 — 컨테이너가 root 로 돈다"
    assert users[-1].split(":")[0] not in ("root", "0")


# ── railway.toml — 컷오프 전까지 여전히 읽힌다 ─────────────────────────────


def test_railway_toml_builds_from_the_dockerfile():
    """🔴 빌더는 DOCKERFILE, buildCommand 는 없다 — 빌드 정의가 두 곳이면 한쪽이 거짓이 된다."""
    build = _railway().get("build", {})
    assert build.get("builder") == "DOCKERFILE", f"builder={build.get('builder')!r}"
    leftover = sorted(set(build) & {"buildCommand", "nixpacksConfigPath", "nixpacksPlan"})
    assert not leftover, f"Dockerfile 빌드에서 쓰이지 않는 키가 남았다: {leftover}"


def test_railway_start_command_is_shell_wrapped():
    """🔴 startCommand 는 대시보드의 확장 안 되는 값을 덮는다 — 그러려면 스스로 셸 래핑이어야 한다."""
    start = _railway().get("deploy", {}).get("startCommand")
    if start is None:
        pytest.skip("railway.toml 이 startCommand 를 두지 않는다 — 이미지 CMD 가 정본")
    assert serves_injected_port(shlex.split(start)), (
        f"startCommand 가 $PORT 를 확장하지 않는다: {start!r}\n"
        "→ '/bin/sh -c \"exec uvicorn … --port $PORT …\"' 형태로 쓸 것(Railway 문서)."
    )


def test_both_start_commands_run_the_same_server():
    """두 시작 명령은 포트 값 표기만 다르고 나머지 플래그가 같다(--proxy-headers 등)."""
    start = _railway().get("deploy", {}).get("startCommand")
    if start is None:
        pytest.skip("railway.toml 이 startCommand 를 두지 않는다")
    image = uvicorn_argv(start_argv(_dockerfile()) or [])
    railway = uvicorn_argv(shlex.split(start))
    assert image and railway, "uvicorn 호출을 읽지 못했다 — 이 대조가 공허하다"
    assert without_port_value(image) == without_port_value(railway), (
        f"이미지 CMD 와 railway.toml startCommand 가 갈렸다:\n  image={image}\n  toml ={railway}"
    )


def test_healthcheck_and_predeploy_still_gate_the_deploy():
    """빌더를 바꿔도 배포 게이트(헬스체크·pre-deploy 마이그레이션)는 그대로다."""
    deploy = _railway().get("deploy", {})
    assert deploy.get("healthcheckPath") == "/health"
    assert deploy.get("healthcheckTimeout") == 60
    assert deploy.get("preDeployCommand") == "alembic upgrade head"


# ── 빌드 컨텍스트 ─────────────────────────────────────────────────────────


def _excluded(path: str, patterns: list[str]) -> bool:
    """Docker 의 `.dockerignore` 판정 근사 — 패턴이 경로 자신이나 상위 디렉토리에 맞으면 제외.

    `**/` 접두는 어느 깊이든 맞는다. 부정 패턴(`!`)은 이 저장소에서 쓰지 않는다(아래 단언).
    """
    parts = path.split("/")
    candidates = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    for pattern in patterns:
        anywhere = pattern.startswith("**/")
        bare = pattern.removeprefix("**/")
        for cand in candidates:
            if fnmatch.fnmatchcase(cand, pattern):
                return True
            if anywhere and fnmatch.fnmatchcase(cand.rsplit("/", 1)[-1], bare):
                return True
    return False


def test_dockerignore_judgement_on_planted_patterns():
    """판정식 뒤집기 — 상위 디렉토리 제외는 하위를 덮고, 비슷한 이름·다른 깊이는 덮지 않는다."""
    assert _excluded("docs/workflow/deploy.md", ["docs"]) is True
    assert _excluded("src/x/__pycache__/a.pyc", ["**/__pycache__"]) is True
    assert _excluded(".env.local", [".env.*"]) is True
    assert _excluded("src/env_utils.py", [".env", ".env.*"]) is False
    assert _excluded("alembic.ini", ["alembic"]) is False
    assert _excluded("src/docs/x.md", ["docs"]) is False


def test_dockerignore_keeps_secrets_out_of_the_image():
    """🔴 로컬 빌드 컨텍스트에는 개발 `.env` 가 있다 — 이미지에 실리면 레이어에 영구히 남는다."""
    patterns = dockerignore_patterns()
    assert not any(p.startswith("!") for p in patterns), "부정 패턴은 아래 판정이 모른다"
    for secret in (".env", ".env.production", ".git/config", ".dbpw"):
        assert _excluded(secret, patterns), f"{secret} 이 빌드 컨텍스트에 들어간다"


@pytest.mark.parametrize("needed", [
    "src/main.py", "alembic/env.py", "alembic.ini", "requirements.txt",
    "package.json", "package-lock.json", "setup.cfg",
])
def test_dockerignore_keeps_what_the_runtime_reads(needed):
    """런타임·빌드가 읽는 경로를 빼면 이미지가 조용히 달라진다(setup.cfg = flake8·pylint 설정)."""
    assert DOCKERIGNORE.is_file(), ".dockerignore 가 없다"
    assert not _excluded(needed, dockerignore_patterns()), f"{needed} 이 빌드 컨텍스트에서 빠진다"
