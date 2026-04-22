from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tree_diagram.core.himawari_structure import extract_himawari_structure_snapshot
from tree_diagram.core.structure_layer import structure_snapshot_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract cold-cloud/front/convective proxies from a Himawari Taipei-window NPZ.",
    )
    parser.add_argument("input", type=Path, help="Path to Himawari extractor NPZ containing field/latitude/longitude.")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Output JSON path. Defaults next to input with _structure.json suffix.",
    )
    parser.add_argument("--top-k-per-kind", type=int, default=4)
    parser.add_argument("--min-pixels", type=int, default=3)
    parser.add_argument("--threshold-quantile", type=float, default=0.90)
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with np.load(args.input) as data:
        field = np.asarray(data["field"], dtype=np.float64)
        lat = np.asarray(data["latitude"], dtype=np.float64)
        lon = np.asarray(data["longitude"], dtype=np.float64)

    snapshot = extract_himawari_structure_snapshot(
        field,
        top_k_per_kind=args.top_k_per_kind,
        min_pixels=args.min_pixels,
        threshold_quantile=args.threshold_quantile,
        metadata={
            "input_npz": str(args.input),
            "latitude_range": [float(lat.min()), float(lat.max())],
            "longitude_range": [float(lon.min()), float(lon.max())],
        },
    )
    out_json = args.out_json or args.input.with_name(args.input.stem + "_structure.json")
    out_json.write_text(structure_snapshot_json(snapshot), encoding="utf-8")

    if args.print_json:
        print(structure_snapshot_json(snapshot))
    else:
        print(f"saved {out_json}")
        print(json.dumps(snapshot.global_scores, ensure_ascii=False, indent=2))
        if snapshot.patches:
            best = snapshot.patches[0]
            print(
                f"top patch: {best.kind} score={best.score:.3f} "
                f"centroid={best.centroid_yx} area={best.area_pixels}"
            )


if __name__ == "__main__":
    main()
