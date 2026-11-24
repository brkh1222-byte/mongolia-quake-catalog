# CLAUDE.md

This is a research project by an independent researcher: an open ML earthquake catalog for Mongolia from FDSN network XL (2012–2016). Read PROPOSAL.md first. It holds the plan, data sources, method and timeline.

- **Compute:** the full run (streaming download + GPU picking, cross-correlation, template matching) runs on a rented cloud **RTX 4090** box (RunPod/Vast, ~400 GB volume); see `docs/cloud_runbook.md`. The Mac is for development and the pilot month. Keep the code runnable on CPU, Apple MPS and CUDA. Use config files for paths.
- **Data:** about 1.3 TB of miniSEED is streamed (download → pick → delete); only picks, a 20 Hz decimated copy (cloud volume) and event snippets are kept. `data/` is git-ignored. Never commit waveforms. Everything must be resumable (ledger `data/ledger.sqlite`).
- **Tools:** Python with ObsPy, SeisBench, PyOcto/GaMMA, NonLinLoc, GrowClust and EQcorrscan + fast_matched_filter. Prefer well-documented off-the-shelf tools over custom methods.
- **Reproducibility:** pin versions in `environment.yml`. Every figure and table in the paper must be regenerable from a script in `src/` or a notebook.
- **Integrity:** Claude drafts the paper; the researcher reviews and edits it; the paper carries an AI-use disclosure. Authorship is undecided: use the placeholders `[AUTHORS — TBD]` and `[AI-USE STATEMENT — TBD]`. Explain methods when implementing them. Verify every citation.
- **Linux-only tools:** GrowClust (Fortran), EQcorrscan and fast_matched_filter are built and smoke-tested on the cloud box by `scripts/cloud_bootstrap.sh`; the Mac has no Fortran compiler.
- **Environment:** laptop uses `uv` (`uv venv --python 3.11 .venv`; pins in `requirements-lock.txt`); the GPU box uses `environment.yml`.
