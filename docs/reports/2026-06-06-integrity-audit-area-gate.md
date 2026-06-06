# 정합성 감사 리포트 — area=gate (2026-06-06)

> `.claude/workflows/integrity-audit.mjs` (Task 4·5 loop-until-dry + completeness critic) **검증 실행** 산출물.
> scope=`area=gate` (gate + pipeline 2 도메인). read-only — fix 는 사용자 PR 결정.

| 항목 | 값 |
|------|-----|
| scope | area=gate (gate, pipeline) |
| 라운드 | 3 (MAX_ROUNDS 도달 — budget 미설정) |
| confirmed | 14 (P0 0 / P1 4 / P2 10) |
| false-positive 차단 | 8 (3-렌즈 다수결 reject) |
| unverified (검증 실패) | 0 |
| 비용(실측) | 75 에이전트 / ~5.7M 토큰 / ~34분 |

> ⚠️ **비용 주의**: plan 은 area=gate 를 "소(small)" 로 추정했으나 loop-until-dry × 3 라운드로 실측 5.7M 토큰.
> `full`(8 도메인)은 약 4× 추정 → **사용자 사전 승인 필수**(Task 9).

## 도메인별 confirmed 결함

| severity | file:line | 도메인 | 요지 |
|----------|-----------|--------|------|
| P1 | src/worker/pipeline.py:173 | pipeline | 정적분석 타임아웃 시 점수 최대 45점 인플레이션 → 무분석 코드 auto-merge 가능 (관측 마커 부재) |
| P1 | src/worker/pipeline.py:411 | pipeline | 동시 insert race 가 DB 제약 통과 후 중복 알림 + 중복 PR 코멘트 유발 |
| P1 | src/webhook/providers/telegram.py:140 | gate | 반자동(Telegram) 승인+머지 경로가 retry 큐 미사용 → CI-pending 영구 드롭 |
| P1 | src/services/merge_retry_service.py:205 | gate | age-만료(24h) 행이 mark_expired 대신 mark_terminal(CI태그) 기록 — 'expired' 상태 미발생 |
| P2 | src/worker/pipeline.py:31 | pipeline | 도구 타임아웃(30s×3) 합 > 배치(60s) → 느린 단일 파일 정적분석 전량 폐기 + 만점 부여 |
| P2 | src/worker/pipeline.py:151 | pipeline | 단일 파일 예외가 전체 배치+파이프라인 중단 (gather return_exceptions·파일 격리 부재) |
| P2 | src/worker/pipeline.py:164 | pipeline | 정적분석 타임아웃 시 to_thread 워커 고아화 — ThreadPoolExecutor 슬롯 고갈 가능 |
| P2 | src/worker/pipeline.py:251 | pipeline | 브랜치 삭제 push(zero-SHA)가 필터 없이 진입 → 매번 GitHub 404 + 예외 로그 |
| P2 | src/worker/pipeline.py:263 | pipeline | 최초 repo 등록 race 가 uncaught IntegrityError → 한 워커 abort |
| P2 | src/worker/pipeline.py:288 | pipeline | 동일 head SHA 가 두 PR head 일 때 _regate_pr_if_needed 가 pr_number 무조건 덮어씀 |
| P2 | src/api/hook.py:167 | pipeline | CLI hook 점수 필드 타입 비정상 입력이 parse_error fallback 우회 → 500 |
| P2 | src/webhook/providers/telegram.py:139 | gate | 반자동 머지 경로 CI-aware retry/terminal 분류 없이 결과 단순 폐기 (관측 공백) |
| P2 | src/config.py:81 | gate | retry 백오프 config 검증자 부재 — max<initial / 0·음수 시 백오프 단조성 깨짐 |

> P1 4건 중 pipeline.py:173/411 = 운영 영향 가능(점수 인플레이션 auto-merge / 중복 알림), gate 2건 = 반자동 경로 terminality 비대칭.
> 각 결함은 correctness/security/repro 3 렌즈 중 **2/3 이상 real=true** 판정만 등재(8건은 다수결에서 reject).

## 🔍 사용자 검증 필요 (정책 2)

- **본 리포트는 워크플로우 검증 실행의 부산물** — 14건은 gate+pipeline 도메인 실 결함이나, fix 는 **정책 7(PR 단위)/15(사전 사고)/18(Codex mutual)** 에 따라 사용자 결정. 자동 수정 없음.
- P1 우선 검토 권장 (특히 pipeline.py:173 점수 인플레이션 — auto-merge 안전성 직결).
- full 골든(8 도메인, Task 9) 실행 여부 = 비용(추정 ~20M+ 토큰) 고려해 사용자 결정.
- 전체 verdict 상세(3 렌즈별 reason·citation_verified): task 출력 `wo1v6gbmg.output`.
