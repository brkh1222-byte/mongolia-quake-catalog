# CLAUDE.md

This is a research project by an independent researcher: an open ML earthquake catalog for Mongolia from FDSN network XL (2012–2016). Read PROPOSAL.md first. It holds the plan, data sources, method and timeline.

- **Compute:** the heavy steps (picking, cross-correlation, template matching) run on a remote NVIDIA H100. Keep the code runnable both locally (small test slices) and on the GPU box. Use config files for paths.
- **Data:** about 1.3 TB of miniSEED goes under `data/` and is git-ignored. Never commit waveforms. Downloads must be resumable.
- **Tools:** Python with ObsPy, SeisBench, PyOcto/GaMMA, NonLinLoc, GrowClust and EQcorrscan + fast_matched_filter. Prefer well-documented off-the-shelf tools over custom methods.
- **Reproducibility:** pin versions in `environment.yml`. Every figure and table in the paper must be regenerable from a script in `src/` or a notebook.
- **Integrity:** the student must understand and write the paper themselves. Explain methods when implementing them. Verify every citation.
