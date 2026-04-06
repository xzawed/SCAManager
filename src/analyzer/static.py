import json
import os
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field


@dataclass
class AnalysisIssue:
    tool: str
    severity: str   # "error" | "warning"
    message: str
    line: int = 0


@dataclass
class StaticAnalysisResult:
    filename: str
    issues: list[AnalysisIssue] = field(default_factory=list)


def analyze_file(filename: str, content: str) -> StaticAnalysisResult:
    if not content.strip():
        return StaticAnalysisResult(filename=filename)

    result = StaticAnalysisResult(filename=filename)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result.issues.extend(_run_pylint(tmp_path))
        result.issues.extend(_run_flake8(tmp_path))
        result.issues.extend(_run_bandit(tmp_path))
    finally:
        os.unlink(tmp_path)

    return result


def _run_pylint(path: str) -> list[AnalysisIssue]:
    try:
        r = subprocess.run(  # nosec B603 B607
            ["pylint", path, "--output-format=json",
             "--disable=C0114,C0115,C0116,C0301,C0411,"
             "E0401,"
             "R0801,R0902,R0903,R0912,R0913,R0914,R0915,R0917,"
             "W0511,W0613,W0621,W0718"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        items = json.loads(r.stdout) if r.stdout.strip().startswith("[") else []
        return [
            AnalysisIssue(
                tool="pylint",
                severity="error" if item["type"] in ("error", "fatal") else "warning",
                message=item["message"],
                line=item["line"],
            )
            for item in items
        ]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def _run_flake8(path: str) -> list[AnalysisIssue]:
    try:
        r = subprocess.run(  # nosec B603 B607
            ["flake8", path, "--max-line-length=120", "--format=%(row)d:%(col)d: %(text)s"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        issues = []
        for line in r.stdout.strip().splitlines():
            parts = line.split(":", 2)
            if len(parts) == 3:
                try:
                    issues.append(AnalysisIssue(
                        tool="flake8",
                        severity="warning",
                        message=parts[2].strip(),
                        line=int(parts[0]),
                    ))
                except ValueError:
                    continue
        return issues
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _run_bandit(path: str) -> list[AnalysisIssue]:
    try:
        r = subprocess.run(  # nosec B603 B607
            ["bandit", "-f", "json", "-q", path],
            capture_output=True, text=True, timeout=30, check=False,
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        return [
            AnalysisIssue(
                tool="bandit",
                severity="error" if item["issue_severity"] == "HIGH" else "warning",
                message=item["issue_text"],
                line=item["line_number"],
            )
            for item in data.get("results", [])
        ]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []
