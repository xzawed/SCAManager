"""Gate Action registry — Protocol + GateContext + REGISTRY.

Analyzer/Notifier 선례와 동일 패턴. `GateAction` 3가지 (review_comment /
approve / auto_merge) 를 개별 객체로 분리해 REGISTRY 순회로 실행.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from src.config_manager.manager import RepoConfigData


@dataclass
class GateContext:
    """Gate action 이 필요로 하는 모든 컨텍스트를 담는 데이터 클래스."""

    repo_name: str
    pr_number: int
    analysis_id: int
    result: dict
    github_token: str
    db: Session
    config: RepoConfigData


@runtime_checkable
class GateAction(Protocol):
    """Gate action 프로토콜 — PR 이벤트에서 실행되어야 하는 개별 처리."""

    name: str

    def is_enabled(self, ctx: GateContext) -> bool:
        """이 action 이 현재 컨텍스트에서 실행되어야 하는지 반환."""
        return False  # pragma: no cover

    async def run(self, ctx: GateContext) -> None:
        """action 을 실행한다. 외부 상태 변경을 일으켜도 다른 action 의 실행은 계속된다."""
        return  # pragma: no cover


REGISTRY: list[GateAction] = []


def register(action: GateAction) -> None:
    """Gate action 을 레지스트리에 등록한다. 등록 순서 = 실행 순서.

    동일 name 중복 등록 시 무시 (analyzer Registry 선례).
    """
    if any(a.name == action.name for a in REGISTRY):
        return
    REGISTRY.append(action)
