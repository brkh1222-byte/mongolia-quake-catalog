#!/usr/bin/env bash
# Run the post-picking chain on a window of picked data (Mac pilot).
#   bash scripts/run_pilot_chain.sh 2013-01-01 2013-02-01 pilot_2013-01 [steps...]
# steps default: ensemble associate locate locate_2l snippets magnitude xcorr quakescope validate analyze report
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
S=$1; E=$2; T=$3; shift 3
STEPS=${*:-ensemble associate locate locate_2l snippets magnitude xcorr relocate quakescope validate analyze report export}
PY=".venv/bin/python"; A=(--start "$S" --end "$E" --stations HD)
for step in $STEPS; do
  echo "=== $step $(date +%H:%M:%S)"
  case $step in
    ensemble)   $PY src/ensemble.py "${A[@]}" ;;
    associate)  $PY src/associate.py "${A[@]}" --tag "$T" ;;
    locate)     $PY src/locate.py "${A[@]}" --tag "$T" ;;
    locate_2l)  $PY src/locate.py "${A[@]}" --tag "$T" --vmodel config/vmodel_2layer.yaml --suffix _2layer ;;
    snippets)   $PY src/snippets.py "${A[@]}" --tag "$T" --threads 2 --local ;;
    magnitude)  $PY src/magnitude.py "${A[@]}" --tag "$T" ;;
    xcorr)      $PY src/xcorr.py "${A[@]}" --tag "$T" --device cpu ;;
    relocate)   GROWCLUST_HOME="${GROWCLUST_HOME:-$REPO/.tools/GrowClust}" $PY src/relocate.py "${A[@]}" --tag "$T" ;;
    export)     $PY src/export_catalog.py "${A[@]}" --tag "$T" ;;
    quakescope) $PY src/compare_quakescope.py "${A[@]}" --tag "$T" ;;
    validate)   $PY src/validate.py "${A[@]}" --tag "$T" ;;
    analyze)    $PY src/analyze.py "${A[@]}" --tag "$T" --pilot --faults config/gem_faults_mongolia.geojson ;;
    report)     $PY src/report_pilot.py "${A[@]}" --tag "$T" ;;
  esac 2>&1 | grep -v -iE "warn|^\s*$|warnings.warn" | tail -6
done
