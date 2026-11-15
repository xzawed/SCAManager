"""회고 · 감사 워크플로의 loop-until-dry 가 «마를 수» 있는가 — finder · 비평가가 받는 입력을 잰다 (회고 원장 L14).

## 사고 (11-06 회고 실측)

- 2라운드부터 finder 는 «이전 라운드 항목 제외» 지시만 받고 그 목록은 받지 못했다. 중복 키는 «관점 + 정확한
  제목» 이라 같은 결함이 라운드마다, 관점마다 다시 확정됐다 — 09-16 «확정 140» 은 원인 22묶음이었다
  (P1-19 · P1-20 · P2-41 · P2-79).
- 관점(domain)은 에이전트가 쓴 자유 문자열이라(한 라운드에 비정규 13종) gap 결과의 키가 검증 항목과
  원리적으로 겹치지 않았다(P2-112).
- +1 완전성 비평가는 검증 항목의 «개수» 만 받아, gap 8개 중 5개가 이미 2~6벌 있는 주제였다(P1-42).

## 계기

워크플로 파일은 런타임 전역(`agent` · `parallel` · `opts`)에 기대므로 통째로 못 돌린다. 그래서 **순수
함수**(`key` · `priorList` · 프롬프트 빌더)만 소스에서 꺼내 node 로 실제로 부른다 — 글자 존재가 아니라
돌려준 값을 본다. node 는 이 리포 최초 설정의 필수 도구다(없으면 red — 못 잰 것은 통과가 아니다).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_WF = Path(__file__).resolve().parents[3] / ".claude" / "workflows"
# 워크플로 → (finder 프롬프트 빌더 이름, 그 빌더를 부르는 JS 식 — `PRIOR` · `ROUND` 자리)
_FINDER = {
    "retrospective.mjs": ("finderPrompt", "finderPrompt({id: 'code', focus: 'f'}, '', ROUND, PRIOR)"),
    "integrity-audit.mjs": ("auditPrompt", "auditPrompt({id: 'gate', focus: 'f', paths: ['src/']}, null, ROUND, PRIOR)"),
}
_PRIOR = [{"severity": "P1", "title": "ALREADY-REPORTED-7f3a", "file": "src/a.py", "line": 9, "domain": "code"}]


def _function_source(text: str, name: str) -> str:
    """최상위 `function NAME(` 부터 열 0 의 `}` 까지 — 없으면 red."""
    m = re.search(rf"^(?:export\s+)?function {name}\(.*?^\}}", text, re.S | re.M)
    assert m, f"`function {name}` 을 찾지 못했다 — 워크플로 구조가 바뀌었다"
    return re.sub(r"^export\s+", "", m.group(0))


def _js(wf: str, names: list[str], expr: str):
    node = shutil.which("node")
    assert node, "node 가 없다 — 최초 설정(`npm install`)을 할 것. 못 잰 것은 통과가 아니다"
    text = (_WF / wf).read_text(encoding="utf-8")
    src = "\n".join(_function_source(text, n) for n in names)
    out = subprocess.run([node, "-e", f"{src}\nconsole.log(JSON.stringify({expr}))"],
                         capture_output=True, text=True, encoding="utf-8", check=False, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout)


@pytest.mark.parametrize("wf", sorted(_FINDER))
def test_the_same_defect_from_two_lenses_has_one_key(wf):
    """같은 위치 · 같은 제목(대소문자 · 공백만 다름)이면 관점이 달라도 키가 같다 — 다른 제목 · 줄은 다르다."""
    a = {"domain": "code", "file": "src/A.py", "line": 3, "title": "Foo  bar"}
    b = {"domain": "Process-Lens", "file": "src/a.py ", "line": 3, "title": "foo bar"}
    c = dict(a, title="foo baz")
    d = dict(a, line=4)
    same, other_title, other_line = _js(
        wf, ["key"],
        f"[key({json.dumps(a)}) === key({json.dumps(b)}), key({json.dumps(a)}) === key({json.dumps(c)}), "
        f"key({json.dumps(a)}) === key({json.dumps(d)})]")
    assert same, "관점만 다른 같은 결함이 다른 키다 — 따로 확정된다"
    assert not other_title and not other_line, "다른 결함을 한 키로 합쳤다"


@pytest.mark.parametrize("wf", sorted(_FINDER))
def test_a_round_keeps_one_of_two_lenses_reporting_the_same_defect(wf):
    """🔴 1라운드는 모든 관점이 동시에 돈다 — 같은 결함 둘이 한 라운드에 오면 하나만 신규다.

    이전 라운드 키(`seen`)만 거르면 둘 다 남는다(Grok claim-review 반증). 이전 라운드에 나온 것은 빠진다.
    """
    a = {"domain": "code", "file": "src/A.py", "line": 3, "title": "Foo bar"}
    b = {"domain": "process", "file": "src/a.py", "line": 3, "title": "foo  bar"}
    old = {"domain": "code", "file": "src/c.py", "line": 1, "title": "seen before"}
    new = {"domain": "code", "file": "src/d.py", "line": 2, "title": "new one"}
    titles = _js(wf, ["key", "freshOf"],
                 f"freshOf({json.dumps([a, b, old, new])}, new Set([key({json.dumps(old)})])).map((f) => f.title)")
    assert titles == ["Foo bar", "new one"], f"한 라운드 안의 중복 또는 이전 라운드 항목이 남았다: {titles}"


@pytest.mark.parametrize("wf", sorted(_FINDER))
def test_the_loop_and_the_gap_round_take_fresh_findings_through_freshof(wf):
    """루프와 gap 라운드가 실제로 `freshOf` 로 신규를 고른다 — 함수만 있고 안 쓰이면 위 시험은 공허하다."""
    code = re.sub(r"//.*", "", (_WF / wf).read_text(encoding="utf-8"))
    assert re.search(r"const fresh = freshOf\(found, seen\)", code), "루프가 freshOf 를 안 쓴다"
    assert re.search(r"const gapFound = freshOf\(", code), "gap 라운드가 freshOf 를 안 쓴다"


@pytest.mark.parametrize("wf", sorted(_FINDER))
def test_finders_from_round_two_receive_the_already_reported_list(wf):
    """🔴 2라운드부터 finder 프롬프트에 이미 보고된 항목이 실제로 들어간다 — 1라운드에는 없다."""
    builder, call = _FINDER[wf]
    prior = json.dumps(_PRIOR)
    r1, r2 = _js(wf, ["priorList", builder],
                 f"[{call.replace('ROUND', '1').replace('PRIOR', prior)}, "
                 f"{call.replace('ROUND', '2').replace('PRIOR', prior)}]")
    assert "ALREADY-REPORTED-7f3a" in r2 and "src/a.py:9" in r2, "2라운드 finder 가 제외할 목록을 못 받는다"
    assert "ALREADY-REPORTED-7f3a" not in r1, "1라운드에 이전 목록이 섞였다"


@pytest.mark.parametrize("wf", sorted(_FINDER))
def test_the_completeness_critic_sees_what_was_already_covered(wf):
    """+1 비평가가 개수가 아니라 이미 다룬 항목의 제목을 받는다."""
    covered = [{"severity": "P2", "title": "COVERED-TOPIC-91c2", "file": "src/b.py", "line": 1, "domain": "code"}]
    prompt = _js(wf, ["priorList", "completenessPrompt"],
                 f"completenessPrompt([{{id: 'code'}}], {json.dumps(covered)}, 'scope')")
    assert "COVERED-TOPIC-91c2" in prompt, "비평가가 이미 검증된 주제를 모른다 — 같은 주제를 gap 으로 다시 고른다"


def _const_source(text: str, name: str, closer: str) -> str:
    """최상위 `const NAME = …` 부터 열 0 의 닫는 괄호까지 — 없으면 red."""
    m = re.search(rf"^const {name} = .*?^\{closer}", text, re.S | re.M)
    assert m, f"`const {name}` 을 찾지 못했다 — 워크플로 구조가 바뀌었다"
    return m.group(0)


@pytest.mark.parametrize("changed", [".github/workflows/ci.yml", "requirements-dev.txt"])
def test_a_diff_audit_touching_supply_chain_files_gets_the_security_lens(changed):
    """🔴 공급망 예외(ci.yml 의 pip-audit 무시 · 의존성 핀)를 바꾼 diff 감사는 보안 렌즈를 받는다.

    다른 도메인과 함께 바뀌면 매칭 0 폴백(전체)이 안 타므로, 보안 경로가 없으면 보안 렌즈가 빠진다(P2-88).
    """
    node = shutil.which("node")
    assert node, "node 가 없다 — 최초 설정(`npm install`)을 할 것"
    text = (_WF / "integrity-audit.mjs").read_text(encoding="utf-8")
    src = "\n".join([_const_source(text, "DOMAINS", "]"), _const_source(text, "ADJACENCY", "}"),
                     _function_source(text, "resolveDomains")])
    expr = f"resolveDomains('diff', {json.dumps([changed, 'src/gate/x.py'])}).map((d) => d.id)"
    out = subprocess.run([node, "-e", f"{src}\nconsole.log(JSON.stringify({expr}))"],
                         capture_output=True, text=True, encoding="utf-8", check=False, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    ids = json.loads(out.stdout)
    assert "gate" in ids and "security" in ids, f"공급망 파일을 바꾼 diff 감사에 보안 렌즈가 없다: {ids}"


def test_the_prior_list_is_capped_and_says_how_many_it_left_out():
    """목록은 상한에서 자르고 몇 건을 뺐는지 말한다 — 프롬프트가 무한히 자라지 않는다."""
    items = [{"severity": "P2", "title": f"T{i}", "file": "x.py", "line": i} for i in range(400)]
    text = _js("retrospective.mjs", ["priorList"], f"priorList({json.dumps(items)})")
    assert "T0" in text and "T399" not in text, "상한 없이 다 넣었다"
    assert re.search(r"\d+건", text), "뺀 건수를 말하지 않는다"
