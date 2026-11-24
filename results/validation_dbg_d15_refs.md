### Reference-bulletin match

| reference   |   n_ref |   n_inside |   n_inside_matched |   match_rate_inside |   n_outside_matched |   median_dist_km |   median_abs_dt_s |   median_ddepth_km |
|:------------|--------:|-----------:|-------------------:|--------------------:|--------------------:|-----------------:|------------------:|-------------------:|
| ISC         |       5 |          5 |                  5 |                1.00 |                   0 |            25.73 |              0.90 |              -5.22 |

#### Every reference event

| ref   |    ref_id | origin_time                 |   latitude |   longitude |   depth | author   | magtype   |    mag | inside   | matched   |   dist_km |   dt_s |   our_depth |   our_ml | our_quality   |   our_nsta | note   |
|:------|----------:|:----------------------------|-----------:|------------:|--------:|:---------|:----------|-------:|:---------|:----------|----------:|-------:|------------:|---------:|:--------------|-----------:|:-------|
| ISC   | 602341249 | 2013-01-01T01:14:16.727000Z |      48.45 |      102.91 |   10.00 | ISC      | mb        |   3.61 | True     | True      |     25.73 |  -0.52 |        0.00 |     4.28 | C             |         36 |        |
| ISC   | 603515264 | 2013-01-01T02:08:56.900000Z |      48.65 |      102.83 |  nan    | BYKL     | nan       | nan    | True     | True      |      4.58 |   0.90 |        0.00 |     3.21 | B             |         32 |        |
| ISC   | 602341250 | 2013-01-02T03:32:02.500000Z |      48.67 |      102.85 |  nan    | BYKL     | nan       | nan    | True     | True      |     33.60 |  -5.04 |        6.00 |     3.33 | C             |         41 |        |
| ISC   | 602400876 | 2013-01-05T06:12:48.673000Z |      46.34 |       99.89 |   10.00 | ISC      | mb        |   3.79 | True     | True      |      7.96 |   0.11 |        4.78 |     3.86 | B             |         70 |        |
| ISC   | 602855173 | 2013-01-05T13:42:48.700000Z |      45.85 |      100.32 |    0.00 | IDC      | mb1       |   4.10 | True     | True      |     65.34 |  -2.14 |        1.82 |     3.96 | B             |         69 |        |

### ISC wide-area list (all magnitudes and event types)

Box 39.4–54.5°N, 87.3–111.6°E: 15 ISC events, 5 inside the station footprint; matched to ours (±20 s, 200 km): 5 (5 of 5 inside).

ISC event types (se = earthquake, ke = known explosion, sm = suspected mine blast, kh/sh = known/suspected chemical explosion):

| etype   | inside   |   n |   matched |
|:--------|:---------|----:|----------:|
| ke      | False    |   3 |         0 |
| ke      | True     |   2 |         2 |
| kh      | False    |   1 |         0 |
| se      | False    |   5 |         0 |
| se      | True     |   3 |         3 |
| sm      | False    |   1 |         0 |

Reference magnitude minus our ML, by agency and type (n ≥ 3):

| key       |   n |   median_ref_minus_ours |   mad |
|:----------|----:|------------------------:|------:|
| IDC ML    |   3 |                   -0.56 |  0.60 |
| IDC mb    |   3 |                   -0.16 |  0.01 |
| IDC mb1   |   3 |                    0.14 |  0.01 |
| IDC mb1mx |   3 |                   -0.56 |  0.44 |
| IDC mbtmp |   3 |                   -0.16 |  0.16 |
