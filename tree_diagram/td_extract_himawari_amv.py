from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tree_diagram.io.himawari_amv import (
    GeoBBox,
    extract_himawari_amv,
    fetch_ptree_full_disk,
    save_himawari_amv_outputs,
)


JST = timezone(timedelta(hours=9))
DEFAULT_BBOX = GeoBBox(
    lon_min=121.2,
    lon_max=122.0,
    lat_min=24.8,
    lat_max=25.4,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download/extract two-frame Himawari pseudo-AMV over Taipei.")
    p.add_argument("--current", type=Path, default=None, help="Current Himawari full-disk .nc")
    p.add_argument("--previous", type=Path, default=None, help="Previous Himawari full-disk .nc")
    p.add_argument("--timestamp-jst", default="2026-04-22T03:40:00+08:00", help="Current frame timestamp in JST if downloading")
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "weather_sat" / "jma_sample" / "processed")
    p.add_argument("--download-dir", type=Path, default=Path(__file__).resolve().parent / "weather_sat" / "jma_sample")
    p.add_argument("--lon-min", type=float, default=DEFAULT_BBOX.lon_min)
    p.add_argument("--lon-max", type=float, default=DEFAULT_BBOX.lon_max)
    p.add_argument("--lat-min", type=float, default=DEFAULT_BBOX.lat_min)
    p.add_argument("--lat-max", type=float, default=DEFAULT_BBOX.lat_max)
    p.add_argument("--tile-rows", type=int, default=3)
    p.add_argument("--tile-cols", type=int, default=4)
    p.add_argument("--print-json", action="store_true")
    return p.parse_args()


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.current and args.previous:
        return args.previous, args.current
    user = os.environ.get("JAXA_PTREE_USER")
    password = os.environ.get("JAXA_PTREE_PASS")
    if not user or not password:
        raise RuntimeError("set JAXA_PTREE_USER and JAXA_PTREE_PASS to download Himawari full-disk files")
    ts_jst = datetime.fromisoformat(args.timestamp_jst)
    if ts_jst.tzinfo is None:
        ts_jst = ts_jst.replace(tzinfo=JST)
    ts_utc = ts_jst.astimezone(timezone.utc).replace(tzinfo=None)
    prev_utc = ts_utc - timedelta(minutes=10)
    prev_path = fetch_ptree_full_disk(prev_utc, args.download_dir, user=user, password=password)
    curr_path = fetch_ptree_full_disk(ts_utc, args.download_dir, user=user, password=password)
    return prev_path, curr_path


def main() -> None:
    args = parse_args()
    bbox = GeoBBox(args.lon_min, args.lon_max, args.lat_min, args.lat_max)
    previous_path, current_path = _resolve_paths(args)
    summary, amv = extract_himawari_amv(
        previous_path,
        current_path,
        bbox,
        tile_rows=args.tile_rows,
        tile_cols=args.tile_cols,
    )
    stem = current_path.name.replace(".nc", "")
    outputs = save_himawari_amv_outputs(args.out_dir, stem, summary, amv)
    payload = {
        "summary": json.loads(json.dumps(summary, default=lambda o: o.__dict__, ensure_ascii=False)),
        "outputs": outputs,
    }
    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"saved {outputs['json']}")
        print(f"saved {outputs['npz']}")
        print(
            f"pseudo-AMV mean={summary.mean_speed_ms:.2f}m/s@{summary.mean_direction_deg:.0f} "
            f"dt={summary.dt_seconds:.0f}s valid={summary.valid_fraction:.2f}"
        )


if __name__ == "__main__":
    main()
