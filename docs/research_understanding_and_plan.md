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

## A5. Verified references *(in progress)*

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
