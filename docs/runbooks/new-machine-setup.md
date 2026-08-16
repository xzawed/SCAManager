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

🔴 **슬러그는 머신마다 다르다 — 하드코딩하지 말고 유도하라.** Claude Code 는 리포의 **절대경로**를
디렉토리명으로 변환해 쓴다(드라이브 콜론과 경로 구분자를 각각 `-` 로: `f:\DEV\SCAManager` →
`f--DEV-SCAManager`). 따라서 PC 를 옮기면 경로가 바뀌고, **메모리는 리포 밖이라 따라오지 않는다.**

```bash
# 이 리포의 메모리 경로를 실제로 산출한다 (문서에 박힌 예시를 복사하지 말 것)
py -3 scripts/check_memory_refs.py     # 첫 줄에 해소된 메모리 디렉토리를 출력한다
```

```
%USERPROFILE%\.claude\projects\<이 리포 경로에서 유도된 슬러그>\memory\   # 프로젝트 메모리 + MEMORY.md
%USERPROFILE%\.claude\CLAUDE.md                                        # 전역 작업 규칙 (모든 프로젝트 공통)
```

> 🔴 **이 문단 자체가 사고 이력이다.** 이전 판은 구 PC 슬러그(`d--Source-SCAManager`)를 **정본으로
> 인쇄**하고 있었다 — PC 이전을 돕는 런북이 이전으로 깨진 경로를 3회차 왕복시킨 셈이다. 같은 값을
> 하드코딩하던 `check_memory_refs.py` 는 그 때문에 이 머신에서 **한 번도 검사하지 않았다**(회고
> 2026-07-31 P0-6). 이식 문서에 머신 고유값을 적으면 그 문서가 이식을 깨뜨린다.

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
| push 전 게이트 | `py -3 scripts/pre_push_gate.py` | 통과 — CI 강제 가드 **13종**(repo-integrity 9 + PR-diff 4). 🔴 **`make gate` 는 대체가 아니다**: pytest·pylint·bandit 3종뿐이라 그 13 가드를 하나도 안 돌리고, 애초에 이 머신에는 `make` 이 없다(backlog R29) |
| 정적 린트 (CI `lint-src` 동일 기준) | `py -3 -m pylint --fail-under=9.90 src/` + `py -3 -m bandit -r src/ -q` | 통과 — 🔴 `make lint` 는 `\|\| true` advisory 라 근거 아님 |
| 🔴 **인터프리터 생존** | `py -3 -c "print(1)"` 과 `python -c "print(1)"` **양쪽** | 둘 다 `1` 출력. `python` 이 **exit 49** 면 Windows Store 스텁이다 — 아래 참조 |
| 가드 훅 등록 | `py -3 -m pre_commit run --all-files` | 훅이 **실행됨** (미등록 시 아무 일도 안 일어남 = 무보호) |
| 로컬 pre-commit 계층 | 세션 시작 시 SessionStart 훅 배너 | "pre-commit 계층 활성" 이 **출력됨** (내려가 있으면 loud 경고) |
| CSS 번들 | `src/static/css/dist/tailwind.css` 존재 | 없으면 `base.html` 의 링크가 404 |
| GitHub 인증 | `gh auth status` | `workflow` scope 포함 |
| SessionStart 훅 | 세션 시작 시 배너 | `check_main_red.py` · `check_precommit_installed.py` 출력이 **보임** |

> SessionStart 카운터는 **advisory(비차단)** 이라, 배선이 빠져도 세션은 정상처럼 진행된다.
> 배너가 안 보이면 훅 배선을 먼저 의심한다.

### 🔴 Windows `python` = Microsoft Store 스텁 (실측 사고 — 훅 6종 무동작)

Windows 는 `python` 을 **아무것도 실행하지 않고 exit 49 를 내는 Store 스텁**으로 선점할 수 있다.
그 상태에서 `.claude/settings.json` 이 `python <스크립트>` 로 훅을 부르면 **6종 전부가 조용히 죽는다** —
`block_credential_dump`(크리덴셜 덤프 차단)와 `check_edit_allowed`(수정 금지 파일 보호)를 포함해서다.
2026-07-30 실측에서 이 상태가 **얼마나 오래 지속됐는지 알 수 없었다** — 실패가 무음이라 흔적이 없다.

**계약**: 이 리포의 훅·문서·명령은 모두 **`py -3` 를 기본**으로 쓰고, 셸 폴백이 필요한 자리에는
`PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); $PY <스크립트>` 형태를 쓴다.
🔴 **bare `python` 을 새로 도입하지 말 것** — 형태상 정당해 보여 배선 가드가 구별하지 못한다.
그 축은 `tests/unit/scripts/test_hook_interpreter_liveness.py` 가 **실제 실행**으로 관측한다.
