#!/usr/bin/env bash
# Run ON THE MAC. Pull results (no waveforms) from the cloud box.
#   REMOTE=root@1.2.3.4 PORT=22 REMOTE_REPO=/workspace/mongolia-quake-catalog bash scripts/sync_back.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
: "${REMOTE:?set REMOTE=user@host}"; PORT="${PORT:-22}"; RR="${REMOTE_REPO:-/workspace/mongolia-quake-catalog}"
rsync -az --info=progress2 -e "ssh -p $PORT" \
  --include='ledger.sqlite' --include='picks/***' --include='catalogs/***' --include='snippets/***' \
  --include='logs/***' --include='meta/***' --exclude='*' "$REMOTE:$RR/data/" "$REPO/data/"
rsync -az -e "ssh -p $PORT" "$REMOTE:$RR/results/" "$REPO/results/"
echo "synced. bash scripts/status.sh --local"
