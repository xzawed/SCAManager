"""분기 프로브 — e2e 실행 하나에서 Jinja `{% if %}` 의 «두 팔» 이 각각 렌더됐는지 센다.

    BRANCH_PROBE_OUT=probe.json py -3 -m pytest e2e/ -p no:asyncio -p e2e.branchprobe

끝나면 터미널에 요약 한 줄을 찍고, `BRANCH_PROBE_OUT` 가 있으면 노드별 결과를 쓴다
(`summarize()` 의 반환값 그대로). e2e 시험 몇 곳이 «그 노드가 돌았는가» 의 심판으로 이 계기를
가리킨다 — DOM 은 «아무것도 안 그리는 팔» 을 판정할 수 없어서다.

🔴 계기 검증: `declared`(이 실행에서 파싱된 `If` 노드)가 `static`(템플릿 전부를 따로 파싱해
   센 정적 전수)과 다르면 **그 실행의 수치는 버린다** — 한 번도 안 불린 템플릿이 있거나 세는
   방식이 어긋난 것이다. 요약 줄과 `valid` 가 그렇게 말한다.
🔴 `find_all` 을 먼저 `list()` 로 굳힌 뒤 교체한다 — 순회 중 교체하면 과소계수한다.
🔴 id 는 `템플릿:줄:순번` — 줄만 쓰면 한 줄에 둘일 때 합쳐진다.
🔴 `jinja2.nodes.If`(`elif` 포함)만 본다 — 인라인 `a if b else c`(`CondExpr`)는 세지 않는다.
🔴 전역 패치(`jinja2.Environment._parse`)는 플러그인으로 켰을 때만(`pytest_configure`) 건다 —
   모듈을 import 만 하면 아무것도 바뀌지 않는다.

Branch probe: records which arm of every Jinja `{% if %}` rendered during one e2e run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import jinja2

_PROBE = "__branch_probe__"
_TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "templates"
_ORIG_PARSE = jinja2.Environment._parse

_DECLARED: set[str] = set()
_SEEN: dict[str, set[bool]] = {}
_PARSES: dict[str | None, list[int]] = {}


def record(key: str, value, seen: dict[str, set[bool]] | None = None) -> bool:
    """`{% if %}` 의 판정값을 지나가며 기록한다.

    🔴 진리값을 «한 번만» 계산해 그 bool 을 돌려준다 — 값을 그대로 돌려주면 `if` 가 한 번 더
       판정해, 호출마다 결과가 바뀌는 `__bool__`·`__len__` 이면 계측 전과 다른 팔로 간다
       (Grok `e4e26763` BROKEN). `if` 는 진리값만 쓰므로 bool 을 돌려줘도 출력은 같다.
    Truthiness is evaluated exactly once, as in the unpatched `if`.
    """
    truth = bool(value)
    (_SEEN if seen is None else seen).setdefault(key, set()).add(truth)
    return truth


def instrument(tree: jinja2.nodes.Template, name: str | None, env: jinja2.Environment) -> list[str]:
    """트리의 모든 `If` 의 `test` 를 기록기 호출로 감싸고, 감싼 노드 id 목록을 돌려준다.

    🔴 템플릿이 기록기 이름을 스스로 쓰면 계측이 렌더 결과를 바꾼다(`{% if __branch_probe__ %}`
       가 참이 된다 — Grok `e4e26763` BROKEN). 그런 템플릿은 감싸지 않고 거부한다.
    """
    if any(n.name == _PROBE for n in tree.find_all(jinja2.nodes.Name)):
        raise ValueError(f"{name}: 템플릿이 예약된 이름 `{_PROBE}` 를 쓴다 — 계측하면 출력이 바뀐다")
    ids = []
    for seq, node in enumerate(list(tree.find_all(jinja2.nodes.If))):
        key = f"{name}:{node.lineno}:{seq}"
        call = jinja2.nodes.Call(jinja2.nodes.Name(_PROBE, "load"),
                                 [jinja2.nodes.Const(key), node.test], [], None, None)
        call.set_lineno(node.lineno)
        call.set_environment(env)
        node.test = call
        ids.append(key)
    return ids


def _patched_parse(self, source, name, filename):
    tree = _ORIG_PARSE(self, source, name, filename)
    ids = instrument(tree, name, self)
    _DECLARED.update(ids)
    _PARSES.setdefault(name, []).append(len(ids))
    self.globals[_PROBE] = record
    return tree


def static_counts(templates_dir: Path = _TEMPLATES) -> dict[str, int]:
    """{템플릿 이름: `If` 수} — 템플릿 전부를 «감싸지 않고» 따로 파싱한 대조군."""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)))
    out = {}
    for path in sorted(templates_dir.rglob("*.html")):
        name = path.relative_to(templates_dir).as_posix()
        tree = _ORIG_PARSE(env, path.read_text(encoding="utf-8"), name, str(path))
        out[name] = len(list(tree.find_all(jinja2.nodes.If)))
    return out


def _declared_counts(declared: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key in declared:
        name = key.rsplit(":", 2)[0]
        out[name] = out.get(name, 0) + 1
    return out


def _valid(declared: set[str], parses: dict[str | None, list[int]], static: dict[str, int]) -> bool:
    """이 실행의 수치를 쓸 수 있는가.

    🔴 총계가 아니라 «템플릿별 개수» 를 본다 — 안 불린 템플릿의 `If` 수를 다른 출처
       (`from_string` 등)가 우연히 메우면 총계는 같다. 그리고 «파싱마다» 정적 개수와 같아야
       한다 — 실행 중 템플릿이 바뀌어 두 번 파싱되면 id 합집합만으로는 맞아 보일 수 있다
       (Grok `19e5d0a7` BROKEN). `If` 0개 템플릿은 id 를 못 만들므로 id 대조에서만 뺀다.
    """
    if _declared_counts(declared) != {k: v for k, v in static.items() if v}:
        return False
    # 정적 전수 밖의 출처(`from_string` 등)는 `If` 를 하나라도 만들었을 때만 이 실행을 버린다 —
    # `If` 0개면 id 를 못 만들어 수치에 닿지 않는다(Grok `19e5d0a7` 재판정).
    return all(all(n == static[name] for n in counts) if name in static else not any(counts)
               for name, counts in parses.items())


def summarize(declared: set[str] | None = None, seen: dict[str, set[bool]] | None = None,
              static: dict[str, int] | None = None,
              parses: dict[str | None, list[int]] | None = None) -> dict:
    """노드별 «참 팔·거짓 팔» 관측 여부와 합계. `valid` 가 거짓이면 수치를 쓰지 않는다."""
    declared = _DECLARED if declared is None else declared
    seen = _SEEN if seen is None else seen
    static = static_counts() if static is None else static
    parses = _PARSES if parses is None else parses
    per_node = {key: {"true": True in seen.get(key, ()), "false": False in seen.get(key, ())}
                for key in sorted(declared)}
    return {
        "declared": len(declared),
        "static": sum(static.values()),
        "valid": _valid(declared, parses, static),
        "arms": 2 * len(declared),
        "unobserved_arms": sum((not v["true"]) + (not v["false"]) for v in per_node.values()),
        "unobserved_both": sum(1 for v in per_node.values() if not (v["true"] or v["false"])),
        "nodes": per_node,
    }


def pytest_configure(config):  # noqa: ARG001 — pytest 훅 서명
    jinja2.Environment._parse = _patched_parse


def pytest_unconfigure(config):  # noqa: ARG001 — pytest 훅 서명
    jinja2.Environment._parse = _ORIG_PARSE


def pytest_terminal_summary(terminalreporter):
    report = summarize()
    out = os.environ.get("BRANCH_PROBE_OUT")
    if out:
        Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    verdict = "" if report["valid"] else "  🔴 declared ≠ static — 이 실행의 수치는 쓰지 않는다"
    terminalreporter.write_line(
        f"branch probe: 미관측 팔 {report['unobserved_arms']}/{report['arms']} · "
        f"양쪽 미관측 노드 {report['unobserved_both']} · "
        f"declared {report['declared']} / static {report['static']}{verdict}")
