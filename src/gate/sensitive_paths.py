"""민감 경로 판정 — 사람 검토 없이 자동 머지되면 안 되는 파일 (B6-a).

## 왜 필요한가 (2026-07-20 실측) / Why this exists (measured)

운영 6개 리포 **전부** `auto_merge=true` · `approve_mode=auto` · `merge_threshold=60` 이고
**6/6 기본 브랜치가 무보호**였다. 즉 점수 60 이상이면 인증·마이그레이션·CI 워크플로를
바꾸는 PR 도 **사람 개입 0으로** 머지된다. 실증: `#1102`~`#1107` 6건이 전부 `reviews=0` ·
생성 후 4분37초~5분27초 만에 자동 머지됐고, 그중 `#1104` 는 **토큰 평문 유출 P0 보안
변경**이었다.

## 🔴 브랜치 보호가 답이 아닌 이유 (Grok 적대 검토 2026-07-20, 코드 실측 확증)

처음 권장안은 GitHub 브랜치 보호(필수 상태 체크)였다. **두 가지로 반증됐다**:

1. **사람 검토를 전혀 추가하지 않는다.** 필수 체크는 경로를 모른다 — CI 가 green 인
   토큰 유출 PR 은 여전히 검토 0으로 머지된다. 두려워한 위험과 다른 위험을 막는 통제다.
2. **오히려 자동 머지를 죽인다.** `mergeable_state="blocked"` →
   `BRANCH_PROTECTION_BLOCKED` 이고 이 태그는 `_RETRIABLE_TAGS` 에 **없다**(실측) →
   재시도 큐가 기다리지 못하는 **종결 실패**. 체크가 0건인 리포
   (`claude-grok-build-plugin`)에 필수 컨텍스트를 걸면 모든 PR 이 영구 차단된다.

그래서 통제를 **경로 인지 + 우리 코드 안**에 둔다. GitHub 설정을 건드리지 않으므로
종결 실패 경로가 생기지 않고, 막히는 것은 민감 경로 PR **하나뿐**이다.
The control lives in our code and is path-aware; branch protection is neither.

## 판정 범위 / Classification scope

리포 무관하게 "무검토 머지가 실제로 위험한" 세 부류만 본다 — 인증/시크릿 · DB 마이그레이션 ·
CI 워크플로 정의(공급망). 넓히면 정상 PR 을 막아 사용자가 가드를 끄게 된다.
"""
import asyncio
import logging
import re

from src.gate.merge_reasons import SENSITIVE_PATH_HOLD
from src.shared.feature_kill_switch import is_disabled

logger = logging.getLogger(__name__)

# 🔴 민감 경로 패턴 — 리포 공통으로 무검토 머지가 위험한 부류만.
#   과하게 넓히면 정상 PR 이 막히고, 그러면 사용자가 가드 자체를 끈다(가드의 자살).
# Deliberately narrow: over-blocking makes users disable the guard entirely.
_SENSITIVE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (
        # 인증·인가·시크릿 / auth, authorization, secrets
        r"(^|/)auth/",
        r"(^|/)(crypto|secrets?|credentials?)\.[a-z]+$",
        r"(^|/)(oauth|session|login|permission)[^/]*\.[a-z]+$",
        # DB 마이그레이션 / DB migrations
        r"(^|/)(alembic|migrations?)/",
        r"(^|/)alembic\.ini$",
        # CI·배포 워크플로 정의 (공급망) / CI & deploy workflow definitions (supply chain)
        r"^\.github/workflows/",
        r"(^|/)Dockerfile$",
    )
)


def sensitive_paths_in(filenames) -> list[str]:
    """민감 경로에 해당하는 파일명만 정렬해 반환. 없으면 빈 리스트.

    Return the sorted subset of filenames that match a sensitive pattern.

    🔴 판정 불가(빈 목록 입력)와 '민감 없음' 은 **다르다** — 호출부가 구별해야 한다.
    빈 리스트를 '안전' 으로 읽으면, 파일 목록 조회 실패가 곧 통과가 된다(fail-open).
    An empty input is "undecidable", not "safe" — callers must not conflate them.
    """
    hits = {
        name for name in (filenames or [])
        if name and any(p.search(str(name)) for p in _SENSITIVE_PATTERNS)
    }
    return sorted(hits)


async def sensitive_paths_block_merge(
    *, github_token: str, repo_name: str, pr_number: int,
) -> bool:
    """민감 경로 가드 — 자동 머지를 보류해야 하면 True.

    Sensitive-path guard — returns True to withhold auto-merge.

    `_run_auto_merge` 진입부에서 2nd-LLM 검증 가드와 **같은 자리**에 호출된다 →
    자동(`AutoMergeAction`)·반자동(telegram `handle_gate_callback`) 양 경로가 공유한다.
    한쪽에만 두면 반자동이 가드를 우회한다(#859 P1-1 이 남긴 교훈).

    🔴 **fail-closed**: 파일 목록 조회가 실패하면 **보류**한다. "무엇이 바뀌었는지 모른다" 를
    "안전하다" 로 접으면, API 장애 한 번이 곧 인증 코드 무검토 머지가 된다. 검증자 가드가
    오류를 차단으로 취급하는 것과 같은 규칙이다.
    If we cannot determine what changed, we withhold — an API failure must not become consent.

    kill-switch: `SENSITIVE_PATH_GUARD_DISABLED=1` (운영자가 즉시 끌 수 있어야 한다).
    """
    if is_disabled("SENSITIVE_PATH_GUARD"):
        return False

    from src.github_client.diff import get_pr_filenames  # pylint: disable=import-outside-toplevel
    try:
        filenames = await asyncio.to_thread(
            get_pr_filenames, github_token, repo_name, pr_number
        )
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        logger.exception(
            "sensitive-path guard could not list PR files — withholding auto-merge "
            "(tag=%s repo=%s pr=%s)", SENSITIVE_PATH_HOLD, repo_name, pr_number,
        )
        return True  # fail-closed / 판정 불가 = 보류

    hits = sensitive_paths_in(filenames)
    if not hits:
        return False

    logger.warning(
        "sensitive-path guard withheld auto-merge (tag=%s) — repo=%s pr=%s files=%s",
        SENSITIVE_PATH_HOLD, repo_name, pr_number, ", ".join(hits[:10]),
    )
    # 지연 임포트 — github_comment ↔ gate 순환 회피 (검증자 가드와 동일 관용구)
    from src.notifier.github_comment import post_plain_pr_comment  # pylint: disable=import-outside-toplevel
    try:
        listed = "\n".join(f"- `{h}`" for h in hits[:20])
        more = f"\n- … and {len(hits) - 20} more" if len(hits) > 20 else ""
        await post_plain_pr_comment(
            github_token, repo_name, pr_number,
            "🔒 **Auto-merge withheld — sensitive paths changed.**\n\n"
            "This PR touches files where an unreviewed merge is genuinely risky "
            "(auth/secrets, DB migrations, or CI workflow definitions). "
            "The score gate alone does not cover path sensitivity, so a human "
            "should look before this lands.\n\n"
            f"{listed}{more}\n\n"
            "_Merge manually after review. To disable this guard entirely, set "
            "`SENSITIVE_PATH_GUARD_DISABLED=1`._",
        )
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        logger.exception(
            "sensitive-path hold comment failed (repo=%s pr=%s)", repo_name, pr_number
        )
    return True
