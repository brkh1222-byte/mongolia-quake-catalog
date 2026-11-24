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
