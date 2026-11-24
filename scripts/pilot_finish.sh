#!/usr/bin/env bash
# Detached finisher for the pilot month: waits until picking is complete, then runs
# the full chain, the strict-ensemble comparison and the report. Safe to rerun.
#   nohup caffeinate -i bash scripts/pilot_finish.sh > data/logs/pilot_finish.out 2>&1 &
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
S=2013-01-01; E=2013-02-01; T=pilot_2013-01; PY=.venv/bin/python
until grep -q "PILOT PICKING DONE" data/logs/pilot_pick.out 2>/dev/null && ! pgrep -f "pilot_pick_loop.sh" >/dev/null; do sleep 300; done
echo "$(date) picking complete; running chain"
nice -n 10 bash scripts/run_pilot_chain.sh $S $E $T
# strict-ensemble comparison (D17)
nice -n 10 $PY src/ensemble.py --start $S --end $E --stations HD --min-prob 0.3 --ensemble-name ens_strict 2>&1 | tail -1
nice -n 10 $PY src/associate.py --start $S --end $E --stations HD --tag ${T}_strict --ensemble-name ens_strict 2>&1 | grep PyOcto
nice -n 10 $PY src/locate.py --start $S --end $E --stations HD --tag ${T}_strict 2>&1 | grep -E "quality|removed"
# QuakeScope picks through the same associator and locator
nice -n 10 $PY scripts/associate_quakescope.py --start $S --end $E --tag ${T}_qs 2>&1 | tail -3
$PY src/report_pilot.py --start $S --end $E --stations HD --tag $T > /dev/null 2>&1
echo "$(date) PILOT FINISH DONE"
