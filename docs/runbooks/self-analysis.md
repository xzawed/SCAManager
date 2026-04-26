# SCAManager 자기 분석 (Self-Analysis) 운영 가이드

SCAManager 자체 GitHub 리포를 분석 대상으로 등록하면 Push/PR마다 자동 분석이 실행된다. 이 문서는 등록 절차, 무한 루프 안전장치, 그리고 루프 발생 시 대응 방법을 다룬다.

## 등록 절차

1. SCAManager 대시보드 → **리포 추가** (Add Repository)
2. 리포 이름: `<owner>/SCAManager` (예: `xzawed/SCAManager`)
3. 등록 완료 후 `.scamanager/install-hook.sh`를 git pull 후 실행

```bash
git pull
bash .scamanager/install-hook.sh
```

등록 직후 첫 커밋 (`commit_scamanager_files`)은 `github-actions[bot]` 타입이 아닌 사용자 토큰으로 수행되므로 분석이 정상 실행된다.

## 무한 루프 안전장치 (3-Layer)

`src/webhook/providers/github.py`의 `_loop_guard_check()` 함수가 다음 3단계를 순서대로 체크한다:

| 레이어 | 조건 | 응답 |
|--------|------|------|
| 1. Kill-switch | `SCAMANAGER_SELF_ANALYSIS_DISABLED=1` 환경변수 | 202 skipped (self_analysis_disabled) |
| 2. 봇 발신 감지 | `sender.type == "Bot"` + BOT_LOGIN_WHITELIST 비포함 | 202 skipped (bot_sender) |
| 3-a. Skip 마커 | 커밋 메시지에 `[skip ci]`, `[skip-sca]`, `[ci skip]` 포함 | 202 skipped (skip_marker) |
| 3-b. Rate limit | 같은 리포에서 1시간 내 6회 초과 | 202 skipped (bot_rate_limit) |

**허용 봇 (분석 진행)**: `github-actions[bot]`, `dependabot[bot]` (BOT_LOGIN_WHITELIST)

## Kill-Switch 즉시 차단

루프가 의심될 때 Railway 환경변수로 즉시 차단:

```bash
# Railway CLI
railway variables --set SCAMANAGER_SELF_ANALYSIS_DISABLED=1

# 차단 해제
railway variables --set SCAMANAGER_SELF_ANALYSIS_DISABLED=0
```

환경변수 변경 후 Railway 재배포는 불필요하다 — pydantic-settings가 `.env` 파일이 아닌 Railway 환경변수를 실시간으로 읽는다.

## 루프 발생 징후 및 대응

**징후**:
- Railway 로그에 `loop_guard: bot rate limit exceeded` 반복
- 대시보드에 분석 건수가 1시간 내 6건 초과
- GitHub Actions에 PR이 자동 생성되고, 해당 PR 분석이 다시 PR을 생성

**대응 순서**:
1. **즉시 차단**: `SCAMANAGER_SELF_ANALYSIS_DISABLED=1` (위 Kill-Switch 참조)
2. **원인 분석**: Railway 로그에서 `loop_guard:` 접두사 라인 확인
3. **봇 PR 정리**: GitHub에서 `claude-fix/` 브랜치 PR을 수동 close + 브랜치 삭제
4. **재활성화**: `SCAMANAGER_SELF_ANALYSIS_DISABLED=0`

## 로그 패턴

```
# 봇 발신 차단
WARNING loop_guard: bot sender skipped repo=owner/SCAManager

# skip 마커 차단
INFO loop_guard: skip marker detected repo=owner/SCAManager

# rate limit 차단
WARNING loop_guard: bot rate limit exceeded repo=owner/SCAManager
```

## 관련 파일

| 파일 | 역할 |
|------|------|
| `src/webhook/loop_guard.py` | is_bot_sender / has_skip_marker / BotInteractionLimiter |
| `src/webhook/providers/github.py` | _loop_guard_check() — 진입점 통합 |
| `src/notifier/github_issue.py` | _BOT_PR_PREFIXES — Issue 생성 시 봇 PR 제외 |
| `src/constants.py` | BOT_LOGIN_WHITELIST / MAX_BOT_EVENTS_PER_HOUR / SKIP_CI_MARKERS |
