"""Fetch 30 days of Taipei hourly weather from Open-Meteo archive API (ERA5)."""
from __future__ import annotations
import json
import urllib.request
from pathlib import Path
from datetime import date, timedelta

TAIPEI_LAT = 25.0478
TAIPEI_LON = 121.5319
TZ = "Asia/Taipei"

# Open-Meteo archive lag: typically ~5 days behind realtime. Use a window that
# ends ~6 days ago to guarantee availability, covers 30 days before that.
today = date(2026, 4, 19)
end = today - timedelta(days=6)           # 2026-04-13
start = end - timedelta(days=29)          # 2026-03-15

hourly_vars = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
])

url = (
    "https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={TAIPEI_LAT}&longitude={TAIPEI_LON}"
    f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
    f"&hourly={hourly_vars}&timezone={TZ}"
)

print(f"Fetching {start} .. {end} ({(end - start).days + 1} days)")
print(url)
with urllib.request.urlopen(url, timeout=60) as r:
    data = json.loads(r.read())

out = Path("D:/treesea/tree_diagram/calibration/taipei_obs_raw.json")
out.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Saved raw → {out} ({out.stat().st_size // 1024} KB)")

# Collapse to per-day means
h = data["hourly"]
times = h["time"]
from collections import defaultdict
bucket = defaultdict(list)
for i, t in enumerate(times):
    d = t.split("T")[0]
    bucket[d].append({
        "T_C":    h["temperature_2m"][i],
        "RH_pct": h["relative_humidity_2m"][i],
        "P_hPa":  h["surface_pressure"][i],
        "ws_ms":  h["wind_speed_10m"][i] / 3.6,   # Open-Meteo returns km/h; we want m/s
        "wd_deg": h["wind_direction_10m"][i],
    })

import math

daily = []
for d in sorted(bucket):
    rows = bucket[d]
    n = len(rows)
    T_mean = sum(r["T_C"] for r in rows) / n
    T_max = max(r["T_C"] for r in rows)
    T_min = min(r["T_C"] for r in rows)
    RH_mean = sum(r["RH_pct"] for r in rows) / n
    P_mean = sum(r["P_hPa"] for r in rows) / n
    ws_mean = sum(r["ws_ms"] for r in rows) / n
    u_sum = sum(r["ws_ms"] * math.sin(math.radians(r["wd_deg"])) for r in rows)
    v_sum = sum(r["ws_ms"] * math.cos(math.radians(r["wd_deg"])) for r in rows)
    wd_vec = (math.degrees(math.atan2(u_sum, v_sum)) + 360.0) % 360.0
    daily.append({
        "date": d, "n_hours": n,
        "T_mean_C": round(T_mean, 2), "T_max_C": round(T_max, 2), "T_min_C": round(T_min, 2),
        "RH_mean_pct": round(RH_mean, 1),
        "P_mean_hPa": round(P_mean, 1),
        "ws_mean_ms": round(ws_mean, 2),
        "wd_vec_deg": round(wd_vec, 0),
    })

out_daily = Path("D:/treesea/tree_diagram/calibration/taipei_obs_daily.json")
out_daily.write_text(json.dumps({"source": "Open-Meteo ERA5 archive",
                                 "location": "Taipei (25.0478, 121.5319)",
                                 "unit_notes": "T_C=°C, RH=%, P=hPa, ws=m/s (converted from km/h), wd=deg clockwise from north",
                                 "days": daily}, indent=2),
                    encoding="utf-8")
print(f"Saved daily → {out_daily}")
print(f"\nFirst 3 days:")
for r in daily[:3]:
    print(f"  {r['date']}: T={r['T_mean_C']:.1f}°C (min {r['T_min_C']:.1f}/max {r['T_max_C']:.1f})  "
          f"RH={r['RH_mean_pct']:.0f}%  P={r['P_mean_hPa']:.0f} hPa  wind={r['ws_mean_ms']:.1f} m/s @ {r['wd_vec_deg']:.0f}°")
print(f"...\nLast 3 days:")
for r in daily[-3:]:
    print(f"  {r['date']}: T={r['T_mean_C']:.1f}°C (min {r['T_min_C']:.1f}/max {r['T_max_C']:.1f})  "
          f"RH={r['RH_mean_pct']:.0f}%  P={r['P_mean_hPa']:.0f} hPa  wind={r['ws_mean_ms']:.1f} m/s @ {r['wd_vec_deg']:.0f}°")
print(f"\nTotal days: {len(daily)}")
