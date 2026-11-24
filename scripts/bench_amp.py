"""Do half-precision (autocast fp16) picks match fp32 picks? Run on the device
that will do the picking (cuda on the cloud box; mps on the Mac).
  python scripts/bench_amp.py --device cuda --station HD01 --day 2013-05-02
"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, torch, seisbench.models as sbm
from obspy import UTCDateTime
from common import load_config, to_epoch
from pick import load_day, run_model
ap = argparse.ArgumentParser(); ap.add_argument("--device", default="mps"); ap.add_argument("--station", default="HD01")
ap.add_argument("--day", default="2013-05-02"); ap.add_argument("--config", default=None); a = ap.parse_args()
cfg = load_config(a.config); t = UTCDateTime(a.day); st = load_day(cfg, "XL", a.station, t)
for spec in cfg["picking"]["models"]:
    m = getattr(sbm, spec["model"]).from_pretrained(spec["weights"]).to(a.device).eval()
    out = {}
    for amp in (False, True):
        with torch.no_grad(), torch.autocast(device_type=a.device, dtype=torch.float16, enabled=amp):
            tic = time.time(); df = run_model(m, st, cfg, t, t + 86400); el = time.time() - tic
        out[amp] = (df, el)
    r, h = out[False][0], out[True][0]
    tr, th = to_epoch(r.time), to_epoch(h.time)
    matched = int(sum(np.min(np.abs(th - x)) <= 0.01 for x in tr)) if len(th) else 0
    print(f"{spec['model']}/{spec['weights']}: fp32 {len(r)} picks {out[False][1]:.1f}s | fp16 {len(h)} picks {out[True][1]:.1f}s | "
          f"fp32 picks reproduced within 10 ms: {matched}/{len(r)}", flush=True)
