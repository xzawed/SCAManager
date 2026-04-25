#!/usr/bin/env python3
"""One-shot script to add English translations alongside Korean-only comments in tests/ and e2e/.

Run from repo root:
    python scripts/i18n_comments/_apply_test_translations.py
"""
from pathlib import Path
import re

# Map: file_rel_path -> list of (korean_text, english_text)
# The script finds the exact Korean line (stripped), prepends the same indentation,
# and inserts the English translation on the NEXT line.
TRANSLATIONS: dict[str, list[tuple[str, str]]] = {

"tests/integration/test_static_analyzer.py": [
    ("# 기존 테스트", "# Legacy tests (baseline coverage)."),
    ("# 정상 Python 코드는 error 심각도 이슈를 생성하지 않는다", "# Clean Python code should not produce error-severity issues."),
    ("# 문제 있는 Python 코드는 이슈를 1개 이상 생성한다", "# Problematic Python code should produce at least one issue."),
    ("# .yml 파일 분석 시 도구들이 이슈를 반환하지 않으면 빈 결과를 반환한다", "# Analyzing a .yml file should return an empty result when no tool fires."),
    ("# pylint FileNotFoundError (바이너리 없음) 처리", "# pylint FileNotFoundError handling (binary not found)."),
    ("# pylint 바이너리가 없을 때 FileNotFoundError → 빈 이슈 목록 반환", "# When pylint binary is missing, FileNotFoundError → return empty issue list."),
    ("# pylint 바이너리 없을 때 analyze_file 은 크래시 없이 StaticAnalysisResult 반환한다", "# analyze_file must return StaticAnalysisResult without crashing when pylint is absent."),
    ("# pylint subprocess 가 TimeoutExpired 를 발생시키면 빈 이슈 목록을 반환한다", "# When pylint subprocess raises TimeoutExpired, return an empty issue list."),
    ("# pylint JSON 파싱 실패 처리", "# pylint JSON parsing failure handling."),
    ("# pylint stdout 이 유효하지 않은 JSON 이면 JSONDecodeError → 빈 이슈 목록 반환", "# Invalid JSON from pylint stdout → JSONDecodeError → return empty issue list."),
    ("# pylint stdout 이 \"[\" 로 시작하지만 파싱 불가능한 JSON 이면 빈 이슈 목록 반환", '# stdout starting with "[" but unparseable JSON → return empty issue list.'),
    ("# pylint 정상 파싱 — AnalysisIssue 생성 검증", "# pylint normal parsing — verify AnalysisIssue creation."),
    ('# pylint 가 type="error" 인 항목을 반환하면 severity="error" 로 매핑된다', '# pylint items with type="error" must map to severity="error".'),
    ('# pylint 가 type="warning" 인 항목을 반환하면 severity="warning" 으로 매핑된다', '# pylint items with type="warning" must map to severity="warning".'),
    ('# pylint 가 type="fatal" 인 항목을 반환하면 severity="error" 로 매핑된다', '# pylint items with type="fatal" must map to severity="error".'),
    ("# test_ 로 시작하는 파일명을 테스트 파일로 감지한다", "# Filenames starting with test_ should be detected as test files."),
    ("# _test.py 로 끝나는 파일명을 테스트 파일로 감지한다", "# Filenames ending with _test.py should be detected as test files."),
    ("# 일반 파일명은 테스트 파일로 감지하지 않는다", "# Regular filenames should not be detected as test files."),
    ("# 경로가 포함된 경우에도 basename 기준으로 테스트 파일 여부를 판단한다", "# Test file detection must use the basename even when a full path is given."),
    ("# 테스트 파일에서 bandit 비실행 검증", "# Verify bandit is not run on test files."),
    ("# 테스트 파일에서 bandit 결과는 없어야 한다", "# bandit must not produce results on test files."),
    ("# bandit 이슈가 있거나 빈 목록이어도 security 카테고리로 분류되어야 함", "# bandit issues (or an empty list) must be classified under the security category."),
],

"tests/integration/test_webhook_to_gate.py": [
    ("# 시나리오 3: 잘못된 서명 → 401, 파이프라인 미실행", "# Scenario 3: invalid signature → 401, pipeline must not run."),
],

"tests/unit/analyzer/io/test_ai_review.py": [
    ('# 실제 프로덕션 분석 #543 에서 "AI 응답 파싱 실패" 경고가 관찰됨.', '# "AI response parsing failure" warning was observed in production analysis #543.'),
],

"tests/unit/analyzer/pure/test_registry.py": [
    ("# run() 없음", "# No run() method."),
    ("# 공백만 있는 content도 빈 결과로 처리된다", "# Content consisting only of whitespace should also yield an empty result."),
],

"tests/unit/analyzer/tools/test_eslint.py": [
    ("# 복수 messages가 있는 출력에서 모든 이슈를 반환해야 한다", "# All issues must be returned when the output contains multiple messages."),
    ("# messages 배열이 비어 있으면 빈 이슈 목록을 반환해야 한다", "# An empty messages array must return an empty issue list."),
    ("# stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다", "# Empty stdout must return an empty issue list."),
    ("# stdout이 JSON이 아닌 일반 텍스트로 시작하는 경우 빈 이슈 목록 반환", "# stdout starting with plain text (not JSON) must return an empty issue list."),
],

"tests/unit/analyzer/tools/test_golangci_lint.py": [
    ("# 사전 조건: go.mod 가 아직 없다", "# Precondition: go.mod does not exist yet."),
    ("# run() 호출 후 go.mod 가 생성되었어야 한다", "# After run(), go.mod must have been created."),
],

"tests/unit/analyzer/tools/test_semgrep.py": [
    ("# stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다", "# Empty stdout must return an empty issue list."),
    ("# 복수 이슈가 포함된 출력에서 모든 이슈를 반환해야 한다", "# All issues must be returned when the output contains multiple findings."),
    ("# semgrep이 비정상 종료코드 반환 시에도 예외 없이 파싱된 이슈를 반환해야 한다", "# Even with a non-zero exit code, semgrep must return parsed issues without raising."),
],

"tests/unit/analyzer/tools/test_shellcheck.py": [
    ("# 복수 이슈가 포함된 출력에서 모든 이슈를 반환해야 한다", "# All issues must be returned when the output contains multiple findings."),
    ("# stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다", "# Empty stdout must return an empty issue list."),
],

"tests/unit/api/test_auth.py": [
    ("# 테스트 1: 올바른 API 키로 요청 시 200 반환", "# Test 1: correct API key → 200 response."),
    ("# 테스트 2: 잘못된 API 키로 요청 시 401 반환", "# Test 2: wrong API key → 401 response."),
    ("# 테스트 3: API_KEY 설정됐는데 헤더 없으면 401", "# Test 3: API_KEY configured but header absent → 401."),
    ("# 테스트 4: API_KEY 미설정(빈 문자열)이면 키 없어도 200 (기존 동작 유지)", "# Test 4: API_KEY not set (empty string) → 200 even without a key (preserve existing behaviour)."),
],

"tests/unit/auth/test_github.py": [
    ("# 라우트 등록 확인 — OAuth 외부 연결 없이 라우트 존재 여부만 검증", "# Verify route registration — only checks route existence, no OAuth external calls."),
    ("# add된 User 객체를 캡처만 하고 반환하지 않는다 (재귀 방지)", "# Capture the added User object but do not return it (prevents recursion)."),
    ("# 성공(302 to /)이어서는 안 된다.", "# Must not be a success redirect (302 to /)."),
],

"tests/unit/config_manager/test_manager.py": [
    ("# 기존 동작 유지 테스트", "# Tests verifying that existing behaviour is preserved."),
    ("# 신규 필드 저장/조회 테스트 (Red: DB 컬럼 미존재)", "# Tests for new field persistence (Red phase: DB column does not exist yet)."),
],

"tests/unit/gate/test_engine.py": [
    ("# 공용 헬퍼", "# Shared helpers."),
    ("# 하위 호환성 — 기존 동작 유지 확인", "# Backward compatibility — verify existing behaviour is preserved."),
    ("# 예외 없이 완료되어야 한다", "# Must complete without raising an exception."),
    ("# 예외 내성 — 각 단계 예외가 다음 단계를 중단시키지 않아야 한다", "# Exception resilience — an exception in one stage must not abort the next."),
    ("# Telegram 알림은 여전히 발송되어야 함", "# Telegram notification must still be sent."),
],

"tests/unit/gate/test_github_review.py": [
    ("# PUT은 호출되지 않아야 한다", "# PUT must not be called."),
    ("# sleep이 1회 이상 호출되어야 한다 (재시도 대기)", "# sleep must be called at least once (retry wait)."),
    ("# GET은 2회 호출 (최초 + 재시도)", "# GET must be called twice (initial + retry)."),
    ("# PUT은 1회 호출", "# PUT must be called exactly once."),
],

"tests/unit/github_client/test_github_repos.py": [
    ("# GET 파일 존재 여부 조회 → 404 (파일 없음)", "# GET to check file existence → 404 (file not found)."),
    ("# PUT 성공 응답", "# PUT success response."),
    ("# 파일이 이미 존재할 때(GET → 200 + sha) PUT 요청에 sha가 포함됨", "# When file already exists (GET → 200 + sha), sha must be included in the PUT request."),
],

"tests/unit/github_client/test_helpers_models.py": [
    ("# 반환값이 dict 타입인지 검증", "# Verify that the return value is of type dict."),
],

"tests/unit/github_client/test_issues.py": [
    ("# 첫 번째 위치 인자 = URL", "# First positional argument = URL."),
],

"tests/unit/github_client/test_repos.py": [
    ("# 시나리오 1: 신규 파일 (GET 404) → PUT에 sha 없이 커밋", "# Scenario 1: new file (GET 404) → commit via PUT without sha."),
    ("# 두 PUT 호출 모두 sha 없이 전송", "# Both PUT calls must be sent without a sha."),
    ("# 시나리오 2: 기존 파일 (GET 200 + sha) → PUT에 sha 포함", "# Scenario 2: existing file (GET 200 + sha) → PUT request must include sha."),
],

"tests/unit/notifier/test_email.py": [
    ("# SMTP 에러 엣지 케이스", "# SMTP error edge cases."),
],

"tests/unit/notifier/test_github_comment.py": [
    ("# P2-11 — 두 빌더의 출력이 동일한지 확인 (통합 회귀)", "# P2-11 — verify both builders produce identical output (integration regression)."),
],

"tests/unit/notifier/test_http.py": [
    ("# src 임포트 전 환경변수 주입 필수", "# Environment variables must be injected before src imports."),
    ("# 127.0.0.1 루프백 주소는 반드시 차단", "# 127.0.0.1 loopback address must be blocked."),
    ("# IPv6 루프백 ::1 도 차단", "# IPv6 loopback ::1 must also be blocked."),
    ("# RFC 1918 10.x.x.x 사설 대역 차단", "# RFC 1918 10.x.x.x private range must be blocked."),
    ("# RFC 1918 192.168.x.x 사설 대역 차단", "# RFC 1918 192.168.x.x private range must be blocked."),
    ("# DNS가 사설 IP를 반환하는 외부처럼 보이는 도메인 차단 (DNS 리바인딩 방어)", "# Block seemingly external domains whose DNS resolves to private IPs (DNS rebinding defence)."),
    ("# 리다이렉트를 따라가지 않아야 한다 (SSRF 방어)", "# Must not follow redirects (SSRF defence)."),
    ("# 경고 로그 테스트", "# Warning log tests."),
],

"tests/unit/notifier/test_n8n_envelope.py": [
    ("# ── 공용 픽스처 ─────────────────────────────────────────────────────────────", "# ── Shared fixtures ────────────────────────────────────────────────────────────"),
    ("# ISO8601 파싱 가능 여부 검증", "# Verify the timestamp is parseable as ISO 8601."),
    ("# HTTP 오류 발생 시 예외가 전파되어야 한다", "# An HTTP error must propagate as an exception."),
],

"tests/unit/notifier/test_telegram.py": [
    ("# 반복 테스트: 다양한 길이로 절단 경계값 확인", "# Parametrised test: verify truncation boundary for various lengths."),
    ("# 절단된 메시지는 반드시 \"...\"로 끝나야 함", '# A truncated message must end with "...".'),
],

"tests/unit/repositories/test_analysis_feedback_repo.py": [
    ("# 첫 번째 피드백 (up)", "# First feedback (up)."),
    ("# 75-89 범위: 2 up → 1.0", "# Score range 75-89: 2 up votes → 1.0."),
],

"tests/unit/repositories/test_merge_attempt_repo.py": [
    ("# 오래된 시도", "# Old attempt."),
    ("# 다른 리포의 시도는 포함되지 않아야 함", "# Attempts from a different repo must not be included."),
    ("# 최근 실패들", "# Recent failures."),
    ("# 성공 — 집계 제외", "# Success — excluded from failure aggregation."),
    ("# 예전 실패 — since 파라미터로 제외되어야 함", "# Old failure — must be excluded by the since parameter."),
    ("# 성공은 키로 나타나지 않음", "# Successes must not appear as keys."),
    ("# 7일 전 실패는 제외", "# Failures older than 7 days must be excluded."),
],

"tests/unit/shared/test_claude_metrics.py": [
    ("# 핵심 필드 모두 포함", "# All essential fields must be present."),
],

"tests/unit/shared/test_http_client.py": [
    ("# 사전 상태 보장 — 다른 테스트가 초기화한 상태를 정리", "# Ensure a clean slate — tear down any state initialised by other tests."),
],

"tests/unit/shared/test_merge_metrics.py": [
    ("# WARNING 레벨의 로그가 최소 1건 기록되어야 함", "# At least one WARNING-level log entry must be recorded."),
],

"tests/unit/shared/test_sentry_scrubbing.py": [
    ("# list 형식은 필터링하지 않되 크래시하지 않음", "# List-typed headers must not be filtered but also must not crash."),
    ("# 민감 헤더 필터", "# Sensitive headers must be filtered."),
    ("# 안전 헤더 보존", "# Safe headers must be preserved."),
    ("# 예외 정보는 보존", "# Exception information must be preserved."),
],

"tests/unit/shared/test_stage_metrics.py": [
    ("# 예외 경로도 로그 발생", "# The exception path must also emit a log entry."),
    ("# 예외는 반드시 전파되어야 함 (swallow 금지)", "# The exception must propagate — swallowing it is forbidden."),
],

"tests/unit/test_config.py": [
    ("# db_sslmode 필드는 기본값이 빈 문자열이어야 한다", "# db_sslmode field default must be an empty string."),
    ("# DB_SSLMODE 환경변수 설정 시 해당 값이 반영되어야 한다", "# When DB_SSLMODE env var is set, that value must be reflected."),
    ("# DB_POOL_SIZE 환경변수 설정 시 해당 정수값이 반영되어야 한다", "# When DB_POOL_SIZE env var is set, the integer value must be reflected."),
    ("# 일반 온프레미스 URL에는 sslmode가 자동으로 추가되지 않아야 한다", "# A plain on-premises URL must not have sslmode added automatically."),
],

"tests/unit/test_crypto.py": [
    ("# 빈 문자열 입력은 암호화 여부와 무관하게 빈 문자열을 반환한다", "# Empty string input must return an empty string regardless of encryption state."),
    ("# 빈 문자열 입력은 복호화 여부와 무관하게 빈 문자열을 반환한다", "# Empty string input must return an empty string regardless of decryption state."),
    ("# 유효한 키가 있을 때 encrypt_token 은 원문과 다른 값을 반환한다(암호화됨)", "# With a valid key, encrypt_token must return a value different from the plaintext (encrypted)."),
    ("# 특수문자가 포함된 토큰도 암호화→복호화 후 원본과 동일하다", "# Tokens containing special characters must be identical to the original after encrypt→decrypt."),
    ("# 암호화된 값은 빈 문자열이 아니다", "# The encrypted value must not be an empty string."),
    ("# Fernet 은 nonce 를 사용하므로 동일한 평문도 암호화할 때마다 다른 값을 생성한다", "# Fernet uses a nonce, so the same plaintext produces a different ciphertext each time."),
    ("# 여기서는 최소한 둘 다 평문과 다른지만 확인", "# Here we only verify that both ciphertexts differ from the plaintext."),
    ("# 잘못된 키로 복호화하면 예외를 발생시키지 않고 입력값을 그대로 반환한다(fallback)", "# Decrypting with a wrong key must not raise — it must return the input as-is (fallback)."),
    ("# 먼저 key_a 로 암호화", "# First, encrypt with key_a."),
    ("# key_b(다른 키)로 복호화 시도", "# Attempt decryption with key_b (a different key)."),
    ("# 암호화 전 평문값(레거시 토큰)을 복호화하면 InvalidToken → 원문 그대로 반환한다", "# Decrypting a plaintext value stored before encryption was introduced → InvalidToken → return as-is."),
    ("# 예외 없이 반환되어야 함", "# Must return without raising an exception."),
    ("# 키가 설정된 상태에서도 빈 문자열 입력은 빈 문자열을 반환한다", "# Even with a key configured, empty string input must return an empty string."),
    ("# _get_fernet() 은 두 번째 호출에서 캐시된 인스턴스를 반환한다(동일 객체)", "# _get_fernet() must return the cached instance on the second call (same object)."),
    ("# 대신 직접 settings 모듈 속성을 제거하는 방식 사용", "# Instead, remove the settings module attribute directly."),
],

"tests/unit/test_failover.py": [
    ("# conftest.py 가 이미 환경변수를 주입하므로 추가 설정 불필요.", "# conftest.py already injects environment variables, so no additional setup is needed."),
    ("# 단, Settings 직접 인스턴스화 테스트에서는 필요한 필드만 명시적으로 전달한다.", "# However, tests that instantiate Settings directly must pass only the required fields explicitly."),
    ("# probe 스레드가 추가되지 않았는지 확인 (생성 전후 daemon 스레드 수 변화 없음)", "# Verify no probe thread was added (daemon thread count must not change before/after creation)."),
    ("# active_db 속성값은 문자열 타입이어야 한다", "# The active_db property value must be of type str."),
],

"tests/unit/test_main.py": [
    ("# --- 라우트 등록 검증 ---", "# --- Route registration verification ---"),
],

"tests/unit/ui/test_router.py": [
    ("# ── 비로그인 리다이렉트 테스트 ──────────────────────────", "# ── Unauthenticated redirect tests ──────────────────────────"),
    ("# ── 로그인 상태 기존 테스트 ──", "# ── Logged-in state baseline tests ──"),
    ("# 튜토리얼 핵심 마커 — 3단계 구성과 CTA 버튼", "# Tutorial key markers — 3-step structure and CTA button."),
    ("# 튜토리얼 마커가 없어야 함", "# Tutorial markers must not be present."),
    ("# (정확한 DOM 검증은 E2E 에서, 여기선 클래스 존재만 확인)", "# (Precise DOM validation is done in E2E; here we only verify class presence.)"),
    ("# ── 분석 상세 페이지 테스트 ──────────────────────────", "# ── Analysis detail page tests ──────────────────────────"),
    ("# ── 리포 삭제 엔드포인트 테스트 ──────────────────────────", "# ── Repository delete endpoint tests ──────────────────────────"),
    ("# ── 네비게이션 사용자 UI 테스트 ──────────────────────────", "# ── Navigation user UI tests ──────────────────────────"),
    ("# ── 이력 페이지 조회 강화 테스트 ──────────────────────────", "# ── Analysis history page enhanced tests ──────────────────────────"),
    ("# ── 분석 상세 버그 수정 TDD 테스트 ──────────────────────────", "# ── Analysis detail bug-fix TDD tests ──────────────────────────"),
    ("# 200 반환", "# Must return 200."),
    ("# 점수 배너 표시", "# Score banner must be displayed."),
    ("# AI 요약 섹션 없음", "# AI summary section must not be present."),
    ("# 로그아웃 버튼 및 URL이 포함되어야 함", "# Logout button and URL must be present."),
    ("# 실제 응답 대신 간단한 HTML 반환", "# Return simple HTML instead of the real response."),
    ("# 3건 반환", "# Must return 3 items."),
    ("# ── P3 커버리지 보강 테스트 ──────────────────────────", "# ── P3 coverage enhancement tests ──────────────────────────"),
    ("# hook_token이 새 값으로 업데이트되어야 한다", "# hook_token must be updated to the new value."),
    ("# label 안에 있는 경우를 걸러낸다.", "# Filters out items that are inside a label."),
],

"tests/unit/webhook/test_merged_pr.py": [
    ("# 공통 픽스처", "# Shared fixtures."),
    ("# 호출된 이슈 번호 집합이 {1, 2}와 일치해야 한다", "# The set of called issue numbers must match {1, 2}."),
],

"tests/unit/worker/test_pipeline.py": [
    ("# owner 토큰이 사용됐는지 확인", "# Verify the owner token was used."),
    ("# 새 시그니처 필수 인자 확인", "# Verify mandatory arguments of the new signature."),
    ("# 낮은 점수로 덮어쓰기", "# Overwrite with a low score."),
    ("# 점수 높게 유지 (85) → 보안 HIGH만으로 트리거돼야 함", "# Keep score high (85) → issue creation must be triggered by bandit HIGH alone."),
],

"tests/unit/worker/test_pipeline_pr_regate.py": [
    ("# 공용 픽스처", "# Shared fixtures."),
    ("# 시나리오 B: PR 이벤트가 신규 SHA로 직접 도착 — 기존 정상 경로 유지", "# Scenario B: PR event arrives directly with a new SHA — existing happy path preserved."),
],

"e2e/conftest.py": [
    ("# E2E 테스트용 고정 사용자 ID", "# Fixed user ID for E2E tests."),
    ("# ── 서버 시작/종료 ──────────────────────────────────────────────────────", "# ── Server start/stop ──────────────────────────────────────────────────────"),
    ("# 서버가 200을 반환할 때까지 대기 (최대 30초)", "# Wait until the server returns 200 (up to 30 seconds)."),
    ("# ── 테스트 데이터 시드 ────────────────────────────────────────────────", "# ── Test data seeding ────────────────────────────────────────────────────"),
    ("# 간단히: 같은 tmpdir 패턴으로 추정하는 대신, 환경변수에서 읽음", "# Simplified: read from the environment variable instead of guessing the tmpdir pattern."),
],

"e2e/test_settings.py": [
    ("# 펼침 직후에는 아직 적용되지 않음 — diff 미리보기만 렌더", "# Immediately after expanding, it is not yet applied — only the diff preview is rendered."),
    ("# 최소 먼저 펼침", "# Expand minimal preset first."),
    ("# 표준 펼침 → 최소가 닫혀야 함", "# Expand standard → minimal must collapse."),
    ("# 다른 버튼에는 active 없어야 함", "# Other buttons must not have the active class."),
    ("# 고급 설정 아코디언 펼치기 (Gate 모드 버튼이 내부에 있어 기본 상태에서 invisible)", "# Expand the advanced settings accordion (Gate mode buttons are inside and invisible by default)."),
    ("# disabled 모드에서는 슬라이더가 숨겨져 있으므로 먼저 auto로 전환", "# In disabled mode the slider is hidden, so switch to auto first."),
    ("# 1열이면 단일 값(예: \"860px\" 또는 \"375px\" 등 하나의 값)", '# Single column: one value (e.g. "860px" or "375px").'),
    ("# 2열: 값 사이에 공백이 있어야 함 (예: \"430px 430px\")", '# Two columns: values must be space-separated (e.g. "430px 430px").'),
    ("# ① 빠른 설정 제목은 기존 유지 — 개별 프리셋 카드로 대체", "# ① Quick settings heading is preserved — replaced by individual preset cards."),
    ("# strict 프리셋 — 현재(기본)와 차이가 많아 하이라이트 대상 다수", "# strict preset — many differences from the current (default) state → many highlighted fields."),
    ("# 클릭 직후 곧바로 클래스 존재 확인 (2.5초 타이머 전)", "# Verify class presence immediately after click (before the 2.5s timer fires)."),
],

"e2e/test_theme.py": [
    ("# 드롭다운 다시 열기", "# Re-open the dropdown."),
    ("# 외부 영역 클릭", "# Click outside the dropdown."),
],

"e2e/test_navigation.py": [
    ("# 또는 테이블이 있는 경우 테이블이 표시", "# Or a table is shown when repositories are present."),
],

}


def apply_translations(base: Path, translations: dict[str, list[tuple[str, str]]]) -> int:
    total_applied = 0
    for rel_path, pairs in translations.items():
        fp = base / rel_path
        if not fp.exists():
            print(f"SKIP (not found): {rel_path}")
            continue
        text = fp.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        changed = False
        for korean, english in pairs:
            # Find the Korean line and insert English on the next line with same indentation
            for i, raw_line in enumerate(lines):
                stripped = raw_line.rstrip("\n\r")
                # Match exact stripped content
                if stripped.rstrip() == korean or stripped.strip() == korean.strip():
                    # Check if next line is already the English translation
                    next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if next_stripped == english.strip():
                        break  # Already applied
                    # Determine indentation from the Korean line
                    indent = len(stripped) - len(stripped.lstrip())
                    english_line = " " * indent + english + "\n"
                    lines.insert(i + 1, english_line)
                    total_applied += 1
                    changed = True
                    break
        if changed:
            fp.write_text("".join(lines), encoding="utf-8")
            print(f"UPDATED: {rel_path}")
    return total_applied


if __name__ == "__main__":
    base = Path("f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager")
    n = apply_translations(base, TRANSLATIONS)
    print(f"\nTotal translations applied: {n}")
