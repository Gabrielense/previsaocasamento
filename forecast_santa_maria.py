#!/usr/bin/env python3
"""
Santa Maria (RS) target-date forecast tracker.

Re-runnable weekly. Automatically picks the correct forecast tier for the
current lead time, always prints the ERA5 climatological baseline for
comparison, and saves a dated JSON snapshot so successive runs can be diffed.

Stdlib only. No pip install required.

Usage:
    python forecast_santa_maria.py
    python forecast_santa_maria.py --target 2026-10-03
    python forecast_santa_maria.py --target 2026-10-03 --compare
"""

import argparse
import json
import os
import statistics as st
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
LAT, LON = -29.6842, -53.8069          # Santa Maria, RS (city centre)
TZ = "America/Sao_Paulo"
TARGET_DEFAULT = "2026-10-03"
WINDOW_DAYS = 5                         # climatology window: target +/- N days
CLIM_START, CLIM_END = "1991-01-01", "2025-12-31"

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
SNAPS = os.path.join(HERE, "snapshots")

# Deterministic models polled inside the 16-day window. Each is an independent
# national NWP centre, so agreement between them is a real skill signal.
DET_MODELS = [
    "ecmwf_ifs025",        # ECMWF IFS  - best global model by objective scores
    "gfs_seamless",        # NOAA GFS
    "icon_seamless",       # DWD ICON
    "ukmo_seamless",       # UK Met Office
    "meteofrance_seamless",  # Meteo-France ARPEGE
    "jma_seamless",        # JMA GSM
]
ENS_MODELS = ["ecmwf_ifs025", "gfs025", "icon_seamless"]

DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum"


# ----------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------
def get(base, **params):
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode())


# ----------------------------------------------------------------------------
# Stats helpers
# ----------------------------------------------------------------------------
def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = round(q * (len(sorted_vals) - 1))
    return sorted_vals[int(i)]


def summarize(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    return {
        "n": len(v),
        "mean": round(st.fmean(v), 1),
        "p10": round(pct(v, 0.10), 1),
        "p25": round(pct(v, 0.25), 1),
        "median": round(pct(v, 0.50), 1),
        "p75": round(pct(v, 0.75), 1),
        "p90": round(pct(v, 0.90), 1),
        "min": round(v[0], 1),
        "max": round(v[-1], 1),
    }


def fmt(s):
    if not s:
        return "  (no data)"
    return ("n={n:<3} mean={mean:>6}  p10={p10:>6}  p25={p25:>6}  med={median:>6}  "
            "p75={p75:>6}  p90={p90:>6}  min={min:>6}  max={max:>6}").format(**s)


def prob(vals, thr, op="ge"):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    c = sum(1 for x in v if (x >= thr if op == "ge" else x <= thr))
    return round(100 * c / len(v))


# ----------------------------------------------------------------------------
# Tier A - ERA5 observed climatology (cached; the stable reference)
# ----------------------------------------------------------------------------
def climatology(target):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"era5_{CLIM_START[:4]}_{CLIM_END[:4]}.json")
    if os.path.exists(path):
        d = json.load(open(path, encoding="utf-8"))
    else:
        print("  downloading ERA5 archive (one-off, ~35 yr)...")
        d = get("https://archive-api.open-meteo.com/v1/archive",
                latitude=LAT, longitude=LON,
                start_date=CLIM_START, end_date=CLIM_END,
                daily="temperature_2m_max,temperature_2m_min,precipitation_sum",
                timezone=TZ)["daily"]
        json.dump(d, open(path, "w", encoding="utf-8"))

    # day-of-year window around the target, wrapping across years
    keep = set()
    for off in range(-WINDOW_DAYS, WINDOW_DAYS + 1):
        dt = target + timedelta(days=off)
        keep.add((dt.month, dt.day))

    tmax, tmin, pr, exact = [], [], [], []
    for i, ds in enumerate(d["time"]):
        y, m, dd = (int(x) for x in ds.split("-"))
        if (m, dd) in keep:
            tmax.append(d["temperature_2m_max"][i])
            tmin.append(d["temperature_2m_min"][i])
            pr.append(d["precipitation_sum"][i])
        if (m, dd) == (target.month, target.day):
            exact.append((y, d["temperature_2m_max"][i],
                          d["temperature_2m_min"][i], d["precipitation_sum"][i]))
    return {"tmax": tmax, "tmin": tmin, "precip": pr, "exact": exact}


# ----------------------------------------------------------------------------
# Tier B - ECMWF SEAS5 / EC46 seasonal ensemble  (lead > 15 days)
# ----------------------------------------------------------------------------
def seasonal(target):
    d = get("https://seasonal-api.open-meteo.com/v1/seasonal",
            latitude=LAT, longitude=LON, daily=DAILY_VARS, timezone=TZ)["daily"]
    if target.isoformat() not in d["time"]:
        return None
    i = d["time"].index(target.isoformat())
    out = {}
    for var in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum"):
        members = [k for k in d if k.startswith(var + "_member")]
        out[var] = [d[k][i] for k in members]
    return out


# ----------------------------------------------------------------------------
# Tier C - deterministic multi-model + ensembles  (lead <= 15 days)
# ----------------------------------------------------------------------------
def deterministic(target):
    lead = (target - date.today()).days + 1
    d = get("https://api.open-meteo.com/v1/forecast",
            latitude=LAT, longitude=LON, daily=DAILY_VARS, timezone=TZ,
            forecast_days=min(16, max(1, lead)), models=",".join(DET_MODELS))["daily"]
    if target.isoformat() not in d["time"]:
        return None
    i = d["time"].index(target.isoformat())
    rows = {}
    for m in DET_MODELS:
        rows[m] = {v: d.get(f"{v}_{m}", [None] * (i + 1))[i]
                   for v in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum")}
    return rows


def ensembles(target):
    lead = (target - date.today()).days + 1
    out = {}
    for m in ENS_MODELS:
        try:
            d = get("https://ensemble-api.open-meteo.com/v1/ensemble",
                    latitude=LAT, longitude=LON, daily=DAILY_VARS, timezone=TZ,
                    forecast_days=min(16, max(1, lead)), models=m)["daily"]
        except Exception as e:
            print(f"  [warn] ensemble {m}: {e}")
            continue
        if target.isoformat() not in d["time"]:
            continue
        i = d["time"].index(target.isoformat())
        block = {}
        for var in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum"):
            members = [k for k in d if k.startswith(var + "_member")] or [var]
            block[var] = [d[k][i] for k in members if k in d]
        out[m] = block
    return out


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=TARGET_DEFAULT)
    ap.add_argument("--compare", action="store_true",
                    help="print how previous snapshots have shifted")
    a = ap.parse_args()

    target = datetime.strptime(a.target, "%Y-%m-%d").date()
    today = date.today()
    lead = (target - today).days

    print("=" * 78)
    print(f"SANTA MARIA / RS  ({LAT}, {LON})   target {target}   run {today}   lead {lead} d")
    print("=" * 78)

    snap = {"run_date": today.isoformat(), "target": target.isoformat(), "lead_days": lead}

    # --- climatology (always) ------------------------------------------------
    print(f"\n[1] ERA5 OBSERVED CLIMATOLOGY  {CLIM_START[:4]}-{CLIM_END[:4]}, "
          f"{target.strftime('%b %d')} +/- {WINDOW_DAYS} d")
    c = climatology(target)
    print("  Tmax  C   " + fmt(summarize(c["tmax"])))
    print("  Tmin  C   " + fmt(summarize(c["tmin"])))
    print("  Rain mm   " + fmt(summarize(c["precip"])))
    print(f"  P(rain >=1mm)={prob(c['precip'],1)}%   >=5mm={prob(c['precip'],5)}%   "
          f">=10mm={prob(c['precip'],10)}%   >=20mm={prob(c['precip'],20)}%")
    print(f"  P(Tmax>=25C)={prob(c['tmax'],25)}%   P(Tmin<=10C)={prob(c['tmin'],10,'le')}%")
    snap["climatology"] = {k: summarize(c[k]) for k in ("tmax", "tmin", "precip")}

    # --- tier selection ------------------------------------------------------
    if lead < 0:
        print("\n[!] Target is in the past. Re-run with --target for a future date.")
    elif lead <= 15:
        print(f"\n[2] DETERMINISTIC MULTI-MODEL  (lead {lead} d - inside skilful range)")
        det = deterministic(target)
        if det:
            print(f"  {'model':<22}{'Tmax':>8}{'Tmin':>8}{'Rain mm':>10}")
            for m, r in det.items():
                print(f"  {m:<22}{str(r['temperature_2m_max']):>8}"
                      f"{str(r['temperature_2m_min']):>8}{str(r['precipitation_sum']):>10}")
            for var, lbl in (("temperature_2m_max", "Tmax"), ("temperature_2m_min", "Tmin"),
                             ("precipitation_sum", "Rain")):
                vals = [r[var] for r in det.values() if r[var] is not None]
                if vals:
                    print(f"  -> {lbl} model spread: {min(vals)} .. {max(vals)}  "
                          f"(mean {round(st.fmean(vals),1)})")
            snap["deterministic"] = det

        print(f"\n[3] ENSEMBLES  ({', '.join(ENS_MODELS)})")
        ens = ensembles(target)
        snap["ensemble"] = {}
        for m, b in ens.items():
            print(f"  -- {m}")
            print("     Tmax  " + fmt(summarize(b["temperature_2m_max"])))
            print("     Tmin  " + fmt(summarize(b["temperature_2m_min"])))
            print("     Rain  " + fmt(summarize(b["precipitation_sum"])))
            p = b["precipitation_sum"]
            print(f"     P(rain >=1mm)={prob(p,1)}%  >=5mm={prob(p,5)}%  >=10mm={prob(p,10)}%")
            snap["ensemble"][m] = {k: summarize(v) for k, v in b.items()}
    else:
        print(f"\n[2] ECMWF SEAS5/EC46 SEASONAL ENSEMBLE  (lead {lead} d)")
        print("    NOTE: beyond day 15 there is no deterministic skill for a single")
        print("    calendar date. Treat the spread below as a probability distribution,")
        print("    not a forecast. Read it against block [1].")
        s = seasonal(target)
        if not s:
            print("  Target outside seasonal model range.")
        else:
            print("  Tmax  C   " + fmt(summarize(s["temperature_2m_max"])))
            print("  Tmin  C   " + fmt(summarize(s["temperature_2m_min"])))
            print("  Rain mm   " + fmt(summarize(s["precipitation_sum"])))
            p = s["precipitation_sum"]
            print(f"  P(rain >=1mm)={prob(p,1)}%   >=5mm={prob(p,5)}%   >=10mm={prob(p,10)}%")
            snap["seasonal"] = {k: summarize(v) for k, v in s.items()}
            snap["seasonal_probs"] = {"rain_ge_1mm": prob(p, 1), "rain_ge_5mm": prob(p, 5),
                                      "rain_ge_10mm": prob(p, 10)}

    # --- save snapshot -------------------------------------------------------
    os.makedirs(SNAPS, exist_ok=True)
    fp = os.path.join(SNAPS, f"{target.isoformat()}_run_{today.isoformat()}.json")
    json.dump(snap, open(fp, "w", encoding="utf-8"), indent=1)
    print(f"\n[saved] {fp}")

    # --- week-over-week convergence -----------------------------------------
    if a.compare:
        print("\n[4] RUN-TO-RUN CONVERGENCE (does the signal hold?)")
        files = sorted(f for f in os.listdir(SNAPS) if f.startswith(target.isoformat()))
        print(f"  {'run':<12}{'lead':>5}{'Tmax med':>10}{'Tmin med':>10}"
              f"{'Rain med':>10}{'P>=1mm':>8}")
        for f in files:
            s = json.load(open(os.path.join(SNAPS, f), encoding="utf-8"))
            src = s.get("seasonal") or (s.get("ensemble", {}) or {}).get("ecmwf_ifs025")
            if not src:
                continue
            pr = s.get("seasonal_probs", {}).get("rain_ge_1mm", "-")
            print(f"  {s['run_date']:<12}{s['lead_days']:>5}"
                  f"{src['temperature_2m_max']['median']:>10}"
                  f"{src['temperature_2m_min']['median']:>10}"
                  f"{src['precipitation_sum']['median']:>10}{str(pr):>8}")


if __name__ == "__main__":
    main()
