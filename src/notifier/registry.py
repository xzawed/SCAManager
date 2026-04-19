"""Notifier registry — Protocol + NotifyContext + REGISTRY."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class NotifyContext:  # pylint: disable=too-many-instance-attributes
    """알림 채널이 필요로 하는 모든 컨텍스트를 담는 데이터 클래스."""
    repo_name: str
    commit_sha: str
    pr_number: int | None
    score_result: Any          # ScoreResult
    analysis_results: list
    ai_review: Any             # AiReviewResult
    owner_token: str
    analysis_id: int | None
    result_dict: dict | None
    pr_head_ref: str | None
    config: Any                # RepoConfigData | None


@runtime_checkable
class Notifier(Protocol):
    """알림 채널 프로토콜 — 모든 채널이 구현해야 하는 인터페이스."""
    name: str

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """이 채널이 현재 컨텍스트에서 실행되어야 하는지 반환."""
        return False  # pragma: no cover

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        return  # pragma: no cover


REGISTRY: list[Notifier] = []


def register(notifier: Notifier) -> None:
    """알림 채널을 레지스트리에 등록한다."""
    REGISTRY.append(notifier)
