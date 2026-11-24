#!/usr/bin/env bash
# Short progress report. On the cloud box:  bash scripts/status.sh
# From the Mac (after scripts/sync_back.sh): bash scripts/status.sh --local
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
PY="$REPO/.venv/bin/python"; CFG=config/cloud.yaml; [ "${1:-}" = "--local" ] && CFG=config/default.yaml
echo "== pass 1 (ledger)"; $PY src/stream_run.py status --config $CFG 2>/dev/null | grep -v INFO
echo "== pass 2"; for d in data/catalogs/full_*; do [ -d "$d" ] && echo "$(basename $d): $(ls $d/.done_* 2>/dev/null | sed 's/.*done_//' | tr '\n' ' ')"; done
echo "== pass 3"; for d in data/catalogs/full_*/templates; do [ -f "$d/done_days.txt" ] && echo "$d: $(wc -l < $d/done_days.txt) days, $(cat $d/detections/*.csv 2>/dev/null | grep -vc template) detections"; done
echo "== disk"; df -h data/ | tail -1; du -sh data/mseed20 data/picks data/snippets 2>/dev/null
command -v nvidia-smi >/dev/null && { echo "== GPU"; nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader; }
echo "== recent errors"; grep -h -E "ERROR|Traceback" data/logs/*.log 2>/dev/null | tail -5
