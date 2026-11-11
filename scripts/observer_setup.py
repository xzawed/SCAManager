"""관측 역할(`scamanager_observer`) 비밀번호 정하기 · 바꾸기 — 사용자가 실행한다 (회고 원장 L02).
Set or rotate the observer role's password. The operator runs this; the password itself is never printed.

    py -3 scripts/observer_setup.py                      # 호스트 · 프로젝트 ref 를 .env 의 풀러 주소에서 가져온다
    py -3 scripts/observer_setup.py --host <풀러 호스트> --ref <프로젝트 ref>

1. 새 비밀번호(무작위 192비트)를 만들어 리포 `.env` 의 `OBSERVER_DATABASE_URL` 줄에 쓴다(있으면 바꾼다).
   주소는 `postgresql://scamanager_observer.<ref>:<비밀번호>@<호스트>:6543/postgres?sslmode=require` 다.
2. Supabase SQL 편집기에 붙일 `ALTER ROLE … LOGIN PASSWORD` 문장을 출력한다. SCRAM 검증값이라 평문 비밀번호가
   없다 — 운영은 `log_statement=ddl` 이라 평문을 쓰면 서버 로그에 남는다.
3. 편집기에서 실행했으면 `py -3 scripts/observe_db.py --audit` 로 확인한다(Claude 가 돌려도 된다).

비밀번호는 화면에 찍지 않으므로 `!` 로 실행해도 대화 기록에 남지 않는다. 남는 것은 검증값뿐이다.
Writes OBSERVER_DATABASE_URL into the repo `.env` and prints only the SCRAM-verifier SQL (no plaintext),
because production logs DDL statements.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROLE = "scamanager_observer"
ENV_KEY = "OBSERVER_DATABASE_URL"
REPO = Path(__file__).resolve().parent.parent
ITERATIONS = 4096  # PostgreSQL scram_iterations 기본값 / PostgreSQL default
POOLER_PORT = 6543  # Supavisor 트랜잭션 모드 — 역할마다 따로 풀을 잡는다 / transaction mode, one pool per role
POOLER_SUFFIX = ".pooler.supabase.com"
# 호스트 · ref 를 빌려 올 .env 주소들 — 비밀번호 자리는 읽기만 하고 쓰지 않는다
# .env URLs that may lend the pooler host and project ref; their passwords are never used.
_SOURCE_KEYS = ("DATABASE_URL", "DATABASE_URL_WORKER", "MIGRATION_DATABASE_URL")


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def scram_verifier(password: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    """PostgreSQL 이 pg_authid 에 저장하는 꼴과 같은 SCRAM-SHA-256 검증값(RFC 5802 · 7677).
    Same SCRAM-SHA-256 verifier PostgreSQL stores in pg_authid (ASCII password: SASLprep is the identity)."""
    if not password.isascii():
        raise ValueError("ASCII 비밀번호만 / ASCII passwords only (SASLprep not implemented)")
    salt = salt if salt is not None else secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("ascii"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    return f"SCRAM-SHA-256${iterations}:{_b64(salt)}${_b64(stored_key)}:{_b64(server_key)}"


def new_password() -> str:
    # 16진 48자 = 192비트 — URL 에 넣어도 인코딩이 필요 없다 / hex only, no URL encoding needed
    return secrets.token_hex(24)


def _env_key(line: str) -> str | None:
    """`.env` 한 줄의 키 — 주석 · 빈 줄 · `=` 없는 줄은 None / the key of one .env line."""
    stripped = line.lstrip("﻿").strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):]
    return stripped.split("=", 1)[0].strip()


def read_env_values(env_file: Path, keys: tuple[str, ...]) -> dict[str, str]:
    """`.env` 에서 고른 키의 값만 읽는다(따옴표 벗김) / read only the chosen keys from .env."""
    if not env_file.is_file():
        return {}
    found: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        key = _env_key(line)
        if key in keys and key not in found:
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            found[key] = value
    return found


def pooler_target(env_file: Path) -> tuple[str, str, str] | None:
    """`.env` 의 Supabase 풀러 주소에서 (호스트, ref, 그 변수 이름) — 비밀번호는 보지 않는다.
    (host, project ref, variable name) from a Supabase pooler URL in .env; the password is not read."""
    values = read_env_values(env_file, _SOURCE_KEYS)
    for key in _SOURCE_KEYS:
        if key not in values:
            continue
        parts = urlsplit(values[key].replace("+psycopg2", "", 1))
        user = unquote(parts.username or "")
        host = parts.hostname or ""
        if host.endswith(POOLER_SUFFIX) and "." in user:
            return host, user.split(".", 1)[1], key
    return None


def observer_url(host: str, ref: str, password: str) -> str:
    return f"postgresql://{ROLE}.{ref}:{password}@{host}:{POOLER_PORT}/postgres?sslmode=require"


def upsert_env_line(env_file: Path, key: str, value: str) -> None:
    """`key=value` 줄을 넣거나 바꾼다 — 다른 줄 · 줄바꿈 꼴은 그대로, 같은 키의 중복 줄은 지운다.
    임시 파일에 다 쓴 뒤 바꿔 끼워, 중간에 실패해도 원본이 반쯤 잘린 채 남지 않는다.
    Insert or replace one line; other lines and line endings stay. Written to a temp file and swapped in,
    so a failure never leaves a truncated .env behind."""
    raw = env_file.read_bytes().decode("utf-8") if env_file.exists() else ""
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines, replaced = [], False
    for line in raw.splitlines():
        if _env_key(line) == key:
            if not replaced:
                lines.append(f"{key}={value}")
                replaced = True
            continue
        lines.append(line)
    if not replaced:
        lines.append(f"{key}={value}")
    tmp = env_file.with_name(env_file.name + ".observer-tmp")
    tmp.write_bytes((newline.join(lines) + newline).encode("utf-8"))
    os.replace(tmp, env_file)


def main(argv: list[str] | None = None, *, env_file: Path | None = None, out=None) -> int:
    out = out or sys.stdout
    env_file = env_file or REPO / ".env"
    parser = argparse.ArgumentParser(description="관측 역할 비밀번호 정하기 / set the observer role password")
    parser.add_argument("--host", help="Supabase 풀러 호스트 (예: aws-1-us-east-1.pooler.supabase.com)")
    parser.add_argument("--ref", help="Supabase 프로젝트 ref")
    args = parser.parse_args(argv)

    host, ref = args.host, args.ref
    if not (host and ref):
        target = pooler_target(env_file)
        if target is None:
            print("풀러 호스트와 프로젝트 ref 를 못 찾았다 — --host 와 --ref 를 함께 준다 "
                  "(Supabase 대시보드 Connect > Transaction pooler 주소에 둘 다 있다).", file=out)
            return 2
        host, ref, source = target
        print(f"호스트 · ref 를 .env 의 {source} 에서 가져왔다: {host} · {ref}", file=out)

    password = new_password()
    upsert_env_line(env_file, ENV_KEY, observer_url(host, ref, password))
    print(f"{env_file} 의 {ENV_KEY} 를 새 비밀번호로 썼다(값은 출력하지 않는다).", file=out)
    print("", file=out)
    print("== Supabase SQL 편집기에서 실행 (검증값만 — 평문 비밀번호 없음)", file=out)
    print(f"ALTER ROLE {ROLE} WITH LOGIN PASSWORD '{scram_verifier(password)}';", file=out)
    print("", file=out)
    print("실행했으면 확인: py -3 scripts/observe_db.py --audit", file=out)
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
