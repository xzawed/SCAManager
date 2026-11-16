"""문서 총량 가드 — 이 PR 이 문서 총 글자 수를 늘렸으면 본문에 그 결정을 적게 한다 (회고 원장 L18 P2-4 · P2-16 · 사용자 11-16 결정).

## 사고

CLAUDE.md «문서 총량은 늘리지 않는다» 를 재는 곳이 없어, 한 창에서 +815자(69,748 → 70,563)가 늘었다. 9 PR 이 순증이었고
그중 넷은 본문에 «뺀 것 없음» 이라고 스스로 적었다. 같은 규칙이 다른 데서는 함정 한 줄을 안 넣는 근거로 쓰였다.

## 이 파일이 잠그는 것

1. 범위 — 추적 `.md` 가운데 `docs/reports/` · `.claude/` · `tests/` · `e2e/` 밖(회고가 잰 묶음).
2. 같거나 줄면 통과 · 늘면 본문 줄 맨 앞 `doc-growth: <16자 이상>` 이 있어야 통과(자리표시자 · 인용 · 문장 중간은 아님).
3. PR 맥락이 없으면 재기만 하고 0 — 로컬 게이트는 «안 잼» 으로 찍는다.
4. 배선 — CI repo-integrity(PR) · 본문 수정 워크플로 · 로컬 게이트의 «PR 맥락 필요» 목록.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 — 격리된 임시 리포와 이 리포의 가드만
import sys
from pathlib import Path

import pytest
import yaml

import scripts.check_doc_growth as mod
from tests.unit.scripts._wiring_shape import invokes

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_doc_growth.py"
_REASON = "verify.md 에 절차 한 줄 — 낡은 문장 둘을 걷었다"


# ── 2. 본문 표지 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("body, counts", [
    (f"## 요약\n\ndoc-growth: {_REASON}\n", True),
    (f"   doc-growth: {_REASON}\n", True),
    ("doc-growth: 짧다\n", False),
    ("doc-growth: <무엇을 뺐고 왜 늘었는가 — 16자 이상>\n", False),
    (f"`doc-growth: {_REASON}`\n", False),
    (f"설명 — doc-growth: {_REASON}\n", False),
])
def test_the_marker_needs_a_real_reason_at_line_start(body, counts):
    assert bool(mod.MARKER.search(body)) is counts, body


# ── 1 · 2 · 3. 임시 리포의 실제 diff ─────────────────────────────────────


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root,
                          check=True, capture_output=True, text=True).stdout.strip()


def _commit(root: Path, files: dict[str, str]) -> str:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        _git(root, "add", rel)
    _git(root, "commit", "-q", "--allow-empty", "-m", "c")
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    base = _commit(tmp_path, {"README.md": "가나다라\n", "docs/workflow/verify.md": "절차\n",
                              "docs/reports/r.md": "보고서\n", ".claude/agents/a.md": "지시\n"})
    return tmp_path, base


def _run(root: Path, base: str, body: str | None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA")}
    if body is not None:
        env.update(PR_BODY=body, PR_BASE_SHA=base, PR_HEAD_SHA=_git(root, "rev-parse", "HEAD"))
    return subprocess.run([sys.executable, str(_SCRIPT)], cwd=str(root), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False)


def test_growth_without_a_reason_is_red_and_names_the_file(repo):
    root, base = repo
    _commit(root, {"docs/workflow/verify.md": "절차\n한 줄 더\n"})
    proc = _run(root, base, "본문 — 사유 없음")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    grown = [line.split()[1] for line in proc.stdout.splitlines() if line.startswith("   + ")]
    assert grown == ["docs/workflow/verify.md"], proc.stdout


def test_growth_with_a_reason_passes(repo):
    root, base = repo
    _commit(root, {"docs/workflow/verify.md": "절차\n한 줄 더\n"})
    assert _run(root, base, f"doc-growth: {_REASON}\n").returncode == 0


def test_a_new_doc_file_counts_as_growth(repo):
    root, base = repo
    _commit(root, {"docs/runbooks/new.md": "새 문서\n"})
    assert _run(root, base, "본문 — 사유 없음").returncode == 1


def test_shrinking_or_trading_lines_passes(repo):
    root, base = repo
    _commit(root, {"README.md": "가나\n", "docs/workflow/verify.md": "절차 한\n"})
    assert _run(root, base, "본문 — 사유 없음").returncode == 0


def test_reports_and_agent_prompts_are_outside_the_total(repo):
    """회고가 잰 묶음 — 보고서 · 에이전트 지시가 늘어도 «문서 총량» 이 아니다."""
    root, base = repo
    _commit(root, {"docs/reports/r.md": "보고서\n" * 50, ".claude/agents/a.md": "지시\n" * 50})
    assert _run(root, base, "본문 — 사유 없음").returncode == 0


def test_an_empty_head_scope_is_a_collapse_not_a_shrink(repo):
    """🔴 총량에 드는 문서가 HEAD 에 하나도 없으면 «줄었다» 가 아니라 범위 붕괴다 — 사유가 있어도 red."""
    root, base = repo
    _git(root, "rm", "-q", "README.md", "docs/workflow/verify.md")
    _git(root, "commit", "-q", "-m", "rm")
    assert _run(root, base, f"doc-growth: {_REASON}\n").returncode == 1


def test_without_a_pr_context_it_measures_and_passes(repo, capsys):
    """로컬 · push — 본문이 없어 사유를 못 잰다. 늘었다는 사실만 찍고 0(로컬 게이트가 «안 잼» 으로 찍는다)."""
    root, base = repo
    _commit(root, {"docs/workflow/verify.md": "절차\n한 줄 더\n"})
    proc = _run(root, base, None)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "안 잼" in proc.stdout, proc.stdout


# ── 1. 범위가 회고가 잰 묶음과 같다 ───────────────────────────────────────

# witness-corpus: 총량에 드는 추적 문서 — 빼는 목록이 알아보지 못해야 할 실제 경로(git ls-files 11-16)
_COUNTED = ["CLAUDE.md", "README.ko.md", "docs/workflow/verify.md", ".github/PULL_REQUEST_TEMPLATE.md",
            "src/scripts/README.md"]


@pytest.mark.parametrize("path", _COUNTED)
def test_real_docs_are_inside_the_total(path):
    assert mod.counts(path) is True, path


@pytest.mark.parametrize("path", ["docs/reports/2026-11-06-retrospective.md", ".claude/agents/doc-consistency-reviewer.md",
                                  "tests/fixtures/x.md", "e2e/notes.md", "src/x.py"])
def test_history_prompts_fixtures_and_code_are_outside(path):
    assert mod.counts(path) is False, path


# ── 4. 배선 ───────────────────────────────────────────────────────────────


def _steps(workflow: str) -> list[dict]:
    doc = yaml.safe_load((_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    return [step for job in doc["jobs"].values() for step in job.get("steps", [])]


@pytest.mark.parametrize("workflow", ["ci.yml", "claim-review-on-body-edit.yml"])
def test_both_workflows_run_it_with_the_body_and_the_range(workflow):
    hits = [s for s in _steps(workflow) if invokes(s.get("run", ""), "scripts/check_doc_growth.py")]
    assert len(hits) == 1, workflow
    passed = hits[0].get("env", {})
    for key in ("PR_BODY", "PR_BASE_SHA", "PR_HEAD_SHA"):
        assert key in passed, (workflow, key)


def test_the_local_gate_marks_it_unmeasured_without_a_body():
    sys.path.insert(0, str(_ROOT / "scripts"))
    import pre_push_gate  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    assert "check_doc_growth.py" in pre_push_gate._INTEGRITY  # pylint: disable=protected-access
    assert "check_doc_growth.py" in pre_push_gate._NEEDS_PR_CONTEXT  # pylint: disable=protected-access
