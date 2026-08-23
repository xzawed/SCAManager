<div align="center">

# 🛡️ SCAManager

**GitHub push·PR 마다 정적 분석 + Claude AI 리뷰 — 점수화·알림·게이트.**

[![CI](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/ci.yml)
[![CodeQL](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml/badge.svg)](https://github.com/xzawed/SCAManager/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/Tests-7330%2B_total_(7140_unit_%2B_190_integration)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![E2E](https://img.shields.io/badge/E2E-121_in_CI-brightgreen?style=flat-square&logo=playwright&logoColor=white)](e2e/)
[![pylint](https://img.shields.io/badge/pylint-9.99%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[🇺🇸 English](README.md)

</div>

## 어떤 도구인가요?

SCAManager 는 GitHub 저장소를 지켜봅니다. 누군가 커밋을 push 하거나 Pull Request 를 열 때마다
변경된 파일에 정적 분석기를 돌리고, Claude 에게 diff 리뷰를 맡기고, 그 둘을 합쳐 100점 만점의
점수 하나로 만든 뒤 알려 줍니다.

원하신다면 그 점수에 따라 직접 행동하게 할 수도 있습니다 — PR 을 승인하거나, 변경을 요청하거나,
squash 머지까지 합니다.

**직접 운영하는 도구입니다.** 가입할 서비스도, 만들 계정도 없습니다. 노트북이든 서버든 본인의
Railway 프로젝트든 원하는 곳에서 돌아가고, GitHub 과 Anthropic 에는 **본인의 자격증명**으로
접속합니다.

**이런 분께 맞습니다** — GitHub 에서 PR 을 리뷰하시고, 모든 PR 에 일관된 second opinion 을 받고
싶지만, 그걸 위해 코드를 남의 호스팅 서비스에 넘기고 싶지는 않은 경우입니다.

<div align="center">

<!-- 재생성 / regenerate: py -3 scripts/capture_readme_hero.py -->
![SCAManager 대시보드](docs/readme/dashboard.ko.png)

<sub>7일치 이력을 미리 넣어 둔 로컬 인스턴스입니다 — 처음 띄웠을 때 보이는 화면은 아닙니다.
AI 비용이 $0.00 인 것은 시드 데이터가 실제 API 를 호출하지 않았기 때문입니다.</sub>

</div>

## 내 PR 에 무슨 일이 일어나나요?

설치 전에 읽어 두실 만한 부분입니다. 저장소를 추가하는 순간 시작되는 것이 있고, 직접 켜기
전까지는 꺼져 있는 것이 있습니다.

| | 동작 | 기본값 |
|---|---|---|
| **분석·채점** | 모든 push 와 PR 을 분석해 점수를 매깁니다. 결과는 저장되고 웹 UI 에 표시됩니다. | **켜짐** |
| **AI 리뷰** | Claude 가 diff 를 리뷰합니다. 끄면 100점 중 55점을 잃습니다 — [점수 산정](#점수는-어떻게-매겨지나요) 참고. | **켜짐** |
| **PR 리뷰 코멘트** | 리뷰 내용을 PR 코멘트로 게시합니다. | **켜짐** |
| **알림** | Telegram · Discord · Slack · Email · webhook · n8n · GitHub 커밋 코멘트 · GitHub 이슈. | 꺼짐 — 단, Telegram 은 봇 토큰과 chat ID 가 있으면 바로 발송됩니다 |
| **승인 / 변경 요청** | 점수에 따라 GitHub 에서 대신 행동합니다. | **꺼짐** |
| **Squash 머지** | 점수가 기준을 넘으면 PR 을 머지합니다. | **꺼짐** |

표의 모든 항목은 저장소마다 따로, 해당 저장소의 **⚙️ 설정** 페이지에서 정합니다. 승인과 머지를
켜기 전까지 GitHub 에 쓰는 것은 리뷰 코멘트뿐입니다.

## GitHub 을 건드리지 않고 먼저 써 보기

무엇을 연결하기 전에, 같은 분석을 작업 트리에 대해 커맨드라인에서 돌려 보실 수 있습니다.
로컬 파일만 읽고, 아무것도 쓰지 않으며, GitHub 을 호출하지 않습니다.

```bash
python -m src.cli review --base main   # 특정 브랜치와 비교
python -m src.cli review --staged      # 또는 staged 변경만
python -m src.cli review --no-ai       # Claude 호출 생략 — API 키 없이 동작합니다
```

## 서버 실행하기

### 먼저 준비할 것

| | |
|---|---|
| **Python 3.12** | CI 가 쓰는 버전입니다. 상위 버전도 대개 동작하지만, 검증된 것은 3.12 입니다. |
| **Node.js 20** | CSS 번들을 한 번 빌드할 때만 필요합니다. |
| **PostgreSQL** | 접속 가능한 DB 가 필요합니다. SQLite 는 테스트 스위트용이고, 앱 구동용이 아닙니다. |
| **GitHub OAuth 앱** | 웹 UI 로그인에 필요합니다. 위의 CLI 만 쓰신다면 없어도 됩니다. |
| **Anthropic API 키** | 선택이지만, 없으면 AI 리뷰가 돌지 않아 모든 점수가 89점에서 막힙니다. |

### 설치와 실행

```bash
git clone https://github.com/xzawed/SCAManager.git && cd SCAManager
make install         # pip install -r requirements-dev.txt + npm install
make css-build       # Tailwind 번들 빌드 (gitignore 대상이라 한 번 만들어 둡니다)
cp .env.example .env
make run             # uvicorn :8000, 부팅 시 DB 마이그레이션 실행
```

Windows 처럼 `make` 이 없는 환경이라면, 각 타깃은 한두 줄짜리 명령입니다.
[Makefile](Makefile) 을 열어 그대로 실행하시면 되고, 시작에 필요한 것은 `install` 과 `run`
둘뿐입니다.

### `.env` 채우기

`.env.example` 에는 대부분의 설정에 동작하는 placeholder 가 들어 있어서, `DATABASE_URL` 만 실제
DB 로 바꾸면 앱이 뜹니다. 실제로 쓰시기 전에 다음 세 가지는 확인해 주세요.

- **`SESSION_SECRET`** — `openssl rand -hex 32` 로 하나 만드세요. 그대로 두면 공개된 개발용
  기본값으로 동작하며 경고 로그만 남깁니다. 다만 프로덕션(`https://` 로 시작하는
  `APP_BASE_URL`, 또는 `ENVIRONMENT=production`)에서는 **부팅 자체를 거부합니다.** 그 기본값이
  알려져 있어 세션 위조가 가능하기 때문입니다.
- **`ANTHROPIC_API_KEY`** — 없으면 AI 리뷰가 돌지 않고 모든 점수가 89점에서 막힙니다.
- **`GITHUB_CLIENT_ID` · `GITHUB_CLIENT_SECRET`** — GitHub OAuth 앱에서 발급받습니다.
  웹 UI 로그인에 필요합니다.

### 첫 저장소 등록하기

<http://localhost:8000> 을 열고 GitHub 으로 로그인한 뒤 **+ 리포 추가** 를 선택하세요. 해당
저장소에 웹훅이 설치되고, 그다음 push 부터 분석이 시작됩니다. 이후에는 저장소의 **⚙️ 설정**
페이지에서 어떤 알림 채널을 쓸지, 게이트가 GitHub 에서 대신 행동해도 되는지를 정하시면 됩니다.

## 점수는 어떻게 매겨지나요?

커밋은 100점에서 출발해 다섯 항목으로 평가됩니다.

| 항목 | 배점 | 출처 |
|---|---|---|
| 코드 품질 | 25 | 정적 분석기 — error 하나당 3점, warning 하나당 1점 감점 |
| 보안 | 20 | 정적 분석기 — HIGH 하나당 7점, LOW·MEDIUM 하나당 2점 감점 |
| 커밋 메시지 | 15 | Claude |
| 구현 방향성 | 25 | Claude — 변경이 표방한 일을 실제로 하는지, 그 방식이 타당한지 |
| 테스트 코드 | 15 | Claude |

등급은 **A** 90점 이상 · **B** 75 · **C** 60 · **D** 45 이고, 그 아래는 **F** 입니다.

AI 가 맡은 절반에 대해 두 가지를 알아 두시면 좋습니다.

- **AI 리뷰가 쓸 만한 결과를 내지 못하면** 뒤의 세 항목이 고정된 중립값으로 대체됩니다. 그래서
  정적 분석이 만점이어도 총점은 89점 — A 가 아니라 B 에서 멈춥니다. 의도된 설계입니다.
  AI 리뷰를 거치지 않은 점수가 거친 점수처럼 보여서는 안 되기 때문입니다.
- **AI 호출이 실제로 실패했다면**(API 오류이거나 응답을 파싱할 수 없는 경우) 점수를 아예 저장하지
  않고, 그 실행은 모든 평균에서 제외합니다.

정적 분석 쪽도 같은 원칙입니다. 배포본에는 분석기 16종이 **계약으로 고정되어** 설치되는데, 실행
시점에 그중 하나라도 없으면 그 분석을 **incomplete** 로 표시하고 게이트가 자동 승인·자동 머지를
거부합니다. 아무것도 분석하지 못한 실행이 좋은 점수를 받아서는 안 되니까요.

<details>
<summary><b>언어 지원 범위</b> — AI 리뷰 49개, 정적 분석 27개</summary>

<br>

Claude 는 **49개 언어**를 각각의 체크리스트로 리뷰합니다. 그중 **27개**는 정적 분석기까지
붙어 있습니다. 등록된 분석기는 모두 **25종**이고, 그중 **16종**이 위에서 말한 계약분으로 모든
배포본에 설치됩니다. 나머지는 해당 바이너리가 `PATH` 에 있을 때만 동작합니다.

로컬에서 `make run` 하시면 25종이 모두 있지는 않을 텐데, 그래도 괜찮습니다. **선택** 분석기가
없으면 조용히 건너뛰고, **계약** 분석기가 없을 때만 실행을 incomplete 로 표시합니다.

정적 분석이 지원하는 언어:

`c · clojure · cpp · csharp · css · dart · dockerfile · elixir · go · html · java · javascript ·
kotlin · php · powershell · protobuf · python · ruby · rust · scala · shell · solidity · sql ·
swift · terraform · typescript · yaml`

</details>

## 게이트

게이트는 GitHub 에서 대신 행동하는 부분입니다. 저장소를 추가한 시점에는 꺼져 있고, 설정
페이지에서 직접 켜기 전까지 그대로 꺼져 있습니다.

켜면 기본값은 75점 이상 승인 · 50점 미만 변경 요청 · 75점 이상 squash 머지입니다. 승인에는 두
가지 방식이 있습니다. `auto` 는 GitHub 에 즉시 반영하고, `semi-auto` 는 Telegram 으로 버튼이
달린 메시지를 보내 답을 기다립니다.

CI 가 아직 돌고 있어 GitHub 이 거절한 머지는 버리지 않고 큐에 넣어 다시 시도합니다.

알림 채널은 서로 독립적이라, 웹훅 하나가 실패하기 시작해도 나머지 채널은 정상적으로 전달됩니다.

## 배포

**Railway** — 저장소를 연결하고 PostgreSQL 데이터베이스를 추가한 뒤, 위의 변수들과 함께
`ANTHROPIC_API_KEY` · `APP_BASE_URL` 을 설정합니다. 이 URL 은 반드시 `https://` 여야 합니다.
`http://` 로 두면 OAuth 리다이렉트와 GitHub 웹훅 전달이 둘 다 실패합니다. 자세한 절차는
[런북](docs/runbooks/railway.md)에 있습니다.

**그 밖의 환경** — 평범한 ASGI 애플리케이션입니다.

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

## 어떤 데이터가 밖으로 나가나요?

직접 운영한다는 것이 곧 네트워크 밖으로 아무것도 나가지 않는다는 뜻은 아닙니다. diff 와 점수는
다음으로 전달됩니다.

- **GitHub** — 리뷰 코멘트, 그리고 켜 두신 경우 승인·머지
- **본인의 데이터베이스** — 점수, diff 에서 뽑아낸 지적사항, AI 리뷰 본문
- **Anthropic** — 리뷰를 받기 위한 diff 자체
- **켜 두신 알림 채널** — 점수 요약
- **OpenAI** — 선택 기능인 2차 검증기를 켜신 경우에만

전체 표와 각각을 끄는 방법은 [SECURITY.md](SECURITY.md#data-egress) 에 있습니다.

## 문서

[아키텍처](docs/architecture.md) · [환경변수](docs/reference/env-vars.md) ·
[런북](docs/runbooks/) · [기여 안내](CONTRIBUTING.md) · [현재 수치](docs/STATE.md)

취약점을 발견하셨다면 공개 이슈 대신
[비공개 advisory](https://github.com/xzawed/SCAManager/security/advisories/new) 로 알려 주세요.

[MIT](LICENSE) © xzawed
