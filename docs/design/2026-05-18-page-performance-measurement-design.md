# SCAManager 페이지 성능 측정 설계

작성일: 2026-05-18  
목적: 전체 서비스 페이지 로딩 속도를 로컬·운영 양쪽에서 정밀 측정해 병목을 진단하고 사용자 만족도를 개선한다.

---

## 1. 측정 대상 페이지

| 카테고리 | 경로 | 로컬 인증 | 운영 인증 |
|----------|------|----------|----------|
| 공개 | `/login` | ❌ | ❌ |
| 공개 | `/` (landing) | ❌ | ❌ |
| 주요 UI | `/overview` | ✅ bypass | TTFB only |
| 주요 UI | `/dashboard` | ✅ bypass | TTFB only |
| 주요 UI | `/settings` | ✅ bypass | TTFB only |
| 리포 | `/repos/add` | ✅ bypass | TTFB only |
| 리포 상세 | `/repos/{name}` | ✅ bypass + seed | TTFB only |
| 분석 결과 | `/repos/{name}/analysis/{id}` | ✅ bypass + seed | TTFB only |
| 인사이트 | `/repos/{name}/insights` | ✅ bypass + seed | TTFB only |
| API | `/health` | ❌ | ❌ |
| API | `/api/repos` | ✅ | TTFB only |
| API | `/api/repos/{name}/report` | ✅ | TTFB only |

**인증 전략**
- **로컬**: `require_login` 의존성 오버라이드 (conftest.py 패턴) → 전체 렌더링 측정
- **운영**: 공개 페이지는 전체 측정 / 인증 필요 페이지는 TTFB + HTTP 상태코드만 기록 (실 미로그인 사용자 체감 반영)

---

## 2. 측정 지표

| 지표 | 수집 방법 | 목표 임계값 |
|------|----------|------------|
| TTFB | Navigation Timing `responseStart - requestStart` | < 300ms |
| FCP | PerformanceObserver `paint` 타입 | < 1,500ms |
| LCP | PerformanceObserver `largest-contentful-paint` | < 2,500ms |
| DCL | Navigation Timing `domContentLoadedEventEnd` | < 1,500ms |
| Load | Navigation Timing `loadEventEnd` | < 3,000ms |
| 반복 | 페이지당 3회 측정 → avg / min / max | — |
| 느린 API | response 시간 > 500ms 요청 캡처 | — |

---

## 3. 파일 구조

```
scripts/
  perf_measure.py            # 독립 실행 성능 측정 스크립트
e2e/
  test_performance.py        # pytest 기반 — make test-e2e 통합
docs/reports/
  perf-YYYY-MM-DD.md         # 자동 생성 Markdown 리포트
```

---

## 4. `scripts/perf_measure.py` 설계

### 실행 인터페이스
```bash
python scripts/perf_measure.py                # 로컬 + 운영 양쪽 (기본)
python scripts/perf_measure.py --local-only   # 로컬만
python scripts/perf_measure.py --prod-only    # 운영만
```

### 처리 흐름
```
1. argparse → 실행 대상 결정
2. [로컬] e2e/conftest.py 의 _setup_e2e_db + _start_uvicorn 재사용
          서버 ready 폴링 (최대 30초)
          seeded_page용 더미 레포 삽입 (_seed_repo)
3. [운영] BASE_URL = https://scamanager-production.up.railway.app
4. Playwright sync_api → Chromium headless 기동
5. 페이지별 measure_page(page, url, runs=3) 호출
6. 결과 수집 → Markdown 리포트 생성 → docs/reports/perf-{date}.md 저장
7. 터미널에 요약 표 출력
8. [로컬] 서버 종료
```

### 핵심 함수

**`_single_measure(page, url) → dict`**
- navigate 전 PerformanceObserver 등록 (FCP, LCP)
- response 이벤트 리스너 등록 (느린 API 캡처)
- `page.goto(url, wait_until="networkidle")` 실행
- Navigation Timing API로 TTFB / DCL / Load 수집
- FCP / LCP window 변수 읽기
- 반환: `{ttfb, fcp, lcp, dcl, load, slow_requests}`

**`measure_page(page, url, runs=3) → dict`**
- `_single_measure` 3회 호출
- avg / min / max 계산
- 반환: 지표별 통계 + 느린 요청 합산

**`render_markdown(local_results, prod_results) → str`**
- 로컬 / 운영 / 비교 표 / 임계값 초과 항목 / 느린 API 섹션 구성

---

## 5. `e2e/test_performance.py` 설계

기존 `e2e/conftest.py` fixtures (`live_server`, `page`, `seeded_page`) 재사용.

```python
THRESHOLDS = {
    "ttfb": 500,   # ms — 로컬 SQLite 기준 완화값
    "fcp":  1500,
    "lcp":  2500,
    "dcl":  1500,
    "load": 3000,
}
```

### 테스트 목록
- `test_login_ttfb` / `test_login_load`
- `test_overview_ttfb` / `test_overview_load`
- `test_dashboard_ttfb` / `test_dashboard_lcp`
- `test_settings_ttfb` / `test_settings_load`
- `test_add_repo_ttfb`
- `test_repo_detail_ttfb` / `test_repo_detail_load` (seeded_page)
- `test_analysis_detail_load` (seeded_page + seeded_analysis)
- `test_repo_insights_load` (seeded_page)

각 테스트는 `@pytest.mark.perf` 마커를 달아 `make test-perf` 로 선택 실행 가능하게 한다.

### 분석 레코드 시딩 전략
`/repos/{name}/analysis/{id}` 페이지는 Analysis ORM 레코드가 필요하다.
- `conftest.py`에 `seeded_analysis` session-scope fixture 추가: SQLite에 최소 Analysis 레코드 직접 INSERT
- `perf_measure.py`에서도 동일하게 `_seed_analysis(db_path)` 헬퍼로 처리
- 분석 ID는 시딩 후 SELECT로 조회해 URL에 삽입

---

## 6. Markdown 리포트 형식

```markdown
# SCAManager 페이지 성능 리포트
측정일시: 2026-05-18 20:30 | 반복: 3회 | 브라우저: Chromium headless

## 🏠 로컬 E2E 서버 (SQLite)
| 페이지 | TTFB avg | FCP avg | LCP avg | DCL avg | Load avg | 판정 |
| /login | 45ms | 210ms | 310ms | 180ms | 420ms | ✅ |
| /dashboard | 890ms | 1.2s | 2.1s | 950ms | 2.8s | ⚠️ |

## 🌐 운영 서버 (Railway)
| 페이지 | TTFB avg | FCP avg | LCP avg | DCL avg | Load avg | 판정 |
| /login | 180ms | 520ms | 780ms | 490ms | 1.1s | ✅ |

## 📊 로컬 vs 운영 비교
| 페이지 | 로컬 Load | 운영 Load | 배율 |

## 🔴 임계값 초과 항목

## 🔍 느린 API 엔드포인트 (> 500ms)
| 엔드포인트 | 평균 응답 | 크기 |
```

---

## 7. Makefile 명령 추가

```makefile
test-perf:          ## 성능 테스트 (pytest 기반, 로컬)
    python -m pytest e2e/ -m perf -v

perf-report:        ## 성능 리포트 생성 (로컬 + 운영)
    python scripts/perf_measure.py
```

---

## 8. 비기능 요구사항

- `perf_measure.py` 완료 후 항상 로컬 서버 정리 (signal handler)
- pylint / flake8 통과 (기존 lint 기준 준수)
- 운영 URL은 환경변수 `PERF_PROD_URL` 또는 스크립트 내 기본값으로 관리
- 리포트 파일명: `docs/reports/perf-YYYY-MM-DD-HHMM.md` (중복 방지)
