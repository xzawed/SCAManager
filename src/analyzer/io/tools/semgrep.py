"""Semgrep static analysis tool — 리포에 고정한 룰로 돌리는 범용 정적분석.

_SemgrepAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
semgrep 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.

룰은 레지스트리에서 받지 않는다 — `src/analyzer/configs/semgrep/rules/` 에 고정한 GitLab sast-rules 의
허용 라이선스 부분(MIT · Apache-2.0 · LGPL-3.0)만 쓴다. 출처 · 판 · 파일별 라이선스는 같은 폴더의
`MANIFEST.json` 이 갖는다. 레지스트리 룰(`p/default`)은 «내부 업무 목적 · 서비스 제공 금지» 라이선스라
서비스로 쓸 수 없고, 실행마다 레지스트리에 기대면 그 장애가 분석 실패가 된다(회고 원장 L03 P1-40).
Rules are not fetched from the registry: the analyzer runs the vendored, allowed-license subset of GitLab
sast-rules (MIT · Apache-2.0 · LGPL-3.0); provenance and per-file licenses live in MANIFEST.json.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import subprocess  # nosec B404
import tempfile
import threading
from pathlib import Path

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

_ERR_EXCERPT = 200
# 고정한 룰 폴더 — 리포 · 이미지에는 이 원본 YAML 만 둔다(라이선스 머리 포함)
# The vendored rule folder; only these original YAML files ship in the repo and the image.
RULES_DIR = Path(__file__).resolve().parents[2] / "configs" / "semgrep" / "rules"

# 룰 폴더 → 이 프로세스가 만든 JSON 묶음. 묶기는 프로세스마다 한 번이다.
# Rule folder -> the JSON bundle this process built; bundling happens once per process.
_BUNDLES: dict[Path, Path] = {}
_BUNDLE_LOCK = threading.Lock()


def _write_bundle(rules_dir: Path) -> Path:
    """고정 룰 YAML 을 JSON 한 파일로 묶어 이 프로세스만 쓰는 임시 폴더에 쓴다.

    semgrep 과 같은 갈래의 파서(ruamel · YAML 1.2)로 읽는다 — semgrep 이 깔린 환경에는 늘 있다.
    The rules are read with the parser family semgrep itself uses (ruamel, YAML 1.2), which is
    always installed alongside semgrep.
    """
    # pylint: disable=import-outside-toplevel
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    loader = YAML(typ="safe", pure=True)
    rules: list = []
    for path in sorted(p for p in rules_dir.rglob("*") if p.suffix in (".yml", ".yaml")):
        try:
            doc = loader.load(path.read_text(encoding="utf-8"))
        except YAMLError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        found = doc.get("rules") if isinstance(doc, dict) else None
        if not isinstance(found, list):
            raise ValueError(f"{path.name}: no rules list")
        rules.extend(found)
    if not rules:
        raise ValueError(f"no rules under {rules_dir}")
    # 권한 0700 폴더 — 다른 사용자가 묶음을 바꿔치기할 수 없다 / private 0700 dir: nobody else can swap the bundle
    out_dir = Path(tempfile.mkdtemp(prefix="scamanager-semgrep-"))
    atexit.register(shutil.rmtree, out_dir, True)
    out = out_dir / "rules.json"
    out.write_text(json.dumps({"rules": rules}, default=str), encoding="utf-8")
    return out


def rules_config() -> Path:
    """semgrep `--config` 에 줄 경로 — 고정 룰을 JSON 한 파일로 묶은 것.

    semgrep 은 YAML 설정을 위치 정보와 함께 읽느라 느리다: 고정 룰 폴더를 그대로 주면 실행마다 약 10 초,
    같은 룰을 JSON 으로 주면 약 2 초다(실측 · 결과 같음). 파일마다 semgrep 을 부르므로 이 차이가 파일 수만큼
    곱해진다. 묶기에 실패하면 경고를 남기고 폴더를 준다 — 같은 룰이고 느릴 뿐이다.

    semgrep parses YAML configs with position tracking and is slow: the vendored folder costs ~10 s per
    run, the same rules as JSON ~2 s (measured, same results). On failure it warns and falls back to the
    folder: the same rules, only slower.
    """
    with _BUNDLE_LOCK:
        bundle = _BUNDLES.get(RULES_DIR)
        if bundle is not None and bundle.is_file():
            return bundle
        try:
            bundle = _write_bundle(RULES_DIR)
        except (ImportError, OSError, ValueError) as exc:
            logger.warning("semgrep rule bundle unavailable, using the rule folder (slower): %s", exc)
            return RULES_DIR
        _BUNDLES[RULES_DIR] = bundle
        return bundle


def _fail(ctx, r, data=None) -> RuntimeError:
    """실패를 예외로 만든다 — `static.py` 는 `run()` 이 **올릴 때만** `incomplete` 로 승격한다.

    🔴 `[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.
    semgrep 은 java · scala · csharp · swift 의 **유일한** 분석기라 그 언어에서는 대체 관측면도
    없다(실측). 형제 `python.py::_fail` 과 같은 관용구다.
    JSON 을 찍고 실패한 실행은 stderr 가 비어 있어(실측) 원인을 JSON 의 `errors` 문장에서 가져온다.

    Returning [] would record the failure as a clean, complete run; semgrep is the only
    analyzer for four languages, so nothing else would notice. A failed run that printed JSON has
    an empty stderr, so the cause comes from the JSON `errors` messages.
    """
    errors = data.get("errors") if isinstance(data, dict) else None
    # 목록이 아니면 원인 문장이 없는 것으로 본다 — 숫자 · 참거짓은 돌 수 없어 여기서 다시 터진다(Grok 반례 96c93f6d)
    # Anything but a list carries no messages; a number or boolean is not iterable.
    messages = [str(e.get("message", "")) for e in (errors if isinstance(errors, list) else [])
                if isinstance(e, dict)]
    detail = ("; ".join(m for m in messages if m)
              or str(getattr(r, "stderr", "") or r.stdout or "")).strip()[:_ERR_EXCERPT]
    return RuntimeError(
        f"semgrep did not analyze {ctx.tmp_path} (exit={r.returncode}): {detail}"
    )


class _SemgrepAnalyzer:
    name = "semgrep"
    category = Category.CODE_QUALITY
    # 🔴 **범용 대체 관측면** — 한 언어의 전담 분석기가 아니라 여러 언어의 폭넓은 fallback 이다.
    #    그래서 「전담 관측면이 돌았는가」를 셀 때 이것은 세지 않는다
    #    (`static.py::no_dedicated_observer`). 규칙 밀도가 언어마다 크게 다르므로
    #    (고정한 룰: swift 5 · typescript 12 · scala 86) semgrep 이 돌았다는 사실만으로
    #    그 언어를 봤다고 말할 수 없다 — 그 판단이 이 표식의 이유다.
    # The generic multi-language fallback: running it does not mean the language was observed.
    is_generic = True

    # 🔴 고정한 룰이 있는 언어만 — 룰이 0개인 언어에서 semgrep 을 돌리면 «이슈 0건 · 완전» 이 된다.
    #    목록은 룰 파일의 `languages` 에서 나온다(`tests/unit/analyzer/test_semgrep_vendored_rules.py` 가 대조).
    # Only languages the vendored rules cover; running semgrep with zero applicable rules reports a clean run.
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
        "python", "javascript", "typescript", "java", "go",
        "csharp", "scala", "kotlin", "swift",
    })

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Semgrep 지원 언어 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """semgrep 바이너리 설치 여부 확인."""
        return shutil.which("semgrep") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """고정한 룰로 분석 후 이슈 목록 반환 — 네트워크에 닿지 않는다(지표 · 판 확인 끔).
        Analyze with the vendored rules and return issues; no network (metrics and version check off).
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["semgrep", "scan", f"--config={rules_config()}", "--json",
                 "--metrics=off", "--disable-version-check",
                 "--timeout", str(STATIC_ANALYSIS_TIMEOUT), ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
                # 폴더로 되돌아가면 비-ASCII 가 든 YAML 을 읽는다 — 로캘 인코딩(예: cp949)이면 semgrep 이 죽는다(실측 Windows)
                # The folder fallback reads YAML with non-ASCII text; a non-UTF-8 locale encoding breaks semgrep.
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            # 🔴 stdout 이 JSON 이 아니면 semgrep 이 **분석하지 않은** 것이다.
            # `--json` 의 정상 «이슈 없음» 도 `{"results": []}` 라 `{` 로 시작한다 —
            # 비-`{` 가 정당한 «이슈 0건» 인 경우는 없다.
            # Non-JSON stdout means semgrep did not analyze; a clean --json run still
            # starts with '{'.
            if not r.stdout.strip().startswith("{"):
                raise _fail(ctx, r)
            try:
                data = json.loads(r.stdout)
            except json.JSONDecodeError as exc:
                raise _fail(ctx, r) from exc
            # 🔴 JSON 이어도 종료 코드가 0 이 아니면 분석하지 않은 것이다. 레지스트리가 룰셋을 거절하거나
            # 설정이 없으면 `{"results": [], "errors": [...]}` 를 찍고 7 로 끝난다(실측 1.183.0).
            # `--json` 은 찾은 것이 있어도 0 으로 끝나므로(`--error` 를 주지 않는다) 0 이 아닌 값은 실패뿐이다.
            # 문법 오류로 일부만 파싱한 파일은 `warn` 오류와 함께 0 으로 끝난다 — 그 파일은 훑은 것이다.
            # A JSON body with a non-zero exit is still a failure: a rejected registry ruleset or a missing
            # config prints {"results": [], "errors": [...]} and exits 7, while --json exits 0 even with
            # findings. Partial parsing exits 0 with a warn-level error: that file was still scanned.
            if r.returncode != 0:
                raise _fail(ctx, r, data)
            issues = []
            for item in data.get("results", []):
                extra = item.get("extra", {})
                metadata = extra.get("metadata", {})
                raw_severity = extra.get("severity", "WARNING").upper()
                severity = Severity.ERROR if raw_severity == "ERROR" else Severity.WARNING
                category = (
                    Category.SECURITY
                    if metadata.get("category") == "security"
                    else Category.CODE_QUALITY
                )
                issues.append(AnalysisIssue(
                    tool="semgrep",
                    severity=severity,
                    message=extra.get("message", item.get("check_id", "")),
                    line=item.get("start", {}).get("line", 0),
                    category=category,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("semgrep timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # 바이너리 부재 — 크래시와 **다른 축**이다. `static.py` 가
            # `unavailable_tools` 로 따로 보고하므로 여기서 예외로 올리지 않는다.
            # Missing binary is reported separately via unavailable_tools.
            logger.warning("semgrep binary missing for %s: %s", ctx.tmp_path, exc)
            return []


def _register_semgrep_analyzers() -> None:
    register(_SemgrepAnalyzer())


_register_semgrep_analyzers()
