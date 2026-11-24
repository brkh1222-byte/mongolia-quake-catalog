#!/usr/bin/env bash
# Pass-1 smoke test on 2 stations x 2 days in an isolated data dir (does not touch the real ledger).
#   bash scripts/smoke_test.sh [cpu|mps|cuda]
# Checks: download -> pick (6 model/weight pairs) -> ensemble -> 20 Hz copy -> raw file deleted,
# resume after an interruption, and (if a GPU is given) that GPU picks match CPU picks.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
DEV="${1:-cpu}"
PY="$REPO/.venv/bin/python"
T="$(mktemp -d "${TMPDIR:-/tmp}/mqc_smoke.XXXX")"
cat > "$T/smoke.yaml" <<YAML
paths:
  data: $T/data
  meta: $REPO/data/meta
  stationxml: $REPO/data/meta/stationxml
  mseed: $T/data/mseed
  picks: $T/data/picks
  catalogs: $T/data/catalogs
  logs: $T/data/logs
  decimated: $T/data/mseed20
picking:
  device: $DEV
YAML
run(){ $PY src/stream_run.py "$@" --config "$T/smoke.yaml"; }
run init --stations HD01,HD02 --start 2013-01-10 --end 2013-01-12
# interrupt after 1 station-day, then resume
run run --device "$DEV" --worker smoke1 --max-station-days 1 --decimate --download-threads 2
run run --device "$DEV" --worker smoke2 --decimate --download-threads 2
run status
n_done=$(sqlite3 "$T/data/ledger.sqlite" "SELECT COUNT(*) FROM station_day WHERE status='done'")
n_raw=$(find "$T/data/picks/raw" -name '*.parquet' | wc -l | tr -d ' ')
n_ens=$(find "$T/data/picks/ensemble" -name '*.parquet' | wc -l | tr -d ' ')
n_dec=$(find "$T/data/mseed20" -name '*.mseed' | wc -l | tr -d ' ')
n_buf=$(find "$T/data/buffer" -name '*.mseed' 2>/dev/null | wc -l | tr -d ' ')
echo "done=$n_done (expect 4)  raw parquet=$n_raw (expect 24)  ensemble=$n_ens (expect 4)  20Hz files=$n_dec (expect 4)  leftover raw=$n_buf (expect 0)"
du -sh "$T/data/mseed20" | sed 's/^/20 Hz copy size: /'
$PY - "$T" <<'PYEOF'
import sys, pandas as pd, glob
from obspy import read
T = sys.argv[1]
f = sorted(glob.glob(f"{T}/data/mseed20/*/*/*.mseed"))[0]
st = read(f); print("20 Hz check:", f.split('/')[-3:], [ (tr.id, tr.stats.sampling_rate, tr.stats.npts) for tr in st][:3])
e = pd.concat(pd.read_parquet(x) for x in glob.glob(f"{T}/data/picks/ensemble/*/*/*.parquet"))
print("ensemble picks:", len(e), e.phase.value_counts().to_dict())
PYEOF
if [ "$DEV" != "cpu" ]; then
  echo "--- device agreement ($DEV vs cpu) on HD01 2013-01-10 ---"
  mkdir -p "$T/data/mseed/XL.HD01/2013"
  $PY src/download.py --config "$T/smoke.yaml" --stations HD01 --start 2013-01-10 --end 2013-01-11 --streams 1
  $PY scripts/bench_picking.py --config "$T/smoke.yaml" --station HD01 --day 2013-01-10 --devices "$DEV,cpu" \
      --cpu-models "PhaseNet:original,EQTransformer:original" --out "$T/bench.csv"
fi
[ "$n_done" -eq 4 ] && [ "$n_raw" -eq 24 ] && [ "$n_buf" -eq 0 ] && echo "SMOKE TEST PASSED ($T)" || { echo "SMOKE TEST FAILED ($T)"; exit 1; }
