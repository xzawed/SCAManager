"""SQLAlchemy engine, session factory, and DB failover logic."""
import concurrent.futures
import logging
import socket
import threading
import time
from urllib.parse import urlparse, parse_qs

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from src.config import settings

logger = logging.getLogger(__name__)

# DB liveness probe — 가장 가벼운 쿼리, 4곳에서 사용
_HEALTH_QUERY = text("SELECT 1")


def _ipv4_connect_args(url: str) -> dict:
    """Railway 컨테이너에서 IPv6 아웃바운드 차단 문제 해결.
    Python socket으로 IPv4 주소를 조회한 뒤 psycopg2 hostaddr에 전달.
    libpq는 hostaddr로 직접 TCP 연결하고, SSL 인증서는 host(hostname)로 검증.
    SQLite는 hostaddr를 지원하지 않으므로 건너뜀.
    DNS 조회 hang 방지: executor.shutdown(wait=False)로 스레드 완료 대기 없이 반환.

    Resolves IPv6 outbound blocking in Railway containers.
    Resolves the hostname to an IPv4 address via Python socket, then passes it as
    psycopg2 hostaddr. libpq connects directly via hostaddr while validating the SSL
    certificate against host (hostname). Skipped for SQLite (no hostaddr support).
    DNS hang prevention: returns without waiting for thread via executor.shutdown(wait=False).
    """
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
    - URL query에 sslmode가 이미 포함된 경우 connect_args에 중복 설정하지 않음
    SQLite URL은 hostaddr/sslmode 모두 미적용.

    Builds connection arguments from environment variables.
    - db_force_ipv4=True: Force IPv4 on Railway/Supabase environments.
    - db_sslmode: Explicit SSL mode for on-premises PostgreSQL etc.
    - Skips adding sslmode to connect_args if the URL query already contains it.
    SQLite URLs: neither hostaddr nor sslmode is applied.
    """
    args: dict = {}
    parsed = urlparse(url)
    if not parsed.hostname:  # SQLite
        return args
    if settings.db_force_ipv4:
        args.update(_ipv4_connect_args(url))
    # URL query에 sslmode가 없을 때만 전역 설정 적용 (Supabase URL 중복 방지)
    url_sslmode = parse_qs(parsed.query).get("sslmode")
    if settings.db_sslmode and not url_sslmode:
        args["sslmode"] = settings.db_sslmode
    return args


class Base(DeclarativeBase):  # pylint: disable=too-few-public-methods
    """SQLAlchemy declarative base for all ORM models."""


class FailoverSessionFactory:  # pylint: disable=too-many-instance-attributes
    """Primary DB 장애 시 Fallback DB로 자동 전환하는 세션 팩토리.

    SessionLocal = FailoverSessionFactory(primary_url, fallback_url)
    with SessionLocal() as db:  # 기존 코드와 동일하게 동작
        ...

    fallback_url이 None이면 단일 엔진 모드로 동작 (기존과 동일).

    Session factory that automatically fails over to a fallback DB on primary failure.

    SessionLocal = FailoverSessionFactory(primary_url, fallback_url)
    with SessionLocal() as db:  # works identically to existing code
        ...

    If fallback_url is None, operates in single-engine mode (identical to the original).
    """

    def __init__(self, primary_url, fallback_url: str | None = None):
        self._primary_url = primary_url if isinstance(primary_url, str) else None
        self._fallback_url = fallback_url
        self._lock = threading.Lock()
        self._active = "primary"
        self._probe_thread: threading.Thread | None = None

        # primary_url은 URL 문자열 또는 이미 생성된 Engine 객체 모두 허용
        if isinstance(primary_url, str):
            self._primary_engine = self._create_engine(primary_url)
        else:
            self._primary_engine = primary_url  # Engine 객체 직접 사용 (테스트용)

        self._fallback_engine = (
            self._create_engine(fallback_url) if fallback_url else None
        )

        # Primary/Fallback 각각 독립적인 sessionmaker 유지
        self._primary_maker = sessionmaker(
            autocommit=False, autoflush=False, bind=self._primary_engine
        )
        self._fallback_maker = (
            sessionmaker(autocommit=False, autoflush=False, bind=self._fallback_engine)
            if self._fallback_engine is not None else None
        )

        if self._fallback_engine is not None:
            self._start_probe_thread()

    def _create_engine(self, url: str):
        """URL에 맞는 SQLAlchemy 엔진을 생성한다."""
        is_pg = url.startswith("postgresql")
        kwargs: dict = {"connect_args": _build_connect_args(url)}
        if is_pg:
            kwargs.update({
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
                "pool_pre_ping": True,
            })
        return create_engine(url, **kwargs)

    def _start_probe_thread(self) -> None:
        """Primary 복구 감지용 daemon 스레드를 시작한다.
        Starts a daemon thread that monitors primary DB recovery."""
        self._probe_thread = threading.Thread(
            target=self._probe_primary_loop, daemon=True, name="db-failover-probe"
        )
        self._probe_thread.start()

    def _switch_to(self, target: str) -> None:
        """활성 maker를 전환한다. 호출 전 self._lock 획득 필요.
        Switches the active session maker. Caller must hold self._lock."""
        self._active = target
        logger.warning("DB failover: switched to %s", target)

    def _current_maker(self):
        """현재 활성 maker를 반환한다.
        Returns the currently active session maker."""
        if self._active == "fallback" and self._fallback_maker is not None:
            return self._fallback_maker
        return self._primary_maker

    def __call__(self) -> Session:
        """세션을 반환한다. Fallback 설정 시 연결 실패에 대해 자동 전환한다.
        Returns a session. Automatically switches to fallback on connection failure when configured."""
        if self._fallback_maker is None:
            # 단일 엔진 모드 — 기존 동작과 동일
            # Single-engine mode — identical to original behavior
            return self._primary_maker()

        # 이미 fallback 모드면 primary 시도 없이 바로 fallback 사용
        if self._active == "fallback":
            session = self._fallback_maker()
            try:
                session.execute(_HEALTH_QUERY)
                return session
            except Exception:
                session.close()
                raise

        try:
            session = self._primary_maker()
            try:
                session.execute(_HEALTH_QUERY)
                return session
            except OperationalError:
                session.close()
                raise
        except OperationalError:
            with self._lock:
                if self._active == "primary" and self._fallback_maker is not None:
                    self._switch_to("fallback")
            session = self._fallback_maker()
            try:
                session.execute(_HEALTH_QUERY)
                return session
            except Exception:
                session.close()
                raise

    @property
    def active_db(self) -> str:
        """현재 활성 DB: "primary" 또는 "fallback".
        Currently active DB: "primary" or "fallback"."""
        return self._active

    def _probe_primary_loop(self) -> None:
        """Fallback 중에 Primary 복구를 주기적으로 확인하고 자동 복귀한다.
        Periodically probes primary DB recovery during fallback and auto-returns when healthy."""
        interval = settings.db_failover_probe_interval
        while True:
            time.sleep(interval)
            if self._active != "fallback":
                continue
            try:
                with self._primary_engine.connect() as conn:
                    conn.execute(_HEALTH_QUERY)
                with self._lock:
                    if self._active == "fallback":
                        self._switch_to("primary")
            except Exception:  # noqa: BLE001 — probe 실패는 무시  # pylint: disable=broad-exception-caught
                pass


_FALLBACK_URL = settings.database_url_fallback or None
SessionLocal = FailoverSessionFactory(settings.database_url, _FALLBACK_URL)
engine = SessionLocal._primary_engine  # pylint: disable=protected-access  # alembic/env.py 호환


def get_db():
    """FastAPI dependency injection용 세션 제너레이터.
    Session generator for FastAPI dependency injection."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
