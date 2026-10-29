"""Anthropic 호출 인자 ↔ 설치된 SDK 시그니처 — 시험 더블이 못 보는 축.

시험은 `client.messages.create` 를 아무 키워드나 받는 더블로 바꿔 끼운다. 그래서 SDK 가 받지
않는 키워드(오타 · SDK 가 지운 인자)는 시험에서 초록이고 운영에서만 `TypeError` 로 터진다.
`temperature`·`top_p`·`top_k` 가 그렇다 — `messages.create` 시그니처에 없고, `extra_body` 로 실으면
API 버전 2026-10-21(anthropic 2.x 기본)이 모든 모델에서 400 으로 거절한다
(platform.claude.com/docs/en/api/migration-2026-10-21 · 1. Sampling parameters are removed).

호출 자리를 AST 로 읽어 **설치된 SDK 메서드의 시그니처**와 대조한다 — 받는 인자를 손으로 적지
않으므로 SDK 판이 바뀌면 기준도 따라간다(그래서 설치본 = requirements.txt 핀인지 먼저 본다).
읽을 수 없는 모양(`**` 펼침 · 리터럴이 아닌 `extra_body` · 호출 없이 꺼낸 별칭 · `.messages.<SDK 메서드>`
모양 밖의 `.messages`)은 통과가 아니라 red 다. `messages` 를 속성 문법이 아니라 문자열로 꺼내는 접근
(`getattr(client, "messages")` · `vars` · `__dict__`)·exec/eval·SDK 범용 요청(`client.post`)·httpx 직접
호출은 보지 않는다 — 실수를 잡는 계기이지 우회를 막는 경계가 아니다.
Test doubles accept any keyword, so check every Anthropic call site against the installed SDK's
signature instead; a shape this test cannot read is a failure, not a pass.
"""
import ast
import inspect
import re
import subprocess
from pathlib import Path

import anthropic
import pytest
from anthropic.resources.beta.messages import AsyncMessages as AsyncBetaMessages
from anthropic.resources.beta.messages import Messages as BetaMessages
from anthropic.resources.messages import AsyncMessages, Messages

_ROOT = Path(__file__).resolve().parents[3]
# 실제 API 에 닿는 코드만 본다 — 시험(tests/ · e2e/)은 더블을 부른다.
# Only code that reaches the real API; the test trees call doubles.
_TEST_TREES = ("tests/", "e2e/")
# API 버전 2026-10-21 이 거절하는 표본추출 인자 — 시그니처에 없으니 `extra_body` 로만 실린다.
# Sampling fields rejected on API version 2026-10-21; only `extra_body` can still carry them.
_SAMPLING = frozenset({"temperature", "top_p", "top_k"})
# `messages.with_raw_response.create(...)` 처럼 `messages` 와 메서드 사이에 끼는 래퍼.
# Wrappers that may sit between `messages` and the method.
_RAW = frozenset({"with_raw_response", "with_streaming_response"})
# 실패 메시지의 종류 설명 / What each violation kind means.
_KIND = {
    "unknown": "설치된 SDK 가 받지 않는 키워드 — 운영에서 TypeError",
    "missing": "SDK 필수 키워드가 빠졌다 — 운영에서 TypeError",
    "positional": "위치 인자 — SDK 메서드는 키워드만 받는다",
    "sampling": "`extra_body` 의 표본추출 인자 — API 버전 2026-10-21 이 400 으로 거절한다",
    "spread": "`**` 로 펼친 인자 — 이 시험이 키워드를 읽을 수 없다(키워드로 적는다)",
    "unreadable": "`extra_body` 가 문자열 키 dict 리터럴이 아니다 — 담긴 키를 읽을 수 없다",
    "alias": "호출 없이 꺼낸 메서드(별칭·partial) — 이 시험이 인자를 읽을 수 없다",
    "resource": "`.messages` 를 `.messages.<SDK 메서드>(...)` 모양 밖에서 썼다 — 뒤따르는 호출의 인자를 읽을 수 없다"
                "(SDK 와 무관한 속성이면 다른 이름을 쓴다)",
    "untyped": "SDK 가 임의 키워드를 받는 메서드 — 이 시험이 판정할 수 없다",
}


def _contract(sync_cls: type, async_cls: type) -> dict[str, tuple[frozenset[str], frozenset[str]] | None]:
    """메서드 → (받는 키워드, 꼭 넣을 키워드). 동기·비동기 둘 다 받는 것만 받는다고 본다.
    임의 키워드(`**`)를 받는 메서드는 None — 대조할 시그니처가 없다.
    Method → (accepted, required) keywords, accepted only when both clients take it;
    None where the SDK takes `**kwargs` and there is nothing to check against."""
    out: dict[str, tuple[frozenset[str], frozenset[str]] | None] = {}
    for name in sorted(set(vars(sync_cls)) & set(vars(async_cls))):
        fns = (vars(sync_cls)[name], vars(async_cls)[name])
        if name.startswith("_") or not all(inspect.isfunction(f) for f in fns):
            continue
        params = [list(inspect.signature(f).parameters.values()) for f in fns]
        if any(p.kind is p.VAR_KEYWORD for ps in params for p in ps):
            out[name] = None
            continue
        kw = [{p.name for p in ps if p.kind is p.KEYWORD_ONLY} for ps in params]
        req = [{p.name for p in ps if p.kind is p.KEYWORD_ONLY and p.default is p.empty} for ps in params]
        out[name] = (frozenset(kw[0] & kw[1]), frozenset(req[0] | req[1]))
    return out


_SDK = {False: _contract(Messages, AsyncMessages), True: _contract(BetaMessages, AsyncBetaMessages)}


def _method(node: ast.AST) -> tuple[bool, str] | None:
    """`<무엇>[.beta].messages[.with_raw_response].<SDK 메서드>` 면 (beta 여부, 메서드), 아니면 None.
    (is_beta, method) for a reference to an SDK messages method, else None."""
    if not isinstance(node, ast.Attribute):
        return None
    owner = node.value
    if isinstance(owner, ast.Attribute) and owner.attr in _RAW:
        owner = owner.value
    if not (isinstance(owner, ast.Attribute) and owner.attr == "messages"):
        return None
    beta = isinstance(owner.value, ast.Attribute) and owner.value.attr == "beta"
    return (beta, node.attr) if node.attr in _SDK[beta] else None


def _extra_body(value: ast.expr, line: int) -> list[tuple[int, str, str]]:
    if not isinstance(value, ast.Dict):
        return [(line, "unreadable", "extra_body")]
    bad = []
    for key in value.keys:
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            bad.append((line, "unreadable", "extra_body"))
        elif key.value in _SAMPLING:
            bad.append((line, "sampling", key.value))
    return bad


def _violations(source: str, rel: str) -> tuple[list[tuple[int, str, str]], int]:
    """(위반 `(줄, 종류, 이름)` 목록, 대조한 호출 수).
    (violations as (line, kind, name), number of calls checked)."""
    tree = ast.parse(source, filename=rel)
    bad: list[tuple[int, str, str]] = []
    calls = 0
    called: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or (hit := _method(node.func)) is None:
            continue
        called.add(id(node.func))
        calls += 1
        contract = _SDK[hit[0]][hit[1]]
        if contract is None:
            bad.append((node.lineno, "untyped", hit[1]))
            continue
        accepted, required = contract
        if node.args:
            bad.append((node.lineno, "positional", str(len(node.args))))
        given = set()
        for kw in node.keywords:
            if kw.arg is None:
                bad.append((node.lineno, "spread", "**"))
                continue
            given.add(kw.arg)
            if kw.arg not in accepted:
                bad.append((node.lineno, "unknown", kw.arg))
            elif kw.arg == "extra_body":
                bad += _extra_body(kw.value, node.lineno)
        # `**` 가 있으면 무엇이 들어갔는지 모른다 — 빠짐은 그쪽 위반이 이미 말한다.
        # With a `**` spread the given set is unknown; the spread violation already speaks.
        if all(kw.arg is not None for kw in node.keywords):
            bad += [(node.lineno, "missing", name) for name in sorted(required - given)]
    parent = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if id(node) not in called and (hit := _method(node)) is not None:
            bad.append((node.lineno, "alias", hit[1]))
        elif isinstance(node, ast.Attribute) and node.attr == "messages":
            bad += [(node.lineno, "resource", name) for name in _escape(node, parent)]
    return bad, calls


def _escape(node: ast.Attribute, parent: dict[int, ast.AST]) -> list[str]:
    """`.messages` 가 `.messages[.with_raw_response].<SDK 메서드>` 모양 밖에서 쓰였는가.
    새는 길(인자·반환·변수·`batches`·던더로 메서드 꺼내기 …)을 열거하면 늘 하나가 남는다 — 그래서
    «이 모양이 아니면 전부» 잡는다. 대입 대상(`self.messages = []`)만 새지 않는다.
    🔴 대가: 시험 밖 코드에서 SDK 와 무관한 `.messages`(`self.messages.append` · `len(x.messages)`)도
    red 다 — 지금 그런 쓰임은 0건이고, 생기면 다른 이름을 쓴다.
    Anything but the checked call shape fails rather than enumerating escape routes; the price is
    that a non-SDK `.messages` outside the test trees fails too (none exist today)."""
    if isinstance(node.ctx, (ast.Store, ast.Del)):
        return []
    up = parent.get(id(node))
    if not (isinstance(up, ast.Attribute) and up.value is node):
        return ["messages"]
    if _method(up) is not None:
        return []
    top = parent.get(id(up))
    if up.attr in _RAW and isinstance(top, ast.Attribute) and top.value is up and _method(top) is not None:
        return []
    return [up.attr]


def _sources() -> list[Path]:
    """git 이 추적하는 `.py` 중 시험 밖 — `rglob` 은 .gitignore 를 무시해 가상환경까지 읽는다.
    Tracked .py files outside the test trees (rglob would ignore .gitignore)."""
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=_ROOT,
                         capture_output=True, check=True).stdout.decode("utf-8")
    names = sorted({n for n in out.split("\0") if n and not n.startswith(_TEST_TREES)})
    return [_ROOT / n for n in names if (_ROOT / n).is_file()]


def test_installed_anthropic_is_the_pinned_one():
    """대조 기준(설치본)이 운영이 설치할 판인가 — 다르면 아래 판정은 다른 SDK 를 잰 것이다.
    The yardstick must be the SDK version production installs."""
    pins = re.findall(r"(?im)^anthropic==([^\s;#]+)", (_ROOT / "requirements.txt").read_text(encoding="utf-8"))
    assert len(pins) == 1, f"requirements.txt 의 anthropic 핀이 {len(pins)}개 — 대조할 판을 정할 수 없다"
    assert anthropic.__version__ == pins[0], (
        f"설치된 anthropic {anthropic.__version__} ≠ 핀 {pins[0]} — "
        "`py -3 -m pip install -r requirements.txt` 뒤 다시 잰다")


def test_anthropic_calls_pass_only_what_the_installed_sdk_accepts():
    """시험 밖 모든 `messages.<메서드>(...)` 호출이 설치된 SDK 가 받는 키워드만 싣는다.
    Every call outside the test trees passes only keywords the installed SDK accepts."""
    bad: list[str] = []
    checked: dict[str, int] = {}
    for path in _sources():
        rel = path.relative_to(_ROOT).as_posix()
        found, calls = _violations(path.read_text(encoding="utf-8"), rel)
        bad += [f"{rel}:{line} `{name}` — {_KIND[kind]}" for line, kind, name in found]
        if calls:
            checked[rel] = calls
    # 🔴 대조한 호출이 0 이면 통과가 아니라 계기가 눈먼 것이다.
    # Zero calls checked means a blind instrument, not a pass.
    assert checked, "Anthropic messages 호출을 하나도 못 찾았다 — 검사 범위가 비었다"
    assert not bad, f"대조한 호출 {checked}\n  " + "\n  ".join(bad)


_OK = "model=m, max_tokens=1, messages=[]"


@pytest.mark.parametrize("snippet, expected", [
    (f"client.messages.create({_OK}, temperature=0)", [("unknown", "temperature")]),
    # 표본추출 단어가 아닌 오타 — `"temperature" in 소스` 로는 못 잡는다.
    # A typo with no sampling word in it — a substring scan would miss it.
    ("client.messages.create(model=m, max_token=1, messages=[])",
     [("unknown", "max_token"), ("missing", "max_tokens")]),
    (f"client.messages.create({_OK}, extra_body={{'top_p': 0.9}})", [("sampling", "top_p")]),
    (f"client.messages.create({_OK}, extra_body=body)", [("unreadable", "extra_body")]),
    (f"client.messages.create({_OK}, extra_body={{**base}})", [("unreadable", "extra_body")]),
    ("client.messages.create(**params)", [("spread", "**")]),
    ("create = client.messages.create", [("alias", "create")]),
    (f"client.with_options(timeout=5).messages.with_raw_response.create({_OK}, top_k=5)",
     [("unknown", "top_k")]),
    ("client.messages.stream(model=m, messages=[])", [("missing", "max_tokens")]),
    ("client.messages.create(m, max_tokens=1, messages=[])", [("positional", "1"), ("missing", "model")]),
    # 리소스가 값으로 새면 뒤따르는 `m.create(...)` 는 `.messages.` 모양이 아니라 위 대조를 비켜 간다.
    # Once the resource escapes as a value, the later `m.create(...)` no longer has the checked shape.
    ("m = client.messages", [("resource", "messages")]),
    ("getattr(client.messages, 'create')(model=m)", [("resource", "messages")]),
    ("client.messages.batches.create(requests=[])", [("resource", "batches")]),
    ("send(client.messages)", [("resource", "messages")]),
    ("def get(c):\n    return c.messages", [("resource", "messages")]),
    ("r = client.messages.with_raw_response", [("resource", "with_raw_response")]),
    ("client.messages.__getattribute__('create')(model=m)", [("resource", "__getattribute__")]),
    # 대가 — SDK 와 무관한 `.messages` 도 구별할 수 없다(시험 밖 코드에 지금 0건).
    # The price: a non-SDK `.messages` is indistinguishable (none outside the test trees today).
    ("n = len(self.messages)", [("resource", "messages")]),
    ("self.messages.append({'temperature': 0})", [("resource", "append")]),
])
def test_instrument_flags_what_the_sdk_rejects(snippet, expected):
    """잡아야 하는 모양 — 계기가 «잡는다» 고 주장하는 것.
    Shapes the instrument claims to catch."""
    bad, _ = _violations(snippet, "x.py")
    assert sorted((kind, name) for _, kind, name in bad) == sorted(expected)


@pytest.mark.parametrize("snippet", [
    # 주석 속 단어 · 다른 벤더 호출 · 대입 대상 — 부분문자열 스캔이라면 잡았을 것.
    # A word in a comment, another vendor's call, an assignment target: a substring scan would flag these.
    f"# temperature=0 은 보내지 않는다\nclient.messages.create({_OK})",
    "openai.chat.completions.create(model=m, temperature=0)",
    "self.messages = []",
    f"client.messages.with_raw_response.create({_OK})",
    f"client.beta.messages.create({_OK}, betas=['x'])",
    f"client.messages.create({_OK}, extra_body={{'x_custom': 1}})",
    f"async def f():\n    return await asyncio.wait_for(client.messages.create({_OK}), timeout=5)",
])
def test_instrument_ignores_what_the_sdk_accepts(snippet):
    """무시해야 하는 모양 — SDK 호출이 아니거나 SDK 가 받는 인자다.
    Shapes the instrument must ignore: not an SDK call, or arguments the SDK accepts."""
    bad, _ = _violations(snippet, "x.py")
    assert bad == []
