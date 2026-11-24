#!/usr/bin/env bash
# Measure EarthScope download throughput vs parallel streams on THIS machine
# (writes into a scratch data dir, then deletes the waveforms).
#   bash scripts/bench_download.sh "4 8 16 24"
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
PY="$REPO/.venv/bin/python"; LEVELS="${1:-4 8 16}"
T="${BENCH_DIR:-$REPO/data/bench_dl}"; mkdir -p "$T"
cat > "$T/bench.yaml" <<YAML
paths: {mseed: $T/mseed, logs: $T/logs, meta: $REPO/data/meta}
YAML
day=1
for n in $LEVELS; do
  # a fresh set of station-days per level (different days of May 2013, all HD stations)
  s=$(printf "2013-05-%02d" $day); day=$((day+2)); e=$(printf "2013-05-%02d" $day)
  $PY src/download.py --config "$T/bench.yaml" --stations HD --start $s --end $e --streams $n --limit $((n*6)) --tag "cloud_bench$n" 2>&1 | grep finished
done
cp "$T/logs/download_timing.csv" "$REPO/data/logs/download_timing_cloud_bench.csv"
$PY - "$T/logs/download_timing.csv" <<'PYEOF'
import sys, pandas as pd
d = pd.read_csv(sys.argv[1]); d = d[d.status == "ok"]
for tag, g in d.groupby("tag", sort=False):
    span = g.finished.max() - (g.finished.min() - g.seconds[g.finished.idxmin()])
    print(f"{tag}: {len(g)} station-days, {g.bytes.sum()/1e6/span:.1f} MB/s total, {(g.bytes/g.seconds).median()/1e6:.2f} MB/s per stream")
PYEOF
rm -rf "$T/mseed"
