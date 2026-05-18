# 시크릿 유출 방지 가이드 (3중 가드)
# Secret Leak Prevention Guide (3-Layer Guard)

> **작성 배경**: 2026-05-03 사이클 66 커밋 메시지 본문에 실제 Telegram Bot Token이 포함되어
> GitHub 공개 커밋으로 노출된 사고(커밋 `7d0fa1fe`)에서 학습한 방지 체계.
> 유출 경로: 커밋 **메시지 본문** → git log diff 스캔만으로는 탐지 불가.

---

## 사고 요약 (2026-05-03)

| 항목 | 내용 |
|------|------|
| 유출 위치 | 커밋 메시지 본문 (코드 diff 아님) |
| 유출 값 | `TELEGRAM_BOT_TOKEN=<실제값>` |
| 커밋 SHA | `7d0fa1fe` (dangling — 어떤 브랜치도 미참조) |
| main 이력 | squash commit `288b55a` — 이미 `***REMOVED***` 치환 완료 |
| 탐지 실패 원인 | `git log --format="" -p` = 메시지 억제 / `-S` pickaxe = diff만 검색 |
| 제거 방법 | GitHub Support 요청 (아래 §잔여 이력 제거 절차 참조) |

---

## 잔여 이력 제거 절차 (dangling commit)

dangling commit은 로컬 git 도구로 직접 삭제 불가. GitHub Support만 가능.

1. https://support.github.com/contact 접속
2. 카테고리: **"Data removal request"** 선택
3. 제목: `Sensitive data removal — exposed token in commit message`
4. 본문:
   ```
   Repository: https://github.com/xzawed/SCAManager
   Commit SHA: 7d0fa1fe02a4fd36d80c5e58e3ac7c5d5166b0a4
   Reason: Real Telegram Bot Token accidentally included in commit message body.
   The token has been revoked. Please purge this commit from GitHub's cache.
   ```
5. 제출 후 24~72시간 내 처리 (긴급 표시 권장)

> **참고**: 토큰을 이미 폐기했다면 노출된 값은 무효화됨.
> GitHub Support 요청은 캐시/검색 인덱스 제거를 위해 권장.

---

## 3중 가드 체계

```
[로컬 커밋 전]          [push / PR]              [유출 후 대응]
Layer 1: pre-commit  →  Layer 2: CI Scan  →  Layer 3: Incident Response
```

---

## Layer 1 — Prevention (커밋 전 자동 차단)

### 1-A. pre-commit 훅 (gitleaks)

`.pre-commit-config.yaml` 설치 후 매 커밋 시 자동 실행:

```bash
pip install pre-commit
pre-commit install          # .git/hooks/pre-commit 등록
pre-commit install --hook-type commit-msg   # 커밋 메시지도 스캔
```

검사 범위:
- **코드 변경 (diff)** — 실제 시크릿 패턴 포함 여부
- **커밋 메시지 본문** — 이번 사고 유형 차단

### 1-B. 커밋 메시지 금지 패턴 체크리스트

커밋 메시지 본문에 아래 패턴 포함 금지:

| 금지 패턴 | 이유 |
|-----------|------|
| `TOKEN=<실제값>` | 토큰 직접 노출 |
| `KEY=<실제값>` | API 키 직접 노출 |
| 실제 IP/URL + 인증정보 | 내부 엔드포인트 노출 |
| `.env` 내용 그대로 붙여넣기 | 모든 시크릿 일괄 노출 |

**대안**: 실제 값 대신 `<REDACTED>` 또는 `***` 사용.

```
# 잘못된 예 (금지)
TELEGRAM_BOT_TOKEN=8763957868:AAFef...

# 올바른 예
TELEGRAM_BOT_TOKEN=<REDACTED> (실제 운영 토큰 — .env 참조)
```

### 1-C. .gitignore 검증

커밋 전 반드시 확인:

```bash
git check-ignore -v .env        # .env가 ignore 목록인지 확인
git status --short | grep "\.env"  # .env가 staged 여부 확인
```

---

## Layer 2 — Detection (CI/CD 자동 탐지)

### 2-A. GitHub Secret Scanning (자동 활성화)

- **위치**: GitHub 저장소 → Settings → Security → Secret scanning
- **기능**: push 시 Telegram/GitHub/AWS 등 알려진 토큰 패턴 자동 탐지
- **알림**: 등록된 이메일로 즉시 통보
- **확인**: `gh api repos/xzawed/SCAManager/secret-scanning/alerts`

### 2-B. CI TruffleHog 스캔 (`.github/workflows/ci.yml`)

PR 및 push 시 커밋 이력 전체 + 메시지 본문 자동 스캔 (ci.yml에 추가됨).

```bash
# 로컬에서 전체 이력 스캔 (커밋 메시지 포함)
docker run --rm -v "$(pwd):/pwd" \
  trufflesecurity/trufflehog:latest \
  git file:///pwd --only-verified
```

### 2-C. 올바른 시크릿 스캔 명령 (교훈 반영)

이번 사고에서 실패한 명령 vs 올바른 명령:

```bash
# 실패 (메시지 제외) — 사용 금지
git log --all -p --format="" | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"

# 올바른 방법 1: 메시지 + diff 동시 스캔
git log --all --format="%H%n%B" -p \
  | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"

# 올바른 방법 2: GitHub PR 브랜치 커밋 메시지까지 스캔 (squash 이전 커밋 포함)
gh pr list --state closed --limit 500 --json number,headRefOid --jq '.[].headRefOid' \
  | while read sha; do
      gh api "repos/xzawed/SCAManager/commits/$sha" --jq '.commit.message' 2>/dev/null
    done \
  | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"
```

> **핵심 교훈**: `git log --all`은 squash merge된 PR 브랜치의 원본 커밋을 포함하지 않는다.
> 로컬 ref graph에서 도달 불가능한 커밋은 GitHub API로만 접근 가능.

---

## Layer 3 — Incident Response (유출 발생 시)

### 즉시 대응 (발견 후 10분 이내)

```
1. 토큰 즉시 폐기
   - Telegram: @BotFather → /revoke → 봇 선택
   - GitHub Token: Settings → Developer settings → Tokens → Revoke
   - Anthropic API: console.anthropic.com → API Keys → Delete

2. 새 토큰 발급 후 Railway 환경변수 즉시 교체

3. 유출 범위 파악
   - 어떤 커밋/파일/PR에 포함됐는지
   - 언제부터 공개됐는지 (커밋 날짜)
   - squash 이전 원본 커밋 vs main 이력 구분
```

### 이력 제거 절차

| 상황 | 방법 |
|------|------|
| main 브랜치 이력에 포함 | `git filter-repo --message-callback` + force push + GitHub cache 무효화 요청 |
| PR 브랜치 dangling commit | GitHub Support 요청 (§잔여 이력 제거 절차 참조) |
| .env 파일이 커밋됨 | BFG Repo Cleaner + force push + GitHub Support |

### git filter-repo 사용법 (main 이력 재작성 시)

```bash
pip install git-filter-repo

# 커밋 메시지에서 실제 토큰 치환
git filter-repo --message-callback '
    import re
    return re.sub(
        b"실제토큰값",
        b"***REMOVED***",
        message
    )
'

# force push (팀 전원 re-clone 필요)
git push origin main --force-with-lease
```

> **주의**: force push 전 팀원 전원에게 공지 필수. 모든 로컬 clone 재설정 필요.

### 사고 기록 의무

유출 사고 발생 시 아래 정보를 `docs/reports/YYYY-MM-DD-secret-leak.md`로 기록:
- 유출 토큰 종류 (실제값 X)
- 발견 경위 및 시각
- 폐기 완료 시각
- 제거 완료 범위
- 재발 방지 추가 조치

---

## 점검 체크리스트 (매 사이클 종료 시)

```bash
# 1. .env gitignore 확인
git check-ignore -v .env

# 2. staged 파일에 민감 정보 없는지 확인
git diff --staged | grep -iE "token|secret|password|key" | grep -vE "os\.getenv|environ|#|example|test"

# 3. GitHub Secret Scanning alert 확인 (정책 14)
gh api repos/xzawed/SCAManager/secret-scanning/alerts \
  --jq '[.[] | select(.state=="open")] | length'

# 4. 커밋 메시지 본문 최근 10개 스캔
git log --format="%H%n%B" -10 \
  | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}" \
  && echo "🚨 토큰 패턴 발견" || echo "✅ 메시지 스캔 이상 없음"
```

---

## 관련 문서

- [환경변수 목록](../reference/env-vars.md)
- [Railway 운영 가이드](railway.md)
- [운영 smoke check](operational-smoke-checks.md)
- [작업 흐름 가이드](workflow.md)
