"""alembic `sqlalchemy.url` 주입이 DB 비밀번호를 예외로 유출하지 않는가 (backlog R8 — 실경로).

## 사고 기전 (2026-08-10 Grok claim-review `019febc8` 가 반증으로 찾아냄)

`alembic/env.py` 는 앱 설정의 URL 을 `config.set_main_option("sqlalchemy.url", …)` 로 주입한다.
그 저장소는 **ConfigParser** 이고 `BasicInterpolation` 이 `%` 를 보간 문법으로 해석한다.
그래서 비밀번호에 `%` 가 있으면 **`ValueError` 가 URL 전문(비밀번호 포함)을 메시지에 담는다**:

    ValueError: invalid interpolation syntax in
      'postgresql://appuser:p%40ss%2Fword@db.example.com:5432/scadb' at position 22

🔴 **이것은 이론적 경로가 아니다.** 비밀번호에 특수문자가 있으면 percent-encoding 이 **표준
관행**이므로(`@`→`%40`, `/`→`%2F`) 오히려 흔한 형태다. 그리고 Railway 는 배포마다
`preDeployCommand = alembic upgrade head` 를 돌리므로, 이 예외는 **배포 로그로 직행**한다.
그 시점엔 앱 로깅 필터(`_RedactSecretsFilter`)가 붙기 전이라 계층 2 backstop 도 닿지 않는다.

🔴 **R8 원장의 초판 서술은 여기서 틀렸다** — *"활성 유출 경로는 존재하지 않는다"* 고 적었는데
SQLAlchemy 축만 보고 **alembic 축을 보지 않았다**. 도구(SQLAlchemy)가 안전하다는 것이
그 도구를 감싼 배선까지 안전하다는 뜻은 아니다.

## 이 파일이 강제하는 것

1. **결함의 존재 증명(대조군)** — 이스케이프 없이는 실제로 ValueError 가 비밀번호를 담는다.
   이 단언이 거짓이 되면(예: alembic 이 보간을 끄면) 아래 수정은 불필요해진 것이므로 알아야 한다.
2. **수정의 계약** — `%%` 이스케이프가 **두 읽기 경로**(`get_main_option` / `get_section`)에서
   모두 원본을 복원한다. `engine_from_config` 는 후자를 쓰므로 한쪽만 맞으면 마이그레이션이 깨진다.
3. **배선** — `env.py` 가 실제로 이스케이프를 거쳐 넣는다(산문이 아니라 AST 로 판정).
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess  # nosec B404
import sys

import pytest
from alembic.config import Config

_ENV_PY = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "env.py"

# percent-encoding 된 비밀번호 = 특수문자 포함 시의 표준 형태(@ → %40, / → %2F).
_PW = "p%40ss%2Fword"
_URL = f"postgresql://appuser:{_PW}@db.example.com:5432/scadb"


def test_unescaped_url_leaks_the_password_into_the_exception():
    """🔴 대조군 — 결함이 실재함을 증명한다. 이게 통과해야 아래 수정이 의미를 갖는다."""
    cfg = Config()
    with pytest.raises(ValueError) as excinfo:
        cfg.set_main_option("sqlalchemy.url", _URL)
    assert _PW in str(excinfo.value), (
        "ConfigParser 가 더 이상 URL 을 예외에 담지 않는다면 이 축의 전제가 바뀐 것이다"
    )


@pytest.mark.parametrize("password", [_PW, "plain", "100%safe", "a%%b", "pw%"])
def test_escaped_url_round_trips_through_both_read_paths(password):
    """🔴 두 경로 **모두** 원본을 복원해야 한다.

    `run_migrations_offline` 은 `get_main_option`, `run_migrations_online` 의
    `engine_from_config` 는 `get_section` 을 쓴다. 한쪽만 맞으면 온라인 마이그레이션이
    잘못된 URL 로 접속을 시도한다(조용한 오작동).
    """
    url = f"postgresql://appuser:{password}@db.example.com:5432/scadb"
    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    assert cfg.get_main_option("sqlalchemy.url") == url
    assert cfg.get_section(cfg.config_ini_section, {})["sqlalchemy.url"] == url


def test_env_py_escapes_before_set_main_option():
    """🔴 배선(불변식 3) — `env.py` 가 **맨 URL** 을 넣지 않는다.

    산문 grep 이 아니라 AST 로 판정한다: `set_main_option` 호출의 두 번째 인자가
    단순 속성 접근(`settings.effective_migration_url`)이면 이스케이프가 없는 것이다.
    """
    tree = ast.parse(_ENV_PY.read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "set_main_option"
    ]
    assert calls, "env.py 에 set_main_option 호출이 없다 — 이 가드의 대상이 사라졌다"
    for call in calls:
        assert len(call.args) >= 2, "set_main_option 인자 형태가 바뀌었다"
        value = call.args[1]
        assert not isinstance(value, ast.Attribute), (
            "URL 이 이스케이프 없이 그대로 들어간다 — 비밀번호에 `%` 가 있으면 "
            "ValueError 가 URL 전문을 배포 로그에 남긴다"
        )
        # 이스케이프 호출이 실제로 걸려 있는가 (`.replace("%", "%%")`)
        replaces = [
            n for n in ast.walk(value)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "replace"
        ]
        assert replaces, "이스케이프(`replace`) 호출이 없다"


def test_alembic_cli_does_not_leak_the_password(tmp_path):
    """🔴 **CLI 축** — 실제 `alembic` 프로세스를 띄워 비밀번호가 출력에 없는지 본다.

    이 테스트가 따로 필요한 이유(적대 검증 지적): 이 브랜치의 다른 가드는 전부
    **로깅 축**(`_RedactSecretsFilter`)에 있다. 그런데 이 유출은 `logging` 을 타지 않고
    **excepthook** 으로 stderr 에 직행하므로, 로깅 축 가드가 전건 초록인 채로 CLI 경로가
    뚫려 있을 수 있다 — [[feedback-false-enforcer-is-worse-than-none]] 의 형태다.

    `railway.toml` 의 `preDeployCommand = alembic upgrade head` 가 정확히 이 경로다.
    접속 불가 주소(127.0.0.1:1)를 써서 DNS 없이 즉시 실패시키되, 유출은 그 **이전**
    단계(`set_main_option`)에서 나므로 관측에는 영향이 없다.
    """
    password = "p%40ssw0rd-LEAKME"
    env = {
        **os.environ,
        "DATABASE_URL": f"postgresql://appuser:{password}@127.0.0.1:1/scadb",
        "MIGRATION_DATABASE_URL": "",
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_ENV_PY.parents[1]), env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "접속 불가 주소인데 성공했다 — 시나리오 전제가 깨졌다"
    assert password not in combined, (
        "alembic CLI 출력에 비밀번호가 남는다 — Railway preDeployCommand 가 매 배포마다 "
        "이 경로를 타므로 배포 로그에 평문으로 축적된다.\n"
        f"출력 꼬리: {combined[-400:]}"
    )
    # 대조군 — 시나리오가 실제로 그 지점을 지났는지(공허한 통과 방지).
    assert "127.0.0.1" in combined or "OperationalError" in combined, (
        "접속 단계까지 도달하지 못했다 — 유출 지점을 지났는지 알 수 없다(공허한 단언)"
    )
