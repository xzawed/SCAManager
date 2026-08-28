"""유한 증거집합 술어에 **외부 반례 코퍼스**를 강제한다 (5회 실측 원인분석의 처방).

## 왜 이 가드가 있나 — 실측 (2026-08-27, 머지 PR 9건)

같은 날 하루 동안 개별 결함 24건을 기록했다. 5회 독립 측정의 결론:

    조용한 결함(내 테스트가 전부 초록)  15건 중 내가 발견 **13%**
    시끄러운 결함(크래시·틀린 수·즉시 red) 9건 중 내가 발견 **89%**   -> 6.7배

그리고 그 기전을 이미 커밋 메시지에 적은 **뒤에** 다시 낸 것이 **15/24 = 62%**.
대응하는 교훈 파일은 2026-08-06·08-08·08-25 자로 이미 있었고 세션마다 로드됐다.
**적어 두는 것으로는 막히지 않는다** — 교훈이 술어를 쓰는 순간에 조회되지 않는다.

Grok(01a043d1)이 그 결함 6건을 한 문장으로 묶었다:

> 의미 부류의 소속 판정을 **유한한 표면 증거 목록**으로 썼다 —
> 그 부류의 다른 증거는 보이지 않고 통과한다.

## 무엇을 강제하나

새로 넣은 증거집합 술어는, **그 검사에서 뽑지 않은** 반례 코퍼스를 테스트가 소비해야
머지된다. 코퍼스가 「다른 사람」의 자리를 대신한다 — 1인 작업에는 다른 사람이 없고,
「쓰는 순간에 기억하라」는 실측 62% 실패 채널이다(Grok 01a043d3).

## 🔴 이 가드도 같은 기전에 걸린다

무엇이 「증거집합 술어」인지를 판정하는 것 자체가 증거집합 술어다. 그래서:

  · 넓게 잡고 **면제로 좁힌다** — 과탐은 한 줄 비용, 미탐은 결함 비용이다.
  · 비공허성을 **실제 사건**으로 증명한다(`fixtures/witness_corpus/`) — 내가 만든
    예제로 증명하면 검사와 증명이 같은 상상을 공유한다.

설계 중에 실제로 그 일이 있었다: 첫 탐지기는 `in` 의 **오른쪽만** 봐서
`"e" in raw`(리터럴이 왼쪽)를 놓쳤다. 내 테스트는 초록이었고, 역사 코퍼스가 잡았다.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pathlib  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402

_ROOT = pathlib.Path(__file__).parents[3]
_SCRIPT = _ROOT / "scripts" / "check_witness_set_predicates.py"
_CORPUS = pathlib.Path(__file__).parent / "fixtures" / "witness_corpus"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(cwd or _ROOT), check=False)


# ─── 계기 자기검증 — 실제 사건으로 ─────────────────────────────────────────


def test_the_historical_corpus_exists_and_parses():
    """🔴 비공허성의 근거가 살아 있는지 먼저 잰다.

    코퍼스가 비면 아래 단언은 **아무것도** 확인하지 않는다.
    """
    import ast  # noqa: PLC0415

    files = sorted(_CORPUS.glob("*.pysnippet"))
    assert len(files) >= 3, f"역사 코퍼스가 {len(files)}건뿐 — 근거가 사라졌다"
    # 🔴 확장자가 `.py` 가 아닌 이유: 이것들은 모듈이 아니라 **증거 스냅샷**이다.
    #    실제 커밋에서 떼어 온 조각이라 그 자체로 완결되지 않고, `.py` 로 두면
    #    CodeQL 이 `py/unused-global-variable` 을 신고한다(실측). 읽는 쪽은
    #    `read_text` + `ast.parse` 라 확장자와 무관하다.
    for f in files:
        ast.parse(f.read_text(encoding="utf-8"))
        head = f.read_text(encoding="utf-8")[:900]
        assert "출처" in head, f"{f.name} 에 출처가 없다 — 사건이 아니라 내 예제가 된다"


@pytest.mark.parametrize("fixture", sorted(p.name for p in _CORPUS.glob("*.pysnippet")))
def test_every_historical_defect_is_detected(fixture):
    """🔴 실제로 머지 직전까지 갔던 술어를 **전부** 잡는다.

    하나라도 놓치면 이 가드는 그 결함을 다시 통과시킨다.
    """
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    hits = find_predicates(_CORPUS / fixture)
    assert hits, f"{fixture} 의 술어를 못 봤다 — 그 사건이 다시 지나간다"


def test_the_left_hand_literal_is_seen(tmp_path):
    """🔴 `"e" in raw` — 리터럴이 **왼쪽**이다.

    첫 탐지기는 오른쪽만 봐서 이 형태를 놓쳤다. 설계 중에 역사 코퍼스가 잡은 그 결함이다.
    """
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    sample = tmp_path / "left.py"
    sample.write_text('def f(raw):\n    return "e" in raw\n', encoding="utf-8")
    assert find_predicates(sample), "리터럴이 왼쪽인 containment 를 못 봤다"


def test_an_ordinary_two_value_choice_is_not_flagged(tmp_path):
    """반대쪽 — 2원소 선택지까지 잡으면 리포 전체가 red 가 되고 사람이 가드를 끈다.

    실측: `src/`+`scripts/` 에 2원소가 49건이다. 그것들은 부류 판정이 아니라 이지선다다.
    """
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    sample = tmp_path / "ok.py"
    sample.write_text(
        'def f(enc):\n    return enc.lower() in ("utf-8", "utf8")\n', encoding="utf-8")
    assert not find_predicates(sample), "이지선다까지 잡는다 — 과탐이다"


# ─── 이 탐지기가 **못 알아보는** 형태 ───────────────────────────────────────

# witness-corpus: 이 탐지기가 못 알아보는 형태 — 검사 바깥의 값이어야 뜻이 있다 —
#   추측이 아니라 **실행으로** 확인했다. 이 가드가 자기 자신에게 요구한 산출물이다:
#   검사가 알아보는 값만으로 테스트를 채우면 초록은 자기일관성만 뜻한다.
_SHAPES_NOT_YET_SEEN = {
    "any(... in ...) 생성식": '_W = ("tok", "sec")\ndef f(s):\n    return any(w in s for w in _W)\n',
    "집합 합집합": '_A = {"a", "b"}\n_B = {"c", "d"}\ndef f(x):\n    return x in _A | _B\n',
    "== 연쇄": 'def f(x):\n    return x == "a" or x == "b" or x == "c"\n',
    "match-case 교대": 'def f(x):\n    match x:\n        case "a" | "b" | "c":\n            return True\n',
}

# witness-corpus: 반대쪽 — 지금 잡는 형태. 좁히면 red 가 되어 조용한 축소를 막는다.
_SHAPES_SEEN = {
    "문자열 containment(왼쪽)": 'def f(raw):\n    return "e" in raw\n',
    "카탈로그 membership": '_S = {"hmac", "secrets"}\ndef f(x):\n    return x in _S\n',
    "인라인 리터럴 3원소": 'def f(x):\n    return x in ("a", "b", "c")\n',
    "isinstance 타입 열거": 'import ast\ndef f(n):\n    return isinstance(n, ast.Assign | ast.Expr | ast.With)\n',
    "startswith 튜플": 'def f(s):\n    return s.startswith(("http://", "https://"))\n',
    "정규식 교대": 'import re\n_P = re.compile(r"alpha|beta|gamma")\n',
    "dict 키 카탈로그": 'def f(k):\n    return k in {"a": 1, "b": 2, "c": 3}\n',
}


def _detects(tmp_path, name: str, src: str) -> bool:
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    sample = tmp_path / f"{abs(hash(name))}.py"
    sample.write_text(src, encoding="utf-8")
    return bool(find_predicates(sample))


@pytest.mark.parametrize("name", sorted(_SHAPES_SEEN))
def test_a_covered_shape_stays_covered(tmp_path, name):
    """🔴 지금 잡는 형태를 조용히 놓치게 되면 red — 축소가 소리 없이 지나가지 않는다."""
    assert _detects(tmp_path, name, _SHAPES_SEEN[name]), f"{name} 을 더 이상 못 잡는다"


def test_the_known_gaps_are_listed_not_assumed_away(tmp_path):
    """🔴 알려진 공백은 **목록에** 있어야 한다 — 다만 넓히는 것을 벌하지 않는다.

    첫 판은 「이 형태들이 여전히 안 잡히는가」를 단언했다. 그러면 탐지기를 넓힌 사람이
    red 를 보고 되돌리게 된다 — 개선에 벌을 주는 래칫이었다(Grok 01a043f2 Q3).

    지금은 **좁힘만** 막는다(위 `test_a_covered_shape_stays_covered`). 여기서는
    공백이 문서로 남아 있는지와, 이미 닫힌 것이 있으면 그것을 알려 주기만 한다.
    """
    closed = [n for n in _SHAPES_NOT_YET_SEEN
              if _detects(tmp_path, n, _SHAPES_NOT_YET_SEEN[n])]
    total = len(_SHAPES_SEEN) + len(_SHAPES_NOT_YET_SEEN)
    covered = len(_SHAPES_SEEN) + len(closed)
    print(f"\n  증거집합 형태 커버리지: {covered}/{total}")
    if closed:
        print(f"  이제 잡는 형태(목록에서 옮기면 좋다): {closed}")
    assert covered / total >= 0.6, (
        f"커버리지 {covered}/{total} — 너무 낮으면 가드가 통과 도장이 된다"
    )


def test_the_shape_list_is_not_empty():
    """🔴 공백 목록이 비면 「완전하다」는 주장이 된다.

    이 세션에서 「완전」이라고 적은 주장은 11건 중 7건이 반증됐다. 목록이 진짜로
    비게 되는 날에는 이 테스트를 지우는 것이 맞고, 그때는 그 판단이 남는다.
    """
    assert _SHAPES_SEEN, "커버 목록이 비었다 — 가드가 아무것도 안 잡는다"
    assert _SHAPES_NOT_YET_SEEN or len(_SHAPES_SEEN) >= 11, (
        "공백 목록이 비었는데 커버가 11종 미만이다 — 어느 쪽도 측정된 상태가 아니다"
    )


# ─── 코퍼스 요구 ────────────────────────────────────────────────────────────


def test_a_corpus_must_hold_values_the_predicate_does_not_recognise():
    """🔴 코퍼스가 **검사 안쪽 값**으로만 채워지면 아무것도 늘리지 못한다.

    `"e" in raw` 때 내 테스트는 `q=1e-400`·`q=0e0` 를 썼다 — 둘 다 검사가 **잡는** 값이다.
    놓친 것(`+0`·`00`·`.0`)은 하나도 없었다. 그것이 초록의 정체다.
    """
    from scripts.check_witness_set_predicates import outside_witness  # noqa: PLC0415

    assert outside_witness(["1e-400", "0e0"], needles={"e"}) == [], (
        "검사가 잡는 값만 있는데 바깥으로 셌다"
    )
    assert set(outside_witness(["+0", "00", ".0", "0e0"], needles={"e"})) == {
        "+0", "00", ".0"}, "검사가 못 잡는 값을 못 골라냈다"


def test_a_marker_without_values_does_not_satisfy_the_guard():
    """🔴 이 가드의 첫 판은 **극장**이었다 — 주석 한 줄로 exit 0 이었다.

    `main()` 이 `outside_witness` 를 한 번도 부르지 않아, 「표기가 있는가」만 봤다.
    Grok(01a043f2 Q1)이 「서류 절차이지 fail-closed 검사가 아니다」라고 반증했고,
    실측으로 재현했다(표기만 있는 파일 -> exit 0).

    이제는 **검사가 못 알아보는 값**을 세므로, 값이 없는 표기는 통과하지 못한다.
    """
    from scripts.check_witness_set_predicates import (  # noqa: PLC0415
        MIN_OUTSIDE,
        outside_witness,
    )

    # 표기만 있고 값이 없으면 바깥 값이 0 이다.
    assert len(outside_witness([], needles={"e"})) < MIN_OUTSIDE

    # 검사가 **잡는** 값만 넣어도 마찬가지다 — 그것이 `"e" in raw` 때의 내 테스트였다.
    assert len(outside_witness(["1e-400", "0e0", "1E5"], needles={"e"})) < MIN_OUTSIDE

    # 바깥 값이 있어야 비로소 통과한다.
    assert len(outside_witness(["+0", "00", ".0"], needles={"e"})) >= MIN_OUTSIDE


def test_growing_a_catalogue_is_itself_a_new_predicate(tmp_path):
    """🔴 카탈로그에 이름을 **하나 더 넣기만** 하면 `in` 줄은 안 바뀐다.

    그러면 diff 한정 스캔이 그것을 못 본다 — 그런데 그것이 오늘의 실제 결함이다
    (`_STRONG_MODULES` 에 이름을 더하는 것으로 보안 오라클이 넓어진다).
    Grok(01a043f2 Q2)이 짚었고, **정의 줄**도 술어로 세게 고쳤다.
    """
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    sample = tmp_path / "cat.py"
    sample.write_text(
        '_NAMES = frozenset({"hmac", "secrets"})\n'
        "def f(x):\n    return x in _NAMES\n", encoding="utf-8")
    lines = {line for line, _k, _s, _e in find_predicates(sample)}
    assert 1 in lines, f"카탈로그 **정의 줄**을 술어로 안 센다: {sorted(lines)}"


def test_the_evidence_values_are_reported_not_just_the_size():
    """🔴 「바깥」을 재려면 증거집합의 **값**을 알아야 한다 — 개수로는 못 잰다."""
    from scripts.check_witness_set_predicates import find_predicates  # noqa: PLC0415

    hits = find_predicates(_CORPUS / "security_oracle_four_names.pysnippet")
    evidence = set()
    for _line, _kind, _size, values in hits:
        evidence |= set(values)
    assert {"hmac", "secrets"} <= evidence, (
        f"실제 증거값을 안 내놓는다: {sorted(evidence)[:8]}"
    )


def test_the_guard_is_green_on_the_current_tree():
    """🔴 이 PR 은 새 술어를 **넣었고**, 위 반례 코퍼스가 그것을 충족한다.

    가드가 자기 자신을 잡았다(술어 4건) — 처방을 자기 구성에 먼저 적용한 것이다.
    코퍼스를 지우면 이 테스트가 red 가 된다.
    """
    proc = _run()
    assert proc.returncode == 0, f"현재 트리에서 red:\n{proc.stdout}\n{proc.stderr}"


def test_an_exemption_needs_a_reason():
    """사유 없는 면제가 통과하면 이 가드는 한 줄로 꺼진다."""
    from scripts.check_witness_set_predicates import MIN_REASON  # noqa: PLC0415

    assert MIN_REASON >= 16


# ─── 면제 채널의 도달성 ─────────────────────────────────────────────────────
#
# 🔴 이 채널은 **CI 에서 한 번도 도달할 수 없었다.** 가드는 실패 메시지에서 「해당 없으면 PR 본문에
#    `witness-corpus-not-applicable: <사유>`」 라고 안내하는데, `main()` 은 그 본문을 `gh pr view`
#    로 스스로 조회했고 두 워크플로 스텝 어디에도 `GH_TOKEN` 이 없었다. 조회가 실패하면 본문이
#    빈 문자열이 되어 면제가 영영 매치되지 않는다 — 안내대로 해도 red 인 **거짓 빨강**이다.
#    (로컬 `pre_push_gate` 는 `gh` 가 인증돼 있어 초록이라, 로컬과 CI 가 갈렸다.)
#    이 절 이전에는 이 채널을 건드리는 테스트가 **0건**이었다 — 도달 불가라 발현하지 않았다.

_VALID_REASON = "이 PR 은 술어가 아니라 배선만 옮긴다"   # 16자 이상


def test_pr_body_comes_from_the_environment_first(monkeypatch):
    """🔴 워크플로가 넘긴 `PR_BODY` 를 쓴다 — CI 에서 `gh pr view` 는 인증이 없어 실패한다."""
    from scripts.check_witness_set_predicates import _pr_body  # noqa: PLC0415

    monkeypatch.setenv("PR_BODY", f"witness-corpus-not-applicable: {_VALID_REASON}")
    assert "witness-corpus-not-applicable" in _pr_body(), "env 로 받은 본문을 버렸다"


def test_pr_body_goes_through_the_hardened_reader(monkeypatch):
    """🔴 HTML 주석에 숨긴 면제는 통하지 않는다 — 단일 리더가 주석을 걷어낸다.

    도달 가능해지기 전에는 이 축이 발현할 수 없었다. 도달성만 고치고 하드닝을 빠뜨리면
    「리뷰어에게 안 보이는 곳에 한 줄 적어 가드 끄기」가 성립한다(회고 N-P0-1).
    """
    from scripts.check_witness_set_predicates import EXEMPT, _pr_body  # noqa: PLC0415

    hidden = f"## 요약\n\n<!--\nwitness-corpus-not-applicable: {_VALID_REASON}\n-->\n"
    monkeypatch.setenv("PR_BODY", hidden)
    assert EXEMPT.search(hidden), "픽스처가 마커를 잘못 적었다 — 대조군 붕괴"
    assert not EXEMPT.search(_pr_body()), "은닉 마커가 면제로 인정됐다"


# --- 새로 도달 가능해진 입력 클래스 (verify.md 「판정식을 쓸 때」 · 완화 절차 7) ---

def test_reachable_class_valid_exemption_matches():
    """클래스 1 — 사유 16자 이상의 면제 선언이 이제 실제로 발화한다."""
    from scripts.check_witness_set_predicates import EXEMPT  # noqa: PLC0415

    assert EXEMPT.search(f"witness-corpus-not-applicable: {_VALID_REASON}")


def test_reachable_class_short_reason_is_rejected():
    """클래스 2 — 사유가 짧으면 면제가 아니다(한 줄로 가드를 끄는 것을 막는다)."""
    from scripts.check_witness_set_predicates import EXEMPT  # noqa: PLC0415

    assert not EXEMPT.search("witness-corpus-not-applicable: 없음")


def test_reachable_class_quoted_marker_is_rejected():
    """클래스 3 — 인용/코드 표기로 **설명**하는 줄은 면제가 아니다.

    본문이 이 마커의 사용법을 적기만 해도 면제되면, 안내문 자체가 가드를 끈다.
    """
    from scripts.check_witness_set_predicates import EXEMPT  # noqa: PLC0415

    assert not EXEMPT.search(f"`witness-corpus-not-applicable: {_VALID_REASON}`")
    assert not EXEMPT.search(f'"witness-corpus-not-applicable: {_VALID_REASON}"')


def test_reachable_class_mid_sentence_marker_is_rejected():
    """클래스 4 — 산문 한가운데의 언급은 면제가 아니다(열 0 요구)."""
    from scripts.check_witness_set_predicates import EXEMPT  # noqa: PLC0415

    assert not EXEMPT.search(f"필요하면 witness-corpus-not-applicable: {_VALID_REASON}")


def test_exemption_actually_fires_end_to_end():
    """🔴 통합 — 정본 스크립트를 `PR_BODY` 와 함께 태우면 **면제 배너**가 나온다.

    수정 전에는 env 를 보지 않았으므로 배너가 「새 증거집합 술어 없음」이었다.
    두 배너 모두 exit 0 이라, 종료코드만 보면 이 축은 측정되지 않는다.
    """
    env = {**os.environ, "PR_BODY": f"witness-corpus-not-applicable: {_VALID_REASON}"}
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(_ROOT), check=False, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "면제 선언" in proc.stdout, (
        f"PR_BODY 의 면제가 발화하지 않았다 — 출력:\n{proc.stdout}")


# --- 배선: 두 워크플로가 본문을 실제로 넘기는가 (배치 회귀 가드) ---

def _repo_integrity_steps(workflow: str) -> list[dict]:
    """`Repo integrity guards` job 의 step 목록을 **구조로** 읽는다(문자열 검색 아님)."""
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load((_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        steps = job.get("steps") or []
        if any("check_witness_set_predicates.py" in str(s.get("run", "")) for s in steps):
            return steps
    raise AssertionError(f"{workflow} 에서 witness 가드를 부르는 job 을 못 찾았다")


@pytest.mark.parametrize("workflow", ["ci.yml", "claim-review-on-body-edit.yml"])
def test_both_workflows_hand_the_body_to_the_guard(workflow):
    """🔴 두 워크플로 모두 `PR_BODY` 를 이 스텝에 넘겨야 한다 — 없으면 면제가 도달 불가다."""
    steps = _repo_integrity_steps(workflow)
    step = next(s for s in steps if "check_witness_set_predicates.py" in str(s.get("run", "")))
    assert "PR_BODY" in (step.get("env") or {}), (
        f"{workflow}: witness 스텝에 PR_BODY 가 없다 — CI 에서 면제가 영영 매치되지 않는다")


def test_ci_reads_the_body_before_the_guard_uses_it():
    """🔴 `ci.yml` 에서 본문 조회 스텝이 witness 스텝보다 **앞**에 와야 한다.

    이 순서가 뒤집힌 것이 원래 결함이다 — 같은 파일의 주석이 「이 조회는 본문을 읽는 모든
    스텝 앞에 있어야 한다」고 적어 두었는데 witness 스텝만 그 앞에 있었다.
    """
    steps = _repo_integrity_steps("ci.yml")
    ids = [s.get("id") for s in steps]
    runs = [str(s.get("run", "")) for s in steps]
    body_at = ids.index("prbody")
    guard_at = next(i for i, r in enumerate(runs) if "check_witness_set_predicates.py" in r)
    assert body_at < guard_at, (
        f"본문 조회(idx {body_at})가 witness 가드(idx {guard_at}) 뒤에 있다 — "
        "가드가 읽을 때 본문이 아직 없다")
