# Cloud runbook: full XL run on one rented RTX 4090

The Mac is used for development and for the pilot month (January 2013, Hangay). The full run streams all of XL through one rented GPU box. It downloads a station-day, picks it, keeps only the picks and a 20 Hz copy, and deletes the raw file. No 1.3 TB disk is needed.

## 0. What to rent

| Item | Choice | Why |
|---|---|---|
| GPU | 1× RTX 4090 (24 GB) | Picking and FMF template matching are FP32-bound. 24 GB holds every model at batch 1024 with room to spare |
| Image | Ubuntu 22.04/24.04 **CUDA 12 *devel*** image (needs `nvcc` for fast_matched_filter), e.g. RunPod "PyTorch 2.x / CUDA 12" devel templates | |
| vCPU / RAM | ≥ 12 vCPU, ≥ 32 GB RAM | SeisBench pre/post-processing runs on the CPU (10–30 % of picking time on the Mac). Three pick workers plus downloads |
| Persistent volume | **400 GB** (see disk budget) | The ledger, picks, 20 Hz copy and snippets survive a dead instance |
| Network | a US data centre if possible | EarthScope serves from AWS us-west-2. The Mac's link to the US capped at ~4.5 MB/s (see below) |
| Pricing | on-demand community/secure cloud, ~$0.35–0.70/h | |

## 1. One-command start

```bash
# on the box, as the default user (root on RunPod)
cd /workspace && git clone https://github.com/brkh1222-byte/mongolia-quake-catalog && cd mongolia-quake-catalog
git checkout research-plan
VOLUME=/workspace bash scripts/cloud_bootstrap.sh      # ~15–30 min, idempotent
bash scripts/run_full.sh                                # pass1 -> pass2 -> pass3 inside tmux "mqc"
```

`cloud_bootstrap.sh` does the following:
1. Installs apt packages (gfortran, FFTW, tmux, sqlite3).
2. Creates a uv venv with the pinned packages and a CUDA torch.
3. Links `data/` to the volume.
4. Builds GrowClust and runs its example.
5. Builds EQcorrscan and fast_matched_filter and runs a GPU smoke test.
6. Caches the SeisBench weights, runs the unit tests and the **2-station × 2-day pass-1 smoke test** (`scripts/smoke_test.sh cuda`), including a CUDA-vs-CPU pick comparison.
7. Runs a **download-throughput benchmark** at 4/8/16/24 streams (`scripts/bench_download.sh`).

Set `DL_THREADS` for `run_full.sh` from that benchmark: total streams = `WORKERS × DL_THREADS`.

**Tested locally (Mac, CPU + MPS):** pass 1 end to end (smoke test, including interruption and resume), and on pilot days 1–2 ensemble → PyOcto → location → snippets → ML → cross-correlation → QuakeScope comparison → ISC validation → analysis → report.

**Compiled tools.** GrowClust, EQcorrscan and fast_matched_filter (CPU build) were built and run on the Mac on pilot data (2026-11-25): GrowClust relocated 44 of 118 events of pilot days 1–5; template matching with 4 templates over 2 days gave identical detections with the FFTW and FMF-CPU backends. EQcorrscan needs its own environment (`.venv-tm`: numpy<2, obspy 1.4.1), which the bootstrap creates. **Not yet tested anywhere: the FMF CUDA build** (needs `nvcc`). Read the bootstrap output before pass 3.

## 2. The three passes

| Pass | Command | What it does | Resumable via |
|---|---|---|---|
| 1 | `run_full.sh pass1` | `stream_run.py` workers (default 3) claim station-days from `data/ledger.sqlite` (Hangay first, day-major). Download threads prefetch into `data/buffer/`. The GPU runs 6 model/weight pairs → raw picks + ensemble picks (parquet) → 20 Hz Steim2 copy → raw file deleted | ledger rows `todo → downloading → downloaded → done/nodata/error`; stale rows of dead workers are reset at start |
| 2 | `run_full.sh pass2` | per subarray: PyOcto association → least-squares location + quality classes → 100 Hz event snippets re-fetched from FDSN (8 threads) → ML → GPU cross-correlation → GrowClust → analysis figures | `data/catalogs/full_XX/.done_<step>` |
| 3 | `run_full.sh pass3` | EQcorrscan + FMF (CUDA) template matching over the 20 Hz copy | `templates/done_days.txt` |

Monitor with `bash scripts/status.sh`: ledger counts, rate (station-days/h and MB/s over the last 6 h), ETA, pass-2 steps, disk, GPU utilisation, recent errors. `tmux attach -t mqc` shows the live session.

If the instance dies: start a new one on the **same volume**, run `cloud_bootstrap.sh` again (fast, idempotent) and then `run_full.sh`. Nothing finished is redone.

## 3. Pull results to the Mac

```bash
REMOTE=root@<ip> PORT=<port> REMOTE_REPO=/workspace/mongolia-quake-catalog bash scripts/sync_back.sh
bash scripts/status.sh --local
```
This syncs the ledger, picks, catalogs, snippets, logs and results, but no waveforms and not the 20 Hz copy (~260 GB; it stays on the volume, or delete it after pass 3).

## 4. Estimates

MEASURED values were measured in this project; the others are extrapolated. The extrapolations will be replaced by the bootstrap benchmarks on the actual box.

### Inputs

| Quantity | Value | Source |
|---|---|---|
| Station-days (metadata epochs) | 75,267 (HD 48,187, HV 17,602, AT 9,478) | MEASURED, `data/meta/stations.csv` |
| Raw size per station-day | ~17.6 MB (HH?, 100 Hz, Steim) | MEASURED on the pilot downloads |
| Total raw volume | ~1.3 TB | 75,267 × 17.6 MB |
| Download, Mac (home link shared with 3 other projects) | 2 streams 3.2 MB/s, 4 streams 4.4 MB/s, 8 streams 4.75 MB/s: saturates at the local link. Later, with the shared network busy, 4 streams gave only 1.3 MB/s | MEASURED, `results/download_throughput.md`. **Not predictive for a data-centre box: measure there (bootstrap step 8)** |
| Picking, Apple M4 GPU (MPS), 6 pairs | PhaseNet ~2.9 s, EQTransformer ~11 s per pair per station-day → **~42 s per station-day** | MEASURED, `results/bench_picking.csv` |
| Non-GPU share of picking (Mac) | PhaseNet ~31 %, EQTransformer ~10 % | MEASURED (pure forward pass vs full `classify`) |
| MPS vs CPU picks | identical (11/11, 14/14 within 10 ms); MPS 16× (PhaseNet) to 34× (EQT) faster than 4 CPU threads | MEASURED |
| fp16 autocast vs fp32 (MPS) | all picks of all 6 pairs reproduced within 10 ms; no speed-up on MPS | MEASURED (`scripts/bench_amp.py`); re-check on CUDA, where tensor cores may give ~2× |
| 20 Hz copy | 14 MB for 4 station-days = **3.5 MB per station-day** | MEASURED (smoke test) |
| Event snippets | 27 MB for 43 events = **0.63 MB per event** | MEASURED (pilot days 1–2) |
| PyOcto association | 0.2–3 s per day for 72 stations with a 300 km cutoff | MEASURED (pilot) |
| Pass-1 smoke test (2 stations × 2 days, MPS), including a deliberate interruption and resume | PASSED: 4/4 done, 24 raw + 4 ensemble parquet, 4 × 20 Hz files, no raw left | MEASURED (`data/logs/smoke_mps.out`) |

### Pass-1 estimate on a 4090 (EXTRAPOLATED)

- GPU part: the M4 forward-pass time over a whole station-day for all 6 pairs is ~32 s. A 4090 has roughly 15–20× the FP32 throughput of the M4's 10-core GPU, but the EQTransformer LSTMs scale worse. Assuming an effective 8–12× gives **~2.7–4 s of GPU per station-day**.
- CPU part (windowing, stacking, peak finding, I/O): ~6 s per station-day on an M4 core, perhaps 8–10 s on a cloud vCPU. With 3–4 workers this overlaps with the GPU, giving **~2.5–3.5 s per station-day**.
- **Picking-bound pass 1: 75,267 × 2.7–4 s ≈ 56–84 h.**
- Download-bound pass 1: 1.3 TB at 14 MB/s ≈ 26 h; at 25 MB/s ≈ 15 h. At the Mac's 4.6 MB/s it would be ≈ 80 h.
- **Pass 1 is therefore probably GPU/picking-bound at ~55–85 h, unless the box's download rate falls below ~5 MB/s.** AMP (fp16) picking could roughly halve the GPU part, but it must first be shown to give the same picks (`scripts/bench_picking.py --devices cuda,cpu` on fp16 vs fp32). It is not enabled by default.

### Passes 2–3 (EXTRAPOLATED)

| Pass | Estimate | Basis |
|---|---|---|
| 2: association + location | < 1 h | MEASURED 0.2–3 s per day of PyOcto and ~5 s per 40 events for location |
| 2: snippet re-fetch | 3–8 h | ~1 bulk request per event (~0.3–1 MB), 8 threads; tens of thousands of events |
| 2: ML + xcorr + GrowClust | 2–5 h | the xcorr pair count scales with clustering |
| 3: template matching | 5–20 h | ~10³–10⁴ templates × ~50 channels × ~1,600 days at 20 Hz. To be measured on the box for one day first, then decided |

### Total

| Scenario | Wall time | Cost at $0.35/h | Cost at $0.70/h |
|---|---|---|---|
| Optimistic (fast GPU scaling, 25 MB/s) | ~70 h | ~$25 | ~$50 |
| Central | ~100 h | ~$35 | ~$70 |
| Pessimistic (slow scaling, template matching 20 h) | ~130 h | ~$45 | ~$90 |

Add the volume: 400 GB × ~$0.05–0.10/GB/month ≈ $20–40/month, kept for about 1–2 weeks.

### Disk budget on the volume (EXTRAPOLATED from the pilot)

| Item | Size |
|---|---|
| 20 Hz copy (Steim2 int32) | 3.5 MB × 75k ≈ **265 GB** (MEASURED rate) |
| Raw picks (6 pairs) + ensemble parquet | ~1–3 GB |
| Event snippets (100 Hz) | 0.63 MB/event (MEASURED) × 20–60k events ≈ 13–40 GB |
| Prefetch buffer | WORKERS × prefetch × 18 MB < 1 GB |
| Env, tools, weights | ~15 GB |
| **Total** | **~280–350 GB → rent 400 GB** |

## 5. If the researcher rents only a few hours

The full run needs ~3–5 days on one 4090, so a 5-hour rental cannot finish it. The download alone takes ≥ 15 h even at 25 MB/s, and picks must be computed where the data are. The best use of a short rental is the **first ~5 h of pass 1 on the Hangay subarray**, plus the benchmarks (bootstrap steps 5–8). That gives the true 4090 picking rate and download rate, so the full rental can be sized exactly.
