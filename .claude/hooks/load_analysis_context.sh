#!/bin/bash
# UserPromptSubmit hook: 분석/실행 관련 키워드 감지 시 핵심 섹션 재주입
# Keywords: 분석, 실행, IPD, estimation, calibration, Cox, matching, outcome, comparator
#
# 섹션 추출은 라인번호가 아니라 헤더 기반(awk)으로 동작 — 문서 개정에 안전.

ROOT="g:/내 드라이브/KHNMC/atlas_auto_with_claude"
KB="$ROOT/docs/system_knowledge_base.md"

# stdin에서 prompt 추출 (Python 필요)
PROMPT=$(python -c 'import sys,json; d=json.load(sys.stdin); print(d.get("prompt",""))' 2>/dev/null)

extract_section() {
  # extract_section <file> <heading-regex>  → 해당 '## ' 헤더부터 다음 '## '까지 출력
  awk -v pat="$2" '
    /^## / { in_sec = ($0 ~ pat) ? 1 : 0 }
    in_sec { print }
  ' "$1"
}

if echo "$PROMPT" | grep -qE '분석|실행|IPD|estimation|calibration|Cox|matching|outcome|comparator'; then
  echo "=== [자동 주입] 분석·실행 키워드 감지 → system_knowledge_base §5, §7 재주입 ==="
  if [ -f "$KB" ]; then
    echo ""
    extract_section "$KB" '^## 5\. 분석 방법론'
    echo ""
    extract_section "$KB" '^## 7\. 파이프라인'
  fi
fi
