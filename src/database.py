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
    DNS 조회가 Railway에서 hang할 수 있으므로 3초 타임아웃 적용."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:  # SQLite (hostname이 None인 경우)
            return {}
        port = parsed.port or 5432
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(socket.getaddrinfo, hostname, port, socket.AF_INET)
            infos = future.result(timeout=3)
        if infos:
            return {"hostaddr": infos[0][4][0]}
    except Exception:  # nosec B110
        pass
    return {}


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args=_ipv4_connect_args(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
