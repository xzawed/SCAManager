# 새 PC 셋업 — 리포가 주지 않는 것

> **목적**: `git clone` 만으로는 "같은 환경" 이 되지 않는다. 리포 **밖**에 있어서 GitHub 를 통해
> 전달되지 않는 자산과, 그것이 없을 때 **조용히** 달라지는 동작을 한곳에 모은다.
>
> **리포 안 절차**(clone → `make install` → `make css-build` → pre-commit 등록 → `.env` → `make run`)는
> [`README.md` §Installation](../../README.md#️-installation) 이 단일 출처다. 이 문서는 **중복하지 않는다.**

---

## 1. 리포가 주는 것 / 주지 않는 것

| 자산 | 리포 포함 | 새 PC 에서 필요한 조치 |
|---|---|---|
| 소스·테스트·마이그레이션 | ✅ | 없음 |
| 프로젝트 규칙 `CLAUDE.md` · `AGENTS.md` · `.claude/{rules,policies,skills,agents,hooks,workflows}` | ✅ | 없음 |
| 가드 설정 `.pre-commit-config.yaml` | ✅ | 🔴 **훅 등록은 별도** (README 절차) |
| Tailwind 번들 `src/static/css/dist/tailwind.css` | ❌ (gitignore 빌드 산출물) | `make css-build` |
| `node_modules/` · Playwright 브라우저 | ❌ | `make install` · `make install-playwright` |
| `.env` **값** | ❌ (`.env.example` 은 ✅) | §2 |
| 에이전트 메모리 (`~/.claude/projects/<slug>/memory/`) | ❌ | §3 |
| 전역 규칙 `~/.claude/CLAUDE.md` | ❌ | §3 |
| MCP 서버 설정 (사용자 스코프 `~/.claude.json`) | ❌ (`.mcp.json` 없음) | §4 |
| `gh` CLI 인증 | ❌ | §5 |

---

## 2. `.env` — 키 목록은 리포, 값은 비-AI 채널

- **키 목록의 원천은 `.env.example`** 이며 로컬 `.env` 의 상위집합이다(미설정 키는 기본값/비활성 경로).
  따라서 "무엇을 채워야 하는지" 는 리포만으로 알 수 있다.
- 🔴 **값(시크릿) 전달은 비-AI 채널 의무** — 비밀번호 관리자·직접 입력 등. AI 세션·이슈·PR 본문·채팅에
  붙여넣지 않는다. (전례: 운영 secret 재설정 시 이 규칙 확립)
- 필수 키의 의미는 `README.md` §Environment Variables, 전체 목록은
  [`docs/reference/env-vars.md`](../reference/env-vars.md).

## 3. 에이전트 메모리 · 전역 규칙 — 공개 리포에 올리지 않는다

경로 (Windows 기준):

```
%USERPROFILE%\.claude\projects\d--Source-SCAManager\memory\   # 프로젝트 메모리 + MEMORY.md 인덱스
%USERPROFILE%\.claude\CLAUDE.md                               # 전역 작업 규칙 (모든 프로젝트 공통)
```

🔴 **이 리포는 PUBLIC 이므로 메모리를 리포에 등재하지 않는다.** 메모리 본문에는 운영 사고 경위·보안
발견·내부 판단 서사가 들어 있고, 공개 게시는 **비가역**이다. 이식 경로는 둘 중 하나를 쓴다.

| 방법 | 장점 | 단점 | 위험 |
|---|---|---|---|
| 수동 복사(USB·개인 클라우드 드라이브) | 노출 0 · 즉시 | 세션마다 수동 동기화 | 낮음 |
| **private** 리포/gist 로 동기화 | 자동화 가능 · 양쪽 최신 유지 | 리포 1개 추가 관리 | 낮음 (private 유지가 전제) |

메모리가 없어도 세션은 동작하지만, `CLAUDE.md` 가 의무화한 **"신규 fixture/테스트/패턴 작성 전 메모리
grep"** 이 성립하지 않아 **이미 학습한 함정을 다시 밟는다**(조용한 품질 저하 — 실패로 드러나지 않음).

## 4. MCP 서버

프로젝트에 `.mcp.json` 이 없다 → MCP 서버는 **사용자 스코프 설정**(`~/.claude.json`)에 있으며 클론으로
따라오지 않는다. 새 PC 에서는 필요한 서버를 다시 등록하고(토큰은 §2 원칙 적용), 인증이 필요한 커넥터는
대화형 세션에서 승인한다.

## 5. `gh` CLI 인증

```bash
gh auth login          # 이후 gh auth status 로 scope 확인
```

🔴 **`workflow` scope 가 없으면 `.github/workflows/**` 를 건드리는 PR 머지가 거부된다**(전례 기록).
`repo` 만으로는 부족하다.

---

## 6. 셋업 검증 (기계로 확인 가능한 것만)

새 PC 에서 아래가 모두 통과해야 "같은 환경" 이다. 하나라도 빠지면 **실패가 아니라 침묵**으로 달라진다.

| 확인 | 명령 | 기대 |
|---|---|---|
| 단위 테스트 | `pytest tests/unit` | 전건 통과 (수치 원천 = 실행 결과) |
| 정적 게이트 (CI 동일 기준) | `make gate` | 통과 — 🔴 `make lint` 는 `\|\| true` advisory 라 근거 아님 |
| 가드 훅 등록 | `python -m pre_commit run --all-files` | 훅이 **실행됨** (미등록 시 아무 일도 안 일어남 = 무보호) |
| CSS 번들 | `src/static/css/dist/tailwind.css` 존재 | 없으면 `base.html` 의 링크가 404 |
| GitHub 인증 | `gh auth status` | `workflow` scope 포함 |
| 회고/원장 카운터 | 세션 시작 시 SessionStart 훅 배너 | 카덴스·owed 원장 경고가 **출력됨** |

> 마지막 항목이 중요하다 — 카덴스·owed 카운터는 **advisory(비차단)** 이라, 배선이 빠져도 세션은
> 정상처럼 진행된다. 배너가 안 보이면 훅 배선을 먼저 의심한다.
