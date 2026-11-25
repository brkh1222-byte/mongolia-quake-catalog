#!/usr/bin/env bash
# Full XL run on the cloud GPU box. One command after scripts/cloud_bootstrap.sh:
#
#   bash scripts/run_full.sh            # = all: pass1 -> pass2 -> pass3, inside tmux
#   bash scripts/run_full.sh pass1      # streaming download + GPU picking only
#   bash scripts/run_full.sh pass2      # association, location, snippets, ML, xcorr, GrowClust, analysis
#   bash scripts/run_full.sh pass3      # template matching on the 20 Hz copy
#   bash scripts/status.sh              # progress, rate, ETA, disk, GPU
#
# Everything is resumable: re-running any pass continues where it stopped
# (ledger data/ledger.sqlite and per-stage "done" files on the persistent volume).
# Tunables (env): WORKERS (pass-1 processes sharing the GPU, default 3),
#                 DL_THREADS (download threads per worker, default 4),
#                 SUBARRAYS (default "HD HV AT"; Hangay first).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO"
[ -f .cloud_env ] && source .cloud_env
PY="$REPO/.venv/bin/python"; CFG=config/cloud.yaml
WORKERS="${WORKERS:-3}"; DL_THREADS="${DL_THREADS:-4}"; SUBARRAYS="${SUBARRAYS:-HD HV AT}"
mkdir -p data/logs
span(){ case $1 in HD) echo "2012-06-10 2014-04-11";; HV|AT) echo "2014-08-05 2016-06-12";; esac; }

pass1() {
  for S in $SUBARRAYS; do set -- $(span $S); $PY src/stream_run.py init --config $CFG --stations $S --start $1 --end $2; done
  $PY src/stream_run.py mark-existing --config $CFG
  pids=()
  for i in $(seq 1 "$WORKERS"); do
    $PY src/stream_run.py run --config $CFG --device cuda --worker "gpu$i" --decimate \
        --download-threads "$DL_THREADS" --prefetch 8 >> data/logs/pass1_gpu$i.log 2>&1 &
    pids+=($!)
  done
  echo "pass 1: $WORKERS workers started (${pids[*]}); logs in data/logs/pass1_gpu*.log"
  wait "${pids[@]}"
  # retry transient errors once
  sqlite3 data/ledger.sqlite "UPDATE station_day SET status='todo' WHERE status='error'"
  $PY src/stream_run.py run --config $CFG --device cuda --worker retry --decimate --download-threads "$DL_THREADS" >> data/logs/pass1_retry.log 2>&1
  $PY src/stream_run.py status --config $CFG
}

pass2() {
  for S in $SUBARRAYS; do
    set -- $(span $S); T=full_$S; A=(--config $CFG --stations $S --start $1 --end $2)
    D=data/catalogs/$T; mkdir -p $D
    step(){ local name=$1; shift; [ -f $D/.done_$name ] && { echo "[$T] $name already done"; return; }
            echo "[$T] $name ..."; "$@" && touch $D/.done_$name; }
    step associate $PY src/associate.py "${A[@]}" --tag $T
    step locate    $PY src/locate.py    "${A[@]}" --tag $T
    step snippets  $PY src/snippets.py  "${A[@]}" --tag $T --threads 8
    step magnitude $PY src/magnitude.py "${A[@]}" --tag $T
    step xcorr     $PY src/xcorr.py     "${A[@]}" --tag $T --device cuda
    step relocate  $PY src/relocate.py  "${A[@]}" --tag $T --growclust-home "${GROWCLUST_HOME:-$HOME/GrowClust}"
    step analyze   $PY src/analyze.py   "${A[@]}" --tag $T
  done
}

pass3() {
  for S in $SUBARRAYS; do
    set -- $(span $S)
    "$REPO/.venv-tm/bin/python" src/template_match.py --config $CFG --stations $S --start $1 --end $2 \
        --tag full_$S --device cuda >> data/logs/pass3_$S.log 2>&1
  done
}

case "${1:-all}" in
  pass1) pass1 ;;
  pass2) pass2 2>&1 | tee -a data/logs/pass2.log ;;
  pass3) pass3 ;;
  all)
    if [ -z "${TMUX:-}" ]; then
      tmux new-session -d -s mqc "bash $0 all-inner; bash" && echo "started in tmux session 'mqc' (tmux attach -t mqc)"
    else
      bash "$0" all-inner
    fi ;;
  all-inner) pass1; pass2 2>&1 | tee -a data/logs/pass2.log; pass3 ;;
  *) echo "usage: $0 [all|pass1|pass2|pass3]"; exit 1 ;;
esac
