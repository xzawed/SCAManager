# Settings 페이지 재설계 — 설계 스펙 (2026-04-21)

## 요약

설정 페이지의 정보 아키텍처를 **의도 기반(사용자 질문: "언제 뭐 하는가")** 기준으로 재편한다.
기능은 그대로, 카드 제목과 필드 배치만 변경. 백엔드 코드·API·스키마 변경 없음.

**해결 페인 포인트 3종**

| ID | 문제 | 해결 방법 |
|----|------|-----------|
| B | 카드 위계가 모호해 "저장 영향 범위"가 불분명 | 6 카드 의도별 재명명 + 위험 구역 최하단 분리 |
| A | 연관 필드가 다른 카드에 흩어져 있음 | auto_merge → PR 카드, create_issue + railway_deploy_alerts → 피드백 카드 |
| D | 프리셋 적용 시 뭐가 바뀌는지 불명확 | P1 펼침 diff 미리보기 + P2 적용 하이라이트 |

---

## 아키텍처

단일 파일 리팩토링. ORM / API / 라우터 / 테스트 변경 없음.

```
src/templates/settings.html   ← 유일한 변경 대상
CLAUDE.md                     ← 구조 규약 섹션 갱신
tests/test_ui_router.py       ← (선택) 렌더 스모크 테스트
```

**불변 제약** (CLAUDE.md 규약):

- 백엔드 필드명 전부 불변 (`pr_review_comment`, `approve_mode`, … 14개)
- PRESETS JS 객체 9개 필드 구성 불변
- 기존 JS 헬퍼 5종 시그니처 불변: `setApproveMode`, `toggleMergeThreshold`, `applyPreset`, `_setPair`, `_showPresetToast`
- 프리셋이 알림 채널 URL을 건드리지 않는 원칙 불변
- 4-way 동기화 (ORM / RepoConfigData / RepoConfigUpdate / UI 폼) 구조 불변

---

## 컴포넌트 — 6 카드 상세

### 1. 🚀 빠른 설정 (프리셋)

**위치**: 페이지 최상단, `<form>` 내부.
**변경**: 구조 유지, P1 diff 미리보기 로직 추가.

```
<details ontoggle="onPresetToggle(this, 'strict')">
  ← 펼치면 renderPresetDiff('strict', this) 호출 → diff 테이블 렌더
  ← "이 프리셋 적용 →" 버튼 (기존 즉시 적용 버튼 대체)
  ← 기존 preset-table (현재값 정적 표시) → diff 표시로 교체
</details>
```

프리셋 아코디언 내부에 표시할 diff 형식:

| 필드 | 현재값 | → | 프리셋값 |
|------|--------|---|---------|
| approve_threshold | 75 | → | **85** |
| reject_threshold | 50 | → | **60** |
| … | … | = | (변화 없음) |

변화 없는 필드는 흐리게(opacity 낮춤) 표시. "알림 채널 URL은 이 프리셋이 변경하지 않습니다" 고정 안내문 유지.

---

### 2. 📋 PR 들어왔을 때

**위치**: 고급설정 `<details>` 내 2-컬럼 그리드 좌측.
**변경**: `auto_merge` + `merge_threshold` 를 이 카드로 이동 (기존 Push 카드에서).

포함 필드 (순서):

1. `pr_review_comment` — toggle-switch
2. approve_mode 3-버튼 (`disabled` / `auto` / `semi-auto`)
3. `approve_threshold` range + number (approve_mode ≠ disabled 일 때만 표시)
4. `reject_threshold` range + number (approve_mode ≠ disabled 일 때만 표시)
5. semi-auto 힌트 블록 (approve_mode = semi-auto 일 때만 표시)
6. `auto_merge` — toggle-switch
7. `merge_threshold` range + number (auto_merge = true 일 때만 표시)

Progressive Disclosure: 기존 `setApproveMode()` + `toggleMergeThreshold()` 그대로 작동.

---

### 3. 📬 이벤트 후 피드백

**위치**: 고급설정 `<details>` 내 2-컬럼 그리드 우측 (기존 Push 카드 대체).
**변경**: 세 가지 "자동 생성" 동작을 트리거별 소제목으로 통합.

```
── Push 이후 ─────────────────────────
  ◻ commit_comment   커밋에 점수 코멘트 남기기

── 점수 미달 시 ──────────────────────
  ◻ create_issue     GitHub Issue 자동 생성

── Railway 빌드 실패 시 ──────────────
  ◻ railway_deploy_alerts   GitHub Issue 자동 생성
```

`railway_deploy_alerts`: 기존 raw `<input type=checkbox>` → **toggle-switch 통일** (UX 일관성).

---

### 4. 📢 알림 채널

**위치**: 고급설정 아코디언 밖, 항상 표시. 기존 구조 유지.
**변경**: 없음 (기존 마스킹 + 👁️ 토글 패턴 그대로).

포함 필드: `notify_chat_id`, `discord_webhook_url`, `slack_webhook_url`, `email_recipients`, `custom_webhook_url`, `n8n_webhook_url`.

---

### 5. 🔧 시스템 & 토큰

**위치**: `<form>` 바깥. 별도 POST action form들을 포함.
**변경**: 기존 ④ 시스템 카드 + ⑤ Railway 카드의 토큰/인프라 부분 통합.

포함 항목:

- **CLI Hook** — hook_ok/hook_fail 상태 배너 + 설치 명령 + "훅 파일 재커밋" 버튼 (form=reinstall_hook_form)
- **Webhook 재등록** 버튼 (form=reinstall_webhook_form)
- **Railway 통합**:
  - `railway_api_token`: `type=password` + **👁️ mask-toggle 버튼 신규 추가** (`.masked-field` 패턴으로 통일)
  - Railway Webhook URL: readonly input + 📋 클립보드 복사 버튼 (기존 유지)

`railway_api_token` 저장 방식: 기존 sentinel(`"****"` → 변경 없음) 유지. 라우터 핸들러 변경 없음.

---

### 6. ⚠️ 위험 구역

**위치**: 페이지 최하단, `<form>` 바깥. 기존 시스템 카드에서 분리.
**변경**: 독립 카드, `<details class="danger-summary">` 기본 접힘 유지.

포함: 리포 삭제 (별도 POST form + confirm()).

---

## 데이터 플로우

### 폼 제출 (변경 없음)

```
사용자 → 저장 버튼 클릭
  → POST /repos/{repo}/settings
  → RepoConfigData 파싱 (14개 필드)
  → upsert_repo_config() → DB
  → ?saved=1 redirect
```

`auto_merge`와 `merge_threshold` 가 PR 카드로 이동해도 `name=` 속성이 같으므로 form 파싱 로직 불변.

### 프리셋 적용 (P1 + P2)

**P1 — 펼침 diff 미리보기**:

```
사용자 → <details> 펼침
  → onPresetToggle(el, name) 실행
  → renderPresetDiff(name, el) 호출
      → DOM에서 현재 필드값 수집
      → PRESETS[name]과 비교
      → diff 테이블 HTML 렌더링
      → "이 프리셋 적용 →" 버튼 노출
사용자 → "이 프리셋 적용 →" 클릭
  → applyPreset(name, el) 실행 (기존)
  → flashPresetChanges(changedFields) 실행 (신규)
```

**P2 — 적용 하이라이트**:

```
flashPresetChanges(changedFields):
  → 각 changedField 의 .s-field-row (또는 .field-wrap) 에
    .preset-just-applied 클래스 추가
  → setTimeout(2500, () => 클래스 제거)
```

CSS 애니메이션 (`@keyframes preset-flash`):

```css
@keyframes preset-flash {
  0%   { box-shadow: 0 0 0 3px rgba(100, 160, 255, 0.5); background: rgba(100,160,255,0.1); }
  100% { box-shadow: 0 0 0 0   rgba(100, 160, 255, 0);   background: transparent; }
}
.preset-just-applied { animation: preset-flash 2.5s ease-out; }
```

---

## 오류 처리

- `approve_threshold < reject_threshold` 검증: 기존 서버사이드 `upsert_repo_config()` 에서 `ValueError` → `?save_error=1` redirect. **변경 없음.**
- 저장 오류 토스트는 상단에 표시되지만 고급설정 아코디언이 접혀 있으면 문제 필드를 볼 수 없음 → **개선 사항**: 저장 오류 시 고급설정 아코디언 자동 펼침 (`detail.open = true`). (이번 범위 포함)

---

## 테스트

### 기존 테스트 회귀 확인 (변경 없음이어야 함)

- `tests/test_ui_router.py` — settings GET/POST 핸들러, 현재 통과 유지
- `e2e/` — 프리셋 클릭 후 슬라이더 값 확인 테스트 통과 유지

### 신규: 렌더 스모크 테스트 (선택)

`tests/test_ui_router.py` 에 추가:

```python
def test_settings_form_fields_preserved(client, db_session):
    """settings.html 리팩토링 후 14개 form name= 속성이 모두 보존되는지 확인."""
    response = client.get("/repos/test-repo/settings")
    body = response.text
    required_names = [
        "pr_review_comment", "approve_mode", "approve_threshold", "reject_threshold",
        "commit_comment", "create_issue", "auto_merge", "merge_threshold",
        "railway_deploy_alerts", "railway_api_token",
        "notify_chat_id", "discord_webhook_url", "slack_webhook_url",
        "email_recipients", "custom_webhook_url", "n8n_webhook_url",
    ]
    for name in required_names:
        assert f'name="{name}"' in body, f"Missing form field: {name}"
```

---

## 범위 밖 (의도적 제외)

| 항목 | 제외 사유 | 권고 |
|------|----------|------|
| P3 영구 배지 (프리셋 상태 표시) | DB 스키마 확장 필요 | 별도 Phase |
| 알림 채널 암호화 통일 | 암호화 정책 결정 + 마이그레이션 필요 | 별도 Phase |
| `approve_mode` 3-버튼 접근성 (aria) | 독립적 개선 | 별도 이슈 |
| 오류 필드 직접 하이라이트 (서버 검증 실패 시) | 서버사이드 검증 응답 구조 확장 필요 | 별도 Phase |

---

## 셀프리뷰 체크리스트

- [x] Placeholder 없음 — 모든 섹션 완결
- [x] 내부 일관성 — `auto_merge` 이동이 데이터 플로우 섹션까지 반영됨
- [x] Scope 적절 — 단일 파일 리팩토링, 백엔드 변경 0
- [x] 모호성 없음 — P1의 "diff 테이블" 형식, P2의 "2.5초 타이머" 등 구체 명시
- [x] `railway_deploy_alerts` toggle-switch 통일 — HTML 구현 명시
- [x] 저장 오류 시 아코디언 자동 펼침 추가 — 오류 처리 섹션 포함
