"""Benchmark SeisBench picking on CPU vs Apple MPS (or CUDA) for one station-day
and check that the picks agree. Writes results/bench_picking.csv.

  python scripts/bench_picking.py --station HD01 --day 2013-05-02 --devices cpu,mps
"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, torch
import seisbench.models as sbm
from obspy import UTCDateTime
from common import load_config, path, to_epoch
from pick import load_day, run_model

ap = argparse.ArgumentParser()
ap.add_argument("--station", default="HD01"); ap.add_argument("--day", default="2013-05-02")
ap.add_argument("--devices", default="cpu,mps"); ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--cpu-models", default="PhaseNet:stead,EQTransformer:stead")
ap.add_argument("--batch", type=int, default=256)
ap.add_argument("--config", default=None); ap.add_argument("--out", default=None)
a = ap.parse_args()
cfg = load_config(a.config); cfg["picking"]["batch_size"] = a.batch
torch.set_num_threads(a.threads)
t = UTCDateTime(a.day)
st = load_day(cfg, "XL", a.station, t)
rows, picks = [], {}
cpu_models = {tuple(x.split(":")) for x in a.cpu_models.split(",")}
for spec in cfg["picking"]["models"]:
    for dev in a.devices.split(","):
        if dev == "cpu" and (spec["model"], spec["weights"]) not in cpu_models:
            continue
        m = getattr(sbm, spec["model"]).from_pretrained(spec["weights"]).to(dev).eval()
        with torch.no_grad():
            run_model(m, st.slice(t, t + 600), cfg, t, t + 600)          # warm-up
            tic = time.time(); df = run_model(m, st, cfg, t, t + 86400); el = time.time() - tic
        picks[(spec["model"], spec["weights"], dev)] = df
        rows.append(dict(model=spec["model"], weights=spec["weights"], device=dev, seconds=round(el, 1),
                         n_picks=len(df), batch=a.batch, threads=a.threads))
        print(rows[-1], flush=True)
res = pd.DataFrame(rows)
# agreement between devices
for (mo, w, dev), df in picks.items():
    if dev == "cpu":
        continue
    ref = picks.get((mo, w, "cpu"))
    if ref is None:
        continue
    tr, td = to_epoch(ref.time), to_epoch(df.time)
    matched = int(sum(np.min(np.abs(td - x)) <= 0.01 for x in tr)) if len(td) else 0
    print(f"{mo}/{w}: cpu {len(ref)} picks, {dev} {len(df)} picks, {matched} cpu picks within 10 ms on {dev}")
    res.loc[(res.model == mo) & (res.weights == w) & (res.device == dev), "cpu_picks_matched"] = matched
    res.loc[(res.model == mo) & (res.weights == w) & (res.device == dev), "cpu_picks"] = len(ref)
out = Path(cfg["paths"]["results"]); out = out if out.is_absolute() else Path(__file__).resolve().parents[1] / out
res.to_csv(a.out or (out / "bench_picking.csv"), index=False)
print(res.to_string(index=False))
