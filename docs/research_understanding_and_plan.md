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

## A2. Key literature

The literature falls into four groups, and they connect in one argument. The XL papers give us benchmarks. The depth and rheology papers give us the hypothesis. The fault papers tell us where to look. The structure papers give us velocity models and an explanation for whatever depths we find. A 2026 ML catalogue from another Mongolian network proves the pipeline works here.

**1. The XL experiment and what has been done with it**

| Paper | What it found | How we use it |
| --- | --- | --- |
| [Meltzer et al. 2019, *SRL*](https://doi.org/10.1785/0220180360) | Describes XL: 112 stations. Hangay preliminary catalogue: Mc 1.2, b 0.71, seismicity in the upper 20 km and mostly above 10 km, crust ~50 km. | Main benchmark for detection, Mc, b and depth. |
| [Dashdondog et al. 2020, *PMAS*](https://doi.org/10.5564/pmas.v60i2.1353) | Mongolian National Data Center analysts hand-picked **12,912 events** in XL Hangay data. 120 of them built a 1-D velocity model for South Hangay (Vp/Vs ~1.73, Moho 50 km). | Starting velocity model. Their count is the real number to beat. |
| [Dashdondog et al. 2024, EGU abstract](https://doi.org/10.5194/egusphere-egu24-1310) | 2,228 South Hangay events relocated with HypoDD; 47 focal mechanisms. | Comparison for relocations (abstract only). |
| [Dashdondog et al. 2026, *PMAS*](https://doi.org/10.5564/pmas.v66i01.5340) | 253 relocated events on the Egiin Davaa fault at 2–30 km depth, deepening near a hot spring. They argue fluids allow lower-crustal earthquakes. | Direct comparison for our depth question. |
| [Ni et al. 2025, *Seismica*](https://doi.org/10.26443/seismica.v4i2.1738) (QuakeScope) | Public PhaseNet picks for all of XL; no events. Example: May 2013 has 209,901 picks on 72 Hangay stations. | Pick baseline; shows picking alone is not a catalogue. |

Welkey et al. (2019) did a 3-D joint relocation of the 7,680 events in an [ESSOAr preprint](https://doi.org/10.1002/essoar.10500539.1) and a Lehigh thesis. They were seen only as metadata and are not in a journal. Scott et al. (2017) reported 43 Khövsgöl events at 5–21 km in a [GSA abstract](https://doi.org/10.1130/abs/2017AM-308111). Scott (2018) wrote a Lehigh thesis on Khövsgöl.

**2. How deep can earthquakes go? (seismogenic depth and rheology)**

| Paper | What it found | How we use it |
| --- | --- | --- |
| [Bayasgalan, Jackson & McKenzie 2005, *GJI*](https://doi.org/10.1111/j.1365-246X.2005.02764.x) | Earthquake centroid depths: seismogenic layer **< 20 km in Mongolia**, but the whole crust in the Baikal rift. | Basis of H2: Khövsgöl (Baikal tip) deeper than the Hangay. |
| [Déverchère et al. 2001, *GJI*](https://doi.org/10.1046/j.0956-540x.2001.1484.484.x) | Baikal events peak at 15–25 km and reach 30–40 km. | Expected Khövsgöl depths. |
| [Emmerson et al. 2006, *GJI*](https://doi.org/10.1111/j.1365-246X.2006.03075.x) | Earthquakes reach ~30 km in the Baikal rift; mantle is aseismic. | Interpreting rift depths. |
| [Sloan et al. 2011, *GJI*](https://doi.org/10.1111/j.1365-246X.2010.04882.x) | Lower-crustal earthquakes occur where lithosphere thickness changes sharply. | Predicts deeper events at dome *margins*. |
| [Huang & Zhao 2022, *GRL*](https://doi.org/10.1029/2022GL099525) | A ring of fast, strong lithosphere may shield the Hangay, so the dome interior is weakly seismic. | A testable claim: rate inside vs at the ring. |

**3. Active faults and great earthquakes**

| Paper | What it found | How we use it |
| --- | --- | --- |
| [Schlupp & Cisternas 2007, *GJI*](https://doi.org/10.1111/j.1365-246X.2007.03323.x) | Source models of 1905 Tsetserleg (Mw ~8) and Bulnay (Mw 8.3–8.5). | Context for Bulnay microseismicity. |
| [Choi et al. 2018, *JGR*](https://doi.org/10.1002/2017JB013962) | 1905 ruptures mapped: ~676 km total, ~388 km on Bulnay. | Fault traces to compare with seismicity. |
| [Calais et al. 2003, *JGR*](https://doi.org/10.1029/2002JB002373) | GPS: Bulnay slips 2.6 ± 1.0 mm/yr; Baikal rift opens ~4 mm/yr. | Compare seismicity rates with slip rates. |
| [Walker et al. 2008, *GJI*](https://doi.org/10.1111/j.1365-246X.2008.03874.x) | Active strike-slip faults inside an "apparently aseismic" Hangay. | Faults to test for microseismicity. |
| [Zelenin et al. 2022, *ESSD*](https://doi.org/10.5194/essd-14-4489-2022) (AFEAD) | Continental active-fault database. | Fault traces for Fig. 5 and Table 2. |
| [Ganbat & Munkhuu 2026, *Geodyn. Tectonophys.*](https://doi.org/10.5800/gt-2026-17-1-0877) | A new local-magnitude (ML) formula for Mongolia, from 2012–2019 data. | Use it for magnitudes instead of deriving our own. |

**4. Structure beneath the stations (velocity models and the thermal story)**

| Paper | What it found | How we use it |
| --- | --- | --- |
| [Feng 2021, *JGR*](https://doi.org/10.1029/2020JB021161) | 3-D shear-velocity model from XL data; thick crust beneath all three regions. | A 3-D model to test depth robustness. |
| [Comeau et al. 2018, *EPSL*](https://doi.org/10.1016/j.epsl.2018.02.007) | Conductive (fluid-rich, weak) lower crust and melt beneath the Hangay. | Explains a shallow brittle layer, if we find one. |
| [Chen et al. 2015, *GRL*](https://doi.org/10.1002/2015GL065018) | Low-velocity mantle conduit beneath the Hangay. | Thermal background. |
| [Hou, Fang & Wang 2024, *JGR*](https://doi.org/10.1029/2024JB028778) | Curie depth and thermal lithosphere for the region. | Independent thermal proxy to correlate with D90. |

**5. ML catalogues in Mongolia (precedent, not XL)**

| Paper | What it found | How we use it |
| --- | --- | --- |
| [Manceau et al. 2026, ESSOAr preprint](https://doi.org/10.22541/essoar.15010413/v1); [data on Zenodo](https://doi.org/10.5281/zenodo.23056177) | ~8,000 events from a 2023–24 network at the Bulnay–Tsetserleg junction. Uses **our exact pipeline**: PhaseNet → PyOcto → NonLinLoc → HypoDD. Reads the activity as century-long 1905 aftershocks. | Proof the pipeline works in Mongolia; a model paper to follow and cite. |
| [Munkhbaatar & Munkhuu 2025, *MJAG*](https://doi.org/10.5564/mjag.v12i1.5191) | PhaseNet + GaMMA, 4,550 aftershocks of the 2020 Tonkhil ML 6.0 earthquake. | A second Mongolian precedent. |

DOIs in groups 2–5 were checked against OpenAlex/Crossref metadata. Read the full text of any paper before citing its numbers in the paper.

## A3. Open questions and the gap

**The gap is still open, but it is narrower than PROPOSAL.md says.** As of 2026-11-24, no associated, located and relocated ML catalogue of XL data has been published or released, for any subarray. But the Hangay subarray is not untouched: the Lehigh/IAG group has a 12,912-event manual catalogue, and they are still publishing from it in 2026. And the ML pipeline itself is no longer new in Mongolia.

| Subarray | What already exists | What is missing (our contribution) |
| --- | --- | --- |
| Hangay (HD, 2012–14) | 7,680-event preliminary catalogue (Meltzer 2019); 12,912 manual events (Dashdondog 2020, not public); 2,228 and 253 HypoDD relocations (2024, 2026); 3-D relocation in a thesis | A public catalogue; ML detection gains measured against the manual catalogue; cross-correlation relocation of the whole array |
| Khövsgöl (HV, 2014–16) | Two 2017 abstracts (>2,100 detections; 43 events at 5–21 km); a 2018 Lehigh thesis | Any peer-reviewed catalogue at all |
| Gobi-Altai (AT, 2014–16) | Nothing found | Everything: first look at microseismicity near the 1957 rupture |
| All three | Public PhaseNet picks (QuakeScope), not associated | One uniform method across three tectonic settings, so depths and b-values can be compared fairly |

**What is genuinely new, ranked by how defensible it is:**

1. The first public, uniform, relocated ML catalogue of XL, with a DOI.
2. The first catalogue for the Khövsgöl and Gobi-Altai subarrays.
3. A same-method comparison of seismogenic depth across a hot dome, a rift tip and a thrust belt.
4. Template-matching enhancement of the catalogue.

The ML pipeline itself is *not* new. Manceau et al. (2026) used the same tools in Mongolia, so cite them as precedent rather than claiming novelty.

**Open questions and live debates the catalogue can speak to:**

- **How deep do earthquakes go under the Hangay?** The published answers disagree: "upper 20 km" (Meltzer 2019; Welkey preprint), "upper 30–35 km" (Welkey thesis), and 2–30 km with fluid-assisted lower-crustal events (Dashdondog 2026). Each used a different catalogue and model. A uniform relocation with honest depth errors can settle this.
- **Is Khövsgöl deeper, like the Baikal rift?** Bayasgalan et al. (2005) found seismogenic thickness below 20 km in Mongolia but whole-crust in Baikal. Khövsgöl sits between the two, and nobody has published its depth distribution.
- **Is the dome interior really quiet?** Walker et al. (2008) found active faults in an "apparently aseismic" Hangay. Huang & Zhao (2022) explain the quiet with a shielding ring. A lower Mc lets us test whether the interior is truly quiet or just under-sampled.
- **Is the low b-value real?** Meltzer's b = 0.71 is unusually low, and the authors warn it may reflect an incomplete catalogue. An ML catalogue with a lower Mc tests this directly.
- **Are these still 1905 aftershocks?** Manceau et al. (2026) interpret Bulnay–Tsetserleg activity as century-long aftershocks. Whether that holds near the Hangay faults is open.

**What this means for the plan.** Do not write "only a preliminary catalogue exists". Write "no catalogue of XL data has been publicly released, and Khövsgöl and Gobi-Altai have no peer-reviewed catalogue." Contact A. Meltzer (Lehigh) and M. Dashdondog (IAG) in week 1. They may share the 12,912-event catalogue as ground truth, and a collaboration beats a race.

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

## B1. Research question and hypotheses

The four questions in PROPOSAL.md §4 become one main question, with one catalogue deliverable and three tests.

> **Main question.** With one uniform ML catalogue of all XL data (2012–2016), how do the depth extent and the size distribution of small earthquakes differ between the Hangay Dome, the Khövsgöl rift and the Gobi-Altai?

**Deliverable D1: the catalogue.** A public, relocated catalogue for all three subarrays, with per-event uncertainties and per-subarray Mc. Success means it recovers at least 90% of ISC/EMSC events inside the network. For the Hangay, it must also reach an Mc lower than Meltzer et al.'s 1.2.

| # | Hypothesis | Prediction we can check | Grounded in |
| --- | --- | --- | --- |
| H1 | The ML catalogue is more complete than the preliminary Hangay catalogue. | Hangay Mc ≤ 1.0, with the bootstrap 95% interval below 1.2. Event count above Mc 1.2 at least equal to Meltzer's for the same months. | Meltzer 2019; detection gains in ML catalogues (A4) |
| H2a | Earthquakes under the Khövsgöl rift go deeper than under the Hangay. | D90(Khövsgöl) − D90(Hangay) > 0, and its bootstrap 95% interval excludes 0. Expected D90 is about 20 km for the Hangay and 25 km or more for Khövsgöl. | Bayasgalan 2005; Déverchère 2001 |
| H2b | Within the Hangay, the dome margins go deeper than the dome interior. | D90(margin) − D90(interior) > 0, with the 95% interval excluding 0. | Sloan 2011; Comeau 2018 |
| H3 | The low Hangay b-value (0.71) is an incompleteness artefact. | Hangay b at our Mc is higher than 0.71, with a 95% interval that excludes 0.71. | Meltzer 2019's own caveat |

**Exploratory (reported, not tested).** Which AFEAD faults carry seismicity above Mc. Whether the dome interior is quieter per km² than the fast ring around it (Huang & Zhao 2022). b-value differences between regions.

**Fix the rules before looking.** Draw the region polygons in `config/regions.geojson` before computing any depth or b-value: Hangay interior, Hangay margin, Khövsgöl, Gobi-Altai. Freeze the depth-quality filter too. Commit both, with H1–H3, to git (or an [OSF](https://osf.io) pre-registration) before the full run. Reviewers trust a result you could not have tuned.

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

## B5. Timeline and risks

Four weeks is enough for the minimum publishable result: a relocated, validated Hangay catalogue with H1 and H3 tested. Khövsgöl and Gobi-Altai (needed for H2a) come next, and template matching is a stretch goal. The dates assume you start on Monday 30 November 2026; shift them as needed.

| Task | Dates (2026) |
| --- | --- |
| Setup + station metadata | Nov 30 – Dec 2 |
| Email Meltzer and IAG | Nov 30 (milestone) |
| Bulk download | Nov 30 – Dec 9 |
| Pilot month, end to end | Dec 2 – Dec 6 |
| Freeze regions + H1–H3 | Dec 6 (milestone) |
| Full picking on H100 | Dec 7 – Dec 13 |
| Associate + locate | Dec 10 – Dec 16 |
| Relocate + magnitudes | Dec 14 – Dec 18 |
| Mc, b, D90, blast filter | Dec 16 – Dec 20 |
| **Gate: Hangay validated** | **Dec 20 (milestone)** |
| Stretch: template matching | Dec 21 – Dec 24 |
| Figures, release, draft | Dec 21 – Dec 27 |

The 20 December gate decides week 4. If the Hangay catalogue is not validated by then, drop template matching and spend week 4 on fixing the catalogue and writing. Writing the paper yourself will likely run past week 4. Plan for submission in January, after an adviser has read the draft.

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Lehigh/IAG publish an overlapping Hangay catalogue | Medium | High | Email Meltzer and Dashdondog in week 1 and offer to collaborate. Lead with Khövsgöl, Gobi-Altai and the same-method comparison, which nobody has done. |
| Depths are poorly resolved (stations ~20–60 km apart) | High | High for H2 | Use only events with a nearby station and small depth errors (rule frozen in advance). Re-locate with a second velocity model (Feng 2021). If D90 is still unresolved, publish as a null-results report. |
| Too few Khövsgöl / Gobi-Altai events for D90 or b | Medium | High for H2a | Bootstrap all estimates and report wide intervals honestly. Template matching adds events. State the minimum event count in advance. |
| Pretrained pickers misfire on Mongolian data | Medium | Medium | Use an ensemble. Hand-check 100 events. Compare with QuakeScope picks and ISC/EMSC events. |
| Quarry and mine blasts in the catalogue | Medium | Medium | Day/night ratio, known mine sites, waveform checks. Report the catalogue with blasts *flagged*, not deleted. |
| H100 or download delays | Medium | Medium | Run the Hangay subarray first. Every script runs on a CPU slice. QuakeScope picks are a fallback input. |
| Credibility as an independent researcher | Medium | Medium | ORCID, an adviser at IAG or a university, public code and data, a preprint on EarthArXiv. |

## Suggested changes to PROPOSAL.md / TASKS.md *(in progress)*
