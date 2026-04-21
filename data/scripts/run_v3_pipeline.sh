#!/bin/bash
# Run v3 main analysis then v3 LOSO sequentially.
set -e
cd "g:/내 드라이브/KHNMC/atlas_auto_with_claude"
RSCRIPT="C:/Program Files/R/R-4.5.2/bin/Rscript.exe"

echo "=== [1/2] v3 MAIN analysis starting $(date -u +%H:%M:%S) ==="
"$RSCRIPT" R/v4_main_365d_analysis_v3_clinicalstate.R
echo "=== v3 MAIN done $(date -u +%H:%M:%S) ==="

echo "=== [2/2] v3 LOSO starting $(date -u +%H:%M:%S) ==="
"$RSCRIPT" R/v4_loso_sensitivity_v3.R
echo "=== v3 LOSO done $(date -u +%H:%M:%S) ==="

echo "=== PIPELINE COMPLETE ==="
