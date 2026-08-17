# 새 PC 셋업 — 리포 밖 자산

리포 안 절차(clone → `make install` → `make css-build` → pre-commit 등록 → `.env` → `make run`)는
[README §Quick start](../../README.md#quick-start) 가 정본이다. 여기는 **clone 으로 따라오지 않는 것**만 적는다.

## 1. `.env` 값

1) `cp .env.example .env` — 채울 키의 원천은 `.env.example`, 의미는 [env-vars.md](../reference/env-vars.md).
2) 값은 비-AI 채널(비밀번호 관리자·직접 입력)로만 옮긴다. AI 세션·Issue·PR 본문에 붙여넣지 않는다.

## 2. 에이전트 메모리 · 전역 규칙

1) `py -3 scripts/check_memory_refs.py` 를 돌린다 — 첫 줄이 이 머신의 메모리 디렉토리를 인쇄한다.
   슬러그는 리포 절대경로에서 유도돼 PC 마다 다르므로 문서·스크립트에 하드코딩하지 않는다.
2) 구 PC 의 그 디렉토리와 `%USERPROFILE%\.claude\CLAUDE.md` 를 옮긴다. 수단은 USB·개인 클라우드
   또는 **private** 리포. 이 리포는 PUBLIC 이라 메모리를 등재하지 않는다.
3) 없어도 세션은 뜬다 — 대신 "패턴 작성 전 메모리 grep" 이 공전한다(실패로 안 드러남).

## 3. MCP 서버

리포에 `.mcp.json` 이 없다. 필요한 서버를 사용자 스코프(`~/.claude.json`)에 다시 등록하고,
토큰은 §1 원칙을 적용한다. 인증이 필요한 커넥터는 대화형 세션에서 승인한다.

## 4. `gh` CLI

`gh auth login` 후 `gh auth status` 로 scope 를 본다. `repo` 만이면 `.github/workflows/**` 를
건드리는 PR 이 거부되므로 `workflow` 를 포함시킨다.

## 5. 검증 — 하나라도 빠지면 실패가 아니라 침묵이다

| 확인 | 명령 | 기대 |
|---|---|---|
| 인터프리터 | `py -3 -c "print(1)"` · `python -c "print(1)"` | 둘 다 `1`. `python` 이 exit 49 면 Store 스텁이다 — 훅·문서·명령은 `py -3` 로만 쓴다 |
| 단위 테스트 | `py -3 -m pytest tests/unit` | 전건 통과 |
| push 게이트 | `py -3 scripts/pre_push_gate.py` | 통과. `--full` 은 pylint·bandit·단위까지. `make gate` 는 대체가 아니다 |
| pre-commit | `py -3 -m pre_commit run --all-files` | 훅이 실제로 실행됨(미등록이면 무반응 = 무보호) |
| CSS 번들 | `src/static/css/dist/tailwind.css` 존재 | 없으면 `base.html` 의 링크가 404 |
| GitHub | `gh auth status` | `workflow` scope 포함 |
| SessionStart | 세션 시작 배너 | `check_main_red.py` · `check_precommit_installed.py` 출력이 보임. advisory 라 안 보여도 세션은 정상처럼 진행된다 — 배선을 먼저 의심한다 |
