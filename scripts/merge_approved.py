"""사용자가 승인한 head 로만 PR 을 squash 머지한다 — 승인 · 검사 · 화면 확인 · 트리를 기계로 확인한 뒤(회고 원장 L06).
Squash-merge a PR only at the head the user approved, after mechanical checks (retro ledger L06).

    py -3 scripts/merge_approved.py 1836 --head 9c01d5c2 --approval "머지 승인합니다"
    py -3 scripts/merge_approved.py 1836 --head 9c01d5c2 --approval "…" --visual "화면 확인했습니다"
    py -3 scripts/merge_approved.py 1836 --head 9c01d5c2 --approval "…" --check   # 조건만 본다

하나라도 못 재면 막는다(fail-closed):
  1. PR 이 열려 있고 초안이 아니며 base 가 main 이다 · --head 는 지금 head 의 앞자리일 뿐이다. 승인은 PR 댓글·리뷰의
     기록이다. 본문의 CRLF 를 LF 로 바꾸고 앞뒤를 뺀 뒤 첫 줄이 `**사용자 승인**` 이고, `- head:` 줄이 지금 head
     40자리, `- 발화:` 줄이 --approval 발화와 정확히 같아야 한다. `**머지 승인 기록**` 이 있거나 리뷰 state 가
     PENDING 이면 세지 않는다. 승인 뒤 head 가 바뀌었으면 그 40자리로 다시 받는다.
  2. 그 head 의 검사가 모두 끝났고 실패 · 취소가 없다 · main 의 required 검사가 모두 그 안에서 통과했다.
  3. `src/templates/` · `src/static/` · `src/i18n/` 를 바꾼 PR 은 사용자가 화면을 본 발화(`--visual`)가 있다 — 정적
     시험 통과는 근거가 아니다. 문구도 화면이다(길이가 줄바꿈을 바꾼다). 바꾼 파일 목록을 다 못 읽으면 시각 변경으로 본다.
  4. main 과 합친 트리 = 시험한 트리(기본 = PR head 의 트리 · 합친 트리를 따로 돌렸으면 `--tested-tree`).
건 뒤에는 PR 에 승인 기록 댓글(발화 인용 · 근거 댓글 · head · 화면 확인 · 트리)을 남기고 `--match-head-commit` 으로 머지한 다음,
머지 커밋의 트리가 시험한 트리인지 다시 본다. 발화는 사용자가 한 말을 그대로 옮긴다 — 지어내지 않는다.
"""
import argparse
import json
import re
import subprocess
import sys

_BASE = "main"
# 화면을 정하는 파일 — 마크업 · 스타일 · 문구. 데이터 로직(`src/ui/`)은 단위 · e2e 가 잰다
# Files that define the screen: markup, style, text. Data logic (src/ui/) is measured by unit and e2e tests.
_VISUAL_PREFIXES = ("src/templates/", "src/static/", "src/i18n/")
# gh pr checks 의 bucket — 통과로 치는 것 / buckets that count as passed
_PASSED = frozenset({"pass", "skipping"})
# gh pr checks 는 실패면 1, 진행 중이면 8 로 끝난다 — 그때도 JSON 은 찍는다
# gh pr checks exits 1 on a failure and 8 while pending, still printing the JSON
_CHECKS_EXIT_OK = frozenset({0, 1, 8})
_HEX = re.compile(r"^[0-9a-f]{7,40}$")
_TREE = re.compile(r"^[0-9a-f]{40}$")
# 스크립트가 다는 기록의 표식 — 이 본문은 사용자 승인이 아니다
# Marker on the record this script posts; that body is not the user's approval.
_MARKER = "**머지 승인 기록**"
# 사용자가 PR 에 올리는 승인 기록의 첫 줄 / the first line of the user's approval record.
_USER_APPROVAL = "**사용자 승인**"
# 훅 표면 — 리포 훅 · 설정은 주 체크아웃의 파일로 돈다. 여기를 바꾼 머지는 주 체크아웃을 당겨야 적용된다(원장 #1917 M01)
# The hook surface runs from the main checkout's files; a merge touching it applies only after that checkout pulls.
_HOOK_SURFACE = (".claude/", "scripts/")
# 세션 시작 때 읽히는 것 — 당겨도 지금 세션에는 안 들어온다(다시 시작해야 한다)
# Read at session start: pulling is not enough, the session must restart.
_SESSION_LOADED = (".claude/settings.json", "CLAUDE.md")


class CommandFailed(RuntimeError):
    """외부 명령 실패 — 막는 쪽으로 간다 / an external command failed; callers fail closed."""

    def __init__(self, args, returncode):
        super().__init__(f"exit {returncode}: {' '.join(args[:4])} …")
        self.returncode = returncode


def _run(args, ok_codes=frozenset({0})):
    """명령을 돌려 표준 출력을 돌려준다 / run a command and return its stdout."""
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=False)
    if proc.returncode not in ok_codes:
        raise CommandFailed(args, proc.returncode)
    return proc.stdout


def _json(run, args, ok_codes=frozenset({0})):
    return json.loads(run(args, ok_codes) or "null")


def _flatten_pages(data):
    """`gh api --paginate --slurp` 는 페이지 배열의 배열이다 — 한 목록으로 펼친다.
    Slurped pages are a list of arrays; flatten them into one list.
    """
    if not isinstance(data, list) or any(not isinstance(page, list) for page in data):
        raise ValueError("댓글·리뷰 페이지 꼴을 못 읽었다")
    return [item for page in data for item in page]


def _author(item: dict) -> str:
    user = item.get("user")
    if isinstance(user, dict) and isinstance(user.get("login"), str):
        return user["login"]
    return ""


def _text_field(item: dict, key: str) -> str:
    value = item.get(key)
    return value if isinstance(value, str) else ""


def _norm_comment(item) -> dict:
    """이슈 댓글에서 본문 · 작성자 · 시각만 남긴다 / keep body, author, and created time."""
    if not isinstance(item, dict):
        raise ValueError("댓글 항목이 객체가 아니다")
    return {"id": item.get("id"), "body": _text_field(item, "body"), "author": _author(item),
            "created_at": _text_field(item, "created_at"), "html_url": _text_field(item, "html_url")}


def _norm_review(item) -> dict:
    """리뷰에서 본문 · 작성자 · 제출 시각만 남긴다 / keep body, author, and submitted time."""
    if not isinstance(item, dict):
        raise ValueError("리뷰 항목이 객체가 아니다")
    return {"id": item.get("id"), "body": _text_field(item, "body"), "author": _author(item),
            "state": _text_field(item, "state"), "submitted_at": _text_field(item, "submitted_at"),
            "html_url": _text_field(item, "html_url")}


def _load_notes(run, path: str, norm) -> list:
    """GET 이다 — `-f` 를 붙이면 gh 가 POST 로 바꾼다. `--jq` 는 페이지마다 따로 돌아 한 JSON 이 아니게 된다.
    GET only: `-f` switches gh to POST. `--jq` runs per page, so it is not one JSON value.
    """
    data = _json(run, ["gh", "api", "--paginate", "--slurp", path])
    return [norm(item) for item in _flatten_pages(data)]


def gather(pr: int, run=_run) -> dict:
    """판정에 쓸 사실을 모은다 — 값만, 판정은 `decide` 가 한다 / collect the facts; `decide` judges them."""
    view = _json(run, ["gh", "pr", "view", str(pr), "--json",
                       "state,isDraft,baseRefName,headRefOid,changedFiles,files"])
    head = view.get("headRefOid") or ""
    checks = _json(run, ["gh", "pr", "checks", str(pr), "--json", "name,bucket"], _CHECKS_EXIT_OK)
    required = _json(run, ["gh", "api", f"repos/{{owner}}/{{repo}}/branches/{_BASE}/protection/required_status_checks",
                           "--jq", ".contexts"])
    notes = f"repos/{{owner}}/{{repo}}"
    comments = _load_notes(run, f"{notes}/issues/{pr}/comments", _norm_comment)
    reviews = _load_notes(run, f"{notes}/pulls/{pr}/reviews", _norm_review)
    run(["git", "fetch", "-q", "origin", _BASE, f"pull/{pr}/head"])
    head_tree = run(["git", "rev-parse", f"{head}^{{tree}}"]).strip() if head else ""
    # 충돌이면 merge-tree 가 1 로 끝난다 — 그때 합친 트리는 없다 / exit 1 = conflict: no merged tree
    try:
        merged_tree = run(["git", "merge-tree", "--write-tree", f"origin/{_BASE}", head]).splitlines()[0].strip()
    except (CommandFailed, IndexError):
        merged_tree = ""
    return {
        "state": view.get("state"), "draft": view.get("isDraft"), "base": view.get("baseRefName"),
        "head": head, "files": [f.get("path", "") for f in view.get("files") or []],
        "changed_files": view.get("changedFiles"), "checks": checks, "required": required,
        "head_tree": head_tree, "merged_tree": merged_tree,
        "comments": comments, "reviews": reviews,
    }


def _check_problems(state: dict) -> list[str]:
    checks, required = state["checks"], state["required"]
    if not isinstance(checks, list) or not checks:
        return ["검사가 하나도 안 보인다 — 아직 안 붙었거나 못 읽었다"]
    if not all(isinstance(c, dict) for c in checks):
        return ["검사 목록의 꼴을 못 읽었다"]
    if not isinstance(required, list) or not required:
        return ["main 의 required 검사 목록을 못 읽었다"]
    problems = [f"검사 «{c.get('name')}» = {c.get('bucket')}" for c in checks if c.get("bucket") not in _PASSED]
    passed = {c.get("name") for c in checks if c.get("bucket") in _PASSED}
    problems += [f"required 검사 «{name}» 가 통과 목록에 없다" for name in required if name not in passed]
    return problems


def _note_records(state: dict) -> list | None:
    """댓글·리뷰를 못 읽으면 None — 빈 목록과 구별한다 / None means unreadable, not an empty list."""
    comments, reviews = state.get("comments"), state.get("reviews")
    if not isinstance(comments, list) or not isinstance(reviews, list):
        return None
    records = []
    for item in [*comments, *reviews]:
        if not isinstance(item, dict) or not isinstance(item.get("body"), str):
            return None
        records.append(item)
    return records


def _when_key(rec: dict) -> tuple:
    when = rec.get("created_at") or rec.get("submitted_at") or ""
    ident = rec.get("id")
    return (when if isinstance(when, str) else "", ident if isinstance(ident, int) else 0)


def _user_approval_text(head: str, utterance: str) -> str:
    """올릴 승인 기록 세 줄 / the three-line approval record to post."""
    return "\n".join([_USER_APPROVAL, f"- head: `{head}`", f"- 발화: «{utterance}»"])


def _is_user_approval(body: str, head: str, utterance: str) -> bool:
    """CRLF 를 LF 로 바꾸고 strip 한 기록이 지금 head · 발화와 정확히 맞는가.
    Whether the normalized lines match this head and utterance exactly.
    """
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    if _MARKER in normalized:
        return False
    lines = normalized.strip().split("\n")
    if not lines or lines[0] != _USER_APPROVAL:
        return False
    return f"- head: `{head}`" in lines and f"- 발화: «{utterance}»" in lines


def matching_approval(state: dict, approval: str) -> dict | None:
    """사용자 승인 기록 중 가장 이른 것. PENDING 리뷰와 머지 기록 표식은 세지 않는다.
    Earliest user-approval record. PENDING reviews and the merge-record marker do not count.
    """
    records = _note_records(state)
    text = approval.strip()
    head = state.get("head") if isinstance(state.get("head"), str) else ""
    if records is None or len(head) != 40 or not text:
        return None
    found = [rec for rec in records
             if rec.get("state") != "PENDING" and _is_user_approval(rec["body"], head, text)]
    return min(found, key=_when_key) if found else None


def _approval_refusal(state: dict, approval: str) -> str | None:
    """사용자 승인이 PR 에 없으면 막을 이유 / why the PR has no usable user approval."""
    if _note_records(state) is None:
        return "PR 댓글·리뷰를 못 읽었다 — 못 읽으면 머지하지 않는다"
    if matching_approval(state, approval) is not None:
        return None
    head = state.get("head") if isinstance(state.get("head"), str) else ""
    shown = head if len(head) == 40 else (head[:12] or "?")
    record = _user_approval_text(shown, approval.strip())
    return (
        "PR 에 사용자 승인이 없다 — 사용자가 이 head 에 대해 그 발화를 한 뒤에만 "
        "`gh pr comment <PR> --body-file <파일>` 로 올린다. "
        "승인 뒤에 head 가 바뀌었으면 사용자에게 다시 받는다.\n"
        + record
    )


def decide(state: dict, *, head: str, approval: str, visual: str | None, tested_tree: str | None) -> list[str]:
    """막을 이유 목록 — 비면 머지해도 된다 / reasons to refuse; empty means the merge may go ahead."""
    problems = []
    if not approval.strip():
        problems.append("승인 발화(--approval)가 비었다")
    # fullmatch — `$` 는 끝 줄바꿈 앞에서도 맞는다(Grok da1b75aa) / `$` also matches before a trailing newline
    if not _HEX.fullmatch(head):
        problems.append("--head 는 7~40자리 16진수다")
    if state["state"] != "OPEN" or state["draft"] is not False:
        problems.append(f"PR 이 열린 비초안이 아니다(state={state['state']}, draft={state['draft']})")
    if state["base"] != _BASE:
        problems.append(f"base 가 {_BASE} 가 아니다({state['base']})")
    if not state["head"] or not state["head"].startswith(head):
        problems.append(f"지금 head {state['head'][:12] or '?'} ≠ 승인한 head {head[:12]} — 승인 뒤 바뀌었다, 다시 받는다")
    refusal = _approval_refusal(state, approval)
    if refusal:
        problems.append(refusal)
    problems += _check_problems(state)
    files_seen = type(state["changed_files"]) is int and state["changed_files"] == len(state["files"])
    visual_change = not files_seen or any(path.startswith(_VISUAL_PREFIXES) for path in state["files"])
    if visual_change and not (visual or "").strip():
        why = "바꾼 파일 목록을 다 못 읽었다" if not files_seen else "templates/ · static/ · i18n/ 을 바꿨다"
        problems.append(f"시각 변경 PR 이다({why}) — 사용자가 화면을 본 발화(--visual) 없이는 머지하지 않는다")
    expected = tested_tree or state["head_tree"]
    if not _TREE.fullmatch(expected or ""):
        problems.append("시험한 트리를 모른다 — head 트리를 못 읽었거나 --tested-tree 가 40자리 16진수가 아니다")
    elif state["merged_tree"] != expected:
        problems.append(f"main 과 합친 트리 {state['merged_tree'][:8] or '(충돌)'} ≠ 시험한 트리 {expected[:8]}"
                        " — rebase 하고 다시 시험하거나 합친 트리를 돌린 뒤 --tested-tree")
    return problems


def _evidence_label(evidence: dict) -> str:
    """근거로 URL 을 적고, 없으면 id / cite the comment URL, or its id when the URL is missing."""
    url = evidence.get("html_url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return str(evidence.get("id"))


def comment_body(state: dict, *, approval: str, visual: str | None, evidence=None) -> str:
    """승인 기록 댓글 — GitHub 에서 승인 주체 · 범위를 되짚을 수 있게 / an approval record on the PR."""
    checks = state["checks"]
    lines = [
        f"{_MARKER} (`scripts/merge_approved.py`)",
        "",
        f"- 승인: «{approval.strip()}»",
    ]
    if evidence is not None:
        lines.append(f"- 근거 댓글: {_evidence_label(evidence)}")
    lines += [
        f"- head: `{state['head']}` — 승인한 head 로만 머지한다(`--match-head-commit`)",
        f"- 화면 확인: «{visual.strip()}»" if (visual or "").strip() else "- 화면 확인: 시각 변경 없음",
        f"- 검사: {len(checks)}개 통과(required {len(state['required'])}개 포함)",
        f"- 트리: `{state['merged_tree'][:8]}` = 시험한 트리",
    ]
    return "\n".join(lines) + "\n"


def after_merge_notes(files: list[str]) -> list[str]:
    """머지 뒤 할 일 — 훅 표면을 바꾼 머지는 주 체크아웃을 당겨야, 등록을 바꿨으면 세션까지 다시 열어야 적용된다.

    11-15 ~ 11-21 주 체크아웃이 기능 브랜치에 있어 머지된 훅 · 설정 10 PR 이 4~6일 꺼져 있었다(원장 #1917 P1-2 · P1-3).
    After-merge steps: pull the main checkout for hook-surface changes; restart the session if registration changed.
    """
    loaded = [f for f in _SESSION_LOADED if f in files]
    if loaded:
        return [f"🔴 세션 시작 때 읽히는 것({' · '.join(loaded)})이 바뀌었다 — 주 체크아웃을 "
                "`git switch main && git pull --ff-only` 로 당긴 뒤 세션을 다시 시작해야 적용된다"]
    if any(f.startswith(_HOOK_SURFACE) for f in files):
        return ["훅 · 스크립트(.claude · scripts)가 바뀌었다 — 주 체크아웃을 `git pull --ff-only` 로 당겨야 다음 호출부터 적용된다"]
    return []


def main(argv=None, *, run=_run, out=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pr", type=int)
    parser.add_argument("--head", required=True, help="지금 head 의 앞자리(7~40) — 승인은 PR 에 올린 기록")
    parser.add_argument("--approval", required=True, help="사용자의 승인 발화 그대로")
    parser.add_argument("--visual", help="시각 변경 PR — 사용자가 화면을 본 발화 그대로")
    parser.add_argument("--tested-tree", help="합친 트리를 따로 돌렸을 때 그 트리(40자리)")
    parser.add_argument("--check", action="store_true", help="조건만 본다(댓글 · 머지 없음)")
    args = parser.parse_args(argv)
    head = args.head.strip().lower()
    tested_tree = (args.tested_tree or "").strip() or None
    try:
        state = gather(args.pr, run)
    except (CommandFailed, ValueError, AttributeError, TypeError) as exc:
        out(f"⛔ 사실을 다 못 모았다 — 머지하지 않는다: {exc}")
        return 2
    evidence = matching_approval(state, args.approval)
    problems = decide(state, head=head, approval=args.approval, visual=args.visual, tested_tree=tested_tree)
    if problems:
        out(f"⛔ PR #{args.pr} 머지하지 않는다:")
        for problem in problems:
            out(f"  - {problem}")
        return 1
    if args.check:
        out(f"✅ PR #{args.pr} 조건 충족(--check — 댓글 · 머지 안 함)")
        return 0
    expected = tested_tree or state["head_tree"]
    try:
        run(["gh", "pr", "comment", str(args.pr), "--body", comment_body(state, approval=args.approval,
                                                                          visual=args.visual, evidence=evidence)])
        run(["gh", "pr", "merge", str(args.pr), "--squash", "--match-head-commit", state["head"]])
        merge_commit = _json(run, ["gh", "pr", "view", str(args.pr), "--json", "mergeCommit"])["mergeCommit"]["oid"]
        run(["git", "fetch", "-q", "origin", _BASE])
        merged = run(["git", "rev-parse", f"{merge_commit}^{{tree}}"]).strip()
    except (CommandFailed, ValueError, KeyError, TypeError) as exc:
        out(f"⛔ 머지 단계 실패 — PR 상태를 직접 본다: {exc}")
        return 2
    if merged != expected:
        out(f"🔴 머지됐지만 머지 커밋 트리 {merged[:8]} ≠ 시험한 트리 {expected[:8]} — main 을 다시 시험한다")
        return 3
    out(f"✅ PR #{args.pr} 머지 {merge_commit[:8]} · 트리 {merged[:8]} = 시험한 트리 — 다음은 배포 확인")
    for note in after_merge_notes(state["files"]):
        out(note)
    return 0


def _make_stdout_safe() -> None:
    """한글 · 기호를 찍으므로 두 출력을 UTF-8 로 — Windows(cp949) 콘솔에서 찍는 순간 죽지 않게.

    Print streams as UTF-8 so Korean text and symbols never crash a cp949 console.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # 캡처 · 대체된 스트림에는 reconfigure 가 없다 — 그 스트림은 이미 호출자가 인코딩을 정했다.
            # Captured or replaced streams lack reconfigure; their owner already chose the encoding.
            continue


if __name__ == "__main__":
    _make_stdout_safe()
    sys.exit(main())
