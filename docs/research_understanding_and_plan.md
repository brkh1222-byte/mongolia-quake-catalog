# Mongolia Quake Catalog — Research Understanding & Plan

> Mirror of the Claude Doc at https://claude.ai/artifact/Ta9P9hMq7pU7tCrsxM8vbf (as of 2026-11-24).
> Sections marked *(in progress)* are still being researched.

# Part A — What we're studying

We will turn about 1.3 TB of open seismometer recordings from central and western Mongolia (2012–2016) into a public list of earthquakes: when, where, how deep and how big each one was. Then we will use that list to ask which faults are active today and how deep earthquakes can happen under the Hangay Dome.

The recordings come from the Central Mongolia Seismic Experiment (FDSN network code XL). A US–Mongolian team ran it, and anyone can download the data. Only a preliminary catalogue for one of its three subarrays has ever been published. Modern machine-learning (ML) tools can now find many more small earthquakes than the older methods could.

## A1. Core concepts

An earthquake catalogue is built in a chain of steps, and each step's errors feed the next. The table below gives every idea you need, in the order the pipeline uses them.

| Concept | What it means (plain words) | Why it matters here |
| --- | --- | --- |
| Seismogram / miniSEED | A seismometer records ground motion in 3 directions (Z, N, E), here 100 samples per second. miniSEED is the file format. | 114 stations × up to 4 years = ~1.3 TB to read. |
| P and S waves | Every earthquake sends a faster P wave (push–pull) and a slower S wave (shear). | The S–P time gap grows with distance: about 8 km per second of gap in the crust. |
| Phase picking | Marking the exact arrival time of P and S on each seismogram. | ML pickers (PhaseNet, EQTransformer) do this as well as an analyst, millions of times faster. |
| Association | Grouping picks from many stations into one event: "these 9 picks are the same earthquake". | Without it you have picks, not earthquakes. QuakeScope released only picks for XL. |
| Location | Finding the point (latitude, longitude, depth) and origin time that best explain the picks, given a velocity model. | Depth is the hardest coordinate; it needs a station closer than about the event depth. |
| Relative relocation | Re-locating nearby events against each other using precise time differences (often from waveform cross-correlation). | Sharpens blurry clouds into fault planes; removes most velocity-model error. |
| Local magnitude (ML) | Size from the peak amplitude of a simulated Wood–Anderson record, corrected for distance. | Mongolia needs its own distance correction; we calibrate against ISC/EMSC events. |
| Magnitude of completeness (Mc) | The smallest magnitude above which (almost) every earthquake was detected. | All statistics must use only events above Mc. Mc changes in space and time. |
| Gutenberg–Richter law and b-value | For every magnitude-4 there are about 10 magnitude-3s when b = 1. b is the slope. | b relates to stress and rock conditions, but it is easy to fake a b-value change (A4). |
| Seismogenic depth | The depth below which rocks are too hot to break in earthquakes and flow instead. Often measured as D90 or D95: the depth above which 90% or 95% of events lie. | Our depth hypothesis: a hotter Hangay crust should have a shallower D90. |
| Template matching | Using recorded earthquakes as "templates" and scanning continuous data for near-copies. | Finds events 10× smaller than the template, but only ones similar to known events. |
| Quarry blasts | Mine explosions look like small shallow earthquakes. | They happen in working hours; they must be flagged before statistics. |

The two formulas you will use most are the Gutenberg–Richter law and Aki's maximum-likelihood b-value (M̄ = mean magnitude of events at or above Mc; ΔM = magnitude bin width, e.g. 0.1):

```latex
\log_{10} N(\ge M) = a - bM \qquad \hat{b} = \frac{\log_{10} e}{\bar{M} - (M_c - \Delta M/2)}
```

**The setting.** Mongolia sits more than 2,000 km north of the India–Asia collision, yet it is squeezed by it. The squeeze is taken up on long strike-slip faults (Bulnay, Bogd) and thrusts (Gobi-Altai). The Hangay Dome is a broad high plateau in central Mongolia, with unusually hot, slow mantle beneath it. The Khövsgöl rift to the north is the south-western tip of the Baikal rift system, where the crust is being pulled apart. XL covered all three settings, which is what makes comparisons between them possible.

## A2. Key literature *(in progress)*

## A3. Open questions and the gap *(in progress)*

## A4. Methods, tools and pitfalls *(in progress)*

## A5. Verified references (PROPOSAL.md §11)

All 12 DOIs in PROPOSAL.md resolve to the right paper, and none is fabricated. Three entries need real fixes: Huang & Zhao has the wrong author list, the QuakeScope paper has the wrong title and venue, and the Meltzer claims are overstated. Each entry was checked against Crossref, DataCite, the publisher page or NASA ADS.

| # | Correct reference (APA) | Status | What to fix |
| --- | --- | --- | --- |
| 1 | Meltzer, A., Stachnik, J. C., Sodnomsambuu, D., Munkhuu, U., Tsagaan, B., Dashdondog, M., & Russo, R. (2019). The Central Mongolia Seismic Experiment: Multiple applications of temporary broadband seismic arrays. *Seismological Research Letters, 90*(3), 1364–1376. [doi:10.1785/0220180360](https://doi.org/10.1785/0220180360) | Fix claims | Paper says **112** stations (72 HD, 26 HV, 14 AT); 114 is the number of station codes in metadata. "7,680 events" were used for a velocity estimate and include regional events; they are not the catalogue size. The catalogue was analyst-reviewed, not pure STA/LTA. Mc 1.2 and b 0.71 are correct. |
| 2 | Woollam, J., Münchmeyer, J., Tilmann, F., et al. (2022). SeisBench—A toolbox for machine learning in seismology. *SRL, 93*(3), 1695–1709. [doi:10.1785/0220210324](https://doi.org/10.1785/0220210324) | Correct | Add volume and pages. |
| 3 | Zhu, W., & Beroza, G. C. (2019). PhaseNet: A deep-neural-network-based seismic arrival-time picking method. *GJI, 216*(1), 261–273. [doi:10.1093/gji/ggy423](https://doi.org/10.1093/gji/ggy423) | Correct | Add issue and pages. |
| 4 | Mousavi, S. M., Ellsworth, W. L., Zhu, W., Chuang, L. Y., & Beroza, G. C. (2020). Earthquake transformer—An attentive deep-learning model for simultaneous earthquake detection and phase picking. *Nature Communications, 11*, 3952. [doi:10.1038/s41467-020-17591-w](https://doi.org/10.1038/s41467-020-17591-w) | Correct | Add article number. |
| 5 | Münchmeyer, J. (2024). PyOcto: A high-throughput seismic phase associator. *Seismica, 3*(1). [doi:10.26443/seismica.v3i1.1130](https://doi.org/10.26443/seismica.v3i1.1130) | Correct | — |
| 6 | Zhu, W., McBrearty, I. W., Mousavi, S. M., Ellsworth, W. L., & Beroza, G. C. (2022). Earthquake phase association using a Bayesian Gaussian mixture model. *JGR: Solid Earth, 127*(5), e2021JB023249. [doi:10.1029/2021JB023249](https://doi.org/10.1029/2021JB023249) | Correct | Journal is *JGR: Solid Earth*. |
| 7 | Trugman, D. T., & Shearer, P. M. (2017). GrowClust: A hierarchical clustering algorithm for relative earthquake relocation… *SRL, 88*(2A), 379–391. [doi:10.1785/0220160188](https://doi.org/10.1785/0220160188) | Correct | Add volume and pages. |
| 8 | Beaucé, E., Frank, W. B., & Romanenko, A. (2018). Fast matched filter (FMF): An efficient seismic matched-filter search for both CPU and GPU architectures. *SRL, 89*(1), 165–172. [doi:10.1785/0220170181](https://doi.org/10.1785/0220170181) | Correct | Add volume and pages. |
| 9 | Ni, Y., Denolle, M. A., Thomas, A. M., Hamilton, A., Münchmeyer, J., Wang, Y., Bachelot, L., Trabant, C., & Mencin, D. (2025). A global-scale database of seismic phases from cloud-based picking at petabyte scale. *Seismica, 4*(2). [doi:10.26443/seismica.v4i2.1738](https://doi.org/10.26443/seismica.v4i2.1738) | **Wrong title/venue** | Cite the Seismica DOI, not only arXiv:2505.18874. "QuakeScope" is the data portal's name, not the paper title. Releases picks only, no events. XL picks have a gap 2014-05 to 2014-07. The XL code is reused by other networks, so filter by time and station. |
| 10 | Dashdondog, M., Dorjsuren, A., & Sereenen, O. (2026). Precise earthquake relocation along the Egiin Davaa fault, Hangay Dome, Central Mongolia. *Proceedings of the Mongolian Academy of Sciences, 66*(01), 27–37. [doi:10.5564/pmas.v66i01.5340](https://doi.org/10.5564/pmas.v66i01.5340) | Correct | 289 events analysed, 253 relocated with HypoDD, from XL 2012–2014. |
| 11 | Huang, Z., & Zhao, D. (2022). Seismotectonics of Mongolia and Baikal rift zone controlled by lithospheric structures. *GRL, 49*(15), e2022GL099525. [doi:10.1029/2022GL099525](https://doi.org/10.1029/2022GL099525) | **Wrong authors** | Two authors, not "et al." It argues a high-velocity ring shields the Hangay, giving weak seismicity under the dome. That is directly relevant to H2. |
| 12 | Zelenin, E., Bachmanov, D., Garipova, S., Trifonov, V., & Kozhurin, A. (2022). The Active Faults of Eurasia Database (AFEAD). *ESSD, 14*(10), 4489–4503. [doi:10.5194/essd-14-4489-2022](https://doi.org/10.5194/essd-14-4489-2022) | Correct | Add full title and pages. |
| — | Meltzer, A. (2012). *Central Mongolia Seismic Experiment* [Data set]. FDSN. [doi:10.7914/SN/XL_2012](https://doi.org/10.7914/SN/XL_2012) | Correct | Operator: Lehigh University. |
| — | Meltzer, A. (2018). *Mongolia Fault Zone Studies* [Data set]. FDSN. [doi:10.7914/SN/ZJ_2018](https://doi.org/10.7914/SN/ZJ_2018) | Minor | 22 short-period stations BU01–BU22, 2018-05-31 to 2018-09-26. |
| — | Scott, A. M., Meltzer, A., Stachnik, J., Russo, R., Munkhuu, U., & Tsagaan, B. (2017). *Crustal structure of Khövsgöl, Mongolia* (Abstract T23E-0660). AGU Fall Meeting. [ADS](https://ui.adsabs.harvard.edu/abs/2017AGUFM.T23E0660S/abstract) | Correct | Says >2,100 events *detected* (not located); largest ML 5.2. |
| — | FDSN network MJ, Mongolian National Network, IAG ([FDSN page](https://www.fdsn.org/networks/detail/MJ/)) | Correct | Page states data are prohibited from distribution to third parties. The OU page has **no** such statement, so do not group OU with MJ. |

**Found during the check, not yet in PROPOSAL.md.** Welkey et al. (2019), an ESSOAr preprint ([doi:10.1002/essoar.10500539.1](https://doi.org/10.1002/essoar.10500539.1)), and a 2019 Lehigh dissertation by Welkey appear to locate all 7,680 Hangay events with a local 1-D model. Both were seen only as metadata. Open and read them before claiming that "only a preliminary catalogue exists" (see A3).

# Part B — How we'll study it

## B1. Research question and hypotheses *(in progress)*

## B2. Study design and methods *(in progress)*

## B3. Analysis plan and outcomes *(in progress)*

## B4. Paper outline and target journal

**Target: Seismica, research article.** Seismica is diamond open access: free to publish and free to read, CC-BY 4.0, and preprints are welcome. Articles run 3,000–10,000 words with up to 10 figures. Its "Reports" category covers data-based reports and null-results reports, so it is also the right home if the science tests come out null ([author guidelines](https://seismica.library.mcgill.ca/author-guidelines), [policies](https://seismica.library.mcgill.ca/policies)).

*SRL* "Data Mine" is not a good fit. That column documents new experiments, and it explicitly excludes "tests of new scientific hypotheses" ([SRL Data Mine info](https://www.seismosoc.org/publications/srl/srl-data-mine-author-information)). The fallbacks are *Journal of Asian Earth Sciences* or *Geophysical Journal International*.

| # | Section | What goes in it | Figures / tables |
| --- | --- | --- | --- |
| 1 | Introduction | Mongolian great earthquakes and hazard; the closed national data; the XL gap; the questions | — |
| 2 | Tectonic setting and data | Hangay Dome, Khövsgöl rift, Gobi-Altai; XL subarrays and their time windows | Fig. 1 station and fault map; Fig. 2 data availability |
| 3 | Methods | Picking ensemble, association, NonLinLoc, cross-correlation + GrowClust, ML calibration, template matching, blast screening | Fig. 3 pipeline diagram |
| 4 | Validation | Matches to ISC/EMSC; head-to-head with Meltzer et al. (2019) on the same months; QuakeScope picks; 100 manually checked events | Fig. 4 detection and location comparison; Table 1 validation numbers |
| 5 | The catalogue | Event counts, Mc per subarray and through time, location uncertainties | Fig. 5 seismicity map on AFEAD faults; Fig. 6 frequency–magnitude curves |
| 6 | Fault activity | Which mapped faults are active, along-strike patterns | Fig. 7 along-fault profiles; Table 2 per-fault statistics |
| 7 | Seismogenic depth and b-values | D90/D95 with bootstrap errors per region; b-value comparison | Fig. 8 depth sections; Fig. 9 depth distributions with D90; Fig. 10 b-values with uncertainty |
| 8 | Discussion | Thermal interpretation; comparison with tomography and other intraplate regions; limitations | — |
| 9 | Conclusions | 4–5 numbered findings | — |
| — | Back matter | Data and code availability (Zenodo DOI, GitHub), CRediT, AI-use statement, acknowledgements, competing interests | — |

That is exactly 10 figures. If one needs to go, merge Figs. 8 and 9.

## B5. Timeline and risks *(in progress)*

## Suggested changes to PROPOSAL.md / TASKS.md *(in progress)*
