from __future__ import annotations

import argparse
import json
from pathlib import Path

from tree_diagram.io.himawari_extract import (
    GeoBBox,
    extract_himawari_features,
    save_himawari_outputs,
)


DEFAULT_BBOX = GeoBBox(
    lon_min=121.2,
    lon_max=122.0,
    lat_min=24.8,
    lat_max=25.4,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a Taipei-window field summary from a JMA Himawari NetCDF sample.",
    )
    parser.add_argument("input", type=Path, help="Path to Himawari .nc or .nc.bz2 file.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "weather_sat" / "jma_sample" / "processed",
        help="Directory for .json and .npz outputs.",
    )
    parser.add_argument("--stem", default="", help="Optional output stem; defaults to input filename stem.")
    parser.add_argument("--lon-min", type=float, default=DEFAULT_BBOX.lon_min)
    parser.add_argument("--lon-max", type=float, default=DEFAULT_BBOX.lon_max)
    parser.add_argument("--lat-min", type=float, default=DEFAULT_BBOX.lat_min)
    parser.add_argument("--lat-max", type=float, default=DEFAULT_BBOX.lat_max)
    parser.add_argument("--print-json", action="store_true", help="Print the summary JSON to stdout.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bbox = GeoBBox(
        lon_min=args.lon_min,
        lon_max=args.lon_max,
        lat_min=args.lat_min,
        lat_max=args.lat_max,
    )
    summary, field, latitude, longitude = extract_himawari_features(args.input, bbox)
    stem = args.stem or args.input.name.replace(".nc.bz2", "").replace(".nc", "")
    outputs = save_himawari_outputs(args.out_dir, stem, summary, field, latitude, longitude)

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
            f"{summary.variable} {summary.crop_shape[0]}x{summary.crop_shape[1]} "
            f"mean={summary.field_mean:.3f} {summary.units} "
            f"edge_p90={summary.edge_p90:.3f}"
        )


if __name__ == "__main__":
    main()
