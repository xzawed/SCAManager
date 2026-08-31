"""RuboCop static analysis tool — Ruby 전용 정적분석 (Phase D.3).

_RuboCopAnalyzer 는 Analyzer Protocol 을 구현하며 registry.register() 로 등록된다.
rubocop 바이너리가 없으면 is_enabled() 가 False 를 반환해 조용히 skip 된다.

rubocop --format json 은 stdout 에 단일 JSON 객체를 출력한다:
  {"files": [{"offenses": [{"severity": ..., "cop_name": ..., ...}]}], ...}

severity mapping:
  error/fatal → Severity.ERROR
  refactor/convention/warning → Severity.WARNING

category mapping:
  cop_name 이 "Security/" 로 시작 → Category.SECURITY (RuboCop Security cop)
  그 외 → Category.CODE_QUALITY
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.analyzer.io.tools._common import analysis_failed
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

_ERROR_SEVERITIES: frozenset[str] = frozenset({"error", "fatal"})


class _RuboCopAnalyzer:
    name = "rubocop"
    category = Category.CODE_QUALITY  # 기본 code_quality, Security/* cop 시 override

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"ruby"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Ruby 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """rubocop 바이너리 설치 여부 확인."""
        return shutil.which("rubocop") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """rubocop JSON 출력을 파싱해 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["rubocop", "--format", "json", ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # 🔴 판별식은 「파싱되는가」가 아니다 — rubocop 은 **크래시해도 유효한 JSON** 을 낸다.
            #    실측(1.90.0, 없는 파일): exit=2 · stdout 231자 · `{"files": [], "summary":
            #    {"offense_count": 0, "target_file_count": 1}}`. `json.loads` 가 성공하므로
            #    「비-JSON 이면 raise」 관용구는 이 크래시를 그대로 통과시킨다.
            #    실제 분석은 대상 파일마다 `files` 항목을 만든다(위반 0건이어도). 그래서
            #    판별식은 **`files` 가 비었는가**다. `target_file_count` 는 크래시에도 1 이라 못 쓴다.
            # Measured: rubocop emits valid JSON with an empty `files` array when it cannot
            # analyze, so "unparseable JSON" is not the crash signal — an empty `files` is.
            if not r.stdout.strip():
                raise analysis_failed("rubocop", ctx, r, "produced no output")
            try:
                payload = json.loads(r.stdout)
            except json.JSONDecodeError as exc:
                raise analysis_failed(
                    "rubocop", ctx, r, "produced unparseable JSON") from exc
            if not payload.get("files"):
                raise analysis_failed(
                    "rubocop", ctx, r, "analyzed no file (empty `files`)")
            return _parse_rubocop_json(r.stdout, ctx.language)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("rubocop timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("rubocop unavailable for %s: %s", ctx.tmp_path, exc)
            return []


def _map_severity(severity_str: str) -> Severity:
    """rubocop severity 문자열을 Severity enum 으로 매핑."""
    return Severity.ERROR if severity_str in _ERROR_SEVERITIES else Severity.WARNING


def _map_category(cop_name: str) -> Category:
    """cop_name 기준 category 매핑 — `Security/` 접두사는 security, 나머지는 code_quality."""
    return Category.SECURITY if cop_name.startswith("Security/") else Category.CODE_QUALITY


def _parse_rubocop_json(json_text: str, language: str) -> list[AnalysisIssue]:
    """rubocop JSON 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 JSON 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.
    files 배열 전체를 순회하며 각 offense 를 AnalysisIssue 로 변환.
    """
    data = json.loads(json_text)
    files = data.get("files", []) or []
    issues: list[AnalysisIssue] = []
    for file_entry in files:
        for offense in file_entry.get("offenses", []) or []:
            cop_name = offense.get("cop_name", "")
            location = offense.get("location", {}) or {}
            issues.append(AnalysisIssue(
                tool="rubocop",
                severity=_map_severity(offense.get("severity", "warning")),
                message=offense.get("message", "").strip() or cop_name,
                line=int(location.get("start_line", 0) or 0),
                category=_map_category(cop_name),
                language=language,
            ))
    return issues


def _register_rubocop_analyzers() -> None:
    register(_RuboCopAnalyzer())


_register_rubocop_analyzers()
