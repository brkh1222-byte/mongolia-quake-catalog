#!/usr/bin/env bash
# Pilot month template matching on the Mac (CPU, FFTW backend). Detached and resumable.
#   nohup caffeinate -i bash scripts/pilot_tm.sh > data/logs/pilot_tm.out 2>&1 &
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
S=2013-01-01; E=2013-02-01; T=pilot_2013-01
nice -n 10 .venv/bin/python scripts/decimate_local.py --start $S --end $E --stations HD
echo "$(date) decimation done: $(du -sh data/mseed20 | cut -f1)"
nice -n 10 .venv-tm/bin/python src/template_match.py --tag $T --stations HD --start $S --end $E --device cpu --backend fftw 2>&1 | grep -E "template INFO|ERROR|Traceback"
echo "$(date) PILOT TM DONE"
