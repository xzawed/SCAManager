import concurrent.futures
import socket
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from src.config import settings


def _ipv4_connect_args(url: str) -> dict:
    """Railway 컨테이너에서 IPv6 아웃바운드 차단 문제 해결.
    Python socket으로 IPv4 주소를 조회한 뒤 psycopg2 hostaddr에 전달.
    libpq는 hostaddr로 직접 TCP 연결하고, SSL 인증서는 host(hostname)로 검증.
    SQLite는 hostaddr를 지원하지 않으므로 건너뜀.
    DNS 조회 hang 방지: executor.shutdown(wait=False)로 스레드 완료 대기 없이 반환."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:  # SQLite (hostname이 None인 경우)
            return {}
        port = parsed.port or 5432
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(socket.getaddrinfo, hostname, port, socket.AF_INET)
            infos = future.result(timeout=3)
        except (concurrent.futures.TimeoutError, socket.gaierror, OSError):  # nosec B110
            return {}
        finally:
            executor.shutdown(wait=False)  # DNS 스레드 완료 대기 없이 즉시 반환
        if infos:
            return {"hostaddr": infos[0][4][0]}
    except (OSError, ValueError):  # nosec B110
        pass
    return {}


def _build_connect_args(url: str) -> dict:
    """환경변수 기반 연결 인수를 구성한다.
    - db_force_ipv4=True: Railway IPv4 강제 (Supabase/Railway 환경)
    - db_sslmode: SSL 모드 명시 설정 (온프레미스 PostgreSQL 등)
    SQLite URL은 hostaddr/sslmode 모두 미적용."""
    args: dict = {}
    parsed = urlparse(url)
    if not parsed.hostname:  # SQLite
        return args
    if settings.db_force_ipv4:
        args.update(_ipv4_connect_args(url))
    if settings.db_sslmode:
        args["sslmode"] = settings.db_sslmode
    return args


class Base(DeclarativeBase):
    pass


_is_postgres = settings.database_url.startswith("postgresql")
_engine_kwargs: dict = {"connect_args": _build_connect_args(settings.database_url)}
if _is_postgres:
    # SQLite(SingletonThreadPool)는 QueuePool 파라미터 미지원 — PostgreSQL에만 적용
    _engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
    })
engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
