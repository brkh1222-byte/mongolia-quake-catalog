# mongolia-quake-catalog

An open, GPU-accelerated deep-learning earthquake catalog for central and western Mongolia (Hangay Dome, Khövsgöl rift, Gobi-Altai), built from the 2012–2016 Central Mongolia Seismic Experiment (FDSN network XL).

📄 **Read the research proposal:** [PROPOSAL.md](PROPOSAL.md)

## Pipeline

Streaming download (EarthScope FDSN) → ensemble picking (SeisBench: PhaseNet + EQTransformer × stead/instance/original weights) → association (PyOcto) → least-squares location → event snippets → local magnitude ML → GPU cross-correlation → GrowClust relocation → template matching (EQcorrscan + fast_matched_filter) → Mc, b-value, D90, blast flags

| Stage | Script |
|---|---|
| stations, map | `src/stations.py` |
| download (pilot) | `src/download.py` |
| availability | `src/availability.py` |
| picking + ensemble | `src/pick.py`, `src/ensemble.py` |
| full streaming run | `src/stream_run.py` (ledger `data/ledger.sqlite`) |
| association, location | `src/associate.py`, `src/locate.py` |
| snippets, magnitudes | `src/snippets.py`, `src/magnitude.py` |
| xcorr, relocation | `src/xcorr.py`, `src/relocate.py` |
| template matching | `src/template_match.py` |
| validation | `src/validate.py`, `src/compare_quakescope.py` |
| analysis | `src/analysis.py`, `src/analyze.py` |

Full run on a rented RTX 4090: see [docs/cloud_runbook.md](docs/cloud_runbook.md). Status and next steps: [notes/STATUS.md](notes/STATUS.md).

## Layout

```
data/       raw waveforms and intermediate files (not committed, about 1.3 TB)
src/        pipeline code
notebooks/  exploration and figures
results/    catalogs and figures
paper/      manuscript
```

## Status

🟡 Pipeline built; pilot month (Jan 2013, Hangay) running on the Mac; full run planned on a cloud GPU (Nov 2026)

## Data credit

Waveform data from the Central Mongolia Seismic Experiment (network XL, doi:10.7914/SN/XL_2012), accessed through the EarthScope Consortium (IRIS) FDSN web services.
