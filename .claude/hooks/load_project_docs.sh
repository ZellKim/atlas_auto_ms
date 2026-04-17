#!/bin/bash
# SessionStart hook: 프로젝트 주요 문서를 context에 주입
# - docs/system_knowledge_base.md (API, 파이프라인, 이슈 해결)
# - studies/appendectomy/study_knowledge_base.md (연구 설계)
# - studies/appendectomy/PROGRESS.md (현재 진행 상황)
# - studies/appendectomy/docs/irb_protocol.md (IRB 프로토콜)

ROOT="g:/내 드라이브/KHNMC/atlas_auto_with_claude"

cat <<'HEADER'
=== [자동 주입] 프로젝트 문서 — 분석·실행 전 반드시 참조 ===
HEADER

for f in \
  "docs/system_knowledge_base.md" \
  "studies/appendectomy/study_knowledge_base.md" \
  "studies/appendectomy/PROGRESS.md" \
  "studies/appendectomy/docs/irb_protocol.md"
do
  if [ -f "$ROOT/$f" ]; then
    echo ""
    echo "=== $f ==="
    cat "$ROOT/$f"
  fi
done
