# 정적분석 직렬 기준선 벤치마크 (2026-04-25)

**목적**: G.6 병렬화(Phase I) 착수 여부 판정을 위한 실측 기준선 수집.

## 측정 환경

- **OS**: win32 (Windows 10 Pro 10.0.19045)
- **Python**: 3.14.2
- **반복 횟수**: 3회 / 페이로드
- **측정 날짜**: 2026-04-25 01:18
- **psutil**: 7.2.2
- **스크립트**: `scripts/benchmark_static_analysis.py`

## 결과 요약

| 페이로드 | 파일 수 | 평균 (s) | 최대 RSS (MB) | 비고 |
|---------|--------|---------|-------------|------|
| Python-heavy (10 .py) | 10 | 24.33 | 110 | pylint+flake8+bandit x 10 |
| JS+semgrep (5 .js) | 5 | 0.19 | 109 | ESLint 미설치 — graceful degradation |
| Mixed (8 .py + 4 .js + 3 .sh) | 15 | 19.75 | 110 | Python 도구 지배적 |

**전체 평균**: 14.76s

## 개별 실행 로그

- **Python-heavy (10 .py)**: 23.62s / 25.37s / 24.01s
- **JS+semgrep (5 .js)**: 0.19s / 0.19s / 0.19s
- **Mixed (8 .py + 4 .js + 3 .sh)**: 18.98s / 20.04s / 20.22s

## 분석

### Python-heavy 페이로드 (24.33s)

pylint, flake8, bandit 세 도구가 파일 수 선형 비례로 증가한다.
10 파일 x ~2.4s/파일. 단일 코어 직렬 처리 확인 (CPU 사용률 한 코어 고정).

### JS+semgrep (0.19s)

ESLint 가 Railway 런타임에는 설치되지만 로컬 Windows 환경에 미설치.
ESLint Analyzer 가 graceful degradation (`success=false, issues=[]`).
semgrep JS: rule pack 미설치로 0건 반환.
**Railway 실측 필요**: JS 파일 비중이 높은 리포에서 실제 소요 시간이 상이할 수 있음.

### Mixed (19.75s)

Python 8 파일이 소요 시간을 지배. sh 파일 3개는 ShellCheck 의존이며 Windows 에서 미설치.

## Go/No-Go 판정

| 기준 | 조건 |
|------|------|
| Go | 평균 >= 60s — Phase I 착수 |
| No-Go | 평균 < 20s — 병렬화 불필요 |
| Borderline | 20s <= 평균 < 60s — ROI 계산 후 재판정 |

**판정: BORDERLINE (로컬) / Railway 실측 필요**

> - 전체 평균 14.76s (No-Go 영역이지만 JS 측정값 0.19s 가 평균을 낮춤)
> - JS ESLint 미설치로 **로컬 벤치마크가 Railway 실측을 대표하지 못한다**
> - Python-heavy 단독(24.33s) 은 Borderline 영역: 파일 10→50개로 늘면 60s 초과 가능

## 결론 및 Phase I 권고

**현재 판정: No-Go (로컬 기준) / 조건부 Phase I**

1. **즉각 착수 조건 미충족** — 전체 평균 14.76s < 20s
2. **Railway 실측 권장** — JS+semgrep+ESLint 환경에서 20 파일 이상 PR 으로 재측정
3. **Phase I 착수 트리거** — Railway 실측 평균 >= 30s OR 50 파일 이상 PR 에서 timeout 발생 시
4. **현재 대응 충분** — `STATIC_ANALYSIS_TIMEOUT=30` 으로 단일 파일 hang 차단 중

## Phase I 설계 메모 (미래 참조용)

G.6 병렬화 착수 시 구현 범위:
- `src/constants.py`: `STATIC_ANALYSIS_CONCURRENCY=2`, `FILE_ANALYSIS_TIMEOUT=90`, `TOTAL_STATIC_TIMEOUT=180`
- `src/worker/pipeline.py::_run_static_analysis`: `asyncio.Semaphore` + 파일별 `to_thread` + `gather`
- `src/analyzer/io/tools/golangci_lint.py`: `go.mod` 파일별 서브디렉토리 격리 (race 가드)
- semgrep warmup 1회 (lifespan startup)
- Railway 스테이징 배포 후 실측 PR 3건 메모리 그래프 기록
