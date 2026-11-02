"""e2e 분기 프로브(`e2e/branchprobe.py`)가 «팔» 을 바르게 센다 — 계기 자체의 시험.

e2e 시험 몇 곳이 «그 노드가 돌았는가» 의 심판으로 이 계기를 가리킨다. 계기가 커밋되지 않으면
그 심판은 없는 것이고(회고 2026-09-16 P2-74), 커밋돼도 틀리게 세면 거짓 심판이다.
여기서는 전역 패치 없이 `instrument` 를 작은 템플릿에 직접 걸어 잰다.

The probe that several e2e tests name as the judge must count arms correctly.
"""
from __future__ import annotations

import jinja2

from e2e import branchprobe


def _render(source: str, **ctx) -> tuple[list[str], dict[str, set[bool]]]:
    """`source` 를 계측해 한 번 렌더한다 — (감싼 id, 관측) 을 돌려준다."""
    env = jinja2.Environment(autoescape=True)
    seen: dict[str, set[bool]] = {}
    tree = env.parse(source, name="t.html")
    ids = branchprobe.instrument(tree, "t.html", env)
    env.globals[branchprobe._PROBE] = lambda key, value: branchprobe.record(key, value, seen)
    env.from_string(tree).render(**ctx)
    return ids, seen


def test_each_arm_is_recorded_only_when_it_renders():
    """참 값이면 «참 팔» 만, 거짓이면 «거짓 팔» 만 기록된다 — 렌더 결과는 그대로다."""
    src = "{% if x %}A{% else %}B{% endif %}"
    ids, seen = _render(src, x=True)
    assert seen == {ids[0]: {True}}
    _, seen = _render(src, x=False)
    assert seen == {ids[0]: {False}}
    assert jinja2.Environment(autoescape=True).from_string(src).render(x=True) == "A"


def test_truthiness_is_evaluated_once_as_in_the_unpatched_if():
    """호출마다 진리값이 바뀌는 값도 계측 전과 같은 팔로 간다(Grok `e4e26763` 반례)."""
    class Flip:
        calls = 0

        def __bool__(self):
            Flip.calls += 1
            return Flip.calls % 2 == 1      # 첫 판정만 참

    src = "{% if q %}Y{% else %}N{% endif %}"
    unpatched = jinja2.Environment(autoescape=True).from_string(src).render(q=Flip())
    Flip.calls = 0
    env = jinja2.Environment(autoescape=True)
    tree = env.parse(src)
    branchprobe.instrument(tree, "t.html", env)
    env.globals[branchprobe._PROBE] = lambda key, value: branchprobe.record(key, value, {})
    assert env.from_string(tree).render(q=Flip()) == unpatched == "Y"
    assert Flip.calls == 1


def test_two_ifs_on_one_line_and_elif_get_distinct_ids():
    """한 줄의 두 `if` · `elif` 는 서로 다른 노드다 — 줄만 열쇠로 쓰면 합쳐진다."""
    src = "{% if a %}1{% endif %}{% if b %}2{% elif c %}3{% endif %}"
    ids, seen = _render(src, a=True, b=False, c=True)
    assert len(ids) == len(set(ids)) == 3, ids
    assert [seen.get(i) for i in ids] == [{True}, {False}, {True}]


def test_summary_counts_unobserved_arms_and_flags_an_invalid_run():
    """«양쪽 미관측» · «미관측 팔» 합계, 그리고 템플릿별 개수가 다르면 `valid` 거짓."""
    declared = {"a.html:1:0", "a.html:2:1", "b.html:3:0"}
    seen = {"a.html:1:0": {True, False}, "a.html:2:1": {True}}
    report = branchprobe.summarize(declared, seen, static={"a.html": 2, "b.html": 1})
    assert (report["arms"], report["unobserved_arms"], report["unobserved_both"]) == (6, 3, 1)
    assert report["valid"]
    assert not branchprobe.summarize(declared, seen, static={"a.html": 2, "b.html": 2})["valid"]
    # 총계는 같아도(3 = 3) 템플릿이 다르면 거짓 — 안 불린 c.html 을 다른 출처가 메운 경우.
    assert not branchprobe.summarize(declared, seen, static={"a.html": 2, "c.html": 1})["valid"]
    # `If` 0개 템플릿은 id 를 만들 수 없다 — 그것 때문에 영원히 거짓이 되면 계기가 죽는다.
    assert branchprobe.summarize(declared, seen,
                                 static={"a.html": 2, "b.html": 1, "z.html": 0})["valid"]


def test_a_run_whose_parse_differs_from_the_static_parse_is_invalid():
    """파싱마다 정적 개수와 같아야 한다 — 실행 중 바뀐 템플릿을 두 번 파싱하면 id 합집합은
    맞아 보일 수 있다(Grok `19e5d0a7` 반례: 정적 2개 · 두 파싱이 서로 다른 줄의 1개씩)."""
    declared = {"t.html:3:0", "t.html:7:0"}
    static = {"t.html": 2}
    assert branchprobe.summarize(declared, {}, static=static, parses={"t.html": [2]})["valid"]
    assert not branchprobe.summarize(declared, {}, static=static,
                                     parses={"t.html": [1, 1]})["valid"]
    # 정적 전수 밖의 출처(`from_string` = 이름 None)가 `If` 를 만들면 이 실행은 쓰지 않는다.
    assert not branchprobe.summarize(declared, {}, static=static,
                                     parses={"t.html": [2], None: [1]})["valid"]
    # `If` 0개 출처는 id 를 못 만들어 수치에 닿지 않는다(Grok `19e5d0a7` 재판정 반례).
    assert branchprobe.summarize(declared, {}, static=static,
                                 parses={"t.html": [2], None: [0]})["valid"]


def test_static_counts_match_a_direct_parse_of_every_template():
    """정적 전수가 템플릿을 하나라도 빼먹으면 `valid` 판정이 거짓 초록을 낸다."""
    env = jinja2.Environment(autoescape=True)
    paths = sorted(branchprobe._TEMPLATES.rglob("*.html"))
    assert paths, "템플릿을 0개 찾았다 — 정적 전수가 공허하다"
    direct = {p.relative_to(branchprobe._TEMPLATES).as_posix():
              len(list(env.parse(p.read_text(encoding="utf-8")).find_all(jinja2.nodes.If)))
              for p in paths}
    assert sum(direct.values()) > 0
    assert branchprobe.static_counts() == direct


def test_a_template_using_the_probe_name_is_refused():
    """기록기 이름을 쓰는 템플릿은 계측하면 출력이 바뀐다 — 조용히 감싸지 않고 거부한다."""
    env = jinja2.Environment(autoescape=True)
    tree = env.parse(f"{{% if {branchprobe._PROBE} %}}y{{% else %}}n{{% endif %}}")
    try:
        branchprobe.instrument(tree, "t.html", env)
    except ValueError as exc:
        assert branchprobe._PROBE in str(exc)
    else:
        raise AssertionError("예약 이름을 쓰는 템플릿을 그대로 계측했다")
    for path in sorted(branchprobe._TEMPLATES.rglob("*.html")):
        assert branchprobe._PROBE not in path.read_text(encoding="utf-8"), path


def test_importing_the_module_does_not_patch_jinja():
    """전역 패치는 플러그인으로 켰을 때만 — import 만으로 단위 스위트의 Jinja 가 바뀌면 안 된다."""
    assert jinja2.Environment._parse is branchprobe._ORIG_PARSE
