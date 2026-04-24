#!/bin/bash
# Continuous monitor: runs v4_phase_e_monitor.py every 1h until all analyses complete.
# Use: `bash data/scripts/v4_monitor_loop.sh &` to run in background.
# Logs to data/v4_monitor_loop.log.

cd "$(dirname "$0")/../.."
LOG="data/v4_monitor_loop.log"

while true; do
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "=========== poll at $ts ===========" >> "$LOG"
  python -u data/scripts/v4_phase_e_monitor.py >> "$LOG" 2>&1
  # sleep 1h (3600s)
  sleep 3600
done
