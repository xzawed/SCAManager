"""repo-integrity 체커 스크립트 회귀 가드 — check_docs_sync / check_toc_anchors.

현재 repo 에서 통과(pre-commit 이 현 상태를 막지 않음) + 합성 위반 적발(실제 drift 차단)을
양방향 고정한다. WF-2(docs 수치 정합) / WF-3(TOC 앵커 slug) 자동화의 회귀 가드.
"""
import sys
from pathlib import Path

# 스크립트 임포트 경로 설정 / Script import path setup (기존 test_extract_design_tokens 패턴)
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_docs_sync  # noqa: E402
import check_toc_anchors  # noqa: E402


# --- check_docs_sync (WF-2) ---

def test_docs_sync_passes_on_current_repo():
    ok, msgs = check_docs_sync.check_consistency(_ROOT)
    assert ok, msgs


def test_docs_sync_flags_count_mismatch(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STATE.md").write_text(
        "**종합 수치**: 전체 **5196** 수집 (단위 **5042** + 통합 154)\n"
        "| 전체 테스트 | **5196 수집** *(...)* | 단위 5042 + 통합 154 (현재). 추적...\n",
        encoding="utf-8",
    )
    # README 배지가 STATE 와 다른 수치(5195/5041) → 불일치 적발
    badge = "Tests-5195%2B_total_(5041_unit_%2B_154_integration)"
    (tmp_path / "README.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    (tmp_path / "README.ko.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    ok, msgs = check_docs_sync.check_consistency(tmp_path)
    assert not ok
    assert any("불일치" in m for m in msgs)


# --- check_toc_anchors (WF-3) ---

def test_toc_anchors_passes_on_current_repo():
    text = (_ROOT / "docs" / "cycle-history.md").read_text(encoding="utf-8")
    ok, msgs = check_toc_anchors.check_anchors(text)
    assert ok, msgs


def test_toc_anchors_flags_broken():
    md = "## 목차\n- [항목](#nonexistent-anchor)\n\n## 실제 헤딩\n본문\n"
    ok, msgs = check_toc_anchors.check_anchors(md)
    assert not ok
    assert any("nonexistent-anchor" in m for m in msgs)


def test_toc_anchors_ignores_inline_code_outside_toc():
    # 본문 섹션의 인라인 코드 예시(`](#...)`)는 목차 앵커가 아니므로 오탐하지 않아야 함
    md = (
        "## 목차\n- [항목](#실제-헤딩)\n\n"
        "## 실제 헤딩\n본문에서 TOC `](#...)` 앵커 형식을 설명하는 코드 예시.\n"
    )
    ok, msgs = check_toc_anchors.check_anchors(md)
    assert ok, msgs


def test_github_slug_em_dash_double_hyphen():
    # em-dash 가 공백 사이에서 제거되어 더블하이픈 slug 생성 (#958 사고 패턴)
    assert check_toc_anchors.github_slug("A — B", {}) == "a--b"


def test_github_slug_dedup_suffix():
    seen: dict[str, int] = {}
    assert check_toc_anchors.github_slug("동일 제목", seen) == "동일-제목"
    assert check_toc_anchors.github_slug("동일 제목", seen) == "동일-제목-1"
