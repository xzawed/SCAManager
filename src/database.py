import socket as _socket

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from src.config import settings

# Railway 컨테이너에서 IPv6 아웃바운드 차단 → IPv4 우선 강제
_orig_getaddrinfo = _socket.getaddrinfo

def _prefer_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    results = _orig_getaddrinfo(host, port, _socket.AF_INET, type, proto, flags)
    if results:
        return results
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

_socket.getaddrinfo = _prefer_ipv4


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
