# TASKS: mongolia-quake-catalog

Work top to bottom. Each task has a "done when" check. Tick boxes in this file as tasks complete. Read PROPOSAL.md and CLAUDE.md first.

> **Where things run:** cloud agents write and test code on *small slices* (1 station-day to 1 week). The full 1.3 TB download and the GPU steps run on the **H100 machine**. Every script must take `--start/--end/--stations` and a `--device cuda|cpu` flag.

## Phase 0: Setup
- [ ] **T0.1** Create `environment.yml` (python 3.11, obspy, seisbench, pyocto, pandas, pyarrow, numpy, scipy, matplotlib, cartopy, tqdm, torch with CUDA) and `config/default.yaml` for paths, time window and subarrays.
- [ ] **T0.2** Write `src/stations.py` to fetch XL station metadata (StationXML) from the EarthScope FDSN service. Save `data/meta/stations.csv` with code, lat, lon, elev, start, end and subarray (HD/HV/AT). Make a station map in `results/fig_stations.png`.
  *Done when:* 114 stations listed; map shows the three subarrays.

## Phase 1: Download
- [ ] **T1.1** Write `src/download.py`: ObsPy MassDownloader, resumable, parallel, organised as day files `data/mseed/{net}.{sta}/{year}/{jday}.mseed`. Log data availability.
  *Done when:* it works for 2 stations × 3 days locally; it skips files that already exist.
- [ ] **T1.2** Write `src/availability.py` to make a data-availability plot (station × time).
- [ ] **T1.3** *(H100 machine)* Run the full download, Hangay subarray first.

## Phase 2: Picking
- [ ] **T2.1** Write `src/pick.py`: SeisBench PhaseNet + EQTransformer (pretrained weights: `stead`, `instance`, `original`). Batch day-files on the GPU and write picks as parquet (station, phase, time, probability, model).
  *Done when:* it runs on 1 station-day on CPU and produces picks.
- [ ] **T2.2** Ensemble logic: merge picks across models (time tolerance, mean probability).
- [ ] **T2.3** Download the QuakeScope XL picks (https://dasway.ess.washington.edu/quakescope/) for one month and compare them with ours (`notebooks/02_compare_quakescope.ipynb`).

## Phase 3: Association and location
- [ ] **T3.1** Write `src/associate.py`: PyOcto with a 1-D velocity model (Vp 6.4, Vs 3.6 km/s, Moho ~50 km; see PROPOSAL §6). Output events with their associated picks.
- [ ] **T3.2** Write `src/locate.py`: NonLinLoc (or the PyOcto location as a first pass). Output event lat, lon, depth and uncertainties.
- [ ] **T3.3** Validation: one month of the Hangay subarray vs the ISC/EMSC events in that window, and vs the counts in Meltzer et al. 2019.
  *Done when:* `results/validation_month.md` contains match rates and location offsets.

## Phase 4: Relocation and magnitudes
- [ ] **T4.1** Write `src/xcorr.py`: GPU waveform cross-correlation (PyTorch) for event pairs within 10 km. Output differential times.
- [ ] **T4.2** GrowClust relative relocation.
- [ ] **T4.3** Write `src/magnitude.py`: local magnitude ML from Wood–Anderson amplitudes, calibrated against ISC/EMSC magnitudes.

## Phase 5: Analysis
- [ ] **T5.1** Mc (maximum curvature + goodness-of-fit) and b-value (Aki MLE) for each subarray; b-value map.
- [ ] **T5.2** Depth sections across the Hangay dome, its margins and the Khövsgöl rift (tests the seismogenic-depth hypothesis).
- [ ] **T5.3** Seismicity overlaid on AFEAD fault traces; statistics per fault.
- [ ] **T5.4** Quarry-blast filter (day/night ratio, known mine locations).

## Phase 6: Stretch
- [ ] **T6.1** Template matching with EQcorrscan + fast_matched_filter (GPU).

## Phase 7: Release
- [ ] **T7.1** Catalog export (CSV + QuakeML) and Zenodo-ready data package.
- [ ] **T7.2** Figures and `paper/notes.md` results summary. **Claude drafts the paper; the researcher reviews and edits it; the paper carries an AI-use disclosure** (`[AUTHORS — TBD]`, `[AI-USE STATEMENT — TBD]`).
