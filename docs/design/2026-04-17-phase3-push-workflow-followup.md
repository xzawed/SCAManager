# Phase 3 (직접 푸시 워크플로우 실질화) — Follow-up

> 2026-04-17. Phase 3-A(커밋 라인 코멘트) / 3-B(회귀 알림) / 3-C(Pre-push 훅 차단)의
> 코드 구현·테스트·마이그레이션은 모두 완료되었으며 `claude/git-workflow-proposal-SE1As`
> 브랜치에 푸시됨. 이 문서는 **자동화만으로 완결되지 않는 운영·UX·수동 검증 잔여 과제**
> 를 정리한다.

## 현재 상태 요약

| Phase | 구현 | 테스트 | 마이그레이션 | 배포 |
|-------|------|--------|-------------|------|
| 3-A 커밋 라인 코멘트 | ✅ | ✅ 36건 신규 | `0011_add_push_workflow_fields` | 배포 필요 |
| 3-B 회귀 감지·경보 | ✅ | ✅ 18건 신규 | `0012_add_analysis_repo_created_index` | 배포 필요 |
| 3-C Pre-push 훅 차단 | ✅ | ✅ 7건 신규 | (마이그레이션 불필요 — `block_threshold`는 3-A에서 선행 추가) | 배포 + 훅 재배포 필요 |

- 누적 테스트: 508 passed
- 품질: pylint 9.68 유지, bandit HIGH 0
- 브랜치: `claude/git-workflow-proposal-SE1As`

## 자동화 범위 밖의 잔여 과제

### 1. 설정 UI 추가 (`src/templates/settings.html`)

`RepoConfig`에 4개 컬럼이 추가됐지만 Web UI 설정 폼에는 반영되지 않음. 사용자는
현재 `PUT /api/repos/{repo}/config` REST API로만 제어 가능. UI 개선 전까지 API 직호출
안내가 필요하다.

추가할 필드:
- `push_commit_comment` — 토글 (기본 ON)
- `regression_alert` — 토글 (기본 ON)
- `regression_drop_threshold` — number input (기본 15)
- `block_threshold` — number input + "비활성" 옵션 (기본 비활성)

**주의**: `src/templates/settings.html`은 Jinja2 렌더링 오류가 pytest로 감지되지 않음
(CLAUDE.md 모바일 환경 보호 규칙). 실제 브라우저에서 설정 저장 → 다시 로드해
모든 필드가 유지되는지 **수동 검증 필수**.

### 2. 기존 등록 리포의 훅 스크립트 재배포

Phase 3-C는 `.scamanager/install-hook.sh` 내부 bash 로직을 변경. 이미 리포를
등록해 구버전 훅을 사용 중인 사용자는 **다음 중 하나**의 조치가 필요하다.

**옵션 A — 수동 재등록**:
1. SCAManager 대시보드에서 해당 리포 삭제
2. "리포 추가"로 재등록 → `commit_scamanager_files`가 sha 포함 PUT으로 최신 스크립트 커밋
3. 개발자: `git pull && bash .scamanager/install-hook.sh`로 훅 재설치

**옵션 B — 재배포 버튼 추가 (권장)**:
- UI 설정 페이지에 "훅 스크립트 재배포" 버튼 추가
- 백엔드: `POST /api/repos/{repo}/redeploy-hook` 엔드포인트 신규
- 내부 동작: 기존 `hook_token`을 유지한 채 `commit_scamanager_files()` 재호출
- 파일 경로: `src/api/repos.py` + `src/templates/settings.html`

현재는 옵션 A만 가능. 옵션 B가 운영 부담이 크게 줄이므로 별도 티켓(Phase 3-D?)으로
추가 권장.

### 3. 수동 End-to-End 검증

단위 테스트(508) 및 정적 분석만으로는 아래 실 환경 동작이 보장되지 않는다.
로컬 `make run` + ngrok 터널 또는 Railway 스테이징에서 직접 확인 필요.

**3-A 커밋 라인 코멘트**
- [ ] 테스트 리포에 임의 파일 수정 후 기본 브랜치로 푸시
- [ ] GitHub 커밋 뷰(`commit/<sha>`)에 AI 리뷰 댓글이 달리는지 확인
- [ ] `push_commit_comment=False`로 설정 후 동일 테스트 → 댓글이 달리지 않는지 확인
- [ ] GitHub App/OAuth 토큰에 `repo` 스코프가 부족하면 403 — 로그 확인

**3-B 회귀 알림**
- [ ] 동일 리포에 일부러 질 낮은 커밋(F등급 유도)을 푸시 → Telegram에 ⚠️📉 경보 수신
- [ ] 일반 분석 알림과 별도 메시지로 오는지(한 메시지에 합쳐지지 않는지)
- [ ] `regression_alert=False`로 설정 후 F등급 커밋 → 경보 미수신
- [ ] 직전 이력 5건 미만인 리포 → 경보 없음 (baseline 부족)

**3-C Pre-push 훅 차단**
- [ ] 리포 설정에 `block_threshold=60` 적용
- [ ] 로컬에서 F등급 유도 변경 후 `git push` → 훅이 `exit 1`로 차단, stderr 메시지 출력
- [ ] `git push --no-verify` → 차단 우회 성공
- [ ] `block_threshold=None` 리포 → 훅이 차단하지 않음(`exit 0`)
- [ ] `claude` CLI 미설치 환경 → 훅이 조용히 skip (기존 동작 유지)

### 4. 프로덕션 배포 체크

- [ ] Railway 배포 시 마이그레이션 `0011`·`0012` 자동 실행 확인 (`/health` 응답 `{"status":"ok"}`)
- [ ] Railway 로그에서 `ix_analyses_repo_created` 인덱스 생성 성공 확인
- [ ] 기존 RepoConfig 레코드가 `server_default`로 안전하게 업그레이드됐는지
  (특히 `push_commit_comment=true`, `regression_alert=true` 기본값 적용)
- [ ] 배포 후 최소 한 개 리포의 첫 푸시·PR 이벤트가 정상 처리되는지 모니터링

### 5. 문서화 보강

- [ ] `README.md`에 "직접 푸시 워크플로우" 섹션 추가 — 3-A/3-B/3-C 기능 한 문단 설명
- [ ] `docs/reference/env-vars.md`는 영향 없음 (새 env var 추가 없음)
- [ ] `CLAUDE.md` 파이프라인 도식에 `push_commit_comment`·regression·block 분기 반영 검토

## 설계 메모 (향후 개선 여지)

### 회귀 감지 민감도
현재 `regression_drop_threshold`는 "직전 5건 평균 대비 N점 하락" 단일 축. 운영 중
false positive가 잦으면 아래 조합 고려:
- 분산/표준편차 기반(평균 ± 2σ를 벗어난 경우만)
- 연속 N회 하락 조건 추가

### block_threshold와 Gate 연계
현재 pre-push 훅 차단은 `block_threshold` 단독 판정. 향후 `approve_threshold`와 연동해
"저점수면 차단 + 서버에서도 REQUEST_CHANGES" 같은 일관 정책 가능. 단 현재는 독립 유지가
이해하기 쉬워 의도적으로 분리.

### Commit Comment vs PR Comment 중복
같은 커밋이 먼저 직접 푸시(→ 커밋 코멘트) 후 PR로 만들어지면(→ PR 리뷰 코멘트) AI 리뷰가
두 곳에 동일 내용으로 남는다. 현재는 `Analysis`의 SHA 중복 체크로 두 번째 이벤트가 건너뛰기
되지만, PR 생성 시점의 재분석 요구와 충돌. 운영 중 필요 시 정책 논의.

### 기존 리포 훅 재배포 자동화
4.2번 항목 — 설정 페이지에 버튼 추가가 가장 UX 개선 효과 큼. 구현 난이도 낮음.
