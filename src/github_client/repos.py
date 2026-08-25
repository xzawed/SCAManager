"""GitHub repos API — list repos, create/delete webhooks, commit .scamanager/ files."""
import base64
import json
import logging
from urllib.parse import quote


from src.constants import GITHUB_API
from src.github_client.helpers import repo_path as _repo_path
from src.shared.http_client import get_http_client
from src.shared.log_safety import safe_repo_full_name, sanitize_for_log
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

# 이 서비스가 구독해야 하는 웹훅 이벤트 목록 (단일 출처)
# The webhook event list this service subscribes to (single source of truth)
WEBHOOK_EVENTS = ["push", "pull_request", "issues", "check_suite"]


def _auth_headers(token: str) -> dict:
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


async def list_user_repos(token: str) -> list[dict]:
    """사용자가 접근 가능한 리포 목록 반환 (public + private, pagination 처리).

    Returns repos accessible by the user (public + private, with pagination).
    """
    client = get_http_client()  # 싱글톤
    results: list[dict] = []
    # GitHub API pagination: Link 헤더의 next URL을 따라 모든 페이지 수집
    # Follow Link header next URLs to collect all pages from GitHub API
    url: str | None = f"{GITHUB_API}/user/repos"
    # 🔴 affiliation 3값 전부 필수 — organization_member 를 빼면 org 팀 권한으로만 접근하는
    # 저장소가 목록에서 사라진다. 이 목록은 `POST /repos/add` 의 소유권 획득 검증
    # (ui/routes/add_repo.py) 에도 쓰이므로, 누락 시 NULL-owner org 저장소를 영영 획득하지 못한다.
    # 🔴 All three affiliation values are required — dropping organization_member hides repos the
    # user reaches only via org team permissions. This list also gates ownership claim in
    # `POST /repos/add`, so a missing value makes NULL-owner org repos permanently unclaimable.
    params: dict | None = {
        "per_page": 100,
        "sort": "updated",
        "affiliation": "owner,collaborator,organization_member",
    }
    while url:
        resp = await client.get(url, params=params, headers=_auth_headers(token))
        resp.raise_for_status()
        results.extend(
            {
                "full_name": r["full_name"],
                "private": r["private"],
                "description": r.get("description") or "",
            }
            for r in resp.json()
        )
        # 다음 페이지 URL 추출 (없으면 None → 루프 종료)
        # Extract next page URL (None = end of pages)
        next_link = resp.links.get("next", {})
        url = next_link.get("url")
        params = None  # 두 번째 요청부터 URL에 파라미터 포함됨
        # params already encoded in next URL from second request onward
    return results


async def create_webhook(token: str, repo_full_name: str, webhook_url: str, secret: str) -> int:
    """Webhook 생성 → webhook_id 반환."""
    client = get_http_client()  # 싱글톤
    resp = await client.post(
        f"{GITHUB_API}/repos/{_repo_path(repo_full_name)}/hooks",
        json={
            "name": "web",
            "active": True,
            # check_suite: CI 완료 감지 → 자동 머지 재시도 트리거 (Phase 12)
            # check_suite: detect CI completion → trigger auto-merge retry (Phase 12)
            "events": WEBHOOK_EVENTS,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        },
        headers=_auth_headers(token),
    )
    resp.raise_for_status()
    return resp.json()["id"]


# 🔴 훅 페이지 순회 상한 — 실물 GitHub 은 next 를 반복하지 않지만 프록시·오설정·
#   악의적 응답이 같은 URL 을 계속 주면 이 함수 하나가 워커를 묶는다.
#   100개/페이지 × 20 = 2,000개로 어떤 실사용 리포보다 크다.
# Page-walk ceiling: a misbehaving proxy repeating `next` would otherwise pin a worker.
_MAX_WEBHOOK_PAGES = 20

# 🔴 이 함수가 던지는 것은 **`ValueError`** 다 — 호출부가 실제로 잡는 타입이기
#   때문이다. 두 호출부 모두 `except (*HTTPX_SEND_ERRORS, KeyError, ValueError, ...)`
#   이고, `RuntimeError` 는 그 튜플에 **안 잡힌다**(`StreamError` 가 `RuntimeError`
#   하위일 뿐 역은 아니다 — 실측). RuntimeError 로 던지면 FastAPI 까지 올라가 500 이
#   되어, 「부분 성공을 알린다」는 의도가 「페이지 전체가 깨진다」로 뒤집힌다.
# Raise ValueError: both call sites catch it, while RuntimeError would escape to a 500.


async def list_webhooks(token: str, repo_full_name: str) -> list[dict]:
    """리포의 **모든** GitHub 웹훅 목록을 반환한다 (pagination 처리).

    🔴 예전에는 단일 요청이라 docstring 이 거짓이었다 (#1504 B). GitHub 기본 페이지
    크기는 30이라 훅이 그보다 많으면 뒤쪽은 **보이지도 않았다.** 결과가 호출부마다
    다르게 나빴다:

    - `_detect_stale_webhook` — 이 리포의 훅이 2페이지면 stale 배너가 영영 안 뜬다
      (조회 실패 시 False 반환이라 조용하다).
    - `reinstall_webhook` 정리 — 2페이지의 옛 훅이 정리되지 않는데 `cleanup_ok` 는
      True 로 남아 **완전 성공으로 보고**된다. #1504 R1 이 방금 고친 결함이
      이 경로로 그대로 되살아난다.

    형제 `list_user_repos` 가 이미 같은 `resp.links["next"]` 순회를 쓴다 —
    이것은 누락이지 설계 결정이 아니었다.

    Previously a single unpaginated request, so the docstring's "every webhook" was false;
    hooks past GitHub's default page size were invisible to both callers.
    """
    client = get_http_client()  # 싱글톤
    results: list[dict] = []
    for page_num in range(1, _MAX_WEBHOOK_PAGES + 1):
        # 🔴 **서버가 준 URL 을 요청하지 않는다.** `Link` 헤더의 next URL 을 그대로
        #   따라가면 그 요청에 `Authorization: Bearer <토큰>` 이 실리고, 응답이 변조되면
        #   토큰이 임의 호스트로 나간다 (CodeQL `py/partial-ssrf` alert #597 — 실제 위험).
        #   origin 을 검증해 봤지만 CodeQL 은 그 비교를 sanitizer 로 인식하지 않았고,
        #   **더 나은 답은 taint 를 아예 없애는 것**이었다: URL 은 우리가 만들고
        #   (`base` + 정수 `page`), 서버에게서는 「더 있는가」라는 **신호만** 받는다.
        # Never request a server-supplied URL: build it ourselves and read only the
        # has-more signal from the Link header. Removes the taint instead of sanitizing it.
        resp = await client.get(
            f"{GITHUB_API}/repos/{_repo_path(repo_full_name)}/hooks",
            params={"per_page": 100, "page": page_num},
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        page = resp.json()
        # 🔴 200 인데 본문이 list 가 아니면 **거부**한다.
        #   `extend` 는 dict 를 주면 조용히 **키**를 넣고(`['message']`), 문자열을 주면
        #   글자로 쪼갠다(실측). 그 쓰레기가 정리 루프로 흘러가면 엉뚱한 곳에서 터지고
        #   로그는 원인을 안 가리킨다.
        # A non-list 200 body would be spread silently (dict -> its keys, str -> chars).
        if not isinstance(page, list):
            raise ValueError(
                f"GitHub hooks 응답이 list 가 아니다 ({type(page).__name__}) - "
                "목록을 신뢰할 수 없다"
            )
        results.extend(page)
        # 다음 페이지 유무는 서버가 안다 — 그 **불리언**만 쓴다(URL 은 안 쓴다).
        # Use only the boolean; never the URL.
        if not resp.links.get("next"):
            return results

    # 🔴 상한에 걸리면 **던진다** - 잘린 목록을 완전한 것처럼 주면 안 된다.
    #   `reinstall_webhook` 은 반환값을 「전부」라고 믿고 정리한 뒤 완전 성공을 보고한다.
    #   잘린 목록이면 못 지운 훅이 있는데도 「다 정리했다」가 된다(#1504 R1 이 고친 결함).
    #   던지면 그 호출부의 `except` 가 받아 **부분 성공**으로 보고한다 - 정확한 결과다.
    # Raising beats returning a truncated list: the caller treats the list as complete.
    raise ValueError(
        f"webhook page count exceeded {_MAX_WEBHOOK_PAGES} - "
        "목록이 잘렸을 수 있어 완전한 것으로 취급하지 않는다"
    )


async def delete_webhook(token: str, repo_full_name: str, webhook_id: int) -> bool:
    """Webhook 삭제. 성공(204) 시 True, 그 외 False 반환."""
    client = get_http_client()  # 싱글톤
    resp = await client.delete(
        f"{GITHUB_API}/repos/{_repo_path(repo_full_name)}/hooks/{webhook_id}",
        headers=_auth_headers(token),
    )
    return resp.status_code == 204


async def update_webhook_events(
    token: str,
    repo_full_name: str,
    webhook_id: int,
    events: list[str],
) -> bool:
    """기존 웹훅의 이벤트 구독 목록을 갱신한다 (PATCH /hooks/{id}).
    Update the event subscription list of an existing webhook (PATCH /hooks/{id}).

    Returns True on success (200), False otherwise.
    이미 최신 이벤트 목록을 구독 중이라면 GitHub 이 멱등하게 처리함.
    GitHub handles this idempotently if the events list is already current.
    """
    client = get_http_client()  # 싱글톤
    resp = await client.patch(
        f"{GITHUB_API}/repos/{_repo_path(repo_full_name)}/hooks/{webhook_id}",
        json={"events": events},
        headers=_auth_headers(token),
    )
    return resp.status_code == 200


# 🔴 **raw 문자열이어야 한다.**
#   논-raw 였을 때 소스의 `\n`(12건)은 값에서 **진짜 개행**이, `\"`(52건)은 **맨 따옴표**가
#   됐다. 그 결과 emit 되는 스크립트의 `python3 -c "..."` 인자가
#     ① 파이썬 문자열 리터럴이 개행에서 끊기고 (`SyntaxError`)
#     ② bash 이중따옴표가 맨 따옴표에서 조기 종료됐다
#   훅은 `set -euo pipefail` 이라 그 실패가 non-zero exit 가 되고, pre-push 훅의
#   non-zero 는 **push 를 차단한다**. 서버 verify 가 200 일 때만 그 지점에 도달하므로
#   설정이 정상일수록 나빠지는 역전이었다.
#   🔴 여는 따옴표 뒤의 `\` 줄이음은 raw 에서 동작하지 않는다 — 첫 줄을 같은 줄에 둔다.
#   MUST stay raw: as a non-raw literal the source escapes were consumed by Python instead of
#   reaching the emitted script, breaking both the Python literals and the bash quoting.
#   Guarded by tests/unit/github_client/test_install_hook_script_is_valid.py (compiles each
#   emitted `python3 -c` argument) — substring asserts cannot see this class of defect.
_INSTALL_HOOK_SH = r"""#!/bin/bash
# SCAManager Hook 설치 스크립트 — 한 번만 실행하면 됩니다
set -euo pipefail
HOOK=".git/hooks/pre-push"
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")

cat > "${ROOT}/${HOOK}" << 'HOOK_SCRIPT'
#!/bin/bash
# SCAManager pre-push 코드리뷰 자동 실행
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
CONFIG="${ROOT}/.scamanager/config.json"

[ -f "${CONFIG}" ] || exit 0
command -v python3 &>/dev/null || exit 0

# config.json에서 값 추출 — python3 -c 에 CONFIG를 argv로 전달해 경로 주입 방지
SERVER=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['server'])" "${CONFIG}" 2>/dev/null)
TOKEN=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['token'])" "${CONFIG}" 2>/dev/null)
REPO=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['repo'])" "${CONFIG}" 2>/dev/null)

[ -n "${SERVER}" ] || exit 0

REPO_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${REPO}")
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${TOKEN}" "${SERVER}/api/hook/verify?repo=${REPO_ENC}" 2>/dev/null)
[ "${STATUS}" = "200" ] || exit 0

read -r LOCAL_REF LOCAL_SHA REMOTE_REF REMOTE_SHA < /dev/stdin 2>/dev/null || true
# 🔴 `:-` 필수 — 위 `read` 의 **리다이렉트 자체가 실패하면**(Windows Git Bash 에
#   `/dev/stdin` 이 없는 경우) read 가 실행되지 않아 변수가 미설정으로 남고,
#   `set -u` 가 `LOCAL_SHA: unbound variable` 로 훅을 죽인다 → pre-push non-zero → push 차단.
#   (실측: stdin 이 비기만 하면 read 는 빈 문자열을 넣지만, 리다이렉트 실패는 미설정이다.)
#   Needed because a failed redirect skips `read` entirely, leaving the vars unset under set -u.
[ -n "${LOCAL_SHA:-}" ] || LOCAL_SHA="HEAD"
[ -n "${REMOTE_SHA:-}" ] || REMOTE_SHA="0000000000000000000000000000000000000000"

if [ "${REMOTE_SHA}" = "0000000000000000000000000000000000000000" ]; then
    DIFF=$(git diff HEAD~1 2>/dev/null || git show HEAD 2>/dev/null)
else
    DIFF=$(git diff "${REMOTE_SHA}" "${LOCAL_SHA}" 2>/dev/null)
fi
[ -n "${DIFF}" ] || exit 0

COMMIT_MSG=$(git log --format="%B" -1 "${LOCAL_SHA}" 2>/dev/null)
echo "\\n🔍 [SCAManager] 코드리뷰 실행 중..."

# 환경변수로 값 전달 후 python3 로 프롬프트 파일 생성 — heredoc 주입 완전 차단
# Build prompt file via python3 with env vars — eliminates heredoc delimiter injection
# (COMMIT_MSG/DIFF could contain the heredoc terminator on its own line).
TMPFILE=$(mktemp /tmp/scamanager_review.XXXXXX)
SCA_COMMIT_MSG="${COMMIT_MSG}" SCA_DIFF="${DIFF}" python3 -c "
import os, sys
commit_msg = os.environ.get('SCA_COMMIT_MSG', '')
diff_content = os.environ.get('SCA_DIFF', '')
prompt = (
    '다음 변경사항을 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.\n\n'
    '코밋 메시지: ' + commit_msg + '\n\n'
    '변경사항:\n' + diff_content + '\n\n'
    '채점 유의사항:\n'
    '- 일반적으로 양호한 코드는 15~18점 범위입니다.\n'
    '- 명확한 문제가 없다면 최소 12점 이상을 부여하세요.\n\n'
    '다음 JSON만 응답:\n'
    '{\"commit_message_score\":<0-20>,\"direction_score\":<0-20>,\"test_score\":<0-10>,'
    '\"summary\":\"요약\",\"suggestions\":[\"제안\"],\"commit_message_feedback\":\"피드백\",'
    '\"code_quality_feedback\":\"피드백\",\"security_feedback\":\"피드백\",'
    '\"direction_feedback\":\"피드백\",\"test_feedback\":\"피드백\",\"file_feedbacks\":[]}'
)
sys.stdout.write(prompt)
" > "${TMPFILE}"

# Anthropic API 직접 호출 — claude -p 대체 (2025-06-15 Agent SDK 크레딧 분리 대응)
# Direct Anthropic API call — replaces claude -p (Agent SDK billing split from 2025-06-15)
[ -n "${ANTHROPIC_API_KEY:-}" ] || {
  echo "⚠️  [SCAManager] ANTHROPIC_API_KEY 환경변수 미설정 — 코드리뷰를 건너뜁니다." >&2
  rm -f "${TMPFILE}"
  exit 0
}
REVIEW_MODEL="${SCAMANAGER_REVIEW_MODEL:-claude-haiku-4-5-20251001}"
RESULT=$(python3 -c "
import json, sys, os, urllib.request
key = os.environ.get('ANTHROPIC_API_KEY', '')
model = sys.argv[2]
with open(sys.argv[1]) as f:
    prompt = f.read()
payload = json.dumps({
    'model': model,
    'max_tokens': int(os.environ.get('CLAUDE_REVIEW_MAX_TOKENS') or 8192),
    'messages': [{'role': 'user', 'content': prompt}]
}).encode()
req = urllib.request.Request(
    'https://api.anthropic.com/v1/messages',
    data=payload,
    headers={
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
        print(d['content'][0]['text'])
except Exception:
    pass
" "${TMPFILE}" "${REVIEW_MODEL}" 2>/dev/null) || true
[ -z "${RESULT}" ] && echo "⚠️  [SCAManager] Anthropic API 호출 실패 또는 빈 응답 — 코드리뷰를 건너뜁니다." >&2
rm -f "${TMPFILE}"

if [ -n "${RESULT}" ]; then
    echo "${RESULT}" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(f'\\n📊 코드리뷰 결과:')
    print(f'  요약: {d.get(\"summary\",\"\")}')
    print(f'  커밋 메시지: {d.get(\"commit_message_feedback\",\"\")}')
    print(f'  코드 품질: {d.get(\"code_quality_feedback\",\"\")}')
    print(f'  보안: {d.get(\"security_feedback\",\"\")}')
except Exception:
    pass
" 2>/dev/null || true

    # python3에 값을 argv로 전달 — 인라인 스크립트에 변수 삽입 금지
    PAYLOAD=$(python3 -c "
import json, sys
repo, token, sha, msg, result_str = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
try:
    ai = json.loads(result_str)
    print(json.dumps({'repo': repo, 'token': token, 'commit_sha': sha, 'commit_message': msg, 'ai_result': ai}))
except Exception:
    print('{}')
" "${REPO}" "${TOKEN}" "${LOCAL_SHA}" "${COMMIT_MSG}" "${RESULT}" 2>/dev/null) || true

    [ -n "${PAYLOAD}" ] && curl -s -X POST "${SERVER}/api/hook/result" \
      -H "Content-Type: application/json" \
      -d "${PAYLOAD}" >/dev/null 2>&1 &
fi

exit 0
HOOK_SCRIPT

chmod +x "${ROOT}/${HOOK}"
echo "✅ SCAManager pre-push 훅 설치 완료: ${ROOT}/${HOOK}"
"""


async def is_public_repo(token: str, repo_full_name: str) -> bool | None:
    """리포가 **공개**면 True, 비공개면 False, 판정 불가면 None.

    🔴 `None` 은 "공개가 아니다" 가 아니라 **"모른다"** 다 — 호출부는 모를 때
    쓰지 않아야 한다(fail-closed). 두 값을 섞으면 GitHub 이 흔들릴 때마다
    시크릿이 나간다.
    Returns True=public, False=private, None=unknown. None must fail closed.
    """
    # 🔴 형태 검증 — URL 경로 **끝**이 사용자 값이면 CodeQL py/partial-ssrf 다
    #    (형제 함수들은 `/hooks` 처럼 고정 접미가 붙어 걸리지 않는다).
    #    「접근 가능 목록에 있는가」는 의미 검증이라 sanitizer 로 인식되지 않는다.
    safe_name = safe_repo_full_name(repo_full_name)
    if safe_name is None:
        logger.warning("repo 이름 형태 거부 (%s)", sanitize_for_log(repo_full_name))
        return None
    try:
        client = get_http_client()
        resp = await client.get(
            f"{GITHUB_API}/repos/{_repo_path(safe_name)}",
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        payload = resp.json()
    except (*HTTPX_SEND_ERRORS, OSError, ValueError) as exc:
        # 🔴 사용자 제어 값은 `sanitize_for_log` 경유 — 원문 보간은 py/log-injection.
        logger.warning(
            "repo visibility 조회 실패 (%s): %s", sanitize_for_log(repo_full_name), exc,
        )
        return None
    private = payload.get("private")
    if not isinstance(private, bool):
        # 🔴 필드가 없거나 형이 다르면 **공개로 간주**한다. 모호할 때 안전한 쪽은
        #    "쓰지 않는다" 이지 "쓴다" 가 아니다.
        # An absent/malformed `private` is treated as public: the safe side of ambiguity.
        logger.warning(
            "repo visibility 응답에 private 없음 (%s) — 공개로 간주",
            sanitize_for_log(repo_full_name),
        )
        return True
    return private is False


async def commit_scamanager_files(
    token: str,
    repo_full_name: str,
    server_url: str,
    hook_token: str,
) -> bool:
    """`.scamanager/config.json`과 `.scamanager/install-hook.sh`를 Repo에 커밋.
    이미 파일이 있으면 sha를 포함해 업데이트. 성공 시 True, 실패 시 False 반환."""
    # 🔴 **공개 리포에는 쓰지 않는다** (2026-08-21 전수 감사).
    #    아래 `config.json` 은 살아 있는 `hook_token` 을 평문으로 담고 사용자 리포에
    #    커밋된다. 공개 리포면 그 토큰이 공개되고, 그 토큰은 `POST /api/hook/result` 를
    #    **X-API-Key 없이** 인증하므로(`src/api/hook.py:147`) 누구나 그 리포의
    #    `score`/`grade` 행을 써 넣을 수 있다 — 게이팅 제품의 1차 산출물에 대한 무인증 쓰기다.
    #    (완화: `hook.py:285` 가 `static_analysis_incomplete` 를 무조건 세워 auto-merge 는 막는다.
    #     그래서 강제 머지는 불가하고 점수·대시보드 오염이 가능하다.)
    #
    # 🔴 「토큰만 빼고 쓰기」가 아니라 「쓰지 않기」인 이유 (Grok claim-review `01a024b5`):
    #    커밋되는 훅 스크립트는 토큰을 config.json 에서만 읽고 **env 폴백이 없다**.
    #    토큰을 빼면 설치된 것처럼 보이고 첫 실행에서 조용히 죽는다. 그리고 그 스크립트는
    #    사용자 리포에 커밋되는 **분산 계약**이라, 폴백을 추가해도 이미 옛 스크립트를
    #    가진 클론은 고쳐지지 않는다. 쓰는 쪽에서 막는 것이 완결된 차단이다.
    # Never commit the token to a public repo; refuse instead of writing a token-less config,
    # because the committed hook reads the token only from config.json (no env fallback).
    public = await is_public_repo(token, repo_full_name)
    if public is not False:
        reason = "공개 리포" if public else "visibility 판정 불가"
        logger.warning(
            "hook 파일 커밋 중단 (%s) — %s. hook_token 을 리포에 넣지 않는다.",
            sanitize_for_log(repo_full_name), reason,
        )
        return False

    config_content = json.dumps({
        "server": server_url.rstrip("/"),
        "repo": repo_full_name,
        "token": hook_token,
    }, indent=2, ensure_ascii=False)

    files = {
        ".scamanager/config.json": config_content,
        ".scamanager/install-hook.sh": _INSTALL_HOOK_SH,
    }

    try:
        client = get_http_client()  # 싱글톤 — 루프 밖에서 1회만 호출
        for path, content in files.items():
            # path 는 module-level 딕셔너리 키(상수) 이지만 방어적 인코딩 적용
            url = f"{GITHUB_API}/repos/{_repo_path(repo_full_name)}/contents/{quote(path)}"
            # 기존 파일 sha 조회
            # Retrieve the existing file sha (required for updates).
            get_resp = await client.get(url, headers=_auth_headers(token))
            body: dict = {
                "message": f"chore: SCAManager hook 설정 추가 ({path})",
                "content": base64.b64encode(content.encode()).decode(),
            }
            if get_resp.status_code == 200:
                body["sha"] = get_resp.json().get("sha", "")

            put_resp = await client.put(url, json=body, headers=_auth_headers(token))
            put_resp.raise_for_status()

        return True
    except HTTPX_SEND_ERRORS as exc:
        logger.warning(
            "commit_scamanager_files 실패 (%s): %s",
            sanitize_for_log(repo_full_name), exc,
        )
        return False
