"""GateAction 추상 기반 클래스 + GateContext + 전역 레지스트리.
GateAction abstract base class + GateContext + global registry.

P0-H 불변 조건: 각 Action.execute()는 내부에서 독립 SessionLocal()을 열어야 함.
asyncio.gather 병렬 실행 시 공유 Session → identity map 오염·PendingRollbackError 방지.
P0-H invariant: each Action.execute() must open its own independent SessionLocal().
Sharing a Session across asyncio.gather coroutines corrupts the SQLAlchemy identity map.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config_manager.manager import RepoConfigData


@dataclass(frozen=True)
class GateContext:  # pylint: disable=too-many-instance-attributes
    """Gate 실행 컨텍스트 — 불변 (frozen). Action 간 공유하되 수정 금지.
    Immutable execution context shared across Gate Actions. Do not mutate.

    too-many-instance-attributes (8/7): 기존 컨텍스트에 commit_sha 를 확장한 사례 —
    이 dataclass 는 게이트 1회 실행의 응집 단위라 분할하면 Action 시그니처가 쪼개져
    응집이 깨진다 (testing.md R0914 결정 트리: 기존 시그니처 확장 → inline disable + 사유).
    too-many-instance-attributes (8/7): commit_sha extends the existing context. This dataclass is
    the cohesive unit of one gate run; splitting it would fragment every Action signature
    (testing.md R0914 decision tree: extending an existing signature → inline disable + reason).
    """
    repo_name: str
    pr_number: int
    analysis_id: int
    result: dict
    github_token: str
    config: "RepoConfigData"
    score: int
    # 실제 분석된 커밋 SHA — auto-merge 가 이 SHA 에만 결속되도록 관통시킨다.
    # 미전달(None) 시 결속 가드 미적용(하위 호환) — 호출부는 항상 전달할 것.
    # The commit SHA that was actually analyzed — threaded through so auto-merge binds only to it.
    # None (omitted) disables the binding guard for backward compatibility; callers should always pass it.
    commit_sha: str | None = None


class GateAction(ABC):
    """Gate 옵션 추상 기반 클래스.
    Abstract base class for Gate options.

    P0-H: execute() 내부에서 반드시 독립 SessionLocal()을 열 것.
    P0-H: execute() must open its own SessionLocal() — never share with gather siblings.
    """

    @abstractmethod
    async def execute(self, ctx: GateContext) -> None:
        """액션을 실행한다. 예외는 내부에서 처리하거나 로깅 후 return.
        Execute the action. Handle exceptions internally or log and return.
        """

    @abstractmethod
    def is_applicable(self, config: "RepoConfigData") -> bool:
        """설정에 따라 이 액션을 실행할지 여부를 반환한다.
        Return True if this action should run given the config.
        """


# 전역 액션 레지스트리 — 각 action 모듈이 import 시점에 register()로 등록
# Global action registry — populated by each action module at import time
GATE_ACTIONS: list[GateAction] = []


def register(action: GateAction) -> None:
    """액션 인스턴스를 레지스트리에 등록한다.
    Register an action instance in the global registry.
    """
    GATE_ACTIONS.append(action)
