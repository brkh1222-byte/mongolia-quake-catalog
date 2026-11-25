# TASKS: mongolia-quake-catalog

Work top to bottom. Each task has a "done when" check. Tick boxes in this file as tasks complete. Read PROPOSAL.md and CLAUDE.md first.

> **Where things run (updated 2026-11-24):** code is written and tested on the Mac (CPU/MPS) on small slices and the pilot month (Jan 2013, Hangay). The full run streams the 1.3 TB through a rented **RTX 4090** cloud box (`docs/cloud_runbook.md`). Every script takes `--start/--end/--stations` and a `--device cpu|mps|cuda` flag.

## Phase 0: Setup
- [x] **T0.1** Create `environment.yml` (python 3.11, obspy, seisbench, pyocto, pandas, pyarrow, numpy, scipy, matplotlib, cartopy, tqdm, torch with CUDA) and `config/default.yaml` for paths, time window and subarrays.
- [x] **T0.2** Write `src/stations.py` to fetch XL station metadata (StationXML) from the EarthScope FDSN service. Save `data/meta/stations.csv` with code, lat, lon, elev, start, end and subarray (HD/HV/AT). Make a station map in `results/fig_stations.png`.
  *Done when:* 114 stations listed; map shows the three subarrays.

## Phase 1: Download
- [x] **T1.1** Write `src/download.py`: ObsPy MassDownloader, resumable, parallel, organised as day files `data/mseed/{net}.{sta}/{year}/{jday}.mseed`. Log data availability.
  *Done when:* it works for 2 stations × 3 days locally; it skips files that already exist.
- [x] **T1.2** Write `src/availability.py` to make a data-availability plot (station × time). *(done: metadata epochs + download logs + QuakeScope proxy; the EarthScope availability service is retired)*
- [ ] **T1.3** *(cloud 4090 box)* Full streaming run (download → pick → delete), Hangay subarray first: `scripts/run_full.sh`.

## Phase 2: Picking
- [x] **T2.1** Write `src/pick.py`: SeisBench PhaseNet + EQTransformer (pretrained weights: `stead`, `instance`, `original`). Batch day-files on the GPU and write picks as parquet (station, phase, time, probability, model). *(done; MPS = CPU picks; 6 pairs ~40–60 s per station-day on M4 MPS)*
  *Done when:* it runs on 1 station-day on CPU and produces picks.
- [x] **T2.2** Ensemble logic: merge picks across models (time tolerance, mean probability). *(done; rule ≥2 of 6 pairs, mean p ≥ 0.1, decisions D6/D17)*
- [ ] **T2.3** Download the QuakeScope XL picks (https://dasway.ess.washington.edu/quakescope/) for one month and compare them with ours (`notebooks/02_compare_quakescope.ipynb`). *(script `src/compare_quakescope.py`; verified on pilot days 1–2: QuakeScope = PhaseNet/instance, 96 % of its picks reproduced; full-month run pending)*

## Phase 3: Association and location
- [ ] **T3.1** Write `src/associate.py`: PyOcto with a 1-D velocity model (Vp 6.4, Vs 3.6 km/s, Moho ~50 km; see PROPOSAL §6). Output events with their associated picks. *(code done + synthetic test; real data days 1–2: 44 events; full month pending)*
- [ ] **T3.2** Write `src/locate.py`: NonLinLoc (or the PyOcto location as a first pass). Output event lat, lon, depth and uncertainties. *(code done: least-squares + quality classes + Dashdondog-2020 sensitivity; NonLinLoc not used yet)*
- [ ] **T3.3** Validation: one month of the Hangay subarray vs the ISC/EMSC events in that window, and vs the counts in Meltzer et al. 2019. *(code done: `src/validate.py`, `src/report_pilot.py`; full month pending)*
  *Done when:* `results/validation_month.md` contains match rates and location offsets.

## Phase 4: Relocation and magnitudes
- [x] **T4.1** Write `src/xcorr.py`: GPU waveform cross-correlation (PyTorch) for event pairs within 10 km. Output differential times. *(done locally: tested on pilot days 1–5: 2,589 dt from 314 pairs; float32 lag bug fixed)*
- [x] **T4.2** GrowClust relative relocation. *(done locally: GrowClust built with brew gfortran and run on pilot days 1–5: 44 of 118 events relocated)*
- [ ] **T4.3** Write `src/magnitude.py`: local magnitude ML from Wood–Anderson amplitudes, calibrated against ISC/EMSC magnitudes. *(code done, tested on days 1–2; calibration needs the full month)*

## Phase 5: Analysis
- [ ] **T5.1** Mc (maximum curvature + goodness-of-fit) and b-value (Aki MLE) for each subarray; b-value map. *(code done + unit tests; pilot-only run)*
- [ ] **T5.2** Depth sections across the Hangay dome, its margins and the Khövsgöl rift (tests the seismogenic-depth hypothesis). *(code done; regions DRAFT in config/regions.geojson, D8)*
- [ ] **T5.3** Seismicity overlaid on AFEAD fault traces; statistics per fault. *(code done; needs an AFEAD GeoJSON, which is not openly downloadable: researcher to supply)*
- [ ] **T5.4** Quarry-blast filter (day/night ratio, known mine locations). *(code done + unit test)*

## Phase 6: Stretch
- [x] **T6.1** Template matching with EQcorrscan + fast_matched_filter (GPU). *(done locally: EQcorrscan + FMF (CPU) built in `.venv-tm`; 2 pilot days, 4 templates: 10 detections, FFTW = FMF)*

## Phase 7: Release
- [ ] **T7.1** Catalog export (CSV + QuakeML) and Zenodo-ready data package. *(code done: `src/export_catalog.py`)*
- [ ] **T7.2** Figures and `paper/notes.md` results summary. **Claude drafts the paper; the researcher reviews and edits it; the paper carries an AI-use disclosure** (`[AUTHORS — TBD]`, `[AI-USE STATEMENT — TBD]`).
