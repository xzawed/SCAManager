# SCAManager

GitHub Repository에 Push된 코드를 정적 분석하여 커밋 메시지 및 변경 내용을 검토하고, 점수와 개선 사항을 개발자에게 피드백하는 서비스.

## 프로젝트 개요

- **목적**: GitHub Webhook을 통해 코드 변경을 감지하고, 정적 분석 + AI 기반 코드 리뷰를 자동으로 수행
- **주요 기능**:
  - GitHub Webhook 수신 및 커밋/PR 이벤트 처리
  - 커밋 메시지 품질 검토 (컨벤션, 명확성, 연관성)
  - 코드 변경 내용 정적 분석 (품질, 보안, 스타일)
  - 구현 방향성 검토 (아키텍처, 패턴 적합성)
  - 점수 산정 및 개선 제안 생성
  - 개발자에게 피드백 전달 (GitHub Comment, Slack, Email 등)

## 아키텍처 구조 (예정)

```
SCAManager/
├── src/
│   ├── webhook/       # GitHub Webhook 수신 및 이벤트 파싱
│   ├── analyzer/      # 정적 분석 엔진 (코드, 커밋 메시지)
│   ├── scorer/        # 점수 산정 로직
│   ├── reviewer/      # AI 기반 코드 리뷰 및 개선사항 생성
│   ├── notifier/      # 개발자 피드백 전달 (GitHub, Slack 등)
│   └── config/        # 설정 관리 (분석 규칙, 점수 기준 등)
├── tests/
└── docs/
```

## 핵심 도메인 개념

- **Commit Review**: 커밋 메시지 컨벤션 준수 여부, 변경 범위와의 일치성 검토
- **Code Analysis**: 정적 분석 도구를 통한 코드 품질, 보안 취약점, 스타일 검사
- **Direction Review**: 변경 내용이 올바른 구현 방향(패턴, 설계 원칙)인지 검토
- **Score**: 각 항목별 점수 합산 및 등급 부여
- **Feedback**: GitHub PR Comment, 커밋 Status Check, 외부 채널 알림

## 외부 연동

- **GitHub API / Webhooks**: 코드 변경 감지, PR/커밋 정보 수집, 결과 코멘트
- **정적 분석 도구**: ESLint, SonarQube, Semgrep 등 (언어별 선택)
- **AI 모델**: Claude API — 코드 리뷰 및 개선 방향 제안에 활용
- **알림 채널**: GitHub Check, Slack, Email (구성에 따라)

## 개발 시 주의사항

- Webhook 이벤트는 멱등성(idempotency)을 보장해야 함 (중복 처리 방지)
- GitHub API Rate Limit 고려 — 대용량 diff는 청크 분할 처리
- 분석 규칙과 점수 기준은 외부 설정(config)으로 분리하여 유연하게 관리
- 개인정보/시크릿이 코드에 포함될 수 있으므로 분석 로그 관리 주의
- PR 단위와 커밋 단위 분석을 명확히 구분하여 처리

## TODO (초기 설정 후 업데이트 필요)

- [ ] 기술 스택 확정 후 빌드/실행 명령어 추가
- [ ] 환경 변수 목록 정리 (`GITHUB_TOKEN`, `CLAUDE_API_KEY` 등)
- [ ] 테스트 실행 방법 추가
- [ ] 배포 방식 및 인프라 구성 추가
