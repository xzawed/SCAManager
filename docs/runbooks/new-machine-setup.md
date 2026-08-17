# 새 PC 셋업 — 리포 밖 자산

리포 안 절차 = [README §Quick start](../../README.md#quick-start). 아래는 clone 밖 자산만.

1. **`.env`** — `cp .env.example .env`, 의미 = [env-vars.md](../reference/env-vars.md).
   값은 비-AI 채널로만(AI 세션·Issue·PR 붙여넣기 금지).
2. **메모리 · 전역 규칙** — `py -3 scripts/check_memory_refs.py` 첫 줄이 이 머신의 메모리
   디렉토리를 인쇄한다(슬러그 = 리포 절대경로 유도 — 하드코딩 금지). 그것과
   `%USERPROFILE%\.claude\CLAUDE.md` 를 구 PC 에서 **private** 경로로 옮긴다(이 리포는 PUBLIC).
   없어도 세션은 뜨고 "패턴 작성 전 메모리 grep" 만 공전한다 — 실패로 안 드러난다.
3. **MCP** — 리포에 `.mcp.json` 없음. 서버는 사용자 스코프(`~/.claude.json`)에 재등록(토큰 §1).
4. **`gh`** — `gh auth status` 에 `workflow` scope 없으면 `.github/workflows/**` PR 거부.

## 검증 — 빠지면 실패 아니라 침묵

- `python -c "print(1)"` 이 exit 49 면 Store 스텁 — 훅·문서·명령은 `py -3` 만.
- `py -3 -m pytest tests/unit` · `py -3 scripts/pre_push_gate.py` 전건 통과
  (`--full` 은 pylint·bandit·단위까지). `make gate` 는 CI 동일 기준이 아니다.
- `py -3 -m pre_commit run --all-files` → 훅이 돈다(미등록 = 무반응 = 무보호).
- `src/static/css/dist/tailwind.css` 없으면 `base.html` 링크 404.
- 시작 배너에 `check_main_red.py` · `check_precommit_installed.py` 출력. advisory 라
  없어도 정상 진행 — 배선 의심.
