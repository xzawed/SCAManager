"""Telegram 봇 텍스트 명령 및 cmd: 콜백 핸들러.
Telegram bot text-command and cmd: callback handlers.

계층 의존성 규칙: repositories/*, models/*, services/analytics_service, config.py 만 import.
Layer dependency rule: only import from repositories/*, models/*, services/analytics_service, config.py.
api/, ui/, webhook/ import 금지.
Do NOT import from api/, ui/, webhook/.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.repository import Repository
from src.repositories import repository_repo, user_repo
from src.services.analytics_service import moving_average, weekly_summary

logger = logging.getLogger(__name__)

# 미연결 사용자 공통 안내 메시지
# Common prompt message for disconnected users
_NOT_CONNECTED_MSG = (
    "먼저 /connect <코드>로 계정을 연결하세요.\n"
    "Connect your account first: /connect <code>"
)


@dataclass(frozen=True)
class CmdCallback:
    """파싱된 cmd: 콜백 데이터.
    Parsed cmd: callback data.
    """

    # 동작 동사 (예: "stats", "connect")
    # Action verb (e.g. "stats", "connect")
    verb: str
    # 대상 리소스 PK (없을 수 있음)
    # Target resource PK (may be absent)
    payload_id: int | None
    # HMAC 토큰 — 위변조 방지
    # HMAC token — tamper prevention
    token: str


def parse_cmd_callback(data: str) -> CmdCallback | None:
    """cmd: 접두사 콜백 데이터를 파싱한다.
    Parse cmd: prefix callback data.

    Returns None for gate: callbacks or malformed data.

    형식 1: cmd:<verb>:<token>           (3-part, id 없음)
    Format 1: cmd:<verb>:<token>          (3-part, no id)
    형식 2: cmd:<verb>:<id>:<token>       (4-part, id 포함)
    Format 2: cmd:<verb>:<id>:<token>     (4-part, with id)
    """
    # cmd: 접두사가 아니면 처리 대상 아님
    # Not a cmd: callback — skip
    if not data.startswith("cmd:"):
        return None

    parts = data.split(":")

    if len(parts) == 3:
        # cmd:connect:<token> 패턴 — id 없음
        # cmd:connect:<token> pattern — no id
        _, verb, token = parts
        return CmdCallback(verb=verb, payload_id=None, token=token)

    if len(parts) == 4:
        # cmd:<verb>:<id>:<token> 패턴
        # cmd:<verb>:<id>:<token> pattern
        _, verb, raw_id, token = parts
        try:
            return CmdCallback(verb=verb, payload_id=int(raw_id), token=token)
        except ValueError:
            # id가 정수로 변환 불가 → 잘못된 데이터
            # id cannot be converted to int → malformed data
            return None

    # 파트 수가 맞지 않는 잘못된 형식
    # Wrong number of parts — malformed
    return None


def handle_message_command(db: Session, telegram_user_id: str, text: str) -> str:
    """Telegram 텍스트 명령을 처리하고 응답 텍스트를 반환한다.
    Handle a Telegram text command and return the reply text.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        telegram_user_id: 발신 Telegram 사용자 ID / Sender Telegram user ID
        text: 수신된 명령 텍스트 / Received command text

    Returns:
        Telegram 응답 텍스트 / Telegram reply text
    """
    text = (text or "").strip()

    # /connect 는 미연결 사용자도 사용 가능 — 먼저 처리
    # /connect is allowed for unlinked users — handle first
    if text.startswith("/connect"):
        parts = text.split(maxsplit=1)
        otp = parts[1].strip() if len(parts) > 1 else ""
        return _handle_connect(db, telegram_user_id, otp)

    # 그 외 명령은 연결된 사용자만 허용
    # All other commands require a linked user
    user = user_repo.find_by_telegram_user_id(db, telegram_user_id)
    if user is None:
        return _NOT_CONNECTED_MSG

    if text.startswith("/stats"):
        parts = text.split(maxsplit=1)
        repo_name = parts[1].strip() if len(parts) > 1 else ""
        return _handle_stats(db, user, repo_name)

    if text.startswith("/settings"):
        return _handle_settings(db, user)

    # 알 수 없는 명령 — 도움말 반환
    # Unknown command — return help
    return (
        "지원하지 않는 명령입니다. 사용 가능: /stats <repo>, /settings, /connect <코드>\n"
        "Unknown command. Available: /stats <repo>, /settings, /connect <code>"
    )


def _handle_connect(db: Session, telegram_user_id: str, otp: str) -> str:
    """OTP를 검증해 계정을 연결한다.
    Validate OTP and link the Telegram account.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        telegram_user_id: 연결할 Telegram 사용자 ID / Telegram user ID to link
        otp: 사용자 입력 OTP / User-supplied OTP

    Returns:
        성공 또는 실패 메시지 / Success or failure message
    """
    # OTP 인수 미입력 시 사용법 안내
    # Show usage if OTP argument is missing
    if not otp:
        return "사용법: /connect <6자리 코드>\nUsage: /connect <6-digit code>"

    # 만료되지 않은 OTP로 사용자 조회
    # Look up user by unexpired OTP
    found = user_repo.find_by_otp(db, otp)
    if found is None:
        return "OTP가 잘못되었거나 만료되었습니다.\nInvalid or expired OTP."

    try:
        # telegram_user_id 매핑 + OTP 무효화
        # Map telegram_user_id and nullify OTP
        user_repo.set_telegram_user_id(db, found.id, telegram_user_id)
    except ValueError:
        # 이미 다른 사용자에게 연결된 Telegram ID
        # Telegram ID already linked to another user
        return (
            "이 Telegram 계정은 이미 다른 사용자에게 연결되어 있습니다.\n"
            "This Telegram account is already linked to another user."
        )

    name = found.display_name or found.github_login or "사용자"
    return f"✅ {name} 님의 계정이 연결되었습니다!\n✅ Account linked for {name}!"


def _handle_stats(db: Session, user: Any, repo_name: str) -> str:
    """리포지토리 주간 통계를 반환한다.
    Return weekly stats for a repository.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        user: 인증된 User ORM 인스턴스 / Authenticated User ORM instance
        repo_name: 조회할 리포 전체 이름 (owner/repo) / Target repo full name
    """
    # 리포 인수 미입력 시 사용법 안내
    # Show usage if repo argument is missing
    if not repo_name:
        return (
            "사용법: /stats <리포지토리 전체 이름 (owner/repo)>\n"
            "Usage: /stats <owner/repo>"
        )

    # 리포 존재 여부 및 소유권 확인
    # Verify repo existence and ownership
    repo = repository_repo.find_by_full_name(db, repo_name)
    if repo is None or repo.user_id != user.id:
        return (
            f"리포지토리를 찾을 수 없습니다: {repo_name}\n"
            f"Repository not found: {repo_name}"
        )

    # 주간 집계 — 현재 시각 기준 7일 전부터
    # Weekly summary — from 7 days before current time
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    summary = weekly_summary(db, repo.id, week_start, now=now)

    if summary is None:
        return (
            f"📊 {repo_name}\n"
            f"최근 7일간 분석 데이터가 없습니다.\n"
            f"No analysis data in the past 7 days."
        )

    avg = summary["avg_score"]
    count = summary["count"]

    # 이동 평균과 비교한 추세 계산 (샘플 부족 시 생략)
    # Compute trend vs moving average (omit when samples are insufficient)
    avg_ma = moving_average(db, repo.id, now=now)
    trend = ""
    if avg_ma is not None:
        diff = round(avg - avg_ma, 1)
        trend = f" (7일 이동평균 대비 {diff:+.1f}점 / vs 7d avg {diff:+.1f})"

    return (
        f"📊 {repo_name}\n"
        f"최근 7일 분석: {count}건\n"
        f"평균 점수: {avg:.1f}점{trend}\n"
        f"최저: {summary['min_score']} / 최고: {summary['max_score']}\n"
        f"Analyses (7d): {count} | Avg: {avg:.1f}{trend}"
    )


def _handle_settings(db: Session, user: Any) -> str:
    """사용자의 등록 리포지토리 목록을 반환한다.
    Return the user's registered repository list.

    Args:
        db: SQLAlchemy 세션 / SQLAlchemy session
        user: 인증된 User ORM 인스턴스 / Authenticated User ORM instance
    """
    # 사용자 소유 리포를 이름순 정렬로 조회
    # Fetch user-owned repos sorted alphabetically
    repos = db.scalars(
        select(Repository)
        .where(Repository.user_id == user.id)
        .order_by(Repository.full_name)
    ).all()

    if not repos:
        return "등록된 리포지토리가 없습니다.\nNo repositories registered."

    lines = ["📋 등록된 리포지토리 / Registered repositories:"]
    for repo in repos:
        lines.append(f"  • {repo.full_name}")
    return "\n".join(lines)
