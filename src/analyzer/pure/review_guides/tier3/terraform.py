"""Terraform/HCL review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Terraform review checklist
- **Security**: No hardcoded secrets → `var.` / env vars / Vault; block S3 public access
- **State**: Remote state backend required (no local tfstate); state locking (DynamoDB)
- **Modules**: Pin module versions (`source = "... version = ..."`); minimal reusable interfaces
- **Variables**: Constrain `variable` types (`type = string`); `sensitive = true` for sensitive vars
- **Naming**: Resource naming convention (`{env}_{service}_{resource}`); common `tags`
- **Idempotency**: Review `plan` output — verify no unintended destroy/replace (force-new resource)
- **Security groups**: Least privilege; minimize `0.0.0.0/0` ingress
"""

COMPACT = "## Terraform: no hardcoded secrets, remote state+lock, pin modules, sensitive vars, review plan"

FULL_KO = """\
## Terraform 검토 기준
- **보안**: 시크릿 하드코딩 금지 → `var.`/환경변수/Vault, S3 버킷 퍼블릭 접근 차단
- **상태**: remote state backend 필수(로컬 tfstate 금지), state locking(DynamoDB)
- **모듈**: 모듈 버전 고정(`source = "... version = ..."`), 재사용 가능한 최소 인터페이스
- **변수**: `variable` 타입 제약(`type = string`), `sensitive = true` 민감 변수
- **명명**: 리소스 명 규칙(`{env}_{service}_{resource}`), `tags` 공통 태그
- **멱등성**: `plan` 결과 검토 — 의도치 않은 삭제/교체(force new resource) 확인
- **보안 그룹**: 최소 권한 원칙, `0.0.0.0/0` ingress 최소화
"""

COMPACT_KO = "## Terraform: 시크릿 하드코딩 금지, remote state+locking, 모듈 버전 고정, sensitive 변수, plan 검토"

FULL_JA = """\
## Terraform レビュー基準
- **セキュリティ**: シークレットのハードコード禁止 → `var.` / 環境変数 / Vault、S3 バケットの公開アクセスをブロック
- **状態**: remote state backend 必須 (ローカル tfstate 禁止)、state locking (DynamoDB)
- **モジュール**: モジュールバージョン固定 (`source = "... version = ..."`)、再利用可能な最小インターフェース
- **変数**: `variable` 型制約 (`type = string`)、機密変数に `sensitive = true`
- **命名**: リソース命名規則 (`{env}_{service}_{resource}`)、共通の `tags`
- **冪等性**: `plan` 結果のレビュー — 意図しない削除/置換 (force new resource) を確認
- **セキュリティグループ**: 最小権限原則、`0.0.0.0/0` ingress を最小化
"""

COMPACT_JA = "## Terraform: シークレット禁止、remote state+locking、モジュールバージョン固定、sensitive 変数、plan レビュー"
