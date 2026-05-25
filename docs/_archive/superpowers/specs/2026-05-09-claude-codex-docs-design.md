# 설계 문서: Claude + Codex 협업 문서 구조 정리

**날짜**: 2026-05-09  
**상태**: 사용자 승인 완료  
**브랜치**: `chore/codex-docs-setup`

---

## 1. 배경 및 문제

### 사용 패턴
- 사용자는 **같은 프로젝트 세션**에서 Claude(복잡한 판단·설계)와 Codex(반복 구현)를 동시 운용
- Claude Code → `CLAUDE.md` 자동 로드 / Codex CLI → `AGENTS.md` 자동 로드

### 현재 문제점

| 문제 | 영향 |
|------|------|
| AGENTS.md = CLAUDE.md 439줄 복사본 (이름만 치환) | 정책 1건 변경 시 두 파일 동기화 필수 → drift 위험 |
| AGENTS.md 내 `.Codex/` (대문자) 경로 오류 | 실제 경로 `.codex/` (소문자) — broken reference |
| `.codex/rules/` 미존재 | AGENTS.md가 참조하는 8개 rule 파일 전혀 없음 |
| Codex 역할 미정의 | AGENTS.md에 Claude 정책(회고·멀티에이전트 등) 그대로 → Codex에 불필요 |

---

## 2. 설계 원칙

- **CLAUDE.md = 단일 권위**: 17개 협업 정책, 사이클 관리, 멀티에이전트 패턴 → Claude 전담
- **AGENTS.md = Codex 역할 정의 + 참조 포인터**: 반복 구현에 필요한 핵심 규칙 + "전체 정책은 CLAUDE.md 참조" 명시
- **정책 변경 → CLAUDE.md만 수정**: Codex는 참조 지시로 최신 정책 자동 적용
- **`.codex/rules/` = 코딩 규칙만**: 협업 정책 제외, 구현 시 즉시 적용 규칙만 포함

---

## 3. 최종 파일 구조

```
프로젝트 루트
├── CLAUDE.md          ← 변경 없음 (439줄, 17개 정책 포함, 단일 권위)
├── AGENTS.md          ← 완전 재작성 (~120줄)
│     • 프로젝트 개요 + 핵심 명령
│     • Codex 역할: 반복 구현 전담
│     • 항상 적용 규칙 (이중 언어 주석, TDD, 브랜치 워크플로, 단순화)
│     • "전체 정책 참조: CLAUDE.md §협업 정책, docs/ 참조"
│     • .codex/ 도구 설정
│
├── .claude/           ← 변경 없음
│   ├── rules/         ← 8개 기존 파일 (path-scoped, 상세)
│   └── agents/        ← 5개 Claude 전용 에이전트
│
└── .codex/            ← 신규 완성
    ├── agents/        ← 현행 유지 (5개, AGENTS.md 참조 → 유지)
    ├── hooks/         ← 현행 유지
    ├── hooks.json     ← 현행 유지
    └── rules/         ← 신규 8개 파일 (코딩 규칙만 — 협업 정책 제외)
```

---

## 4. 작업 범위 (3개 병렬 에이전트)

### Agent A: AGENTS.md 재작성
**담당**: AGENTS.md 완전 재작성 (439줄 → ~120줄)

**포함 내용**:
- 프로젝트 개요 (SCAManager 설명, 핵심 명령 표)
- 아키텍처 포인터 (`docs/architecture.md` 참조)
- Codex 역할 정의 (반복 구현 전담 — 테스트 작성, 리팩토링, 단순 코드 수정)
- **항상 적용 코딩 규칙** (4개):
  1. 이중 언어 주석 (한국어 먼저, 바로 다음 줄 영어)
  2. TDD 우선 (구현 전 테스트 먼저 — `test-writer` 에이전트 활용)
  3. 브랜치 워크플로 (`git checkout -b type/scope` → PR, main 직접 커밋 금지)
  4. 코드 단순화 (정확성·성능 유지, 불필요한 추상화 금지)
- **전체 정책 참조** 명시: "협업 정책 17개, 회고 패턴, 사이클 관리 전체: `CLAUDE.md` §협업 정책 참조"
- `.codex/` 도구 설정 (에이전트 경로, 훅 설명)
- 브랜치 명명 규칙 + 완료 5-step

**포함하지 않는 내용** (Claude 전담):
- 17개 협업 정책 전문
- 회고 패턴 (5+1 에이전트)
- 사이클 관리 (Phase 진행/종료 신호)
- 자유 발언 / 정책 9

---

### Agent B: `.codex/rules/` 8개 파일 신설
**담당**: `.claude/rules/` 대비 Codex 전용 slim 버전 생성

**파일별 방침**:

| 파일 | 포함 (구현 즉시 적용) | 제외 (Claude 판단 영역) |
|------|---------------------|----------------------|
| `testing.md` | asyncio_mode, mock 패턴, fixture 주의사항 | 에이전트 디스패치 결정, 회귀 가드 정책 |
| `db.md` | ORM 컬럼 → 마이그레이션 필수, batch_alter 금지, dialect 분기 | RLS 미들웨어 아키텍처 결정 |
| `pipeline.md` | 멱등성, 오류 처리 패턴 | pipeline-reviewer 에이전트 승인 절차 |
| `api.md` | 라우트 패턴, 의존성 주입, 인증 | smoke check 정책 절차 |
| `security.md` | 비밀 로깅 금지, 토큰 암호화 | Code Scanning 정책 |
| `ui.md` | 4-테마 지원, 템플릿 패턴 | 8 조합 시각 검증 의무 절차 |
| `i18n.md` | 번역 키 패턴, locale 미들웨어 | i18n 전략 결정 |
| `deploy.md` | requirements.txt 핀 고정, Railway 설정 | 배포 파이프라인 변경 승인 |

각 파일: **frontmatter (description + paths) + 코딩 규칙 bullet** 형식. 20~30줄 목표.

---

### Agent C: `.codex/agents/` 정합성 검증
**담당**: `.codex/agents/` 5개 파일 검증 및 필요 시 수정

**확인 사항**:
1. AGENTS.md 참조가 재작성 후에도 유효한지 (설명 내용이 새 AGENTS.md와 일치)
2. `.codex/rules/` 참조가 있다면 올바른 경로인지
3. `.claude/agents/` 대비 누락 에이전트 없는지
4. 에이전트 역할이 Codex 역할(반복 구현)과 정합하는지

---

## 5. 변경 없는 파일

- `CLAUDE.md` — 단일 권위, 수정 없음
- `.claude/` 전체 — 수정 없음
- `.codex/hooks/` — 현행 유지
- `.codex/hooks.json` — 현행 유지

---

## 6. 완료 기준

- [ ] AGENTS.md: ~120줄, Codex 역할 명확, CLAUDE.md 정책 참조 포인터 포함
- [ ] `.codex/rules/`: 8개 파일 생성, path-scoped frontmatter 포함
- [ ] `.codex/agents/`: 5개 파일 정합성 확인
- [ ] `.Codex/` 대문자 경로 오류 0건
- [ ] 브랜치 `chore/codex-docs-setup` → PR 생성

---

## 7. 고려했으나 채택하지 않은 방안

- **공유 docs/shared/ 도입**: 두 AI 모두 외부 파일 참조 의존 — AGENTS.md가 완전 자립적이지 않음
- **동기화 스크립트**: 근본 문제(역할 미분리) 미해결, 실행 깜빡히면 drift
