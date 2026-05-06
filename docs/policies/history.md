# 사용자 협업 정책 진화 이력

> CLAUDE.md 분리 후속 (사이클 85 정리, 2026-05-06). 정책 본문의 "사이클 N 진화" 누적 이력 archive 영역 (Q3 권고 default 채택).
>
> **현재 상태**: 정책 본문은 CLAUDE.md 에 default rule + WHY/HOW 만 보존. 사이클 N 진화 entry 누적은 본 문서로 점진적 이전 (Phase 2 — 사이클 86+ 후속 작업 default).

## 추출 대상 영역 (사이클 86+ 점진적 작업)

다음 정책 본문 안의 "사이클 N 진화" / "사이클 N 정정" / "사이클 N 강화" 영역 본문은 본 문서로 이전 후 CLAUDE.md 에서 압축:

| 정책 | 진화 entry 카운트 (실측) | 이전 우선순위 |
|------|------------------------|---------------|
| 정책 1 (옵션 + 장단점 표) | 진화 강화 1건 (사이클 84 Q1 — 다중 PR 빠른 진행 신호 ≥ 10회) | Medium |
| 정책 2 (PR 본문 검증 섹션) | 진화 1건 (Phase 종료 일괄 회신) + sync 실측 의무 (사이클 67) | Low |
| 정책 3 (자율 판단 보고) | 진화 강화 1건 (사이클 84 — ⚠️ 마커 정량 기준 5조건) + MCP 자율 실행 결과 별도 섹션 | High |
| 정책 5 (사이클 종료 신호) | 강화 2건 (Phase 단계별 + cross-reference 강화) + NEW-P0-N 예외 | High |
| 정책 7 (PR 단위 응집) | 강화 2건 (응집 = URL+화면+데이터 3종 + 단일 큰 PR 사전 확인) | High |
| 정책 8 (회고 5+1) | 진화 2건 (단일 작업일 ≥5 dispatch + dispatch vs invocation 구분) + cross-verify ROI 정량 | High |
| 정책 9 (회고 자유 발언) | 완화 1건 (사이클 83 — 회신 부재 default = 자율 판단 보고) | Medium |
| 정책 10 (PR 직접 생성) | 환경 관련 fix-up commit format 진화 | Low |
| 정책 11 (UI/시각 검증) | 강화 1건 (Phase 종료 누적 회신 묶음 + 인증 flow 검증 추가) | Medium |
| 정책 16 (단순화 default) | 5번째 원칙 추가 (사이클 72 — 토큰 비용 효율) + 4 단계 caching timeline | High |

## 이전 default 패턴

CLAUDE.md 에 보존할 형식:
```markdown
#### 정책 N: <한 줄 default rule>

<2~3 문장 WHY + HOW 본문>

> 진화 이력: [`docs/policies/history.md#정책-n`](docs/policies/history.md#정책-n) (사이클 진화 entry 누적)
```

## 사이클 86+ 작업 default

본 문서는 사이클 85 정책 16 4번 원칙 (사용처 ≥ 3) 정합 분리 default 를 따른다 — 즉, 정책 본문에서 진화 entry 가 누적되어 매 작업 의무 영역 (default rule) 의 가독성을 침해할 때 이전한다.

**사이클 85 시점**: 정책 본문 진화 entry 가 누적된 상태이지만 이전 작업은 사이클 86+ 점진적 작업으로 default. 본 문서는 분리 의도 + 추출 대상 영역 매트릭스 보존 영역.
