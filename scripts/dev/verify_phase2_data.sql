-- Phase 2 진입 전 데이터 충분성 검증 SQL.
-- Phase 2 readiness check: data sufficiency for new dashboard KPI cards.
--
-- 운영 환경 호환성 (PR 갱신 — 2026-05-02):
--   ✓ Supabase Dashboard SQL Editor (전체 paste + Run)
--   ✓ Supabase MCP (Claude 직접 실행 — mcp__claude_ai_Supabase__execute_sql)
--   ✓ 온프레미스 PostgreSQL (psql CLI: psql "$DATABASE_URL" -f scripts/dev/verify_phase2_data.sql)
--   ✓ Railway PostgreSQL (psql CLI 또는 Dashboard Query)
--
-- psql `\echo` meta-command 제거 — Supabase SQL Editor 호환.
-- 각 SELECT 의 첫 컬럼 'section' 으로 결과 그룹 식별.
--
-- 검증 항목 (Phase 2 KPI 후보별):
-- 1. analysis_feedbacks row 수 — AI 정합도 카드 (thumbs +1/-1 비율)
-- 2. merge_attempts row 수 — Auto-merge 성공률 카드
-- 3. failure_reason 분포 — Phase 3 advisor 활용
-- 4. analyses 활성도 — 현재 KPI 카드 보강 검증
-- 5. author_login 분포 — Q5 모드 토글 Phase 3 가치 측정
--
-- 컬럼명 주의: merge_attempts 는 attempted_at (created_at 아님 — MCP 검증 결과 반영).


-- ── (1) analysis_feedbacks 전체 + 최근 30일 + 분포 (AI 정합도 KPI 입력) ──
SELECT
    '1_analysis_feedbacks'                                  AS section,
    COUNT(*)                                                AS total_feedbacks,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(*) FILTER (WHERE thumbs = 1)                      AS thumbs_up,
    COUNT(*) FILTER (WHERE thumbs = -1)                     AS thumbs_down,
    COUNT(DISTINCT user_id)                                 AS distinct_users,
    COUNT(DISTINCT analysis_id)                             AS distinct_analyses
FROM analysis_feedbacks;


-- ── (2) merge_attempts 전체 + 최근 30일 + 성공률 (Auto-merge 성공률 KPI 입력) ──
SELECT
    '2_merge_attempts'                                      AS section,
    COUNT(*)                                                AS total_attempts,
    COUNT(*) FILTER (WHERE attempted_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(*) FILTER (WHERE success = TRUE)                  AS success_count,
    COUNT(*) FILTER (WHERE success = FALSE)                 AS failure_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE success = TRUE) / NULLIF(COUNT(*), 0),
        1
    )                                                       AS success_rate_pct,
    COUNT(DISTINCT failure_reason) FILTER (WHERE success = FALSE) AS distinct_failure_reasons
FROM merge_attempts;


-- ── (3) merge_attempts 실패 사유별 분포 (Phase 3 merge_failure_advisor 후속 활용) ──
SELECT
    '3_failure_reason'                                      AS section,
    COALESCE(failure_reason, '(none)')                      AS reason,
    COUNT(*)                                                AS occurrences,
    COUNT(*) FILTER (WHERE attempted_at >= NOW() - INTERVAL '30 days') AS last_30d
FROM merge_attempts
WHERE success = FALSE
GROUP BY failure_reason
ORDER BY occurrences DESC
LIMIT 10;


-- ── (4) analyses 전체 + 최근 7/30일 + 활성도 (현재 KPI 카드 보강 검증) ──
SELECT
    '4_analyses'                                            AS section,
    COUNT(*)                                                AS total_analyses,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')  AS last_7d,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS last_30d,
    COUNT(DISTINCT repo_id)                                 AS distinct_repos,
    ROUND(AVG(score)::numeric, 1)                           AS avg_score_all_time
FROM analyses;


-- ── (5) 활성 author (author_login) 분포 (Q5 모드 토글 Phase 3 의 사용자별 노트 가치 측정) ──
SELECT
    '5_author_login'                                        AS section,
    COUNT(DISTINCT author_login)                            AS distinct_authors,
    COUNT(*) FILTER (WHERE author_login IS NOT NULL)        AS with_author,
    COUNT(*) FILTER (WHERE author_login IS NULL)            AS without_author
FROM analyses;
