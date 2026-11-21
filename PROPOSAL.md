# Research Proposal

## An Open Deep-Learning Earthquake Catalog for Central and Western Mongolia from the 2012–2016 Central Mongolia Seismic Experiment

**Author:** Berkh (independent student researcher)
**Field:** Seismology / Geophysics
**Planned duration:** 4 weeks
**Compute:** 1× NVIDIA H100 (80 GB)
**Status:** Proposal, Nov 2026

---

## 1. Summary

Mongolia is one of the most seismically active intraplate regions on Earth. Four earthquakes of magnitude ~8 struck it between 1905 and 1957: Tsetserleg and Bulnay in 1905, Fu-Yun in 1931 and Gobi-Altai in 1957. Yet there is **no open, modern, machine-learning-based earthquake catalog for any part of the country**. The Mongolian national network data are not publicly distributable.

Between 2012 and 2016, a US–Mongolian team deployed 114 broadband seismometers across the Hangay Dome, the Khövsgöl rift and the Gobi-Altai (FDSN network **XL**). All of the data are openly downloadable. Only a *preliminary* STA/LTA catalog for the Hangay subarray was ever published (Meltzer et al., 2019). The Khövsgöl and Gobi-Altai subarrays have only conference abstracts.

This project will run a fully open, GPU-accelerated deep-learning pipeline on the whole XL dataset and publish the result as a reusable public catalog. The pipeline is: phase picking → association → location → relative relocation → magnitudes → template matching. The catalog will be used to map seismicity on the major active faults, magnitude of completeness, b-values and seismogenic depth.

## 2. Background and motivation

- **Hazard:** The great Mongolian earthquakes ruptured hundreds of kilometres of strike-slip and thrust faults, e.g. the Bulnay rupture of ~375 km. Faults near Ulaanbaatar, such as Emeelt and Hustai, host recurring earthquake swarms. More than half of Mongolia's population lives in Ulaanbaatar.
- **Data access problem:** The national networks (FDSN codes **MJ** and **OU**, operated by IAG) are registered with FDSN but their data are not distributed. The FDSN page for MJ states the data are prohibited from distribution to third parties. The open XL deployment is therefore the best openly available record of small-magnitude seismicity in Mongolia.
- **Why ML now:** Deep-learning pickers trained on millions of labelled arrivals routinely detect 5–10× more events than STA/LTA methods. Examples are PhaseNet (Zhu & Beroza 2019) and EQTransformer (Mousavi et al. 2020), both available through SeisBench (Woollam et al. 2022, doi:10.1785/0220210324). Modern associators make building a catalog from those picks straightforward: PyOcto (doi:10.26443/seismica.v3i1.1130) and GaMMA (doi:10.1029/2021JB023249).

## 3. Prior work and the gap

| Work | What it did | What is missing |
|---|---|---|
| Meltzer et al. 2019, *SRL* (doi:10.1785/0220180360) | Preliminary Antelope STA/LTA catalog for the Hangay subarray, 7,680 events, Mc ≈ 1.2, b ≈ 0.71 | Explicitly preliminary; Hangay only; no final catalog published |
| Dashdondog et al. 2026, *PMAS* (doi:10.5564/pmas.v66i01.5340) | HypoDD relocation of ~253 events on the Egiin Davaa fault | One fault only; not ML |
| AGU 2017 abstract (Khövsgöl subarray, ADS 2017AGUFM.T23E0660S) | Reports more than 2,100 events | No peer-reviewed catalog |
| QuakeScope (Ni et al. 2025, *Seismica*; arXiv:2505.18874) | PhaseNet **picks** for XL (and ZJ, IU) are public | Picks are **not associated** into events, located or relocated |
| Huang et al. 2022, *GRL* (doi:10.1029/2022GL099525) | Tomography and seismotectonics | Not a catalog |
| Ambient-noise tomography of the Hangay (≥5 papers, 2021–2025) | Crustal velocity structure | Different problem; can supply velocity models |

**Gap:** No associated, located, relocated and publicly released ML earthquake catalog exists for any of the three XL subarrays. In particular, the 2014–2016 Khövsgöl and Gobi-Altai subarrays have never been published in a peer-reviewed journal.

## 4. Research questions

1. **Catalog:** How many earthquakes are detectable in the XL data with a modern ML pipeline, and what is the magnitude of completeness for each subarray, compared with the preliminary Meltzer catalog?
2. **Fault activity:** Which mapped active faults (Bulnay, Bogd, South Hangay, Egiin Davaa, Mogod, the Khövsgöl rift faults) show ongoing microseismicity, and how is it distributed along strike?
3. **Seismogenic depth:** Is the seismogenic layer beneath the elevated, hot Hangay Dome shallower than at its margins and beneath the Khövsgöl rift? (Hypothesis: yes, consistent with elevated heat flow and low upper-mantle velocities beneath the Hangay.)
4. **Statistics:** How do b-values vary between the dome interior, the dome margins and the rift?

## 5. Data

All data are open and come from the EarthScope (IRIS) FDSN web services.

| Network | Description | Span | Use |
|---|---|---|---|
| **XL** (doi:10.7914/SN/XL_2012) | Central Mongolia Seismic Experiment, 114 sites, broadband HH 100 Hz | 2012-06 → 2016-06 | Main dataset |
| ↳ HD01–HD75 | Hangay subarray | 2012-06-10 → 2014-04-10 | |
| ↳ HV01–HV32 | Khövsgöl subarray (26 sites; some gaps) | 2014-08-05 → 2016-06-11 | |
| ↳ AT01–AT15 | Gobi-Altai subarray (14 sites) | 2014-08 → 2016-06 | |
| **ZJ** (doi:10.7914/SN/ZJ_2018) | 22 short-period stations on the Bulnay fault | 2018-06 → 2018-09 | Optional extension |
| **IU.ULN**, **II.TLY**, **IC.HIA** | Permanent regional stations | Long-running | Extra stations and magnitude ties |
| QuakeScope XL picks | Public PhaseNet picks (parquet) | 2012–2016 | Baseline to compare against |
| ISC Bulletin / EMSC | Reference events | 2012–2016 | Validation and magnitude calibration |
| AFEAD (doi:10.5194/essd-14-4489-2022) | Active-fault database | — | Fault traces for interpretation |

**Volume:** about 76,600 station-days × ~17 MB ≈ **1.3 TB** of miniSEED. The Hangay alone is about 0.86 TB. At about 1.7 MB/s per stream, 8 parallel streams should finish the download in about 1–3 days (ObsPy `MassDownloader`).

## 6. Method

```
miniSEED (XL) ─► SeisBench picking ensemble (PhaseNet + EQTransformer, several pretrained weights)   [H100]
             ─► PyOcto / GaMMA association
             ─► NonLinLoc absolute locations (1-D model: Vp 6.4, Vs 3.6 km/s, Moho ~50 km)
             ─► waveform cross-correlation differential times                                       [H100]
             ─► GrowClust (or HypoDD) relative relocation
             ─► local magnitude ML calibrated to ISC/EMSC events
             ─► (stretch) template matching with EQcorrscan + fast_matched_filter GPU backend           [H100]
             ─► Mc, b-value maps, depth sections, fault-by-fault statistics
```

**Quality control**
- Compare picks with the QuakeScope baseline and with manual picks on a random sample of about 100 events.
- Compare the Hangay results with Meltzer et al. (2019), using their counts, Mc and b-value.
- Flag likely quarry blasts using the ratio of daytime to night-time events, mine locations and depth.
- Remove teleseismic and regional events from outside the network.

**What the H100 does**
- **Ensemble picking** on 76k station-days: a few GPU-hours, limited mainly by reading data from disk.
- **Cross-correlation** of millions of event pairs for relocation: about 1 GPU-hour.
- **Template matching** with about 10⁴ templates × about 30 channels × 21 months at 20 Hz, roughly 10¹⁷ FLOPs: about 2–10 H100-hours, compared with days to weeks on a CPU. This step finds the small events that the ML picker misses.

## 7. Timeline (4 weeks)

| Week | Tasks | Deliverable |
|---|---|---|
| 1 | Set up the environment (ObsPy, SeisBench, PyOcto, NonLinLoc, GrowClust). Start the bulk download. Run the pipeline on one month of the Hangay subarray. Compare with QuakeScope and Meltzer. | Working end-to-end pipeline on 1 month |
| 2 | Tune the association and location parameters. Run all three subarrays on the H100. | Raw catalog (absolute locations) |
| 3 | Cross-correlation relocation, magnitudes, Mc and b-value maps, depth sections, quarry-blast filtering. | Relocated catalog and figures |
| 4 | (Stretch) template matching. Write the paper. Release the catalog on Zenodo with a DOI. Post the preprint to EarthArXiv. | Preprint, data DOI, public code |

**Minimum viable result (end of week 3):** a relocated ML catalog for the Hangay subarray, compared against Meltzer et al. 2019. This is publishable on its own.

## 8. Expected outputs

1. **Catalog:** a public earthquake catalog (CSV + QuakeML) for 2012–2016 covering the Hangay, Khövsgöl and Gobi-Altai, archived on Zenodo with a DOI.
2. **Code:** a fully reproducible open-source pipeline in this repository.
3. **Paper:** submitted to *Seismica* as a Report (free to publish, open access, accepts preprints). Alternatives are the *Journal of Asian Earth Sciences* or *SRL*.
4. **Preprint:** posted to EarthArXiv. Its requirements are an ORCID with affiliation history and a framing as a research paper, not a course project.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| The simple 1-D velocity model biases depths | Test alternative models from published Hangay tomography; use relative relocation; report depth uncertainties |
| Khövsgöl data gaps | Report completeness for each subarray and time window |
| The Lehigh/IAG group publishes its own final catalog | Post the preprint quickly; cite and compare with their work; contact the XL PI (A. Meltzer, Lehigh) early |
| Quarry blasts contaminate the catalog | Day/night ratio, known mine locations, depth filter |
| Download is slow or interrupted | Resumable MassDownloader; start with the Hangay subarray |
| Being 17 and unaffiliated limits credibility | List the school as affiliation; get an ORCID; seek an adviser at IAG (Institute of Astronomy and Geophysics, Mongolian Academy of Sciences) or Lehigh |

## 10. Relevance to Mongolia

The faults that hosted Mongolia's great 20th-century earthquakes sit inside or next to the XL footprint. The Mogod fault (M7.4, 1967) is about 250 km from Ulaanbaatar. An open, modern catalog of present-day microseismicity on these faults is a direct input to national seismic hazard models. Those models can currently draw only on a catalog that is not public.

## 11. Key references

- Meltzer, A. et al. (2019). The Central Mongolia Seismic Experiment. *SRL* 90(3). doi:10.1785/0220180360
- Woollam, J. et al. (2022). SeisBench. *SRL*. doi:10.1785/0220210324
- Zhu, W. & Beroza, G. (2019). PhaseNet. *GJI* 216. doi:10.1093/gji/ggy423
- Mousavi, S. M. et al. (2020). Earthquake Transformer. *Nat. Commun.* 11. doi:10.1038/s41467-020-17591-w
- Münchmeyer, J. (2024). PyOcto. *Seismica*. doi:10.26443/seismica.v3i1.1130
- Zhu, W. et al. (2022). GaMMA. *JGR*. doi:10.1029/2021JB023249
- Trugman, D. & Shearer, P. (2017). GrowClust. *SRL*. doi:10.1785/0220160188
- Beaucé, E. et al. (2018). fast_matched_filter. *SRL*. doi:10.1785/0220170181
- Ni, Y. et al. (2025). QuakeScope. *Seismica*. arXiv:2505.18874
- Dashdondog, M. et al. (2026). *Proc. Mongolian Acad. Sci.* doi:10.5564/pmas.v66i01.5340
- Huang, Z. et al. (2022). *GRL*. doi:10.1029/2022GL099525
- Zelenin, E. et al. (2022). Active Faults of Eurasia Database (AFEAD). *ESSD*. doi:10.5194/essd-14-4489-2022

> ⚠️ These references were compiled by an AI research assistant. Verify every citation (authors, year, DOI) against the source before using it in the paper.
