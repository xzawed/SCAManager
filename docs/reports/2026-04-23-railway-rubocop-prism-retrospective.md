# 회고: Railway 빌드 실패 — rubocop/prism 의존성 트랩 (2026-04-23)

> Phase D.3 RuboCop 도구 추가 이후 Railway 프로덕션 배포가 **두 번 연속 실패**한 후 3번째 시도에서 성공한 경위와 교훈.

## 타임라인

| 시각 | 이벤트 | 커밋 |
|------|--------|------|
| 2026-04-23 오전 | Phase D.3 (RuboCop) + D.4 (golangci-lint) 동시 추가 — 로컬 1188 passed | `2eb0ef0` / `d78b449` |
| 오전 | Railway 자동 배포 → **1차 실패**: prism 네이티브 확장 컴파일 오류 | — |
| 오전 | 1차 수정 시도: `build-essential + libyaml-dev` 추가 + rubocop 1.57.2 다운그레이드 | `6aaa268` |
| 11:02 | Railway 2차 배포 → **2차 실패**: 동일한 prism 오류 재현 | — |
| 오후 | 로그 상세 분석으로 근본 원인 특정 — **rubocop-ast transitive prism 의존성** | — |
| 오후 | 3차 수정: `rubocop-ast 1.36.2` 명시 핀 | `8042f12` |
| 오후 | Railway 3차 배포 → **✅ 성공** | — |

**총 소요**: 사용자 대기 시간 ~2시간, 최종 수정 크기는 buildCommand 한 줄 추가.

---

## 무엇이 문제였나

### 표면 증상

Railway 빌드 로그에서 rubocop 설치 중 다음 오류로 실패:

```
ERROR:  Error installing rubocop:
	ERROR: Failed to build gem native extension.
    current directory: /var/lib/gems/3.2.0/gems/prism-1.9.0/ext/prism
/usr/lib/ruby/3.2.0/mkmf.rb:490:in `try_do': The compiler failed to generate an executable file.
You have to install development tools first.
```

### 첫 가설 (틀린 가설)

> "`prism` 네이티브 확장이 C 컴파일러(gcc)를 필요로 하는데, nixpacks 환경에 C 개발 도구가 없다. `build-essential + libyaml-dev` 를 aptPkgs 에 추가하면 해결될 것."

이 가설로 1차 수정 (`6aaa268`) 을 적용했으나 **2차 빌드에서 동일 오류 재발**. Ruby 의 `mkmf.rb` 가 컴파일러를 찾지 못하는 근본 원인은 nix/apt 혼재 PATH 문제로 의심됨.

### 진짜 원인 (3차 수정에서 확정)

**rubocop 1.57.2 자체는 pure Ruby** 이지만, transitive 의존성 체인:

```
rubocop 1.57.2
 └─ rubocop-ast (>= 1.28.1, < 2.0)   ← gem 이 최신 버전 선택
      └─ rubocop-ast 1.43.x+         ← 2025년 이후 버전
           └─ prism (>= 1.2)          ← 네이티브 확장 필요!
                └─ mkmf/gcc 필요
```

**핵심 통찰**: 버전 제약 `rubocop-ast >= 1.28.1, < 2.0` 는 **2023년 릴리스 당시** 에는 prism 을 끌어오지 않았지만, 시간이 지나 rubocop-ast 1.43.0+ 가 prism 을 필수 의존성으로 만들면서 **동일한 rubocop 1.57.2 를 설치해도 2024년 이후에는 prism 이 포함**되게 변함.

이는 "재현 가능한 빌드" (reproducible build) 가 아님 — 같은 버전을 고정해도 transitive 의존성이 떠다니면 시간에 따라 동작이 달라진다.

---

## 수정 내용

### 최종 해결책 — 커밋 [`8042f12`](https://github.com/xzawed/SCAManager/commit/8042f12)

`railway.toml` 의 `buildCommand` 에 rubocop 설치 **직전** `rubocop-ast` 를 명시적으로 고정:

```diff
- ... && gem install rubocop -v 1.57.2 --no-document && ...
+ ... && gem install rubocop-ast -v 1.36.2 --no-document \
+     && gem install rubocop -v 1.57.2 --no-document && ...
```

### 왜 1.36.2 인가

- `rubocop-ast 1.36.2`: prism 의존성이 없는 **마지막** 버전 (pure Ruby)
- `rubocop-ast 1.37.0`: prism 을 optional 로 추가
- `rubocop-ast 1.43.0`: prism 을 required 로 승격

1.36.2 는 rubocop 1.57.2 의 제약 `>= 1.28.1, < 2.0` 을 만족하므로 gem 이 이미 설치된 버전을 재사용 → prism 이 설치되지 않음.

### 부수 효과

- 빌드 시간 단축 (네이티브 컴파일 생략)
- nix/apt PATH 혼재 문제 회피
- `build-essential + libyaml-dev` 는 불필요해졌으나 **안전망으로 유지** — 향후 다른 gem 이 네이티브 확장 필요 시 대비

---

## 배운 점

### 1. "Pinning 했다" ≠ "재현 가능하다"

`gem install rubocop -v 1.57.2` 는 rubocop 본체는 고정하지만 **transitive 의존성은 열어둔다**. 진정한 재현성을 원한다면:

- `Gemfile.lock` 사용 (Bundler 기반 설치)
- 또는 **모든 transitive 의존성을 명시적으로 고정**

NodeJS 의 `package-lock.json`, Python 의 `pip-compile` 이 해결하는 것과 동일한 문제가 Ruby 생태계에도 있다.

### 2. 로그 분석의 층위

1차 수정 실패는 **증상(컴파일 오류) 기반 추측**이었다. "컴파일러 문제니까 build-essential 을 추가하자"는 표면적 처방.

3차 수정은 **의존성 트리 추적** — "컴파일이 실패하는 gem 이 뭔가? prism. prism 은 어디서 왔나? rubocop-ast. rubocop-ast 는 왜 prism 이 필요한 최신 버전을 선택했나? 제약이 느슨해서."

**교훈**: 오류 메시지만 보고 처방하지 말고, **왜 그 오류 상황에 도달했는지** 의존성/설치 경로를 역추적할 것.

### 3. 환경 차이의 위험

로컬 devcontainer 에서는 rubocop 설치 자체를 **mock 기반 단위 테스트**로만 검증했다 (분석기 클래스의 `supports`/`run` 동작). 실제 gem 설치 과정은 Railway 프로덕션에서 처음 실행됨.

**P4-Gate 제도의 존재 이유**가 이것이다: 로컬과 프로덕션의 환경 차이 때문에 단위 테스트만으로는 "도구가 실제로 실행된다"를 보장할 수 없다. P4-Gate-1 (cppcheck/slither) 은 통과했지만 P4-Gate-2 (rubocop/golangci-lint) 에서 prism 문제를 발견.

### 4. 빠른 피드백 루프의 중요성

Railway 빌드는 푸시 → 실패까지 약 1분이 걸린다. 1차 수정은 "추측 기반 추가"라 2차 빌드에서 동일 오류를 만났다. 로그를 **완전히** 읽고 나서 패치하는 것이 결과적으로 더 빠르다.

---

## 재발 방지 전략

### 즉시 적용

1. **`rubocop-ast` 핀을 `railway.toml` 에 영구 유지** — 이미 완료
2. **P4-Gate-2 가이드**에 prism 트랩 사례 기록 — 향후 Ruby 도구 추가 시 참조
3. **CLAUDE.md "배포" 섹션**에 "gem transitive 의존성 주의" 추가 후보

### 장기 검토 (추후 필요 시)

| 방향 | 장점 | 단점 |
|------|------|------|
| **Bundler + Gemfile.lock 도입** | 완전한 재현성 | Ruby 생태계에 본격 진입 (SCAManager 는 Python 서비스) |
| **Docker 전환** | 이미지 snapshot 으로 고정, 환경 차이 제거 | 빌드 시간·복잡도 증가 |
| **루비 도구 gem 바이너리 pre-caching** | 빌드 시간 단축 | devcontainer 이미지 수정 필요 |
| **현 상태 유지 (명시 pinning)** | 간단, 즉시 동작 | 새 루비 gem 도구 추가 시마다 transitive 확인 필요 |

**권고**: 현재의 "명시 pinning" 전략을 유지하되, Phase D 로 더 많은 언어 도구를 추가할 때마다 유사한 trap 가능성을 미리 검증한다.

---

## 재배포 확인 체크리스트 (완료된 것)

- [x] Railway 빌드 로그: `Successfully installed rubocop-ast-1.36.2`
- [x] Railway 빌드 로그: `Successfully installed rubocop-1.57.2` (prism 없이)
- [x] Railway 빌드 로그: `golangci-lint has been installed to /usr/local/bin`
- [x] Railway 전체 배포: 성공 (Build Failed 문구 없음)
- [ ] 런타임 동작 확인 → **[P4-Gate-2 가이드](../guides/p4-gate-2-verification.md) 2단계 이후로 이어짐**

---

## 관련 커밋

- [`2eb0ef0`](https://github.com/xzawed/SCAManager/commit/2eb0ef0) Phase D.3 RuboCop 도구 추가
- [`d78b449`](https://github.com/xzawed/SCAManager/commit/d78b449) Phase D.4 golangci-lint 도구 추가
- [`6aaa268`](https://github.com/xzawed/SCAManager/commit/6aaa268) 1차 수정 (실패): build-essential + libyaml-dev + rubocop 1.57.2
- [`8042f12`](https://github.com/xzawed/SCAManager/commit/8042f12) **최종 수정 (성공)**: rubocop-ast 1.36.2 명시 핀

## 관련 문서

- [P4-Gate-2 검증 가이드](../guides/p4-gate-2-verification.md)
- [사용자 수행 필요 잔여 작업](../guides/user-actions-remaining.md)
- [STATE.md](../STATE.md) 그룹 24 (Railway 빌드 안정화)
