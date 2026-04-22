from __future__ import annotations

import argparse
import json
from pathlib import Path

from tree_diagram.core.structure_alignment import scan_td_probe_against_satellite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare satellite-derived structure patches against TD structure patches across a TD probe sequence.",
    )
    parser.add_argument("satellite_json", type=Path, help="Satellite structure JSON from td_extract_himawari_structure.py")
    parser.add_argument("td_probe", type=Path, help="TD probe NPZ containing h/T/q/u/v sequences")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Output path for the comparison report. Defaults next to the satellite JSON.",
    )
    parser.add_argument("--top-k-per-kind", type=int, default=4)
    parser.add_argument("--min-pixels", type=int, default=6)
    parser.add_argument("--threshold-quantile", type=float, default=0.93)
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = scan_td_probe_against_satellite(
        args.satellite_json,
        args.td_probe,
        top_k_per_kind=args.top_k_per_kind,
        min_pixels=args.min_pixels,
        threshold_quantile=args.threshold_quantile,
    )
    out_json = args.out_json or args.satellite_json.with_name(args.satellite_json.stem + "_vs_td.json")
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    best = report["best_frame"]
    print(f"saved {out_json}")
    if not best:
        print("no comparable frames")
        return
    print(f"best frame: {best['frame_idx']} score={best['frame_score']:.3f}")
    for item in best["alignments"]:
        print(
            f"{item['satellite_kind']} -> {item['td_kind']} "
            f"score={item['alignment_score']:.3f} "
            f"centroid_dist={item['centroid_distance']:.3f} "
            f"orientation_delta={item['orientation_delta_deg']:.1f}"
        )


if __name__ == "__main__":
    main()
