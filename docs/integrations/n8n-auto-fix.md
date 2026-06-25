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

**토큰 릴레이 모델**: `notify_n8n_issue()`(`src/notifier/n8n.py`)가 GitHub 토큰을 envelope `data.repo_token`으로 릴레이한다 — **HMAC 서명 시크릿(`N8N_WEBHOOK_SECRET`)이 설정된 인증 채널로만 전송**(미설정 시 토큰 생략, `n8n.py:93-95` 방어 심화). 따라서 n8n 워크플로는 별도 GitHub credential 없이 이 payload 토큰을 `GH_TOKEN`으로 주입한다(아래 Node 6 참조).

> ⚠️ `repo_token` 파라미터 + 릴레이 로직은 SCAManager 측 코드(`notify_n8n_issue(repo_token=...)`)에 포함된 기능이다 — 본 가이드의 "코드 변경 없음"이라는 과거 서술은 부정확했다(2026-06-25 정정).

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
# n8n 실행 노드가 env로 주입하는 변수: REPO, ISSUE_NUMBER, ISSUE_TITLE, ISSUE_BODY, GH_TOKEN
# (GH_TOKEN = SCAManager payload 릴레이 repo_token — Node 6 참조)
# ANTHROPIC_API_KEY 는 노드가 주입하지 않음 — n8n 호스트 프로세스 env 또는 claude 로그인 상태에서 제공.
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
# 🔴 PROMPT 은 부모 셸 변수다. `sh -c '...'` 서브셸은 export 안 된 부모 변수를 상속하지 않으므로
# `sh -c 'printf "%s" "$PROMPT" | ...'` 로 감싸면 $PROMPT 가 빈 문자열이 되어 claude 가 무지시 실행된다.
# printf 를 부모 셸에서 직접 실행해 파이프로 stdin 전달 (timeout 은 claude 만 래핑, set -o pipefail 로 실패 전파).
# 🔴 PROMPT is a parent-shell var; a `sh -c '...'` subshell does NOT inherit non-exported vars → empty prompt.
# Run printf in the parent shell and pipe into claude (timeout wraps claude only).
# rc 캡처(|| rc=$?)로 set -e 중단 회피 + pipefail 로 claude/timeout 종료코드 전파.
# Capture rc to avoid set -e abort; pipefail propagates claude/timeout's status.
rc=0
printf '%s' "$PROMPT" | timeout 900 claude -p --permission-mode acceptEdits \
      > "${CLAUDE_OUT}" 2> "${CLAUDE_ERR}" || rc=$?
if [ "${rc}" -ne 0 ]; then
  [ "${rc}" -eq 124 ] && exit 124   # timeout 은 124 보존 (exit code 표 참조)
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

> 🔴 **보안 — HMAC 검증 (hard-reject) 의무 + 직렬화 주의**: claude_fix.sh 는 GitHub 토큰으로 clone·push·PR 을 수행하는 고권한 경로이므로 **불일치 시 거부(hard-reject)가 운영 기본값**이어야 한다. 위 코드는 그 권장 구현이며 **반드시 Node 1 의 "Raw Body" 옵션을 켜고 `rawBody`(원본 바이트)로 검증**해야 한다.
>
> ⚠️ **이유**: SCAManager 는 Python `json.dumps(payload)`(키 사이 공백 O)로 서명하는데, n8n 의 `JSON.stringify(parsedBody)`(공백 X)는 **바이트가 달라 HMAC 이 항상 불일치**한다. 따라서 파싱된 body 를 재직렬화해 검증하면 정상 webhook 도 전부 거부된다 → 반드시 **수신 원본 바이트(`rawBody`)** 로 검증할 것.
>
> 🔴 **번들 `n8n-workflow.json` 주의**: 출하 JSON 의 HMAC 노드는 위 직렬화 불일치를 회피하려 **soft-pass(불일치 시 경고만 남기고 통과)** 로 되어 있다 — 즉 **무인증 트리거를 차단하지 못한다**. 운영 배포 전 위 hard-reject 구현으로 교체하고 Raw Body 검증이 동작하는지 **반드시 실 n8n 인스턴스에서 확인**할 것(Claude 정적 검증 불가 영역 — 운영자 의무).

### Node 3 — 이벤트 필터 (IF)

```
Condition: {{ $json.body.event_type }} == "issue"
AND: {{ $json.body.data.action }} ∈ {"opened", "reopened"}
```

False 경로는 NoOp으로 연결 (무시).

> ⚠️ **이벤트 필터 로직 주의 (번들 JSON 결함)**: 출하 `n8n-workflow.json` 의 이벤트 필터 IF 노드는 세 조건 `[event_type==issue, action==opened, action==reopened]` 를 `combineOperation: any` 로 결합한다. `any` 는 **셋 중 하나만 참이면 통과**하므로 `event_type==issue` 이기만 하면 `closed`·`edited` 등에서도 트리거되어 불필요한 claude_fix.sh 실행이 발생한다. 의도는 `event_type==issue AND action∈{opened,reopened}` 다. 단일 IF(v1) 로는 `A AND (B OR C)` 를 표현할 수 없으므로 **(a) `event_type==issue` 선행 IF(all) + `action∈{opened,reopened}` 후행 IF(any) 2단 분리**, 또는 **(b) Code 노드에서 `event_type==='issue' && ['opened','reopened'].includes(action) ? items : []` 명시 평가**로 교체할 것(운영자 검증 영역).

### Node 4 — 작업 변수 세팅 (Set)

```
repo         = {{ $json.body.repo }}
issue_number = {{ $json.body.data.issue.number }}
issue_title  = {{ $json.body.data.issue.title }}
issue_body   = {{ $json.body.data.issue.body || '' }}
work_key     = {{ $json.body.repo + '#' + $json.body.data.issue.number }}
repo_token   = {{ $json.body.data.repo_token || '' }}
```

> envelope 은 webhook body 아래 중첩되므로 표현식은 `$json.body.*` 경로다(출하 JSON Set 노드와 일치). `repo_token` 은 SCAManager 가 릴레이한 GitHub 토큰(Node 6 `GH_TOKEN` 출처).

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

### Node 6 — claude_fix.sh 실행

```
Command: /opt/claude-runner/claude_fix.sh
Environment Variables:
  REPO          = {{ $json.repo }}
  ISSUE_NUMBER  = {{ $json.issue_number }}
  ISSUE_TITLE   = {{ $json.issue_title }}
  ISSUE_BODY    = {{ $json.issue_body }}
  GH_TOKEN      = {{ $json.repo_token }}   # ← SCAManager payload 릴레이(Node 4 repo_token), credential 아님
```

> ⚠️ **번들 JSON 구현 차이 (정합 주의)**:
> - **GH_TOKEN 출처** = `repo_token`(SCAManager 가 HMAC 인증 채널로 릴레이한 payload 토큰, 위 "토큰 릴레이 모델" 참조) — **n8n GitHub credential 이 아니다**.
> - **`ANTHROPIC_API_KEY` 는 노드 env 로 주입하지 않는다** — 번들 JSON 의 실행 노드 env 에 없으며, claude CLI 는 **n8n 호스트 프로세스 env 또는 claude 설정**에서 키를 읽는다. 호스트에 `ANTHROPIC_API_KEY` 를 export 하거나 `claude` 로그인 상태를 준비할 것.
> - **실행 방식**: 번들 `n8n-workflow.json` 은 이 단계를 "Execute Command" 노드가 아니라 **Code 노드의 `execFileSync('/opt/claude-runner/claude_fix.sh')`** 로 구현한다(exitCode/stdout/stderr 캡처). UI 로 직접 구성 시 동등 동작이면 무방.

### Node 7 — Switch (exit code)

```
Value: {{ $json.exitCode }}
Rules:
  0   → 성공 분기 (output 0, 미연결)
  1   → NO_CHANGE_NEEDED 분기 (output 1 → Issue 코멘트)
  2   → claude 실패 분기 (output 2 → Issue 코멘트 + Telegram)
  3   → push 실패 분기 (output 3 → Issue 코멘트 + Telegram)
  124 / 그 외 → fallbackOutput (output 4 → Telegram 알림)
```

> timeout(124) 등 0~3 외 종료코드는 Switch 의 `fallbackOutput`(output 4)으로 떨어진다 — 번들 JSON 은 output 4 → Telegram 알림으로 연결한다(Telegram 노드는 기본 disabled, Node 9 참조).

### Node 8 — GitHub Issue Comment

실패 케이스별 메시지로 Issue에 코멘트 작성:

| 케이스 | 메시지 |
|--------|--------|
| exit 1 | `🤖 코드 변경이 필요하지 않은 이슈로 판단됐습니다. 수동 검토가 필요한 경우 재오픈 해주세요.` |
| exit 2 | `🤖 자동 처리 중 오류가 발생했습니다:\n\n\`\`\`\n{{ $json.stderr }}\n\`\`\`` |
| exit 3 | `🤖 원격 push에 실패했습니다. PAT 권한(contents:write)을 확인해 주세요.` |

### Node 9 — Telegram 알림 (실패 케이스)

> ⚠️ 번들 `n8n-workflow.json` 의 Telegram 노드는 **기본 `disabled: true`** 다(자격증명 미설정 환경 보호). 실패 알림을 받으려면 n8n UI 에서 노드를 활성화(`disabled: false`)하고 Telegram credential·chat_id 를 설정할 것.

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

| 항목 | 값 | 용도 | 위치 |
|------|---|------|------|
| HMAC 시크릿 | SCAManager `.env`의 `N8N_WEBHOOK_SECRET` 동일 값 | HMAC 검증 | 번들 JSON 은 `/etc/n8n-secrets/hmac_secret` 파일에서 읽음 (n8n credential 로 대체 가능) |
| GitHub PAT (`githubApi` credential) | GitHub Fine-grained PAT | **Issue 코멘트 작성**(Node 8) | n8n credential |
| clone·push·PR 용 토큰 | SCAManager 가 릴레이한 `repo_token` | clone · push · PR 생성 | **n8n credential 아님** — payload 릴레이(위 "토큰 릴레이 모델"). SCAManager 측에 토큰 설정 |
| `ANTHROPIC_API_KEY` | Anthropic Console 발급 | claude cli | **n8n credential 아님** — n8n 호스트 프로세스 env 또는 claude 로그인 |

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

**구현 완료 (Phase 2)**: `src/notifier/github_issue.py`의 `_IssueNotifier.is_enabled()`가 PR `head.ref`를 `_BOT_PR_PREFIXES`(`claude-fix/`·`bot/`·`renovate/`·`dependabot/`) 중 하나로 시작하는지 검사해 봇/자동화 PR에서는 `create_issue`를 건너뜀 — 토글 off 없이도 무한 루프 자동 차단.

```python
# src/notifier/github_issue.py:22
_BOT_PR_PREFIXES = ("claude-fix/", "bot/", "renovate/", "dependabot/")

# _IssueNotifier.is_enabled() 내부
is_bot_pr = ctx.pr_head_ref and any(
    ctx.pr_head_ref.startswith(prefix) for prefix in _BOT_PR_PREFIXES
)
if is_bot_pr:
    return False  # 봇 PR은 create_issue 채널 비활성
```

---

## End-to-end 검증 체크리스트

```
[ ] 1. curl로 잘못된 HMAC 서명 전송 → (hard-reject 적용 시) workflow 중단 / (번들 JSON soft-pass 시) "HMAC mismatch — soft pass" 경고 로그 확인 후 hard-reject 로 하드닝
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
| (hard-reject 시) workflow 2단계 중단 / (soft-pass 시) "HMAC mismatch" 경고 | HMAC 불일치 | SCAManager `.env`의 `N8N_WEBHOOK_SECRET` == n8n 시크릿 값 확인 + Node 2 가 **rawBody**로 검증하는지 확인(Python json.dumps↔JS JSON.stringify 직렬화 차이) |
| exit 3 루프 | PAT 권한 부족 또는 만료 | GitHub Fine-grained PAT `contents:write` + `pull_requests:write` 재발급 |
| claude exit 2, "No such file" | claude cli 미설치 | n8n 호스트에서 `npm i -g @anthropic-ai/claude-code` 재실행 |
| PR 생성됐지만 SCAManager 분석 안 됨 | 리포에 n8n_webhook_url 미설정 | SCAManager 설정 페이지 → 알림 채널 → n8n URL 입력 |
| Issue close 안 됨 | PR merge됐지만 "Closes #N" 미인식 | `gh pr create --body` 에 `Closes #N` 정확히 포함됐는지 확인 |
| 타임아웃 반복 | 대형 리포 또는 복잡한 이슈 | claude_fix.sh의 `timeout 900` 값 조정 (최대 권장 1800) |

---

## Phase 분할

| Phase | 내용 | 상태 |
|-------|------|------|
| **1** | n8n workflow + claude_fix.sh + HMAC + 실패 피드백 + 문서 | ✅ 완료 |
| **2** | 봇 PR auto_merge 누락 수정 — SHA 멱등성 re-gate + `claude-fix/*` 무한루프 가드 + `merge_pr` 진단 강화 | ✅ 완료 |
| 3 | `GET /api/analyses/by-pr` 추가 — PR 점수를 Issue 코멘트에 요약 | 대기 |
| 4 | `edited`/`labeled` 트리거 확장, 우선순위 큐 | 대기 |
| 5 | Prometheus `/metrics` + Grafana 처리시간·성공률 대시보드 | 대기 |
