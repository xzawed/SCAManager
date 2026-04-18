# Settings Page UI/UX 리디자인 v2 — 프리셋 + Progressive Disclosure

**날짜:** 2026-04-17
**상태:** 구현 완료
**관련 커밋:** `1ecb317`(4카드 재그룹핑), `45cda4f`(프리셋 카드)
**선행 문서:** [2026-04-09-settings-ui-redesign-design.md](./2026-04-09-settings-ui-redesign-design.md)

---

## 배경 및 목적

v1(2026-04-09)에서 테마 변수화·2컬럼 그리드·슬라이더+숫자 입력 쌍을 도입했으나, 실제 운영 과정에서 다음 불편이 드러났다.

1. **카드 7개 · 필드 15개로 수직 스크롤 과다** — 모바일 1컬럼 시 약 2800~3200px
2. **기본값으로 충분한 필드도 항상 노출** — 비활성 Approve 모드에서 슬라이더가 보여 "뭘 만져야 하나?" 혼동 유발
3. **"알림" 성격이 두 카드(③ 알림 채널, ⑤ Push 분석 알림)로 분산** — 분류 기준 불일관
4. **진짜 필수 입력 필드가 0개**인데도 UI는 모든 옵션을 항상 펼쳐 보여 불필요한 의사결정 부담

사용자 요구: **"가능한 간소화 + 최소의 터치로 설정 완료"**

백엔드 스키마(ORM · `RepoConfigData` · API body)는 **변경 없이** 템플릿·UI만 리디자인.

---

## 최종 디자인 결정

| 항목 | 결정 |
|------|------|
| 카드 수 | **7 → 4**로 재그룹핑 ("언제 발송되나" 축) |
| 진입 경로 | **상단 프리셋 3버튼 + 하단 커스텀 4카드** 이중 흐름 |
| 기본값 노출 | Progressive Disclosure — 토글 상태에 따라 세부 옵션 자동 show/hide |
| 알림 URL | 프리셋 영향 받지 않음 (사용자 고유값 보호) |
| 위험 구역 | `<details>` 접힘 — 오탭 방지 |

---

## 카드 재그룹핑 (7 → 4)

| 새 카드 | 헤더 | 포함 항목 | 재편 근거 |
|---------|------|-----------|-----------|
| ① **PR 동작** | `hdr-gate` | `pr_review_comment` / `approve_mode` 3-way / `approve_threshold`·`reject_threshold` / `notify_chat_id`(semi-auto 선택 시 조건부) | "PR 열릴 때 일어나는 일" 축. Telegram Chat ID는 semi-auto 전용이므로 여기로 이동 |
| ② **Push 동작** | `hdr-merge` | `commit_comment` / `create_issue` / `auto_merge` + `merge_threshold` | "Push/merge 시점 자동화" 축. Auto Merge도 merge 시점 동작이므로 병합 |
| ③ **알림 채널** | `hdr-notify` | 5개 URL (Discord/Slack/Email/Custom/n8n) 2-컬럼 `channel-grid` | "어디로 보내는가" 축. Telegram Chat ID는 ①로 이전 |
| ④ **시스템** | `hdr-hook` | CLI Hook 재커밋 / Webhook 재등록 / `<details>` 위험 구역 | 운영/관리 축 |

결과: **카드 수 43% 감소**, 헤더 그라디언트가 기능 축과 일치.

---

## Progressive Disclosure 규칙

JS에서 토글/버튼 상태 변화에 따라 `.is-hidden` 클래스를 토글해 세부 옵션을 자동 show/hide 한다.

| 트리거 | 대상 | 동작 |
|--------|------|------|
| `approve_mode = "disabled"` | `#approveThresholds` | 승인·반려 슬라이더·hint 숨김 |
| `approve_mode = "semi-auto"` | `#telegramChatRow` | Telegram Chat ID 인라인 노출 |
| `auto_merge = OFF` | `#mergeThresholdRow` | Merge 임계값 슬라이더 숨김 |

초기 렌더링 시 서버 측 Jinja2가 `{% if ... %}is-hidden{% endif %}`로 초기 상태를 결정, 이후 JS가 동일 클래스를 토글하는 방식.

### 값 보존 원칙

`.is-hidden` 요소는 `display:none`이지만 DOM에는 존재하므로 **폼 제출 시 값이 함께 submit됨**. 예를 들어 Approve 모드를 `disabled`로 바꿔도 기존 Telegram Chat ID는 DB에 그대로 보존되며, 나중에 `semi-auto`로 복귀하면 자동으로 다시 사용 가능.

---

## 프리셋 시스템 (🚀 빠른 설정)

상단 카드에 3개 프리셋 버튼 배치. 원클릭으로 관련 필드 일괄 세팅 후 사용자가 `저장` 버튼으로 확정.

| 프리셋 | 🌱 최소 | ⚙️ 표준 | 🛡️ 엄격 |
|--------|---------|---------|---------|
| `pr_review_comment` | ✓ | ✓ | ✓ |
| `commit_comment` | ✗ | ✓ | ✓ |
| `create_issue` | ✗ | ✗ | ✓ |
| `approve_mode` | disabled | auto | auto |
| `auto_merge` | ✗ | ✗ | ✓ |
| `approve_threshold` | 75 | 75 | 85 |
| `reject_threshold` | 50 | 50 | 60 |
| `merge_threshold` | 75 | 75 | 85 |
| 알림 채널 URL | **변경 안 함** | **변경 안 함** | **변경 안 함** |

### 자동 submit 하지 않는 이유

프리셋 클릭 시 값만 세팅하고 **즉시 저장하지 않음**. 사용자가 값 확인 후 일부 커스텀할 수 있는 여지를 남기는 안전 장치. 피드백은 토스트 "✅ [이름] 프리셋 적용됨 — 저장 버튼을 눌러주세요"로 제공.

### JS 헬퍼 구조

```javascript
const PRESETS = { minimal: {...}, standard: {...}, strict: {...} };
applyPreset(name, btn)
  ├─ 토글 4개 checkbox 설정
  ├─ _setPair() — 슬라이더 + 숫자 인풋 동기화 (3쌍)
  ├─ setApproveMode() 재사용 — approve_mode 상태 + Progressive Disclosure
  ├─ toggleMergeThreshold() 재사용 — merge 슬라이더 show/hide
  ├─ hint 텍스트 동적 업데이트
  ├─ recently-applied 하이라이트
  └─ _showPresetToast() — 3.6초 후 자동 소멸
```

---

## 터치 수 시나리오

| 시나리오 | v1 (7카드) | v2 (4카드 + 프리셋) |
|----------|-----------|---------------------|
| 기본값 그대로 저장 | 1터치 (필드 15개 피로) | **1터치** (보이는 필드 3~4개) |
| 표준 설정 적용 | 5~7터치 (개별 조정) | **2터치** (프리셋 + 저장) |
| Telegram만 연결 | 3터치 + 눈 탐색 | 3터치 (탐색 0) |
| Auto Merge 활성화 | 4터치 | 3터치 |
| 반자동 Approve 설정 | 5터치 (카드 이동) | 3터치 (같은 카드 내 완결) |

---

## 모바일 최적화

- 1컬럼 전환 시 세로 길이: **약 2800~3200px → 약 1100~1400px (55~60% 감소)**
- 프리셋 버튼 3개도 모바일에서 세로 3단으로 전환 (`@media max-width:640px`)
- `<details>` 접힘으로 위험 구역의 모바일 오탭 방지

---

## 수정 파일

- `src/templates/settings.html` — 전면 재구성
  - 상단 프리셋 카드 추가 (L217-247)
  - `.is-hidden`, `.hdr-preset`, `.preset-*`, `.channel-grid`, `.s-divider`, `.s-section-label`, `.danger-summary` CSS 추가
  - 4카드 구조 재작성 + Progressive Disclosure JS
  - `<details>` 위험 구역

**무변경** — 백엔드 필드명 보존으로 영향 전파 차단:
- `src/ui/router.py` `update_repo_settings` 폼 파서
- `src/config_manager/manager.py` `RepoConfigData`
- `src/models/repo_config.py` ORM
- `src/api/repos.py` API body

---

## 검증

1. `make test` — 기존 504 단위 테스트 전체 통과 (HTML 변경이므로 pytest가 렌더 구조를 직접 검증하지 않음; UI 라우터 49개는 그대로 green)
2. 브라우저 수동 확인:
   - 3개 프리셋 버튼 각각 클릭 → 필드 변경 + 토스트 등장
   - Approve 3-way 모드 전환 → 슬라이더·Telegram 인풋 show/hide
   - Auto Merge 토글 → Merge 임계값 show/hide
   - 프리셋 적용 후 저장 → `?saved=1` 토스트
3. 3개 테마(Dark/Light/Glass) 시각 확인
4. Chrome DevTools 모바일 에뮬레이터 375px — 1컬럼 세로 길이 측정

---

## 향후 확장 여지 (미구현)

| 단계 | 내용 | 트리거 조건 |
|------|------|-------------|
| Phase 3 | 알림 채널 "칩 추가" UI + 요약 배지 | 채널 수 추가 요청 발생 시 |
| Phase 4 | 카드 헤더 상태 배지 (기본값/커스텀) + 변경 diff 카운트 | 저장 전 실수 방지 피드백 필요 시 |
| — | `reject ≥ approve` 인라인 실시간 경고 | 현재는 저장 후 토스트로만 안내 |
