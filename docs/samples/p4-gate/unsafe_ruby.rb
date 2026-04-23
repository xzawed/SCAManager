# P4-Gate-2 RuboCop 실증 샘플 — 외부 테스트 리포 PR 에 포함해 분석 결과 검증.
# 의도적 결함 (Security + Style):
#   1) Security/YamlLoad — YAML.load 대신 YAML.safe_load 권장 (security)
#   2) Security/Open — Kernel#open (URL 호출 가능) (security)
#   3) Security/Eval — eval 사용 (security)
#   4) Style/StringLiterals — 단일따옴표/이중따옴표 일관성 (code_quality)
#   5) Lint/UselessAssignment — 사용되지 않는 지역 변수 (code_quality)

require 'yaml'

def load_config(path)
  # Security/YamlLoad
  YAML.load(File.read(path))
end

def fetch_content(url)
  # Security/Open — URL 호출 가능
  open(url).read
end

def run_expression(expr)
  # Security/Eval
  eval(expr)
end

def greeting
  # Style/StringLiterals — 프로젝트 기본 = single quotes 가정 시 경고
  message = "hello world"
  # Lint/UselessAssignment — unused 가 사용되지 않음
  unused = 42
  puts message
end

greeting
