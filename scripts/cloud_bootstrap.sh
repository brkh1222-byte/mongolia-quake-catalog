#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 22.04/24.04 + CUDA 12 box (RunPod / Vast.ai)
# with this repo already cloned. Idempotent: safe to re-run.
#
#   VOLUME=/workspace bash scripts/cloud_bootstrap.sh
#
# What it does
#   1. apt packages (gfortran, FFTW, build tools, tmux, rsync, sqlite3)
#   2. uv + Python 3.11 venv with the pinned packages; torch with the CUDA
#      wheel that matches the driver (uv --torch-backend=auto)
#   3. data/ -> $VOLUME/mqc-data (persistent volume), so a dead instance loses nothing
#   4. GrowClust (Fortran, official repo) build + its example as a smoke test
#   5. EQcorrscan (FFTW) + fast_matched_filter (CUDA) build + GPU smoke test
#   6. SeisBench weights pre-download, station metadata, unit tests
#   7. pass-1 smoke test on 2 stations x 2 days (CPU and GPU picks compared)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VOLUME="${VOLUME:-/workspace}"
cd "$REPO"
log(){ echo -e "\n=== $* ===" ; }

log "1. system packages"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO apt-get update -qq
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git build-essential gfortran \
    libfftw3-dev pkg-config tmux rsync sqlite3 curl ca-certificates >/dev/null
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
command -v nvcc >/dev/null && nvcc --version | tail -1 || echo "WARNING: nvcc not found (needed for fast_matched_filter GPU build); use a *-devel CUDA image"

log "2. Python env"
if ! command -v uv >/dev/null; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$PATH"
[ -d .venv ] || uv venv --python 3.11 .venv
grep -v '^torch==' requirements-lock.txt > /tmp/req-notorch.txt
uv pip install --python .venv/bin/python -r /tmp/req-notorch.txt
uv pip install --python .venv/bin/python --torch-backend=auto "torch==$(grep '^torch==' requirements-lock.txt | cut -d= -f3)" \
  || uv pip install --python .venv/bin/python --torch-backend=auto torch
PY="$REPO/.venv/bin/python"
$PY -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

log "3. data -> $VOLUME/mqc-data"
mkdir -p "$VOLUME/mqc-data"
if [ -d data ] && [ ! -L data ]; then rsync -a data/ "$VOLUME/mqc-data/" && rm -rf data; fi
[ -L data ] || ln -s "$VOLUME/mqc-data" data
df -h "$VOLUME" | tail -1

log "4. GrowClust"
GC="$VOLUME/tools/GrowClust"
[ -d "$GC" ] || git clone -q https://github.com/dttrugman/GrowClust "$GC"
( cd "$GC/SRC" && make -s ) || ( cd "$GC" && find . -name Makefile -execdir make -s \; )
GCBIN="$(find "$GC" -type f -name growclust -perm -u+x | head -1)"
echo "growclust binary: ${GCBIN:-NOT BUILT}"
EXINP="$(find "$GC" -name '*.inp' | head -1)"
if [ -n "$GCBIN" ] && [ -n "$EXINP" ]; then
  ( cd "$(dirname "$EXINP")" && timeout 600 "$GCBIN" "$(basename "$EXINP")" > /tmp/growclust_example.log 2>&1 \
    && echo "GrowClust example: OK" || echo "GrowClust example: FAILED (see /tmp/growclust_example.log)" )
fi
echo "export GROWCLUST_HOME=$GC" > "$REPO/.cloud_env"

log "5. EQcorrscan + fast_matched_filter"
uv pip install --python .venv/bin/python "eqcorrscan==0.5.2" || echo "WARNING: EQcorrscan build failed"
uv pip install --python .venv/bin/python "git+https://github.com/beridel/fast_matched_filter" || echo "WARNING: FMF build failed"
$PY - <<'PYEOF' || echo "WARNING: FMF GPU smoke test failed (template matching will fall back to FFTW on CPU)"
import numpy as np
from fast_matched_filter import matched_filter
rng = np.random.default_rng(0)
data = rng.standard_normal((1, 3, 20 * 3600)).astype(np.float32)   # (stations, components, samples)
tmpl = data[None, :, :, 1000:1080].copy()                           # (templates, stations, components, samples)
mv = np.zeros((1, 1, 3), np.int32)
w = np.full((1, 1, 3), 1 / 3, np.float32)
cc = matched_filter(tmpl, mv, w, data, 1, arch="gpu")
print("FMF gpu OK, max cc at", int(np.argmax(cc[0])), "(expect 1000)")
PYEOF
$PY -c "import eqcorrscan; print('EQcorrscan', eqcorrscan.__version__)" || true

log "6. weights, metadata, unit tests"
$PY - <<'PYEOF'
import seisbench.models as sbm
for m in ("PhaseNet", "EQTransformer"):
    for w in ("stead", "instance", "original"):
        getattr(sbm, m).from_pretrained(w)
print("SeisBench weights cached")
PYEOF
$PY src/stations.py --config config/cloud.yaml --no-map
$PY -m pytest -q tests

log "7. pass-1 smoke test: 2 stations x 2 days"
bash scripts/smoke_test.sh cuda

log "8. download throughput vs streams (sets DL_THREADS for run_full.sh)"
bash scripts/bench_download.sh "4 8 16 24" | tee data/logs/bench_download_cloud.txt
echo -e "\nBootstrap finished. Start the run with:  bash scripts/run_full.sh"
