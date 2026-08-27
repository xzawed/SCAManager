"""새로 넣은 **유한 증거집합 술어**에 외부 반례 코퍼스를 강제한다.

## 왜 (실측 2026-08-27, 머지 PR 9건 · 개별 결함 24건 · 5회 독립 측정)

    조용한 결함(내 테스트가 전부 초록)   15건 중 내가 발견 **13%**
    시끄러운 결함(크래시·틀린 수·즉시 red)  9건 중 내가 발견 **89%**   -> 6.7배
    기전을 이미 커밋에 적은 **뒤** 재발    15/24 = **62%**

대응 교훈 파일은 2026-08-06·08-08·08-25 자로 이미 있었고 세션마다 로드됐다.
**적어 두는 것으로는 막히지 않는다.** Grok(01a043d3): 교훈은 세션 시작과 커밋 시점에
쓰이는데 결정은 그 사이, 술어를 타이핑하는 순간에 있다.

Grok(01a043d1)이 그 결함들을 한 문장으로 묶었다:

    의미 부류의 소속 판정을 **유한한 표면 증거 목록**으로 썼다 —
    그 부류의 다른 증거는 보이지 않고 통과한다.

## 무엇을 요구하나

새 술어를 넣으면, 그 PR 의 테스트가 **검사에서 뽑지 않은** 값을 최소 2개 소비해야 한다.
코퍼스가 「범위를 정하지 않은 사람」의 자리를 대신한다 — 1인 작업에는 그 사람이 없고,
「쓰는 순간에 기억하라」는 실측 62% 실패 채널이다.

코퍼스 표기:

    # witness-corpus: <왜 이것들이 같은 부류인가 — 16자 이상>
    _SOME_NAME = ["+0", "00", ".0"]

## 🔴 이 가드도 같은 기전에 걸린다

무엇이 「증거집합 술어」인지 판정하는 것 자체가 증거집합 술어다. 그래서 넓게 잡고
면제로 좁히며(과탐은 한 줄, 미탐은 결함), 비공허성을 **실제 사건**으로 증명한다
(`tests/unit/scripts/fixtures/witness_corpus/`).

설계 중에 실제로 그 일이 있었다 — 첫 탐지기는 `in` 의 오른쪽만 봐서 `"e" in raw`
(리터럴이 왼쪽)를 놓쳤다. 내 테스트는 초록이었고 역사 코퍼스가 잡았다.

Require an externally-sourced counterexample corpus for any newly added predicate that
decides class membership from a finite list of surface witnesses.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import subprocess
import sys


def _make_stdout_safe() -> None:
    """Windows(cp949) 콘솔에서 한국어 출력이 UnicodeEncodeError 로 죽는 것을 막는다.

    이미 UTF-8 이면 손대지 않는다 — 무조건 감싸면 pytest 캡처 스트림을 닫는다.
    """
    encoding = str(getattr(sys.stdout, "encoding", "") or "")
    if encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


_make_stdout_safe()

# 🔴 임계값은 **직관이 아니라 코퍼스**가 정했다. 첫 판은 「크기 3 이상」 일괄이었고,
#    역사 코퍼스가 그것을 반증했다 — 실제 보안 오라클은 크기 **2**(`{"hmac","secrets"}`)
#    였다. 세 규칙을 코퍼스로 비교한 실측:
#
#        규칙                       역사 3건   트리 발화   이지선다 오탐
#        크기>=3 일괄                 2/3        56          아니오
#        카탈로그>=2 · 인라인>=3      3/3 ✅     65          아니오
#        크기>=2 일괄                 3/3        96          예(나쁨)
#
#    가르는 것은 크기가 아니라 **모양**이다: 모듈 최상위에 이름을 붙여 둔 집합은
#    「부류의 카탈로그」고, 인라인 2원소는 대개 이지선다(`("utf-8","utf8")`, 실측 49건)다.
#    문자열 containment 는 크기와 무관하다 — `"e" in raw` 가 크기 1 이었다.
# Thresholds chosen by the corpus, not by intuition: a named module-level set is a
# catalogue of a class; an inline pair is usually a spelling choice.
MIN_CATALOGUE_SIZE = 2   # 모듈 최상위 명명 상수
MIN_INLINE_SIZE = 3      # 그 자리에 쓴 리터럴
MIN_REASON = 16
MIN_OUTSIDE = 2

CORPUS_MARKER = re.compile(r"#\s*witness-corpus:\s*(\S.*)")
EXEMPT = re.compile(
    r"^[ \t]*(?![`'\"])witness-corpus-not-applicable\s*:\s*\S.{%d,}" % (MIN_REASON - 1),
    re.MULTILINE)

_SCANNED = ("src", "scripts")

# (줄, 형태, 증거 수, 증거값) — 증거값이 있어야 「바깥」을 잴 수 있다.
Hit = tuple[int, str, int, frozenset]


def _literal_size(node: ast.AST | None) -> int | None:
    """리터럴만으로 이루어진 컨테이너의 원소 수 — 아니면 None.

    🔴 dict 는 여기에 둔다 — 이 함수는 `in` 비교의 피연산자에서만 불리므로
    `k in {"a": 1, "b": 2}` 만 잡고, 그냥 놓인 dict 리터럴은 안 잡는다.
    독립 절로 뒀을 때는 **아무 3키 dict** 나 잡았다(Grok 01a043f2 MISSED).
    """
    if isinstance(node, ast.Set | ast.List | ast.Tuple):
        if node.elts and all(isinstance(e, ast.Constant) for e in node.elts):
            return len(node.elts)
    if isinstance(node, ast.Dict) and node.keys \
            and all(isinstance(k, ast.Constant) for k in node.keys if k):
        return len(node.keys)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("frozenset", "set", "tuple", "list") and node.args:
        return _literal_size(node.args[0])
    return None


def _module_constants(tree: ast.Module) -> dict[str, int]:
    """모듈 최상위의 리터럴 컨테이너 상수 이름 -> 원소 수."""
    out: dict[str, int] = {}
    for node in tree.body:
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        targets = ([node.target] if isinstance(node, ast.AnnAssign)
                   else getattr(node, "targets", []))
        size = _literal_size(value) if value is not None else None
        if size:
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = size
    return out


def _module_values(tree: ast.Module) -> dict[str, frozenset[str]]:
    """모듈 최상위 리터럴 컨테이너 상수 이름 -> 그 안의 문자열 값들."""
    out: dict[str, frozenset[str]] = {}
    for node in tree.body:
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        targets = ([node.target] if isinstance(node, ast.AnnAssign)
                   else getattr(node, "targets", []))
        vals = _literal_values(value) if value is not None else frozenset()
        if vals:
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = vals
    return out


def _literal_values(node: ast.AST | None) -> frozenset[str]:
    """리터럴 컨테이너 안의 문자열 값 — 증거집합의 **실제 증거**들."""
    if isinstance(node, ast.Set | ast.List | ast.Tuple):
        return frozenset(e.value for e in node.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str))
    if isinstance(node, ast.Dict):
        return frozenset(k.value for k in node.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("frozenset", "set", "tuple", "list") and node.args:
        return _literal_values(node.args[0])
    return frozenset()


def _compare_hits(node: ast.Compare, consts: dict[str, int],
                  values: dict[str, frozenset[str]]) -> list[Hit]:
    """`in` / `not in` 의 **양쪽**을 본다.

    🔴 `"e" in raw` 는 리터럴이 왼쪽이다 — 오른쪽만 보면 이 탐지기가 바로 그 결함을
    재현한다(설계 중에 실제로 재현했고, 역사 코퍼스가 잡았다).
    """
    out: list[Hit] = []
    for side in [node.left, *node.comparators]:
        if isinstance(side, ast.Constant) and isinstance(side.value, str):
            out.append((node.lineno, "문자열 containment", 1, frozenset({side.value})))
        elif (size := _literal_size(side)) and size >= MIN_INLINE_SIZE:
            out.append((node.lineno, "인라인 리터럴 집합", size, _literal_values(side)))
        elif isinstance(side, ast.Name) and consts.get(side.id, 0) >= MIN_CATALOGUE_SIZE:
            out.append((node.lineno, f"카탈로그 {side.id}", consts[side.id],
                        values.get(side.id, frozenset())))
    return out


def _call_hits(node: ast.Call) -> list[Hit]:
    """호출 형태의 증거집합 — `isinstance` 타입 열거 · 접두/접미 튜플 · 정규식 교대."""
    out: list[Hit] = []
    if isinstance(node.func, ast.Name) and node.func.id == "isinstance" \
            and len(node.args) > 1:
        arg = node.args[1]
        size = (len(arg.elts) if isinstance(arg, ast.Tuple)
                else ast.dump(arg).count("BitOr") + 1 if isinstance(arg, ast.BinOp)
                else 0)
        if size >= MIN_INLINE_SIZE:
            out.append((node.lineno, "isinstance 타입 열거", size, frozenset()))
    elif isinstance(node.func, ast.Attribute):
        if node.func.attr in ("startswith", "endswith") and node.args:
            size = _literal_size(node.args[0])
            if size and size >= MIN_CATALOGUE_SIZE:
                out.append((node.lineno, f"{node.func.attr} 튜플", size,
                            _literal_values(node.args[0])))
        elif node.func.attr == "compile":
            out += [(node.lineno, "정규식 교대", a.value.count("|") + 1,
                     frozenset(a.value.split("|")))
                    for a in node.args
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)
                    and a.value.count("|") + 1 >= MIN_INLINE_SIZE]
    return out


def find_predicates(path: pathlib.Path) -> list[Hit]:
    """파일에서 유한 증거집합 술어를 찾는다 -> [(줄, 형태, 증거 수, 증거값)]."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    consts = _module_constants(tree)
    values = _module_values(tree)
    hits: list[Hit] = []

    # 🔴 카탈로그 **정의 줄**도 술어로 센다. 이름에 값을 하나 더 넣기만 하면
    #    `in` 줄은 안 바뀌어 diff 밖으로 빠진다 — 그것이 오늘의 실제 결함이었다
    #    (`_STRONG_MODULES` 에 이름을 더하는 것으로 오라클이 넓어진다). Grok 01a043f2 Q2.
    # A catalogue that merely GROWS leaves the `in` line untouched; count the definition.
    for node in tree.body:
        targets = ([node.target] if isinstance(node, ast.AnnAssign)
                   else getattr(node, "targets", []))
        for target in targets:
            if isinstance(target, ast.Name) \
                    and consts.get(target.id, 0) >= MIN_CATALOGUE_SIZE:
                hits.append((node.lineno, f"카탈로그 정의 {target.id}",
                             consts[target.id], values.get(target.id, frozenset())))

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) \
                and any(isinstance(o, ast.In | ast.NotIn) for o in node.ops):
            hits += _compare_hits(node, consts, values)
        elif isinstance(node, ast.Call):
            hits += _call_hits(node)
    return sorted(set(hits))


def outside_witness(values: list[str], *, needles: set[str]) -> list[str]:
    """증거집합이 **알아보지 못하는** 값만 남긴다.

    🔴 이것이 요구의 본체다. `"e" in raw` 때 내 테스트는 `1e-400`·`0e0` 를 썼는데
    둘 다 검사가 잡는 값이라, 초록이 「부류를 덮었다」를 전혀 뜻하지 않았다.
    """
    return [v for v in values if not any(n in v for n in needles)]


def _git(*args: str) -> str:
    """🔴 git 출력을 **UTF-8 로** 읽는다.

    `text=True` 만 주면 로케일(Windows cp949)로 디코드해 한국어가 든 diff 에서
    `UnicodeDecodeError` 로 죽고, 그때 `stdout` 은 None 이라 뒤에서 또 터진다.
    실제로 이 가드의 첫 판이 그렇게 죽었다.

    Decode git output as UTF-8; the locale codec dies on Korean diffs.
    """
    proc = subprocess.run(["git", *args], capture_output=True, check=False,
                          encoding="utf-8", errors="replace")
    return proc.stdout or ""


def _added_files(base: str) -> list[pathlib.Path]:
    out = _git("diff", "--name-only", f"{base}...HEAD")
    return [pathlib.Path(p) for p in out.split("\n")
            if p.strip() and p.split("/")[0] in _SCANNED and p.endswith(".py")]


def _added_lines(base: str, path: pathlib.Path) -> set[int]:
    """PR 에서 **새로 추가된** 줄 번호 — 기존 술어까지 요구하면 착수가 막힌다."""
    diff = _git("diff", "-U0", f"{base}...HEAD", "--", str(path))
    added: set[int] = set()
    for line in diff.split("\n"):
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or 1)
            added.update(range(start, start + count))
    return added


def _corpus_values(paths: list[pathlib.Path]) -> tuple[list[str], list[str]]:
    """`# witness-corpus:` 표기가 붙은 컬렉션의 **문자열 값**과 사유를 뽑는다.

    🔴 표기만 세면 주석 한 줄로 통과한다 — 첫 판이 그랬고 실측으로 exit 0 이었다.
    값을 세야 「검사가 못 알아보는 것을 실제로 넣었는가」를 물을 수 있다.

    Collect the literal values under a marker, not just the marker.
    """
    values: list[str] = []
    reasons: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        marked = {i for i, line in enumerate(text.split("\n"))
                   if (m := CORPUS_MARKER.search(line))
                   and len(m.group(1).strip()) >= MIN_REASON}
        if not marked:
            continue
        reasons += [CORPUS_MARKER.search(line).group(1).strip()
                    for i, line in enumerate(text.split("\n")) if i in marked]
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign | ast.AnnAssign):
                continue
            # 표기는 대입 **바로 위** 줄들에 있다 — 몇 줄 위까지 본다(데코레이터·주석 여유).
            if not any(node.lineno - k - 2 in marked for k in range(4)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    values.append(sub.value)
    return values, reasons


def _new_predicates(base: str) -> list[tuple[str, int, str, frozenset]]:
    """PR 에서 **새로 추가된 줄**에 있는 증거집합 술어."""
    out = []
    for path in _added_files(base):
        if not path.exists():
            continue
        added = _added_lines(base, path)
        for line, kind, _size, evidence in find_predicates(path):
            if line in added:
                out.append((path.as_posix(), line, kind, evidence))
    return out


def _report_missing(new, values, needles, outside) -> int:
    """왜 막혔는지 말한다 — 「무엇을 하라」까지 적지 않으면 사람이 가드를 끈다."""
    if values:
        print(f"🔴 반례 코퍼스가 있지만 **검사가 알아보는 값뿐**이다 "
              f"(바깥 {len(outside)} < {MIN_OUTSIDE}):")
        print("   The corpus holds only values the check already recognises.")
        print(f"   증거집합: {sorted(needles)[:8]}")
        print(f"   코퍼스 값: {values[:8]}")
        print()
        print('   `"e" in raw` 때 내 테스트는 `1e-400`·`0e0` 를 썼다 — 둘 다 검사가')
        print("   **잡는** 값이라, 초록이 부류를 덮었다는 뜻이 전혀 아니었다.")
        return 1

    print("🔴 새 **유한 증거집합 술어**에 외부 반례 코퍼스가 없다:")
    print("   New finite-witness-set predicate without an external counterexample corpus:")
    for path, line, kind, evidence in new:
        shown = f" {sorted(evidence)[:5]}" if evidence else ""
        print(f"   - {path}:{line}  {kind}{shown}")
    print()
    print("해결 / Fix: 이 PR 의 테스트에 그 부류이면서 **검사가 못 알아보는** 값을")
    print(f"   {MIN_OUTSIDE}개 이상 두고, 그 컬렉션 위에 표기하세요:")
    print("     # witness-corpus: <왜 이것들이 같은 부류인가 — 16자 이상>")
    print("   그 값은 검사에서 뽑지 마세요 — 이슈·코퍼스·실사건에서 가져옵니다.")
    print("   해당 없으면 PR 본문 열 0 에 "
          "`witness-corpus-not-applicable: <사유 16자 이상>`.")
    print()
    print("   실측 근거: 조용한 결함 발견율 13% vs 시끄러운 결함 89% · "
          "기전 인지 후 재발 62%.")
    return 1


def main() -> int:
    """새 술어가 있는데 **검사 바깥의** 반례가 부족하면 1."""
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    body = subprocess.run(
        ["gh", "pr", "view", "--json", "body", "--jq", ".body"],
        capture_output=True, check=False, encoding="utf-8", errors="replace",
    ).stdout or ""
    if EXEMPT.search(body):
        print("✅ 면제 선언 — witness-corpus-not-applicable (사유 있음)")
        return 0

    new = _new_predicates(base)
    if not new:
        print("✅ 새 증거집합 술어 없음")
        return 0

    changed = _git("diff", "--name-only", f"{base}...HEAD")
    tests = [pathlib.Path(p) for p in changed.split("\n")
             if p.strip().startswith(("tests/", "e2e/")) and p.endswith(".py")]
    values, reasons = _corpus_values(tests)

    # 🔴 여기가 이 가드의 본체다. 표기가 있는지가 아니라, **검사가 못 알아보는 값을
    #    실제로 넣었는지**를 묻는다. 첫 판은 표기만 세서 주석 한 줄로 통과했다
    #    (Grok 01a043f2 Q1, 실측 exit 0) — 그것은 서류 절차이지 가드가 아니었다.
    needles: set[str] = set()
    for _p, _l, _k, evidence in new:
        needles |= set(evidence)
    outside = outside_witness(values, needles=needles) if needles else values

    if len(outside) >= MIN_OUTSIDE:
        print(f"✅ 새 술어 {len(new)}건 · 검사 **바깥** 반례 {len(outside)}건")
        for reason in reasons[:3]:
            print(f"   - {reason[:70]}")
        return 0

    return _report_missing(new, values, needles, outside)


if __name__ == "__main__":
    sys.exit(main())
