# 보안 정책

🇺🇸 [English](SECURITY.md)

SCAManager는 여러분의 소스 코드를 읽고, 연결된 모든 리포지토리에 대해 GitHub OAuth 토큰을 보관하며,
여러분을 대신해 Pull Request를 승인하고 머지할 수 있습니다. 여기의 취약점은 이 도구를 운영하는 사람에게
공급망 문제가 되므로, 책임 있게 신고해 주시길 부탁드립니다.

---

## 취약점 신고 방법

**보안 취약점을 공개 Issue · Pull Request · Discussion 으로 올리지 마세요.**

GitHub의 비공개 경로로 신고해 주세요:

👉 **[취약점 신고하기](https://github.com/xzawed/SCAManager/security/advisories/new)**
(리포지토리 → *Security* 탭 → *Report a vulnerability*)

신고자와 메인테이너에게만 보이는 비공개 advisory 가 열립니다. 공개 이력이 리포지토리에 붙어 남고,
수정과 공개 advisory 를 함께 낼 수 있습니다.

**포함해 주시면 좋은 것:**

- 취약점의 내용과, 판단하신 영향 범위
- 테스트한 커밋 SHA (태그 릴리스가 없습니다 — 아래 참조)
- 재현 절차, 가능하면 최소 PoC
- 관련이 있다면 배포 형태 (Railway / 온프레미스, PostgreSQL 버전, 리버스 프록시)

**하지 말아 주실 것:**

- 본인 소유가 아닌 배포본 대상 테스트
- 타인이 호스팅하는 인스턴스에 자동 스캐너 실행
- 본인 것이 아닌 데이터의 유출 · 변조 · 보관

### 응답 기대치

1인 메인테이너 프로젝트이고 on-call 조직이 있는 벤더가 아닙니다. 아래는 계약상 SLA가 아니라 정직한
목표치입니다:

| 단계 | 목표 |
|------|------|
| 접수 확인 | 5일 이내 |
| 1차 판정 (유효/무효, 대략적 심각도) | 14일 이내 |
| 확인된 고영향 이슈의 수정 또는 완화 방안 문서화 | best effort, 기능 작업보다 우선 |
| 공개 advisory | 수정 반영 후. 원치 않으신다고 하지 않는 한 신고자를 credit 에 명시 |

14일 안에 회신이 없으면 advisory 스레드에 다시 남겨주세요 — 무시된 게 아니라 알림을 놓친 것입니다.

---

## 지원 버전

태그 릴리스가 없습니다. **`main` 이 유일한 지원 버전입니다.** 수정은 `main` 에 반영되며, SCAManager를
운영 중이라면 `main` 기준으로 재배포해 반영하시면 됩니다. 과거 커밋에 대한 신고도 환영하지만 수정은
현재 `main` 기준으로 이뤄집니다.

---

## 신고 범위

**범위 내** — 이 리포지토리에서 공격자가 다음을 할 수 있게 하는 모든 것:

- GitHub webhook 서명 검증 우회 또는 webhook 재전송(replay)
- REST API · 내부 cron · CLI Hook · Telegram 콜백 인증 우회
- 다른 테넌트의 리포지토리 · 분석 결과 · 설정 열람 또는 조작 (cross-tenant 접근)
- 저장된 GitHub OAuth 토큰 · API 키 · webhook 시크릿 복원
- 설정된 점수 게이트를 충족하지 않은 PR을 승인/머지시키기, 또는 **분석되지 않은 커밋을 다른 커밋의
  점수로** 머지시키기
- 분석 대상 코드 · webhook 페이로드 · 커밋 메시지 · 리포지토리 이름을 통한 명령 주입 · 경로 탐색 · SSRF
- 발신 알림에 명령처럼 동작하거나 자격증명을 수집하는 콘텐츠 주입
- 인증 이전(pre-auth) 서비스 거부 (예: 위조 입력으로 인한 무제한 메모리 증가)

**범위 밖:**

- 운영자 본인의 배포 설정 문제 — `.env` 노출, 인터넷에 열린 DB, 리버스 프록시 부재, placeholder 로
  방치된 `SESSION_SECRET` 등. [배포 하드닝](#배포-하드닝) 참조.
- 공격자가 이미 관리자 API 키 · 유효한 OAuth 세션 · 호스트 파일시스템 접근권을 가진 상태를 전제하는 것
- SCAManager가 호출하는 외부 서비스의 취약점 (GitHub · Anthropic · Telegram · Discord · Slack ·
  Railway) — 해당 서비스에 신고해 주세요
- 정적 분석기 자체의 취약점 (pylint · semgrep · eslint 등) — 상위 프로젝트에 신고
- 실증된 영향 없는 보안 헤더 누락 · 모범사례 미준수
- 동작하는 PoC 없이 제출된 자동 스캐너 출력
- 아래 [알려진 트레이드오프](#알려진-트레이드오프)에 명시된 항목

---

## 코드가 어디로 가는가

SCAManager는 셀프 호스팅입니다. 즉 **컨트롤 플레인** — 파이프라인 · DB · 웹 대시보드 · 정적 분석기 —
는 전부 여러분 인프라에서 돕니다. 하지만 그것이 *코드가 그 안에 머문다*는 뜻은 아닙니다. 분석은 본질적으로
콘텐츠를 밖으로 보내며, 그 대상은 **여러분이 설정한** 서비스입니다.

전체 목록입니다.

### 항상 활성

| 목적지 | 전송 내용 | 이유 |
|--------|----------|------|
| **GitHub API** (`api.github.com` + 로그인용 `github.com/login/oauth/*`) | 변경 파일·diff 조회 요청, 발신 PR 리뷰·PR 댓글·커밋 댓글·Issue·머지 | 코드가 원래 있는 곳 — 이벤트 소스이자 액션 대상 |
| **여러분의 `DATABASE_URL`** | 점수 · AI 리뷰 요약 · 분석기 이슈 메시지 — 전부 여러분 소스에서 파생된 내용 — 이 여기 영속화됩니다 | 서비스 동작에 필수. 🔴 **DB가 여러분 것일 때만 "셀프 호스팅"입니다** — `DATABASE_URL` 이 Supabase 등 매니지드 공급자를 가리키면 이 내용이 그쪽으로 갑니다. |

### 설정 시 활성

| 목적지 | 전송 내용 | 비활성화 방법 |
|--------|----------|--------------|
| **Anthropic API** (`api.anthropic.com`) | AI 리뷰를 위한 **변경 파일의 diff** + 커밋 메시지 | `ANTHROPIC_API_KEY` 미설정 — AI 항목이 중립 기본값이 되고 점수 상한이 89점(B등급)으로 내려갑니다. 리포 단위로는 설정에서 `ai_review_enabled` 를 끄세요. |
| **Telegram Bot API** (`api.telegram.org`) | 점수 · 등급 · AI 요약 · 개선 제안 · 정적 분석 이슈 메시지 | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 미설정 |
| **Discord / Slack / 일반 Webhook / n8n** | 점수 · 등급 · AI 요약 · 이슈 메시지 | 리포별 opt-in — 설정에서 URL 을 비우면 됩니다 |
| **여러분의 SMTP 서버** | 위와 동일 내용의 HTML 메일 | `SMTP_*` 미설정 |
| **OpenAI 또는 OpenAI-호환 엔드포인트** | 선택 기능인 2차 LLM 머지 검증자용 diff + AI 리뷰 요약 | `OPENAI_API_KEY` 미설정 — 검증자는 기본 비활성입니다. `VERIFIER_BASE_URL` 로 다른 공급자로 전환 가능. |
| **Railway API** | 배포 상태 조회만 — 소스 코드 전송 없음 | 리포별 Railway API 토큰을 비워두면 됩니다 |
| **semgrep.dev** | Semgrep 이 `p/default` 룰셋을 레지스트리에서 내려받고, 레지스트리 룰 사용 시 CLI 가 익명 사용 메트릭(룰 ID·발견 건수 — **소스 코드 아님**)도 보고합니다. 코드 스캔 자체는 로컬에서 수행됩니다. | `semgrep` 바이너리를 제거하세요 — `PATH` 에 없으면 분석기가 스스로 skip 합니다. 또는 서비스 환경에 `SEMGREP_SEND_METRICS=off` 를 설정해 메트릭 전송만 차단할 수 있습니다. |

### 호스트에 머무는 분석기

나머지 등록 분석기 24종 — pylint · flake8 · bandit · ESLint · ShellCheck · cppcheck · slither ·
RuboCop · golangci-lint 등 — 은 임시 파일을 대상으로 로컬 subprocess 로 실행됩니다.
**semgrep 만 예외**이며 위 표에 명시했습니다.

24종 중 어느 것도 네트워크 플래그를 붙여 호출하지 않습니다. 다만 2종은 분석 대상 파일 주변에 일회용
프로젝트를 만듭니다(`golangci-lint` 는 최소 `go.mod` 를 쓰고, `clippy` 는 임시 Cargo 프로젝트를 만듭니다).
분석 대상 코드가 로컬 모듈/크레이트 캐시에 없는 패키지를 import 하면 그 툴체인이 패키지 레지스트리에
접근할 수 있습니다. 소스 코드는 전송되지 않으며, Go/Rust 빌드가 통상 수행하는 의존성 해석일 뿐입니다.

### 외부 전송 줄이기

`ANTHROPIC_API_KEY` · `OPENAI_API_KEY` · `TELEGRAM_BOT_TOKEN` 과 모든 채널 URL을 비워두고 `semgrep` 을
설치하지 않으면 됩니다. AI 벤더 · 알림 벤더 · semgrep 레지스트리가 전부 제거되고, 정적 분석 · 점수 산출 ·
대시보드는 그대로 남습니다.

다만 2가지가 남으므로 이 구성을 "외부 전송 0"이라고 부르는 건 정확하지 않습니다:

- **GitHub** — 이벤트 소스이자 액션 대상이라 불가피합니다.
- **여러분의 DB** — `DATABASE_URL` 이 호스트 밖(Supabase, 매니지드 PostgreSQL)을 가리킨다면. 점수 ·
  AI 요약 · 분석기 이슈 메시지가 영속화되고, 그 메시지들은 여러분 소스에서 파생된 것입니다. 직접
  통제하는 DB 를 가리키면 닫힙니다.
- 그리고 Go/Rust 를 분석한다면 위에 적은 레지스트리 접근 건.

이 구성의 점수 상한은 89점(B등급)입니다. AI 배점 3개 항목은 합계 55점인데, API 키가 없으면 중립
기본값 44점이 부여되므로 **11점**에 도달할 수 없습니다. 나머지 45점은 정적 분석 몫이라 영향이 없습니다.

---

## SCAManager가 하는 보호 조치

목록을 믿기보다 코드와 대조하실 수 있도록 그대로 적습니다.

| 영역 | 조치 |
|------|------|
| Webhook 진위 | GitHub webhook 은 유효한 `X-Hub-Signature-256` 을 요구하며, 서명 부재·형식 오류·불일치 시 `401`. 설정된 시크릿이 비어 있어도 `401` 입니다. Telegram gate 콜백은 이벤트별 HMAC 인증. |
| REST API | **fail-closed.** `API_KEY` 미설정 시 익명 접근을 허용하지 않고 모든 요청이 `503`. 우회하려면 로컬 개발용 명시 opt-out 인 `API_AUTH_DISABLED=1` 이 필요합니다. 키 비교는 타이밍 안전 비교. |
| 내부 cron 엔드포인트 | 관리자 키와 분리된 `INTERNAL_CRON_API_KEY`. 미설정 시 `503`. |
| 토큰 저장 | `TOKEN_ENCRYPTION_KEY` 설정 시 GitHub OAuth 토큰을 Fernet 으로 암호화 저장. `STRICT_TOKEN_ENCRYPTION=1` 이면 운영에서 키 없이 기동을 거부합니다. |
| 머지 안전성 | auto-merge 는 **점수를 산출한 바로 그 커밋**에 결속됩니다. 머지 요청에 그 SHA 를 함께 보내 브랜치 head 가 움직였으면 GitHub 이 거부합니다. 머지 시도 시점에 이미 head 가 드리프트했다면 머지도 재시도 큐 등록도 하지 않고 시도를 버립니다. 이미 큐에 있던 재시도는 드리프트를 감지하면 폐기됩니다. 어느 경로든 새 커밋이 **구 커밋의 점수로 머지되는 일은 없고**, 새 커밋은 자신의 `synchronize` webhook 으로 다시 게이트를 돕니다. |
| 분석 대상 콘텐츠를 통한 주입 | pre-push 훅은 커밋 메시지와 diff 를 셸/heredoc 텍스트에 보간하지 않고 환경변수와 argv 로 전달합니다 — 과거 버전은 커밋 메시지의 셸 메타문자에 취약했습니다. |
| 발신 알림 주입 | 신뢰할 수 없는 분석기 메시지는 Markdown / Slack mrkdwn 에 넣기 전 채널별로 escape 합니다. 조작된 파일명이나 발견 문자열이 링크나 `@channel` 멘션을 주입할 수 없습니다. |
| SSRF | 사용자 지정 webhook URL 로의 발신은 목적지를 해석·검증하는 클라이언트를 경유합니다. 신뢰 API 는 별도 풀링 클라이언트를 씁니다. |
| Rate limiting | 리포지토리 · 통계 · 리포트 · 이슈 등록 · CLI Hook 경로에 경로별 제한이 걸려 있습니다. 모든 HTTP 경로가 그런 것은 아닙니다 — admin · 사용자 · 내부 cron 경로는 인증에 의존하고, webhook 수신기는 제한된 공급자 IP 대역에서 오기 때문에 의도적으로 제한을 걸지 않습니다. |
| 인증 이전 자원 증가 | 리포별 webhook 시크릿 캐시에 상한이 있습니다 — 이 캐시는 공격자가 위조 가능한 리포 이름으로 키가 정해지고 **서명 검증 이전에** 조회되기 때문입니다. |
| 운영 하드닝 | `ENVIRONMENT=production` 이면 `APP_BASE_URL` 오설정과 무관하게 HSTS · `Secure` 쿠키 · `/docs` 비노출이 강제됩니다. |
| 헬스 엔드포인트 | `GET /health` 는 `{"status":"ok"}` 만 반환합니다 — 버전 · 의존성 · DB 상태 미노출. |
| 공급망 | CI 에서 CodeQL · TruffleHog · `bandit -r src/` 실행, Dependabot 의존성 추적. Semgrep 은 여기서 **CI job 이 아닙니다** — SCAManager 가 리뷰하는 리포지토리에 적용되는 런타임 분석기입니다. |

---

## 알려진 트레이드오프

아래는 의도된 결정이므로 별도 신고가 필요하지 않습니다. 다만 여기 서술된 범위를 **넘어서 확대**할 수
있는 방법을 찾으셨다면 그건 꼭 신고해 주세요.

- **AI 요약은 Markdown escape 하지 않습니다** (GitHub · Discord · Slack 채널). AI 요약은 Claude 가
  diff 로부터 작성한 것이고, escape 하면 리뷰를 읽기 좋게 만드는 의도된 서식이 깨집니다. 그 결과
  2차 경로가 남습니다 — diff 안의 prompt injection 이 모델을 설득해 링크로 렌더링되는 Markdown 을
  내보내게 할 수 있습니다. Telegram 과 이메일은 전부 escape 하므로 채널 간 비대칭이 있습니다.
- **`flake8` 은 머지 게이트에 없습니다.** pylint 와 bandit 은 있습니다. 실질 결함을 잡는 flake8 부분집합은
  별도 CI job 에서 강제합니다.
- **E2E 테스트는 CI에 배선돼 있지 않습니다.** 로컬 전용입니다.
- **approve 동작은 원자적으로 만들 수 없습니다.** GitHub 리뷰 API 에는 머지 API 의 `sha` 파라미터에
  해당하는 수단이 없어서, 원리적으로 직전에 움직인 head 에 대해 리뷰가 기록될 수 있습니다. SCAManager는
  POST 직전에 head 를 조회해 불일치 시 리뷰를 건너뛰지만 잔여 레이스는 남으며, 새 head 의
  `synchronize` webhook 이 다시 게이트를 돕니다.

---

## 배포 하드닝

SCAManager를 운영하신다면 아래는 코드가 아니라 운영자의 몫입니다:

- `SESSION_SECRET` 을 32바이트 이상 랜덤으로 설정 (`openssl rand -hex 32`). 내장 기본값은 placeholder 이며
  절대 운영에 올라가면 안 됩니다.
- `TOKEN_ENCRYPTION_KEY` 를 설정하고, OAuth 토큰이 조용히 평문 저장되는 대신 기동을 거부하도록
  `STRICT_TOKEN_ENCRYPTION=1` 도 고려하세요.
- `APP_BASE_URL` 을 HTTPS URL 로, `ENVIRONMENT=production` 을 설정하세요. 없으면 OAuth redirect 와
  webhook URL 이 `http://` 로 떨어집니다.
- REST API 를 쓴다면 `API_KEY` 를 설정하고, 로컬 개발 외에는 `API_AUTH_DISABLED=1` 을 **절대** 쓰지 마세요.
- `GITHUB_WEBHOOK_SECRET` 과 `TELEGRAM_WEBHOOK_SECRET` 을 설정하세요.
- DB 를 공개 인터넷에서 차단하고, 매니지드 PostgreSQL 은 `DB_SSLMODE=require` 를 쓰세요.
- TLS 는 리버스 프록시에서 종단하고 uvicorn 은 `--proxy-headers` 로 실행하세요.
- `auto_merge` 를 켜기 전에 임계값을 검토하세요. auto-merge 는 **숫자 하나에 기본 브랜치 반영 권한을
  주는 것**입니다.

전체 변수 레퍼런스: [`docs/reference/env-vars.md`](docs/reference/env-vars.md).

---

## Credit

신고자는 원치 않으신다고 밝히지 않는 한 공개 advisory 에 credit 으로 명시됩니다. 버그 바운티는
없습니다 — 자금 지원 없는 개인 프로젝트이며, 존재하지 않는 보상을 암시하기보다 먼저 정직하게 밝히는
편이 낫다고 생각합니다.
