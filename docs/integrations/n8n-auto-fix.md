# n8n 자동화 워크플로 — GitHub Issue → Claude CLI → PR → auto_merge

SCAManager와 자체 호스팅 n8n 서버를 연동해 GitHub Issue 등록 시 Claude CLI가 자동으로 코드를 수정하고 PR을 생성하는 완전 무인 파이프라인 구성 가이드.

---

## 전체 흐름

```
GitHub Issue 등록
  └─> SCAManager /webhooks/github
        └─> notify_n8n_issue() [envelope + HMAC-SHA256]
              └─> n8n 서버 Webhook
                    ├─ HMAC 검증
                    ├─ action=="opened" 필터
                    ├─ 세마포어 (repo#N 중복 방지)
                    └─> Execute Command: claude_fix.sh
                          1. git clone (shallow)
                          2. checkout -b claude-fix/issue-N
                          3. claude -p (stdin 프롬프트)
                          4. diff 검증 · commit · push
                          5. gh pr create (Closes #N)

PR open
  └─> SCAManager PR 파이프라인 (기존)
        · 정적 분석 + AI 리뷰 + 점수
        · run_gate_check → auto_merge 평가
        · 점수 ≥ merge_threshold → squash merge
        · Issue 자동 close (Closes #N)
```

**SCAManager 코드 변경 없음.** 기존 `notify_n8n_issue()`가 이미 envelope을 전송한다.

---

## n8n 호스트 사전 준비

```bash
# 필수 도구
apt install -y git curl jq

# GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | tee /etc/apt/sources.list.d/github-cli.list
apt update && apt install gh -y

# Claude CLI (Node 18+ 필요)
npm i -g @anthropic-ai/claude-code

# 워크스페이스 디렉토리
mkdir -p /var/lib/n8n/claude-workspace
chown n8n:n8n /var/lib/n8n/claude-workspace

# 스크립트 설치
mkdir -p /opt/claude-runner
install -o n8n -g n8n -m 750 claude_fix.sh /opt/claude-runner/claude_fix.sh

# 주기 정리 cron (orphan 워크스페이스 방지)
echo "0 4 * * * n8n find /var/lib/n8n/claude-workspace -mindepth 2 -mtime +1 -exec rm -rf {} +" \
  >> /etc/cron.d/claude-workspace-cleanup
```

---

## claude_fix.sh

`/opt/claude-runner/claude_fix.sh` 에 배치. n8n Execute Command 노드가 호출.

```bash
#!/bin/bash
# /opt/claude-runner/claude_fix.sh
# n8n Execute Command 노드가 env로 주입하는 변수:
#   REPO, ISSUE_NUMBER, ISSUE_TITLE, ISSUE_BODY, GH_TOKEN, ANTHROPIC_API_KEY
set -euo pipefail

WORK_ROOT="/var/lib/n8n/claude-workspace"
SAFE_REPO="${REPO//\//_}"
WORK_DIR="${WORK_ROOT}/${SAFE_REPO}/${ISSUE_NUMBER}"
BRANCH="claude-fix/issue-${ISSUE_NUMBER}"

# 종료 시 워크스페이스 자동 정리 (성공·실패 무관)
trap 'rm -rf "${WORK_DIR}"' EXIT

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# shallow clone (PAT을 HTTPS userinfo로만 사용 — argv 노출 방지)
git clone --depth 20 "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" .
git config user.email "claude-bot@your-domain.xyz"
git config user.name  "Claude Auto-Fix"
git checkout -b "${BRANCH}"

# 프롬프트 stdin 전달 (argv 주입 방어)
PROMPT=$(cat <<EOP
다음 GitHub Issue를 해결하는 코드 수정을 수행하세요.

# 엄격한 요구사항 (위반 시 작업 실패)
1. 이슈에서 명시된 변경만 수행 — 관련 없는 리팩터링 금지
2. 변경에 대응되는 테스트를 반드시 추가·수정하고 로컬에서 통과 확인
3. public API·CLI·설정·동작 변경은 README/CLAUDE.md/docs/ 중 해당 문서에 반영
   → 문서 누락 시 작업 완료로 간주하지 말 것
4. 커밋 메시지 형식: "fix: #${ISSUE_NUMBER} - <한 줄 요약>"
5. 이슈가 코드 변경 불필요(질문/중복/스팸)로 판단되면 어떤 변경도 하지 말고
   stdout 에 정확히 "NO_CHANGE_NEEDED"를 출력하고 종료
6. 작업 불가·불명확하면 stderr 에 "TASK_UNCLEAR: <사유>"를 출력하고 비정상 종료

# 이슈 정보
제목: ${ISSUE_TITLE}
본문:
${ISSUE_BODY}
EOP
)

CLAUDE_OUT=$(mktemp); CLAUDE_ERR=$(mktemp)

# claude cli — 15분 타임아웃
if ! timeout 900 sh -c 'printf "%s" "$PROMPT" | claude -p --permission-mode acceptEdits' \
      > "${CLAUDE_OUT}" 2> "${CLAUDE_ERR}"; then
  head -c 4000 "${CLAUDE_ERR}" >&2
  exit 2
fi

# NO_CHANGE_NEEDED 판단
if grep -q "^NO_CHANGE_NEEDED$" "${CLAUDE_OUT}"; then
  exit 1
fi

# 실제 변경 없음
if git diff --quiet && git diff --cached --quiet; then
  echo "claude completed without producing file changes" >&2
  exit 1
fi

git add -A
git commit -m "fix: #${ISSUE_NUMBER} - automated patch by Claude"

if ! git push origin "${BRANCH}"; then
  exit 3
fi

gh pr create \
  --title "fix: #${ISSUE_NUMBER} ${ISSUE_TITLE}" \
  --body  "Closes #${ISSUE_NUMBER}

> 자동 생성 PR — n8n + Claude CLI

## Claude 수정 요약
$(head -c 2000 "${CLAUDE_OUT}")" \
  --head "${BRANCH}" --base main --repo "${REPO}"
```

### exit code 의미

| code | 의미 | n8n 분기 동작 |
|------|------|-------------|
| 0 | PR 생성 성공 | 종료 (SCAManager 파이프라인이 나머지 처리) |
| 1 | 변경 불필요 / 변경 없음 | Issue 코멘트만 |
| 2 | claude 실행 실패 | Issue 코멘트 + Telegram 알림 |
| 3 | push 실패 | Issue 코멘트 + Telegram 알림 |
| 124 | timeout (15분 초과) | Telegram 알림만 |

---

## n8n 워크플로 구성 (9 nodes)

n8n UI에서 새 workflow 생성 후 아래 순서대로 노드 추가. JSON export는 `n8n-workflow.json` 참조.

### Node 1 — Webhook Trigger

```
Type: Webhook
HTTP Method: POST
Path: scamanager-issue
Response Mode: Immediately
```

raw body를 다음 노드로 전달하기 위해 **"Raw Body"** 옵션 활성화.

### Node 2 — HMAC 검증 (Code)

```javascript
// N8N_WEBHOOK_SECRET은 n8n Credential에서 읽어옴
const secret = $env.N8N_WEBHOOK_SECRET;
const header = $input.first().headers['x-scamanager-signature-256'] || '';
const rawBody = $input.first().binary?.data
  ? Buffer.from($input.first().binary.data, 'base64').toString()
  : JSON.stringify($input.first().json);

const crypto = require('crypto');
const expected = 'sha256=' + crypto.createHmac('sha256', secret)
  .update(rawBody).digest('hex');

// 타이밍 세이프 비교
const sigBuf = Buffer.from(header);
const expBuf = Buffer.from(expected);
const valid = sigBuf.length === expBuf.length &&
  crypto.timingSafeEqual(sigBuf, expBuf);

if (!valid) {
  throw new Error('HMAC verification failed — rejecting webhook');
}

return $input.all();
```

### Node 3 — 이벤트 필터 (IF)

```
Condition: {{ $json.event_type }} == "issue"
AND: {{ $json.data.action }} == "opened"
```

False 경로는 NoOp으로 연결 (무시).

### Node 4 — 작업 변수 세팅 (Set)

```
repo         = {{ $json.repo }}
issue_number = {{ $json.data.issue.number }}
issue_title  = {{ $json.data.issue.title }}
issue_body   = {{ $json.data.issue.body }}
work_key     = {{ $json.repo + '#' + $json.data.issue.number }}
```

### Node 5 — 세마포어 락 (Code)

```javascript
const key = $json.work_key;
const staticData = $getWorkflowStaticData('node');

if (staticData[key] && Date.now() - staticData[key] < 20 * 60 * 1000) {
  // 20분 내 동일 키 실행 중 → 중단
  return [];
}
staticData[key] = Date.now();
return $input.all();
```

### Node 6 — Execute Command

```
Command: /opt/claude-runner/claude_fix.sh
Environment Variables:
  REPO          = {{ $json.repo }}
  ISSUE_NUMBER  = {{ $json.issue_number }}
  ISSUE_TITLE   = {{ $json.issue_title }}
  ISSUE_BODY    = {{ $json.issue_body }}
  GH_TOKEN      = {{ $credentials.githubPat.token }}
  ANTHROPIC_API_KEY = {{ $credentials.anthropic.apiKey }}
```

### Node 7 — Switch (exit code)

```
Value: {{ $json.exitCode }}
Rules:
  0   → 성공 분기
  1   → NO_CHANGE_NEEDED 분기
  2   → claude 실패 분기
  3   → push 실패 분기
  124 → timeout 분기
```

### Node 8 — GitHub Issue Comment

실패 케이스별 메시지로 Issue에 코멘트 작성:

| 케이스 | 메시지 |
|--------|--------|
| exit 1 | `🤖 코드 변경이 필요하지 않은 이슈로 판단됐습니다. 수동 검토가 필요한 경우 재오픈 해주세요.` |
| exit 2 | `🤖 자동 처리 중 오류가 발생했습니다:\n\n\`\`\`\n{{ $json.stderr }}\n\`\`\`` |
| exit 3 | `🤖 원격 push에 실패했습니다. PAT 권한(contents:write)을 확인해 주세요.` |

### Node 9 — Telegram 알림 (실패 케이스)

기존 SCAManager Telegram Bot Token 재사용:

```
Chat ID: {{ $env.TELEGRAM_CHAT_ID }}
Text:
  exit 2: ❌ *Issue #{{ $json.issue_number }}* 자동 처리 실패\n`{{ $json.repo }}`
  exit 3: ❌ *Issue #{{ $json.issue_number }}* push 실패\n`{{ $json.repo }}`
  exit 124: ⏱️ *Issue #{{ $json.issue_number }}* 타임아웃 (15분 초과)
```

---

## 시크릿·권한 설정

### n8n Credential 등록

| Credential 이름 | 값 | 용도 |
|----------------|---|------|
| `N8N_WEBHOOK_SECRET` | SCAManager `.env`의 `N8N_WEBHOOK_SECRET` 동일 값 | HMAC 검증 |
| `GH_TOKEN` | GitHub Fine-grained PAT | clone · push · PR 생성 |
| `ANTHROPIC_API_KEY` | Anthropic Console에서 발급 | claude cli |

### GitHub PAT 권한 (Fine-grained 권장)

대상 리포별 설정:
- **Contents**: Read & Write (clone, push)
- **Pull requests**: Read & Write (PR 생성)
- **Issues**: Read & Write (코멘트 작성)
- **Metadata**: Read (기본)

---

## 실패 피드백 매트릭스

| 케이스 | exit | Issue 코멘트 | Telegram |
|--------|------|-------------|----------|
| PR 생성 성공 | 0 | — (PR Closes #N 자동 링크) | — |
| 변경 불필요 | 1 | 🤖 변경 불필요 판단 | — |
| claude 실패 | 2 | 🤖 오류 내용 | ❌ Issue #N 처리 실패 |
| push 실패 | 3 | 🤖 PAT 권한 확인 | ❌ Issue #N push 실패 |
| 타임아웃 | 124 | — | ⏱️ Issue #N 타임아웃 |

---

## 동시성·안정성

- **세마포어**: n8n static data 또는 Redis SETNX(TTL 20분)로 `repo#issue_number` 중복 실행 차단
- **타임아웃**: `timeout 900` 래핑으로 15분 상한 (claude 폭주 방어)
- **워크스페이스 격리**: `/var/lib/n8n/claude-workspace/{repo}/{issue_number}/`
- **디스크 정리**: `trap EXIT` 즉시 + 일 단위 cron

---

## 무한 루프 방지

SCAManager의 `create_issue` 기능이 활성화된 리포에서, claude PR이 낮은 점수를 받으면 또 이슈가 생성되어 루프가 발생할 수 있다.

**Phase 1 권장**: 자동화를 적용할 리포의 설정 페이지에서 `create_issue` 토글을 **off**로 유지.

향후 필요 시: 봇 계정이 작성한 커밋/PR은 `create_issue` 조건에서 제외하는 필터를 SCAManager에 추가.

---

## End-to-end 검증 체크리스트

```
[ ] 1. curl로 잘못된 HMAC 서명 전송 → workflow 중단 로그 확인
[ ] 2. "안녕하세요 문의입니다" 이슈 → exit 1 + Issue 코멘트 (코드 변경 없음)
[ ] 3. "README 오타 수정" 이슈 → PR 생성 → SCAManager 분석 → auto_merge → Issue close
[ ] 4. 테스트가 있는 리포에 기능 추가 이슈 → claude가 테스트까지 커밋 → PR CI 통과
[ ] 5. 문서 변경 이슈 → README/docs 함께 수정됐는지 PR diff 확인
[ ] 6. 불가능한 이슈 → TASK_UNCLEAR → Issue 코멘트 + Telegram 수신
[ ] 7. 동일 이슈 webhook 2회 → 두 번째 실행 세마포어 차단 확인
[ ] 8. n8n execution log · PR 히스토리 · SCAManager Analysis 세 곳에서 이벤트 추적 확인
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| workflow 2단계에서 중단 | HMAC 불일치 | SCAManager `.env`의 `N8N_WEBHOOK_SECRET` == n8n Credential 값 확인 |
| exit 3 루프 | PAT 권한 부족 또는 만료 | GitHub Fine-grained PAT `contents:write` + `pull_requests:write` 재발급 |
| claude exit 2, "No such file" | claude cli 미설치 | n8n 호스트에서 `npm i -g @anthropic-ai/claude-code` 재실행 |
| PR 생성됐지만 SCAManager 분석 안 됨 | 리포에 n8n_webhook_url 미설정 | SCAManager 설정 페이지 → 알림 채널 → n8n URL 입력 |
| Issue close 안 됨 | PR merge됐지만 "Closes #N" 미인식 | `gh pr create --body` 에 `Closes #N` 정확히 포함됐는지 확인 |
| 타임아웃 반복 | 대형 리포 또는 복잡한 이슈 | claude_fix.sh의 `timeout 900` 값 조정 (최대 권장 1800) |

---

## Phase 분할

| Phase | 내용 |
|-------|------|
| **1 (현재)** | n8n workflow + claude_fix.sh + HMAC + 실패 피드백 + 문서 |
| 2 | `GET /api/analyses/by-pr` 추가 — PR 점수를 Issue 코멘트에 요약 |
| 3 | `edited`/`labeled` 트리거 확장, 우선순위 큐 |
| 4 | Prometheus `/metrics` + Grafana 처리시간·성공률 대시보드 |
