"""GitHub webhook 무한 루프 방지 — 봇 발신 감지 + skip marker + rate limit.
GitHub webhook infinite-loop guard — bot sender detection, skip markers, rate limit.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from src.constants import BOT_LOGIN_WHITELIST, MAX_BOT_EVENTS_PER_HOUR, SKIP_CI_MARKERS

# 슬라이딩 윈도우 크기 (초) — 1시간
# Sliding window size in seconds — 1 hour
_WINDOW_SECONDS: int = 3600


def is_bot_sender(data: dict) -> bool:
    """봇 발신 여부 확인 — sender.type == "Bot" 이고 화이트리스트에 없으면 True.
    Check if the event was sent by a non-whitelisted bot.

    Returns True if sender.type is "Bot" and the login is not in BOT_LOGIN_WHITELIST.
    Returns False for human senders, missing sender field, or whitelisted bots.
    """
    # sender 필드 없으면 안전 기본값 False 반환
    # Return safe default False when sender field is absent
    sender = data.get("sender")
    if not sender:
        return False

    # sender.type 이 "Bot" 이 아니면 봇 아님
    # Not a bot if sender.type is not "Bot"
    if sender.get("type") != "Bot":
        return False

    # 화이트리스트 봇(github-actions, dependabot)은 허용
    # Whitelisted bots (github-actions, dependabot) are allowed
    login = sender.get("login", "")
    return login not in BOT_LOGIN_WHITELIST


def is_whitelisted_bot(data: dict) -> bool:
    """화이트리스트 봇 발신 여부 — sender.type == "Bot" 이고 BOT_LOGIN_WHITELIST 에 포함.
    Whitelisted bot sender — sender.type == "Bot" AND login is in BOT_LOGIN_WHITELIST.

    Layer 3-b 레이트 리미터를 화이트리스트 봇 한정으로 적용하기 위한 헬퍼.
    Helper used to scope the Layer 3-b rate limiter to whitelisted bots only.
    Phase 9 가이드: 사람 발신과 sender 누락은 무한 통과, 비-화이트리스트 봇은
    이미 Layer 2 (`is_bot_sender`) 에서 차단된다.
    Per Phase 9: human senders and missing-sender events pass freely; non-whitelisted
    bots are already blocked at Layer 2 (`is_bot_sender`).
    """
    sender = data.get("sender")
    if not sender:
        return False
    if sender.get("type") != "Bot":
        return False
    login = sender.get("login", "")
    return login in BOT_LOGIN_WHITELIST


def has_skip_marker(commit_message: str) -> bool:
    """커밋 메시지에 분석 skip 마커가 포함되어 있는지 확인 (대소문자 무시).
    Check whether a commit message contains any analysis skip marker (case-insensitive).

    Returns True if any string in SKIP_CI_MARKERS appears in commit_message.
    """
    # 대소문자 구분 없이 비교하기 위해 소문자 변환 — None 안전 처리 포함
    # Convert to lowercase for case-insensitive comparison — None-safe
    lower_message = (commit_message or "").lower()
    return any(marker in lower_message for marker in SKIP_CI_MARKERS)


class BotInteractionLimiter:  # pylint: disable=too-few-public-methods
    """리포별 봇 이벤트 슬라이딩 윈도우 레이트 리미터.
    Per-repo bot event rate limiter using a sliding window.

    MAX_BOT_EVENTS_PER_HOUR 초과 시 이벤트를 차단한다.
    Blocks events exceeding MAX_BOT_EVENTS_PER_HOUR within the last 3600 seconds.
    """

    def __init__(self) -> None:
        # 리포별 이벤트 타임스탬프 deque — {repo_full_name: deque[float]}
        # Per-repo event timestamp deque — {repo_full_name: deque[float]}
        self._events: dict[str, deque[float]] = {}
        # 멀티스레드 환경에서 self._events 접근 보호
        # Protect self._events access in multi-threaded environments
        self._lock = threading.Lock()

    def allow(self, repo_full_name: str) -> bool:
        """이벤트 허용 여부를 결정하고, 허용 시 타임스탬프를 기록한다.
        Decide whether to allow the event and record the timestamp if allowed.

        Returns True if the event is within the rate limit and records it.
        Returns False if the hourly limit has already been reached (event not recorded).
        """
        # 현재 시각 조회 — mock 교체 가능하도록 직접 time.time() 호출
        # Fetch current time — call time.time() directly so mocks work
        now = time.time()
        cutoff = now - _WINDOW_SECONDS

        # 경쟁 조건 방지 — check-and-append 원자적 실행
        # Prevent race conditions — atomic check-and-append
        with self._lock:
            # 리포 deque 초기화 (첫 이벤트)
            # Initialize deque for repo on first event
            if repo_full_name not in self._events:
                self._events[repo_full_name] = deque()

            window = self._events[repo_full_name]

            # 윈도우 밖(3600초 이전) 타임스탬프 제거
            # Evict timestamps older than the sliding window
            while window and window[0] <= cutoff:
                window.popleft()

            # 현재 윈도우 내 이벤트 수가 한도 이상이면 차단
            # Block if current window count has reached or exceeded the limit
            if len(window) >= MAX_BOT_EVENTS_PER_HOUR:
                return False

            # 허용 — 현재 타임스탬프 기록
            # Allowed — record current timestamp
            window.append(now)

        return True
