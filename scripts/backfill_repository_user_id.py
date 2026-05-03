"""Legacy NULL `Repository.user_id` backfill script — author_login JOIN 패턴 (옵션 🅐-2).

Phase 3 postlude — 사이클 64 회고 P1 후속. SaaS 전환 시점 RLS 격리 정합성 보강.

## 사용 방법

```bash
# Dry-run (default — 영향 row + SQL 출력만, DB 변경 X)
python -m scripts.backfill_repository_user_id

# 실제 적용 (사용자 명시 의무)
python -m scripts.backfill_repository_user_id --apply
```

## 동작
1. `Repository.user_id IS NULL` 조회
2. 각 repo 의 첫 (created_at asc) `Analysis.author_login` 가져옴
3. `users.github_login = author_login` 매칭 → user.id 발견
4. dry-run = SQL UPDATE 출력만 / `--apply` = 실제 UPDATE
5. 결과 보고: `resolved` (매칭 성공) + `skipped_no_analysis` + `skipped_no_author` + `skipped_no_user`

## 사용자 결정 영역 (정책 3)
실제 backfill 적용은 사용자 명시 의무 (`--apply`). dry-run 으로 영향 미리 확인 후 결정.

Legacy NULL backfill — author_login JOIN pattern (option 🅐-2). User-explicit `--apply` only.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal  # pylint: disable=import-error
from src.models.analysis import Analysis  # pylint: disable=import-error
from src.models.repository import Repository  # pylint: disable=import-error
from src.models.user import User  # pylint: disable=import-error

logger = logging.getLogger(__name__)


def _resolve_user_id_for_repo(db: Session, repo: Repository) -> Optional[int]:
    """주어진 repository 의 첫 Analysis 의 author_login 으로 user_id 매칭.

    Resolve user_id by joining the first Analysis's author_login to users.github_login.

    None 반환 케이스:
    1. repo 에 Analysis 0건
    2. 첫 Analysis 의 author_login NULL/빈 문자열
    3. users 테이블에 매칭 github_login 없음
    """
    # 첫 Analysis (created_at asc) 조회 — author_login 추출
    # First Analysis chronologically — extract author_login
    first_analysis = db.scalars(
        select(Analysis)
        .where(Analysis.repo_id == repo.id)
        .order_by(Analysis.created_at.asc())
    ).first()

    if first_analysis is None:
        return None

    author_login = first_analysis.author_login
    if not author_login:
        return None

    # users.github_login 매칭 user 검색
    # Match users.github_login
    user = db.scalars(
        select(User).where(User.github_login == author_login)
    ).first()

    if user is None:
        return None

    return int(user.id)


def _format_update_sql(repo_id: int, user_id: int) -> str:
    """dry-run 출력용 SQL UPDATE 문 빌더 (실제 실행 X — 시각 출력 전용)."""
    # SQL UPDATE statement builder for dry-run output (NOT executed — display only)
    # Both args are int (caller responsibility — type hints) — no SQL injection vector.
    return f"UPDATE repositories SET user_id = {user_id} WHERE id = {repo_id};"  # nosec B608


def main(argv: list[str] | None = None) -> int:
    """Legacy NULL user_id backfill main — dry-run default, --apply 명시 시 실제 적용.

    Returns: 0 = success, 1 = errors during apply.
    """
    parser = argparse.ArgumentParser(
        description="Legacy NULL Repository.user_id backfill (author_login JOIN — 옵션 🅐-2)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 DB UPDATE 실행 (default = dry-run only).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("=" * 60)
    logger.info("Legacy NULL Repository.user_id backfill — mode=%s", mode)
    logger.info("Pattern: 옵션 🅐-2 (author_login JOIN — Claude 권장 default)")
    logger.info("=" * 60)

    counters = {
        "resolved": 0,
        "skipped_no_analysis": 0,
        "skipped_no_author": 0,
        "skipped_no_user": 0,
    }
    sql_lines: list[str] = []

    with SessionLocal() as db:
        # Repository.user_id IS NULL 만 처리 — 이미 매칭된 row 변경 X
        # Process only rows with NULL user_id — never touch already-mapped rows
        legacy_repos = list(
            db.scalars(select(Repository).where(Repository.user_id.is_(None))).all()
        )
        logger.info("Legacy NULL repositories: %d", len(legacy_repos))

        for repo in legacy_repos:
            resolved_user_id = _resolve_user_id_for_repo(db, repo)
            if resolved_user_id is None:
                # 세분 카운트 — 진단용
                # Detailed counters for diagnostics
                first = db.scalars(
                    select(Analysis)
                    .where(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.asc())
                ).first()
                if first is None:
                    counters["skipped_no_analysis"] += 1
                elif not first.author_login:
                    counters["skipped_no_author"] += 1
                else:
                    counters["skipped_no_user"] += 1
                continue

            counters["resolved"] += 1
            sql_lines.append(_format_update_sql(repo.id, resolved_user_id))
            if args.apply:
                # 실제 UPDATE 실행 — Repository row 직접 수정
                # Apply UPDATE — directly mutate the Repository row
                repo.user_id = resolved_user_id

        if args.apply:
            db.commit()
            logger.info("Applied %d UPDATE rows.", counters["resolved"])
        else:
            logger.info("Dry-run SQL (실제 실행 X — `--apply` 명시 의무):")
            for sql in sql_lines:
                logger.info("  %s", sql)

    logger.info("-" * 60)
    logger.info("Result counters:")
    logger.info("  ✓ resolved (user_id 매칭 성공): %d", counters["resolved"])
    logger.info("  ⊘ skipped_no_analysis (Analysis 0건): %d", counters["skipped_no_analysis"])
    logger.info("  ⊘ skipped_no_author (author_login NULL): %d", counters["skipped_no_author"])
    logger.info("  ⊘ skipped_no_user (users 매칭 없음): %d", counters["skipped_no_user"])
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
