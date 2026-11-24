#!/usr/bin/env bash
# Resilient pilot download: batches of 100 station-days; a watchdog kills a batch
# that makes no progress for 15 min (hung sockets after a network outage) and retries.
#   caffeinate -i bash scripts/pilot_download_loop.sh 2013-01-01 2013-02-01 HD 4
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
S=$1; E=$2; ST=$3; N=${4:-4}; LOG=data/logs/download_timing.csv
while true; do
  left=$(.venv/bin/python src/download.py --start $S --end $E --stations $ST --dry-run 2>&1 | sed -n 's/.*, \([0-9]*\) station-days to fetch.*/\1/p')
  echo "$(date) remaining: $left"
  [ "${left:-1}" = "0" ] && break
  nice -n 10 .venv/bin/python src/download.py --start $S --end $E --stations $ST --streams $N --limit 100 --tag pilot &
  pid=$!; last=$(wc -l < $LOG 2>/dev/null || echo 0); idle=0
  while kill -0 $pid 2>/dev/null; do
    sleep 60; now=$(wc -l < $LOG 2>/dev/null || echo 0)
    if [ "$now" = "$last" ]; then idle=$((idle+1)); else idle=0; last=$now; fi
    if [ $idle -ge 15 ]; then echo "$(date) watchdog: no progress for 15 min, restarting"; kill $pid; sleep 5; kill -9 $pid 2>/dev/null; fi
  done
done
echo "$(date) PILOT DOWNLOAD DONE"
