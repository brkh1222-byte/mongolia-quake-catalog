# STATUS (updated 2026-11-25 01:30 +08)

## Researcher decisions received 2026-11-25
1. Velocity model: Dashdondog 2020 primary (done, D18); 2-layer = robustness check (`--vmodel config/vmodel_2layer.yaml --suffix _2layer`).
2. Regions: Claude freezes `config/regions.geojson` from published geology with sources in decisions.md + a map figure. **IN PROGRESS**: DEM is at `data/reference/dem/etopo1.nc` (ETOPO1 via ERDDAP); a literature helper is collecting quotable definitions. Plan: interior = largest patch of 50-km-smoothed elevation above a published threshold; margin = HD footprint minus interior; Khövsgöl and Gobi-Altai = HV/AT footprints checked against published extents. Write `src/make_regions.py` + `results/fig_regions.png`.
3. Faults: GEM (done, D19, `config/gem_faults_mongolia.geojson`).
4. `brew install gcc fftw` is being run by the coordinator. When `brew list --versions gcc fftw` shows both: build GrowClust (git clone dttrugman/GrowClust, `make` in SRC with gfortran), `uv pip install eqcorrscan` and fast_matched_filter (CPU), test on pilot data. Only when picking is not competing; max 2 heavy processes.
- Commit trailer is now `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## Running now (detached, resumable)
- `scripts/pilot_download_loop.sh 2013-01-01 2013-02-01 HD 2` (log `data/logs/dl_loop.out`), ~800 station-days left at 01:20.
- `scripts/pilot_pick_loop.sh 2013-01-01 2013-02-01 HD` (MPS; ~45–50 s per station-day; day 4 of 31 at 01:25; ETA ≈ 26 Nov 05:00).
Restart both after a reboot:
```bash
cd ~/Desktop/mongolia-quake-catalog
nohup caffeinate -i bash scripts/pilot_download_loop.sh 2013-01-01 2013-02-01 HD 2 > data/logs/dl_loop.out 2>&1 &
nohup caffeinate -i bash scripts/pilot_pick_loop.sh 2013-01-01 2013-02-01 HD > /dev/null 2>&1 &
```

## When picking is done
`bash scripts/run_pilot_chain.sh 2013-01-01 2013-02-01 pilot_2013-01` (ensemble → associate → locate → locate_2l → snippets → magnitude → xcorr → quakescope → validate → analyze → report). Then:
- confirm the 0.1 ensemble threshold on the full month (rerun ensemble/associate with `--min-prob 0.3 --ensemble-name ens_strict --tag pilot_strict` and compare);
- magnitude calibration: `data/catalogs/pilot_2013-01/attenuation_fit.json` (joint inversion for n, K) and `results/magcal_pilot_2013-01.csv` (ISC all-magnitude matches); a helper is extracting the Ganbat & Munkhuu (2026) Mongolian ML formula;
- fill paper §4 from `results/validation_month.md`; update `paper/notes.md`;
- delete `data/mseed` (keep snippets) once everything is validated.

## Done and verified
- Pass-1 smoke test (MPS) passed; the pilot chain was verified end to end on days 1–2 (tag `dbg_d12`, made with the old 2-layer primary).
- The cloud runbook stays in the repo (no GPU rental for now).

---
(older checkpoint below)

# STATUS (checkpoint 2026-11-24 ~16:05 +08, Mac shutdown)

## Plan as of the latest instructions
- The Mac is for development and the **pilot month (Jan 2013, Hangay HD, 72 stations)** only. The full run goes to a rented **RTX 4090** cloud box (RunPod/Vast, ~400 GB volume). Do not rent anything; the researcher provides SSH.
- Deliverables still owed: the pilot validation (`results/validation_month.md`), the QuakeScope comparison, measured download throughput, `docs/cloud_runbook.md` + `scripts/cloud_bootstrap.sh` + `scripts/run_full.sh` (pass 1 streaming with a 20 Hz decimated copy, pass 2 assoc/loc/xcorr/GrowClust/ML, pass 3 EQcorrscan+FMF), a local CPU test on 2 stations × 2 days, the paper draft (`paper/main.tex`, `paper/notes.md`), and TASKS.md ticks.

## Done (committed)
- uv venv (.venv, py3.11), `requirements-lock.txt`, `environment.yml`, `config/default.yaml`
- T0.2 `src/stations.py`: 114 codes (74 HD, 26 HV, 14 AT), `results/fig_stations.png`
- T1.1 `src/download.py` (MassDownloader, resumable, tested on 2 stations × 3 days; a rerun skips existing files)
- `notes/novelty.md` (verdict: open, except Khövsgöl is covered by Emanov & Eshkunova 2025), `notes/decisions.md` D1–D7
- Code written, untested on real data: `src/pick.py`, `src/ensemble.py`, `src/associate.py`, `src/locate.py`, `src/snippets.py`, `src/magnitude.py`, `src/xcorr.py`, `src/stream_run.py` (ledger-based streaming), `tests/test_pipeline.py` (5 tests pass)

## In progress when stopped
- The Jan 2013 download (2 processes, lists in `data/logs/listA`, `listB`) was at ~2 GB, ~3.4 MB/s total for 2 MassDownloader processes.
- CPU pick benchmark on HD01 2013-05-02: the 3 PhaseNet runs took ~1 min each on 4 threads (very slow). The EQT runs did not finish. **Next: benchmark MPS** (`--device mps`) and check that its picks match CPU.

## Findings so far
- ISC has only 50 events in 43–50N, 94–105E for 2012-06 to 2014-04 (Jan 2013: 8, the most of any month); EMSC 2, USGS 4. Reference validation will be thin.
- The EarthScope availability web service is retired, so availability comes from metadata plus download logs.
- service.iris.edu redirects to service.earthscope.org (configured).
- pandas 3 datetime resolution bug fixed by `common.to_epoch`.
- micromamba install was denied by the permission classifier. No gfortran, cmake or docker on the Mac, so GrowClust, EQcorrscan and FMF can only be built and tested on the Linux cloud box (apt). Ask the researcher about `brew install gcc fftw` if a local test is wanted.
- QuakeScope picks: `https://dasway.ess.washington.edu/quakescope/data/picks/network=XL/year=YYYY/month=MM/docdb2025-XL.parquet` (the download was started into `data/reference/quakescope/`; check that the files are complete).

## Restart commands
```bash
cd ~/Desktop/mongolia-quake-catalog
# 1. resume the pilot download (skips finished station-days; deletes stray .part files first)
find data/mseed -name "*.part.mseed" -delete; find data/mseed -name "*.tmp" -delete
nice -n 10 .venv/bin/python src/download.py --start 2013-01-01 --end 2013-02-01 --stations $(cat data/logs/listA) > data/logs/dl_jan_A.out 2>&1 &
nice -n 10 .venv/bin/python src/download.py --start 2013-01-01 --end 2013-02-01 --stations $(cat data/logs/listB) > data/logs/dl_jan_B.out 2>&1 &
# 2. MPS benchmark (compare with data/picks/raw/*/XL.HD01/2013/122.parquet from CPU)
.venv/bin/python src/pick.py --start 2013-05-02 --end 2013-05-03 --stations HD01 --device mps --force
# 3. pilot picking (resumable: skips station-days whose parquet exists)
caffeinate -i nice -n 10 .venv/bin/python src/pick.py --start 2013-01-01 --end 2013-02-01 --stations HD --device mps
# 4. then: ensemble.py -> associate.py --tag pilot_2013-01 -> locate.py -> snippets.py -> magnitude.py -> xcorr.py
```
Note: MassDownloader writes per-channel `.part.mseed` files and merges them once a station finishes. A station interrupted mid-way is re-fetched on restart (merge_day_files also merges leftover parts).
