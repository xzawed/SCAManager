# SCAManager — 4테마 역할 정의서 (Claude Design 브리프용)

## 테마 설계 원칙

- **dark** 테마를 기준(ground truth)으로 먼저 완성한다
- 나머지 3테마는 dark에서 정의한 구조와 컴포넌트를 유지하되, 색상 팔레트만 교체한다
- 4테마 모두에서 Grade A~F 색상이 명확히 구분되어야 한다 (색맹 기준 포함)
- 어떤 테마에서도 "2등급 테마"가 없어야 한다 — 완성도 동일

---

## dark — Premium Dark (기준 테마)

**성격**: 고급스럽고 예리한 개발자 도구. 야간 작업 최적화.

**색상 방향**:
- 배경: 거의 순수 검정에 가까운 깊은 어두운 색 (#07070f 계열 유지 또는 개선)
- 카드: 배경 대비 미세하게 밝은 반투명 레이어
- Accent: 인디고~보라 그라디언트 (현재 `#6366f1~#a855f7`) — 재해석 가능
- 텍스트: 따뜻한 흰색 (순수 #fff 보다 약간 따뜻하게)
- 등급 색상: 채도 높고 선명하게 — 어두운 배경에서 빛나는 효과

**무드 키워드**: 우주적(cosmic) · 정밀한(precise) · 몰입적(immersive)

---

## light — Clean Professional

**성격**: 비즈니스 미팅·데모·외부 공유에 적합한 깔끔한 전문가용 테마.

**색상 방향**:
- 배경: 순수 흰색보다 약간 차가운 오프화이트 (#f6f6fd 계열)
- 카드: 흰색 + 미세한 border
- Accent: dark와 동일한 인디고 계열 — 밝은 배경에서도 충분한 대비
- 텍스트: 따뜻한 검정 (순수 #000 보다 약간 부드럽게)
- 등급 색상: 채도를 약간 낮춰 눈부심 방지, WCAG AA 충족

**무드 키워드**: 신뢰적(trustworthy) · 명료한(clear) · 전문적(professional)

---

## pastel — Soft Focus

**성격**: 장시간 모니터 사용 시 눈 피로를 최소화하는 부드러운 테마.

**색상 방향**:
- 배경: 크림·라벤더 계열 따뜻한 오프화이트
- 카드: 배경보다 약간 밝고 따뜻한 흰색
- Accent: 파스텔 톤으로 낮춘 인디고/보라 — 자극 최소화
- 텍스트: 충분한 대비를 유지하면서 부드러운 dark gray
- 등급 색상: 파스텔 톤이되 WCAG AA 기준은 반드시 충족

**무드 키워드**: 부드러운(gentle) · 집중적(focused) · 편안한(comfortable)

---

## catppuccin — Dev Aesthetic

**성격**: IDE 테마와 조화를 이루는 개발자 서브컬처 감성. Catppuccin Mocha 팔레트 영감.

**색상 방향**:
- 배경: 따뜻한 다크 (#1e1e2e 계열 Catppuccin Mocha Base)
- 카드: Catppuccin Surface0 (#313244) 계열
- Accent: Catppuccin Mauve (#cba6f7) 또는 Lavender (#b4befe)
- 텍스트: Catppuccin Text (#cdd6f4)
- 등급 색상: Catppuccin 팔레트의 Green·Blue·Yellow·Peach·Red 대응

**참고 팔레트 (Catppuccin Mocha)**:
- Base: #1e1e2e / Mantle: #181825 / Crust: #11111b
- Surface0: #313244 / Surface1: #45475a
- Text: #cdd6f4 / Subtext0: #a6adc8
- Mauve: #cba6f7 / Lavender: #b4befe / Green: #a6e3a1
- Blue: #89b4fa / Yellow: #f9e2af / Peach: #fab387 / Red: #f38ba8

**무드 키워드**: 미적(aesthetic) · 취향적(opinionated) · 친숙한(familiar to devs)
