#!/usr/bin/env bash
# Pilot month on the Mac: keep picking (MPS) behind a running download until it finishes.
#   caffeinate -i bash scripts/pilot_pick_loop.sh 2013-01-01 2013-02-01 HD
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
S=${1:-2013-01-01}; E=${2:-2013-02-01}; ST=${3:-HD}; DEV=${DEV:-mps}
while pgrep -f "pilot_download_loop.sh $S" >/dev/null || pgrep -f "src/download.py --start $S" >/dev/null; do
  nice -n 10 .venv/bin/python src/pick.py --start $S --end $E --stations $ST --device $DEV --require-next-day >> data/logs/pilot_pick.out 2>&1
  sleep 120
done
nice -n 10 .venv/bin/python src/pick.py --start $S --end $E --stations $ST --device $DEV >> data/logs/pilot_pick.out 2>&1
echo "PILOT PICKING DONE $(date)" >> data/logs/pilot_pick.out
