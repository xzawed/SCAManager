"""Notifier 채널 패키지.

본 `__init__.py` 가 import 되면 모든 notifier 모듈이 자동 로드되어
Notifier Protocol 구현체가 `src/notifier/registry.py::REGISTRY` 에
등록된다 (analyzer/tools 선례 패턴).

등록 순서 = `REGISTRY` 순회 순서 = 알림 발송 우선순위.
"""
# pylint: disable=unused-import
import src.notifier.telegram  # noqa: F401 — register() 자동 트리거
import src.notifier.discord  # noqa: F401
import src.notifier.slack  # noqa: F401
import src.notifier.webhook  # noqa: F401
import src.notifier.email  # noqa: F401
import src.notifier.n8n  # noqa: F401
import src.notifier.github_commit_comment  # noqa: F401
import src.notifier.github_issue  # noqa: F401
