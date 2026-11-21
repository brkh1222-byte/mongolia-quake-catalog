# mongolia-quake-catalog

An open, GPU-accelerated deep-learning earthquake catalog for central and western Mongolia (Hangay Dome, Khövsgöl rift, Gobi-Altai), built from the 2012–2016 Central Mongolia Seismic Experiment (FDSN network XL).

📄 **Read the research proposal:** [PROPOSAL.md](PROPOSAL.md)

## Pipeline (planned)

Download (ObsPy) → ML phase picking (SeisBench: PhaseNet + EQTransformer) → association (PyOcto/GaMMA) → location (NonLinLoc) → relocation (GrowClust) → magnitudes → template matching (EQcorrscan + GPU) → analysis

## Layout

```
data/       raw waveforms and intermediate files (not committed, about 1.3 TB)
src/        pipeline code
notebooks/  exploration and figures
results/    catalogs and figures
paper/      manuscript
```

## Status

🟡 Proposal stage (Nov 2026)

## Data credit

Waveform data from the Central Mongolia Seismic Experiment (network XL, doi:10.7914/SN/XL_2012), accessed through the EarthScope Consortium (IRIS) FDSN web services.
