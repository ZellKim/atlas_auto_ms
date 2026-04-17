#!/bin/bash
# UserPromptSubmit hook: 분석/실행 관련 키워드 감지 시 핵심 섹션 재주입
# Keywords: 분석, 실행, IPD, estimation, calibration, Cox, matching, outcome, comparator

ROOT="g:/내 드라이브/KHNMC/atlas_auto_with_claude"
KB="$ROOT/docs/system_knowledge_base.md"

# stdin에서 prompt 추출 (Python, jq 없는 환경 지원)
PROMPT=$(python -c 'import sys,json; d=json.load(sys.stdin); print(d.get("prompt",""))' 2>/dev/null)

if echo "$PROMPT" | grep -qE '분석|실행|IPD|estimation|calibration|Cox|matching|outcome|comparator'; then
  echo "=== [자동 주입] 분석·실행 키워드 감지 → system_knowledge_base §5, §7 재주입 ==="
  if [ -f "$KB" ]; then
    echo ""
    echo "--- §5 분석 방법론 ---"
    sed -n '241,256p' "$KB"
    echo ""
    echo "--- §7 파이프라인 + 체크리스트 ---"
    sed -n '267,324p' "$KB"
  fi
fi
