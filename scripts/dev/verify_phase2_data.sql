-- Phase 2 진입 전 데이터 충분성 검증 SQL.
-- Phase 2 readiness check: data sufficiency for new dashboard KPI cards.
--
-- 사용법:
--   psql "$DATABASE_URL" -f scripts/dev/verify_phase2_data.sql
--
-- 또는 Railway 콘솔에서 직접 실행. 결과를 Claude 에게 회신하면 Phase 2 진입 여부 결정.
--
-- 검증 항목 (Phase 2 KPI 후보별):
-- 1. analysis_feedbacks row 수 — AI 정합도 카드 (thumbs +1/-1 비율)
-- 2. merge_attempts row 수 — Auto-merge 성공률 카드
-- 3. 최근 30일 활성도 — 카드 표시 가치 측정

\echo '=== Phase 2 Data Readiness Check ==='
\echo ''

\echo '── (1) analysis_feedbacks 전체 + 최근 30일 + 분포 (AI 정합도 KPI 입력) ──'
SELECT
    COUNT(*)                                                AS total_feedbacks,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(*) FILTER (WHERE thumbs = 1)                      AS thumbs_up,
    COUNT(*) FILTER (WHERE thumbs = -1)                     AS thumbs_down,
    COUNT(DISTINCT user_id)                                 AS distinct_users,
    COUNT(DISTINCT analysis_id)                             AS distinct_analyses
FROM analysis_feedbacks;

\echo ''
\echo '── (2) merge_attempts 전체 + 최근 30일 + 성공률 (Auto-merge 성공률 KPI 입력) ──'
SELECT
    COUNT(*)                                                AS total_attempts,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(*) FILTER (WHERE success = TRUE)                  AS success_count,
    COUNT(*) FILTER (WHERE success = FALSE)                 AS failure_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE success = TRUE) / NULLIF(COUNT(*), 0),
        1
    )                                                       AS success_rate_pct,
    COUNT(DISTINCT failure_reason) FILTER (WHERE success = FALSE) AS distinct_failure_reasons
FROM merge_attempts;

\echo ''
\echo '── (3) merge_attempts 실패 사유별 분포 (Phase 3 merge_failure_advisor 후속 활용) ──'
SELECT
    COALESCE(failure_reason, '(none)')                     AS reason,
    COUNT(*)                                                AS occurrences,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d
FROM merge_attempts
WHERE success = FALSE
GROUP BY failure_reason
ORDER BY occurrences DESC
LIMIT 10;

\echo ''
\echo '── (4) analyses 전체 + 최근 7/30일 + 보안 HIGH (현재 KPI 카드 보강 검증) ──'
SELECT
    COUNT(*)                                                AS total_analyses,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')  AS last_7d,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(DISTINCT repo_id)                                 AS distinct_repos,
    ROUND(AVG(score)::numeric, 1)                           AS avg_score_all_time
FROM analyses;

\echo ''
\echo '── (5) 활성 author (author_login) 분포 (Q5 mode toggle Phase 3 의 사용자별 노트 가치 측정) ──'
SELECT
    COUNT(DISTINCT author_login)                            AS distinct_authors,
    COUNT(*) FILTER (WHERE author_login IS NOT NULL)        AS with_author,
    COUNT(*) FILTER (WHERE author_login IS NULL)            AS without_author
FROM analyses;

\echo ''
\echo '=== End of Phase 2 Readiness Check ==='
