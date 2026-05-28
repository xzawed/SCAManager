# 2026-04-23 프로젝트 구조 3-에이전트 감사 보고서

> 전체 폴더 구조·파일 배치의 효율성·확장성을 3개 Explore 에이전트가 서로 다른 관점에서 병렬 감사. 합의된 이슈만 선별해 Phase S.1~S.3 으로 단계 실행.

---

## 1. 3-에이전트 관점 분담

| Agent | 관점 | Top 1 지적 |
|-------|------|----------|
| **A** | Python 표준 관례 (src layout, 네이밍, test 배치) | `tests/unit/` 분리 + `src/shared/` 수렴 |
| **B** | 확장성 (새 도구·채널·action 추가 용이성) | **Notifier 9채널 Protocol 전환** |
| **C** | 도메인 경계·계층 의존성 (Clean Architecture) | Service 계층 통합 + Repository 정규화 |

각 에이전트는 약 800단어 보고서 + Top 5 우선순위 제시. 세 결과를 교차 매핑해 **2명 이상 동의 = 실제 진행 대상** 으로 분류.

---

## 2. 합의 매트릭스

| 이슈 | A | B | C | 합의도 | 비용 | 이득 |
|------|---|---|---|--------|------|------|
| `src/shared/` 공용 유틸 수렴 | ✅ Top 2 | ✅ Top 5 (간접) | — | 🟢 2명 | 낮음 | 중간 |
| UI/Webhook router 서브패키지 | 간접 | ✅ Top 3 | — | 🟢 2명 | 중간 | 높음 |
| Gate `actions/` 스캐폴딩 결정 | — | ✅ Top 2 | ✅ (계층 모호) | 🟢 2명 | 낮음 (삭제) | 중간 |
| Repository 패턴 정규화 | ⚠️ 네이밍 | — | ✅ Top 2 | 🟡 1.5명 | 중간 | 중간 |
| `get_repo_or_404` UI/webhook 확산 | — | — | ✅ Top 3 | 🟡 1명 | 낮음 | 높음 |
| Notifier Protocol 전환 | — | ✅ Top 1 | — | 🟡 1명 | **높음** | 높음 |
| Service 계층 신설 | — | — | ✅ Top 1 | 🟡 1명 | **높음** | 중간 |
| Analyzer pure/io 분리 | — | — | ✅ Top 4 | 🟡 1명 | 높음 | 낮음 |
| `tests/unit/` 66파일 이동 | ✅ | — | — | 🟡 1명 | 높음 | 중간 |
| `pyproject.toml` 통합 | ✅ | — | — | 🟡 1명 | 낮음 | 낮음 |
| Language Tier 주석 | — | ✅ Top 4 | — | 🟡 1명 | **매우 낮음** | 중간 |
| API domain 가이드 | — | ✅ Top 5 | — | 🟡 1명 | 낮음 | 중간 |

🟢 = 2명 이상 합의 · 🟡 = 1명 지적이나 효과 명확

---

## 3. 실행 Phase 분류

### Phase S.1 — 낮은 리스크, 즉시 수행 (~1.5h)

**포함 작업 4건**:
1. `src/shared/` 패키지 생성 + `http_client.py` / `log_safety.py` 이동 — A+B 합의
2. Gate `actions/` 스캐폴딩 삭제 + `registry.py` 내 Protocol/GateContext 는 유지 — B+C 합의
3. Language Tier 기준 주석 3줄 (`src/analyzer/review_guides/__init__.py`) — B 최저 비용
4. `get_repo_or_404` UI/webhook 에서도 사용 — C 직접

**예상 영향**: import 경로 10곳 내외 / 테스트 회귀 없음 기대 / 죽은 코드 ~200줄 제거

### Phase S.2 — 중간 리스크, 사용자 승인 후 (~3h)

**포함 작업 3건**:
5. UI router 서브패키지 분리 (`src/ui/routes/` — overview/repos/analysis/settings/cli) — B 직접
6. Webhook router 서브패키지 분리 (`src/webhook/providers/github.py`, `railway.py`) — B 직접
7. `repository_repo.py` 개명(이름 충돌 해소) + `find_by_full_name` 추가 — C 직접

**예상 영향**: import 경로 재작성 다수 / `src/main.py` 의 router include 수정 필요 / 테스트 회귀 주의

### Phase S.3 — 큰 리팩토링, 별도 세션 (~5~10h)

**포함 작업 4건**:
8. **Notifier 9채널 클래스 Protocol 전환** — B Top 1. 테스트 15곳+ mock 재작성 비용 큼. Analyzer/Gate 선례 재발 방지.
9. Service 계층 신설 (`src/services/`) — C Top 1. 기존 pipeline/engine/manager 의 책임을 명확화하되 기존 테스트와의 호환성 검토 필요.
10. Analyzer pure/io 분리 (`src/analyzer/pure/`, `io/`) — C Top 4. 파일 7개 이동, import 경로 다수.
11. `tests/unit/` 66파일 계층화 — A Top 1. 테스트 검색·유지보수 향상이나 이동 비용 큼.

**예상 영향**: 프로덕션 코드 크게 흔들림 / pipeline-reviewer 승인 필수 / 전체 테스트 회귀 의무

---

## 4. 의도적 제외 (3 에이전트 제안이나 미진행 항목)

| 항목 | 제외 사유 |
|------|----------|
| `__init__.py` 공개 API 재-export (A) | 현재 17/19 빈 파일로 작동 중 — 정책 강제보다 명시성 자유도 유지 |
| `pyproject.toml` 통합 (A) | 현행 `setup.cfg` + `pytest.ini` 정상 동작. Railway/Nixpacks/CI 호환 우려 — 별도 큰 마이그레이션 Phase 필요 |
| Service 계층 대규모 이관 (C) | 기존 위치(`worker/pipeline.py`, `gate/engine.py`, `config_manager/manager.py`) 에 테스트가 고착. 이득 대비 회귀 위험 과대 |

---

## 5. 추후 재감사 권장

Phase S.1~S.3 전부 완료 후 3 에이전트 재감사 실행해 실제 개선도 측정.
현재 감사 시점 기준선 수치: `src/` 135 py / 5019 LOC / 1175 passed / pylint 10.00 / SonarCloud QG OK.
