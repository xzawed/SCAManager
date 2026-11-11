"""관측 역할 비밀번호 설정 도구 — SCRAM 검증값 · .env 한 줄 갱신 · 비밀번호 비출력 (회고 원장 L02).
Observer password setup: SCRAM verifier, one-line .env update, password never printed.
"""
# fail-open-reviewed: 읽는 파일은 이 시험이 tmp_path 에 직접 쓴 .env 이고, 판정 대상이 그 원문 바이트 자체다(주석·산문 없음)
import base64
import io

import pytest

from scripts import observer_setup as setup

# 실제 PostgreSQL 17 이 같은 비밀번호 · 소금으로 pg_authid 에 저장한 값(로컬 컨테이너에서 받아 적었다)
# The value real PostgreSQL 17 stored in pg_authid for this password and salt (taken from a local container).
_VECTOR_PASSWORD = "observer-vector-password-0123456789abcdef"
_VECTOR_SALT = base64.b64decode("0OQGVhJJhYGL/anajHcnRQ==")
_VECTOR = ("SCRAM-SHA-256$4096:0OQGVhJJhYGL/anajHcnRQ==$nIKfNLZ5IO/vowGh0q/p2vnvSB9SOFVG2fIhhyGrsMQ=:"
           "b+mZimqtzgNHAvZumvhBTnn7taIcfEdjp/IonzZTFLc=")
_POOLER = "postgresql://scamanager_app.abcref:apppw@aws-1-us-east-1.pooler.supabase.com:6543/postgres"


def test_scram_verifier_matches_postgres():
    """PostgreSQL 이 만든 검증값과 바이트까지 같다 / byte-identical to PostgreSQL's own verifier."""
    assert setup.scram_verifier(_VECTOR_PASSWORD, salt=_VECTOR_SALT) == _VECTOR


def test_scram_verifier_rejects_non_ascii():
    with pytest.raises(ValueError):
        setup.scram_verifier("비밀번호")


def test_new_password_is_url_safe_and_long():
    pw = setup.new_password()
    assert len(pw) == 48 and all(c in "0123456789abcdef" for c in pw)


def test_upsert_replaces_one_line_and_keeps_the_rest(tmp_path):
    """같은 키 줄은 하나로 바꾸고(중복 제거), 주석 · 다른 줄 · CRLF 는 그대로 / replace one key, keep everything else."""
    env = tmp_path / ".env"
    env.write_bytes(b"A=1\r\n# OBSERVER_DATABASE_URL=commented\r\nOBSERVER_DATABASE_URL=old\r\n"
                    b"B=2\r\nexport OBSERVER_DATABASE_URL=dup\r\n")
    setup.upsert_env_line(env, "OBSERVER_DATABASE_URL", "new")
    assert env.read_bytes() == (b"A=1\r\n# OBSERVER_DATABASE_URL=commented\r\nOBSERVER_DATABASE_URL=new\r\n"
                                b"B=2\r\n")
    assert not (tmp_path / ".env.observer-tmp").exists()


def test_upsert_appends_when_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"A=1\n")
    setup.upsert_env_line(env, "OBSERVER_DATABASE_URL", "new")
    assert env.read_bytes() == b"A=1\nOBSERVER_DATABASE_URL=new\n"


def test_pooler_target_reads_host_and_ref_only(tmp_path):
    """.env 의 풀러 주소에서 호스트 · ref 만 가져온다 / host and project ref from a pooler URL in .env."""
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=sqlite:///local.db\n"
                   f"DATABASE_URL_WORKER=\"{_POOLER}\"\n", encoding="utf-8")
    assert setup.pooler_target(env) == ("aws-1-us-east-1.pooler.supabase.com", "abcref", "DATABASE_URL_WORKER")


def test_main_writes_the_url_and_prints_only_the_verifier(tmp_path):
    """주소는 .env 에만, 화면에는 검증값 SQL 만 — 비밀번호 · 다른 변수 값은 출력에 없다.
    The URL goes to .env only; the output carries the verifier SQL, never the password or other values."""
    env = tmp_path / ".env"
    env.write_text(f"DATABASE_URL={_POOLER}\n", encoding="utf-8")
    out = io.StringIO()
    assert setup.main([], env_file=env, out=out) == 0
    url = setup.read_env_values(env, ("OBSERVER_DATABASE_URL",))["OBSERVER_DATABASE_URL"]
    password = url.split(":", 2)[2].split("@", 1)[0]
    assert url == setup.observer_url("aws-1-us-east-1.pooler.supabase.com", "abcref", password)
    printed = out.getvalue()
    assert password not in printed and "apppw" not in printed
    assert "ALTER ROLE scamanager_observer WITH LOGIN PASSWORD 'SCRAM-SHA-256$4096:" in printed
    # 출력된 검증값이 .env 의 비밀번호로 만든 것이다 / the printed verifier belongs to the stored password
    verifier = printed.split("PASSWORD '", 1)[1].split("'", 1)[0]
    salt = base64.b64decode(verifier.split(":", 1)[1].split("$", 1)[0])
    assert setup.scram_verifier(password, salt=salt) == verifier


def test_main_without_a_pooler_url_asks_for_flags(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=sqlite:///local.db\n", encoding="utf-8")
    out = io.StringIO()
    assert setup.main([], env_file=env, out=out) == 2
    assert "--host" in out.getvalue()
    assert "OBSERVER_DATABASE_URL" not in env.read_text(encoding="utf-8")
