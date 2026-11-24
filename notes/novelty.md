# Novelty check (2026-11-24)

**Verdict: the catalog idea is not fully done, so the project goes ahead with narrower wording.** No associated, located and openly released ML catalog exists for the whole XL network, or for the Hangay (HD) or Gobi-Altai (AT) subarrays. The Khövsgöl (HV) subarray already has one automated ML (EQTransformer) catalog: Emanov & Eshkunova (2025). The Khövsgöl part is therefore an extension, not a first.

Suggested claim for the paper: *"the first open, uniform, ML-based catalog of all three XL subarrays, with relocation, uniform magnitudes and completeness analysis; it extends the Khövsgöl catalog of Emanov & Eshkunova (2025)."*

DOIs marked ✔ were checked against Crossref metadata (title, authors, venue) on 2026-11-24. The literature search was done by a helper agent (WebSearch, Crossref, OpenAlex, ADS, Zenodo). I re-checked the new DOIs myself.

## What exists, by subarray

| Subarray | Existing work | Method | Overlap with us |
|---|---|---|---|
| HD (Hangay) 2012–14 | Meltzer et al. 2019 *SRL* ✔ doi:10.1785/0220180360 | Preliminary analyst-reviewed catalog; Mc 1.2, b 0.71 | Benchmark |
| HD | Dashdondog et al. 2020 *PMAS* doi:10.5564/pmas.v60i2.1353 | 12,912 hand-picked events (not public); 1-D model | Benchmark, not public |
| HD | Dashdondog et al. 2024 EGU abstract doi:10.5194/egusphere-egu24-1310 | 2,228 HypoDD relocations, 47 focal mechanisms, analyst picks | Partial (relocation, South Hangay only) |
| HD | Dashdondog et al. 2026 *PMAS* ✔ doi:10.5564/pmas.v66i01.5340 | 253 HypoDD relocations, Egiin Davaa fault | One fault |
| HD | Welkey et al. 2019 ESSOAr doi:10.1002/essoar.10500539.1; Welkey 2019 Lehigh dissertation | Relocation of the preliminary events | Not in a journal |
| HD | Ganbat, Yoshizawa, Meltzer & Stachnik 2026 *Tectonophysics* ✔ doi:10.1016/j.tecto.2026.231293 | Coda Q from 554 local events at 72 XL stations | None (attenuation) |
| HD | Lkhagvasuren & Kissling, JpGU-AGU 2026 abstract SSS13-10 (**unverified**, title only) | Minimum 1-D models and seismicity, Hangay | Watch |
| HV (Khövsgöl) 2014–16 | **Emanov & Eshkunova 2025** *Izv. Phys. Solid Earth* 61(6):938–950 ✔ doi:10.1134/S1069351325700806 | **EQTransformer picks → grid-search association → VELEST 1-D → Hypoinverse**, 26 XL HV stations | **High** for HV detection and location. No relocation, Mc, b or open data |
| HV | Emanov, Emanov, Gladyshev & Eshkunova 2026 *Russ. J. Geophys. Technol.* ✔ doi:10.18303/2619-1563-2026-1-39 | Depth sections from the 2025 catalog | Moderate for HV depths |
| HV | Scott et al. 2017 AGU abstract (2017AGUFM.T23E0660S); Scott 2018 Lehigh thesis | >2,100 detections | Not peer reviewed |
| HV | Ganbaatar & Sereenendorj 2024 *MJAG* ✔ doi:10.5564/mjag.v11i1.4188 | Mc 1.3–2.1, b 0.81–0.90 from the national catalog, 1964–2023 | Comparison baseline |
| AT (Gobi-Altai) 2014–16 | Davaasuren 2025 PhD thesis (theses.fr), doi:10.70675/835ab1a6ze016z443cz8131zfb2eea774da4 (not Crossref-checked) | Analyst picks, iLoc/RSTT, cross-correlation, HypoDD near Ikh Bogd. Use of AT stations unconfirmed | Partial |
| All XL | Ni et al. 2025 *Seismica* doi:10.26443/seismica.v4i2.1738 (QuakeScope) | PhaseNet picks; no association | Pick baseline |
| Other networks | Manceau et al. 2026 ESSOAr doi:10.22541/essoar.15010413/v1; Zenodo doi:10.5281/zenodo.23056176 | The same pipeline (PhaseNet → PyOcto → NonLinLoc → HypoDD), TDBnet 2023–24 | Methodological precedent |

No global ML catalog associates the QuakeScope picks into events. VORA (arXiv:2607.10450) shows only a Ridgecrest demonstration. No XL event catalog is on Zenodo.

## Consequences for the plan

1. The project goes ahead. The pilot validates the pipeline on the Hangay, which is still the largest gap: no ML catalog and no public catalog.
2. In the paper, Emanov & Eshkunova (2025) must be cited and compared for Khövsgöl. The Khövsgöl section becomes "reproduce and extend": relocation, uniform ML magnitudes, Mc and b, open data.
3. Ranked emphasis if a reviewer calls the catalog incremental:
   1. Same-method seismogenic depth and b-value comparison across a hot dome (HD), a rift tip (HV) and a transpressional belt (AT). Nobody has done this.
   2. A Hangay ML catalog benchmarked against Meltzer 2019 and Dashdondog 2020.
   3. A Gobi-Altai focus (no ML work found).
   4. Khövsgöl alone is the weakest angle.

## Reference-catalog finding (affects validation)

The ISC Bulletin (comprehensive search) has only **50 events** in 43–50°N, 94–105°E for the whole Hangay deployment (2012-06-10 to 2014-04-10), mostly from BYKL and IDC/ISC. EMSC has **2**, and USGS ComCat has **4** (queried 2026-11-24, files in `data/reference/`). The Mongolian national bulletin is not contributed to the ISC for this period. Validation against ISC/EMSC can therefore only check a handful of M≳3.5 events per month. Detection completeness has to be judged against Meltzer et al. (2019) rates and against QuakeScope picks instead.
