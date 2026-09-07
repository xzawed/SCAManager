"""회고 범위의 «git log 가 원리적으로 못 보는» 두 축을 잠근다 (회고 2026-09-07 P0·P1-1).

## 왜 이 두 축인가

- **stacked PR** — base 가 `main` 이 아닌 머지는 부모의 squash 하나로 접혀 main 제목에
  `(#N)` 을 남기지 않는다. 실측: 한 창에서 3건이 사라졌고 그중 하나가 심의 훅 자신을
  고친 PR 이었다.
- **경계 갭** — 경계는 리포트가 «머지된» 커밋인데 회고의 분석은 그보다 앞에서 끝난다.
  그 사이 머지분은 직전 창에도 다음 창에도 없다. 실측: 2건, 그중 하나가 직전 회고의
  «처방» PR 이었다 — 검증 이력이 가장 짧은 산출물이 회고를 피한다.

## 🔴 이 파일이 «하지 않는» 판정

커밋 **본문** 파싱은 처방이 아니다. 재현율만 보면 3/3 이지만 정밀도가 3/10 이다 —
본문의 `(#N)` 대다수는 Issue 번호이고 GitHub 은 Issue 와 PR 이 번호 공간을 공유한다.
그래서 본문 기반 판정을 «금지» 하는 단언을 여기 두지 않는다: 금지는 산문을 막고,
필요한 것은 **base 로 판정하는 축이 살아 있는가** 다.

## 🔴 「안 쟀음」은 「통과」가 아니다

`gh` 가 없거나 직전 리포트가 분석 종료 HEAD 를 안 적었으면 근사하지 않고 `unmeasured`
에 담는다. 그리고 그 필드를 워크플로 스키마가 **요구** 해야 배선이 끊겼을 때 red 가 난다
— 관측만 하고 집행하지 않는 가드가 이 리포의 반복 결함이었다.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "retro_scope.py"
_WORKFLOW = _ROOT / ".claude" / "workflows" / "retrospective.mjs"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_xc", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()


# ── stacked PR 축 ────────────────────────────────────────────────────────────


def test_stacked_prs_are_selected_by_base_not_by_date(monkeypatch):
    """판정식은 `baseRefName != main` 이다 — 날짜는 후보를 줄이는 필터일 뿐이다.

    날짜로 «판정» 하면 직전 창 말미가 겹쳐 들어와 과포함이 된다(실측: 리포트 날짜로
    자르니 3~7건). base 로 판정하면 하루가 헐거워도 결과가 흔들리지 않는다.
    """
    rows = [
        {"number": 900, "mergedAt": "2026-08-30T00:00:00Z", "baseRefName": "main"},
        {"number": 901, "mergedAt": "2026-08-30T00:00:00Z", "baseRefName": "feat/parent"},
        {"number": 902, "mergedAt": "2026-08-28T00:00:00Z", "baseRefName": "feat/parent"},
        {"number": 903, "mergedAt": "2026-08-20T00:00:00Z", "baseRefName": "feat/old"},
    ]
    monkeypatch.setattr(rs, "_gh_json", lambda _a: rows)
    got = rs.github_stacked_prs("2026-08-29")
    assert got == [901, 902], f"base 로 판정하지 않는다 — {got}"


def test_stacked_axis_reports_unmeasured_when_gh_is_absent(monkeypatch, tmp_path):
    """🔴 `gh` 가 없으면 조용히 줄지 않는다 — `unmeasured` 에 담고 `ok` 는 유지한다.

    `ok:false` 로 뒤집으면 워크플로가 `prs` 를 통째로 버리고 호출자 범위로 되돌아간다
    (그 폴백이 3개월 무앵커 사고의 형태였다). 오프라인 산출은 살리고, 못 잰 축만 알린다.
    """
    monkeypatch.setattr(rs, "_gh_json", lambda _a: None)
    monkeypatch.setattr(rs, "merged_prs", lambda _b: [11, 12])
    monkeypatch.setattr(rs, "boundary_commit", lambda _f: "a" * 40)
    monkeypatch.setattr(rs, "report_head", lambda _f: "b" * 40)
    monkeypatch.setattr(rs, "_REPORTS", tmp_path)
    (tmp_path / "2026-01-01-retrospective.md").write_text("x", encoding="utf-8")

    out = rs.compute()
    assert out["ok"] is True, "오프라인 산출까지 버리면 안 된다"
    assert out["prs"] == [11, 12], "못 잰 축 때문에 잰 축을 버리면 안 된다"
    assert out["gh_checked"] is False
    assert "stacked-pr-cross-check" in out["unmeasured"], out["unmeasured"]


# ── 경계 갭 축 ───────────────────────────────────────────────────────────────


def test_gap_axis_uses_recorded_head_when_the_report_has_one(monkeypatch, tmp_path):
    """리포트가 분석 종료 HEAD 를 적어 뒀으면 경계가 아니라 «그 HEAD» 부터 센다."""
    monkeypatch.setattr(rs, "_REPORTS", tmp_path)
    (tmp_path / "2026-01-01-retrospective.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(rs, "boundary_commit", lambda _f: "c" * 40)
    monkeypatch.setattr(rs, "report_head", lambda _f: "deadbee")
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [])
    seen = {}

    def _fake(scan_from):
        seen["from"] = scan_from
        return [21]

    monkeypatch.setattr(rs, "merged_prs", _fake)
    out = rs.compute()
    assert seen["from"] == "deadbee", f"기록된 HEAD 를 안 쓴다 — {seen}"
    assert "report-merge-gap" not in out["unmeasured"]


def test_gap_axis_is_reported_unmeasured_when_the_report_records_no_head(monkeypatch, tmp_path):
    """🔴 기록이 없으면 «날짜로 근사» 하지 않는다 — 안 쟀다고 말한다.

    날짜 근사는 정밀한 척하면서 직전 창 말미를 끌어온다. 근사값은 다음 회고가 그것을
    참으로 물려받게 만들고, 직전 리포트의 거짓 헤더가 정확히 그렇게 만들어졌다.
    """
    monkeypatch.setattr(rs, "_REPORTS", tmp_path)
    (tmp_path / "2026-01-01-retrospective.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(rs, "boundary_commit", lambda _f: "c" * 40)
    monkeypatch.setattr(rs, "report_head", lambda _f: None)
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [])
    monkeypatch.setattr(rs, "merged_prs", lambda _b: [31])
    out = rs.compute()
    assert "report-merge-gap" in out["unmeasured"], out["unmeasured"]


def test_report_head_ignores_a_sha_that_does_not_resolve(monkeypatch, tmp_path):
    """적혀 있어도 **해석되는** SHA 만 쓴다 — squash 로 소멸한 SHA 를 믿으면 안 된다."""
    monkeypatch.setattr(rs, "_REPORTS", tmp_path)
    (tmp_path / "r.md").write_text("| head | `0123456` |", encoding="utf-8")
    monkeypatch.setattr(rs, "resolve_ref", lambda _r: None)
    assert rs.report_head("r.md") is None


def test_report_head_reads_the_shipped_report():
    """계기 자기검증 — 이 리포에 실재하는 리포트에서 실제로 뽑혀야 한다.

    스텁만으로는 «형식이 맞는가» 를 못 잰다. 형식이 어긋나면 다음 회고가 조용히
    경계 갭 미측정으로 떨어진다.
    """
    reports = sorted(p.name for p in (_ROOT / "docs" / "reports").glob("*retrospective*.md"))
    assert reports, "회고 리포트가 0건 — 판정이 공허하다"
    heads = {name: rs.report_head(name) for name in reports}
    assert any(v for v in heads.values()), (
        "어떤 리포트에서도 분석 종료 HEAD 를 못 읽는다 — 형식이 어긋났다:\n  "
        + "\n  ".join(f"{k} -> {v}" for k, v in heads.items()))


# ── 워크플로 배선 ────────────────────────────────────────────────────────────


def test_workflow_schema_requires_the_unmeasured_field():
    """🔴 스크립트가 「안 쟀다」를 내도 워크플로가 안 읽으면 누락이 다시 조용해진다.

    스키마의 `required` 에 이름이 있어야 배선이 끊겼을 때 red 가 난다 — 관측만 하고
    집행하지 않는 가드가 이 리포가 반복해 적발한 형태다.
    """
    src = _WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"const SCOPE_SCHEMA = \{(.*?)\n\}", src, re.S)
    assert m, "SCOPE_SCHEMA 를 찾지 못했다 — 워크플로 구조가 바뀌었다"
    block = m.group(1)
    req = re.search(r"required:\s*\[([^\]]*)\]", block)
    assert req, "SCOPE_SCHEMA 에 required 가 없다"
    assert "'unmeasured'" in req.group(1), (
        f"`unmeasured` 가 required 에 없다 — 못 잰 축이 조용히 통과한다: {req.group(1)}")
    assert "unmeasured:" in block, "SCOPE_SCHEMA properties 에 unmeasured 선언이 없다"


def test_workflow_does_not_overwrite_the_unmeasured_note():
    """🔴 뒤따르는 분기가 `scopeNote =` 로 덮으면 경고가 사라진다 — `+=` 여야 한다.

    (이 시험은 실제로 그 결함을 잡았다: 첫 판이 대입이었다.)
    """
    src = _WORKFLOW.read_text(encoding="utf-8")
    start = src.index("if (!machineScope")
    end = src.index("const scopedContext", start)
    body = src[start:end]
    assigns = re.findall(r"^\s*scopeNote\s*=\s*$|^\s*scopeNote\s*=\s*[`'\"]", body, re.M)
    assert len(assigns) <= 1, (
        f"`scopeNote =` 대입이 {len(assigns)}회 — 뒤 분기가 앞 경고를 덮는다. `+=` 를 쓸 것")


def test_the_shipped_script_emits_the_three_fields():
    """계기 자기검증 — 실제 실행 산출에 세 필드가 다 있어야 한다(형식 드리프트 방지)."""
    out = rs.compute()
    if not out.get("ok"):
        pytest.skip(f"이 환경에서 범위 산출 불가: {out.get('reason')}")
    for key in ("gh_checked", "gh_only", "unmeasured"):
        assert key in out, f"`{key}` 가 산출에 없다 — 워크플로 스키마가 요구하는 이름이다"
    assert json.dumps(out, ensure_ascii=False), "JSON 직렬화 불가"
