"""
make_walk_loop.py — tile the ~1 s walk in human_walk.usdc into a long loop.

A USD reference plays its animation once; our evacuation runs 90-220 s. So we
read the SkelAnimation's time samples (one walk cycle) and repeat them end to
end to cover the whole run, then save a new character file. Every crowd person
references THIS file, so the tiling cost is paid once.

Pure USD (pxr) -- run inside the container, no Kit, no GPU:
  bash sim/usdpy.sh sim/make_walk_loop.py \
      --in assets/human_walk.usdc --out assets/human_walk_loop.usdc --seconds 240
"""
import argparse
import math

from pxr import Usd, UsdSkel

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=240.0, help="loop long enough to cover the evac")
a = ap.parse_args()

stage = Usd.Stage.Open(a.inp)
tcps = stage.GetTimeCodesPerSecond() or 24.0

anim = None
for p in stage.Traverse():
    if p.IsA(UsdSkel.Animation):
        anim = UsdSkel.Animation(p)
        break
if anim is None:
    raise SystemExit("no UsdSkelAnimation found in " + a.inp)

attrs = [anim.GetRotationsAttr(), anim.GetTranslationsAttr(), anim.GetScalesAttr()]
# cycle length from whichever attr is animated
ref_ts = []
for at in attrs:
    if at and at.GetTimeSamples():
        ref_ts = sorted(at.GetTimeSamples())
        break
if not ref_ts:
    raise SystemExit("SkelAnimation has no time samples")
start, end = ref_ts[0], ref_ts[-1]
cycle = (end - start) or tcps
target = a.seconds * tcps
ncycles = int(math.ceil(target / cycle))

for at in attrs:
    if not at:
        continue
    ts = sorted(at.GetTimeSamples())
    if not ts:
        continue
    base = {t: at.Get(t) for t in ts}
    for c in range(1, ncycles):           # cycle 0 is the originals
        off = c * cycle
        for t in ts:
            at.Set(base[t], off + t)

stage.SetStartTimeCode(start)
stage.SetEndTimeCode(start + ncycles * cycle)
stage.GetRootLayer().Export(a.out)
print(f"[walk_loop] tiled {ncycles} cycles (cycle={cycle:.2f} tc, tcps={tcps}) "
      f"-> {a.out}  end_tc={start + ncycles * cycle:.0f} (~{(ncycles*cycle)/tcps:.0f}s)")
