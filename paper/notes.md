# Paper notes: every number and its source

Status: DRAFT, updated as results come in. "PILOT" marks one-month numbers (Jan 2013, Hangay). They are a methods check, not results.

## A. Literature numbers (read from the full texts, 2026-11-24)

| Number | Statement | Source (page/section) |
|---|---|---|
| 72 | HD stations, June 2012 to April 2014 | Meltzer et al. 2019, p. 1365 |
| 10–15 km; 25–80 km | HD station spacing: two SW–NE transects; 2-D array | Meltzer et al. 2019, p. 1365 |
| 21 months | Hangay deployment length | Meltzer et al. 2019, Fig. 5a caption |
| Mc 1.2 | MAXC + 0.2 correction | Meltzer et al. 2019, p. 1371, Fig. 5b |
| b 0.71 | Aki MLE, bin 0.1. "Could also reflect an incomplete earthquake catalog" | Meltzer et al. 2019, p. 1371 |
| 7680 | Events (**local and regional**) whose arrival times gave Vp 6.4 / Vs 3.6 km/s. **Not the catalog size** | Meltzer et al. 2019, p. 1371 |
| — | Detection: Antelope STA/LTA > 4 (P 1–10 Hz, S 1–5 Hz), ak135 association; events with ≥ 10 phases and M > 0 reviewed by analysts | Meltzer et al. 2019, p. 1371 |
| upper 20 km; majority upper 10 km | Depth of Hangay seismicity | Meltzer et al. 2019, p. 1371 |
| >500 | Aftershocks of the 3 Oct 2012 Mw 4.58 Bayanbulag event | Meltzer et al. 2019, p. 1372 |
| no catalog size, no release | Meltzer et al. 2019 give neither | Meltzer et al. 2019 (Data and Resources) |
| 12,912 | Events detected in the HD data, June 2012 to April 2014, **all picked manually** by MNDC (IAG) analysts | Dashdondog et al. 2020, pp. 4–6 (Fig. 4) |
| ≈ 587 per month | 12,912 / 22 months (Jun 2012 – Apr 2014): **our derived average rate**, used as the pilot benchmark | derived |
| Vp/Vs 1.73 ± 0.03 | Wadati diagram | Dashdondog et al. 2020, p. 6 |
| 8-layer model | Table 1: −5 km 6.06/3.50; 14 km 6.16/3.50; 20 km 6.27/3.63; 25 km 6.36/3.68; 30 km 6.53/3.79; 35 km 6.63/3.91; 45 km 7.16/4.18; 50 km 8.00/4.62 (Vp/Vs km/s) | Dashdondog et al. 2020, p. 8 |
| 209,901 picks, 72 stations | QuakeScope XL picks for May 2013. **We reproduced this count exactly** from the public parquet | Ni et al. 2025; `data/reference/quakescope/XL_2013_05.parquet` |
| 165,585 picks, 71 stations | QuakeScope XL picks, Jan 2013 (P 119,554, S 46,031). Minimum conf 0.20 | `data/reference/quakescope/XL_2013_01.parquet` |
| 50 / 2 / 4 | ISC / EMSC / USGS events in 43–50°N, 94–105°E during the Hangay deployment | FDSN event queries, `data/reference/*hangay_2012_2014*` |

## B. Data and compute (MEASURED)

| Number | Statement | Source file |
|---|---|---|
| 114 codes (74 HD, 26 HV, 14 AT) | station metadata | `data/meta/stations.csv` (src/stations.py) |
| 75,267 station-days (48,187 / 17,602 / 9,478) | sum of station epochs | `data/meta/stations.csv` |
| ~18.6 MB | mean raw size per station-day (HH?, 100 Hz) | `results/download_throughput.csv` |
| 3.23 / 4.37 / 4.75 MB/s | Mac download throughput at 2 / 4 / 8 streams (saturates; the local link is the limit) | `results/download_throughput.md` |
| 2.8–3.0 s / 9.9–12.5 s | PhaseNet / EQTransformer per station-day on the Apple M4 GPU (MPS), batch 256 | `results/bench_picking.csv` |
| 49.5 s / 338 s | the same on 4 CPU threads (PhaseNet / EQT stead) | `results/bench_picking.csv` |
| 11/11, 14/14 | CPU picks reproduced on MPS within 10 ms | `results/bench_picking.csv` |
| 31 % / 10 % | non-GPU share of PhaseNet / EQT picking time on MPS | profiling run (scratch); to be re-run on the 4090 |

## C. Pilot (Jan 2013, HD): filled from results/validation_month.md

Days 1–2 only (debug run, tag `dbg_d12`); full month pending:
| Number | Statement | Source |
|---|---|---|
| 3,265 → 25 | strict ensemble (p ≥ 0.3) picks → events | associate log, `data/catalogs/dbg_d12*` |
| 13,384 → 44 | adopted ensemble (p ≥ 0.1) → events (96 % of strict events included) | same |
| 37,423 → 64 | "any" (≥ 1 pair) → events (22 D-class) | same |
| 14,465 → 45 | QuakeScope picks → events, same PyOcto settings | debug run |
| 4 of 44 | split duplicates removed | `events_split_duplicates.csv` |
| 96 % | QuakeScope picks reproduced by our PhaseNet/instance at p ≥ 0.2, dt = 0 | `results/quakescope_dbg_d12.csv` |
| 3 / 3 | ISC events inside the footprint on days 1–2 matched, median offset 5.6 km | `results/validation_dbg_d12.csv` |
| 411 dt from 16 pairs | cross-correlation, CC ≥ 0.6 | xcorr log |
| 0.63 MB/event | snippet size | `data/snippets` |
| 3.5 MB per station-day | 20 Hz copy size | smoke test |


## D. Citations

All 44 entries in `paper/references.bib` were checked against Crossref, DataCite, JaLC or publisher records by a helper agent on 2026-11-24. Corrections made: zhu2019 (volume/pages added), wiemer2000 and woessner2005 (second authors), storchak2017 (journal is *Geoscience Letters* 4:32), aki1965 (DOI 10.15083/0000033631). Open items: `uhrhammer1990` has no DOI (BSSA 80(3), 702–716). `utsu1966` is the b-value significance-test paper usually cited for the ΔM/2 correction; confirm. The paper text must not say "Meltzer catalog of 7,680 events".

## C2. Pilot days 1–5 (interim; tag `dbg_d15`, primary model, datum, Mongolian ML). Source: `results/validation_days1-5_interim.md` unless noted

| Number | Statement | Source |
|---|---|---|
| 355 | station-days with data (5 empty) | §1 |
| 36,402 | ensemble picks (P 17,103, S 19,299) | §2 |
| 120 = 22 A + 67 B + 29 C + 2 D | events after removing 4 split duplicates | §4 |
| 24 per day; 718 per month; 1.2× | event rate against the manual catalogue average (587 per month) | §4 |
| 0.34 s; 0.7 km; 1.9 km; 144° | A+B median rms, erh, erz, gap | §4 |
| 68 events (p ≥ 0.3); 114 events (QuakeScope picks), 102 in common | pick-set comparison | §4 table |
| 0.37 s vs 0.46 s; 89 vs 43 A+B | primary vs 2-layer model | `notes/decisions.md` D18b |
| 23 % vs 74 % above 10 km; D90 18.9 vs 16.8 km | depth sensitivity to the model (quality A) | D18b |
| 93–95 % | QuakeScope picks reproduced by PhaseNet/instance p ≥ 0.2 (P 22,287 of 23,845; S 13,793 of 14,519) | §3 |
| 5 of 5 | ISC events inside the footprint matched; median 26 km, 0.9 s; 2 are ISC "known explosions" | §5 |
| slope 0.01–0.03 | station residual vs log R with the Mongolian scale (0.10 with Hutton & Boore, days 1–2) | magnitude log |
| n 0.57–0.60, K 0.0020 | own attenuation inversion, days 1–5 (6,226 amplitudes, 118 events); CI n 0.35–0.90 | `data/catalogs/dbg_d15/attenuation_fit.json` |
| 2,589 dt, 297 pairs, CC median 0.76 | cross-correlation | relocation section |
| 44 of 118 in 7 clusters; 0.75 km / 1.0 km shift; 0.11 / 0.22 km errors | GrowClust | relocation section |
| 4 templates, 2 days, 10 detections, FFTW = FMF | template-matching functional test | `data/catalogs/dbg_d15/templates/` |
| 0.9287, 0.0012 | Mongolian ML coefficients (Ganbat & Munkhuu 2026, Eq. 4; full text read) | paper |
| ~200,000 km²; 2500 m; ~1000 m above trend | Hangay upland (Meltzer et al. 2019, p. 1364) → 2000 m interior rule | `notes/decisions.md` D20 |
