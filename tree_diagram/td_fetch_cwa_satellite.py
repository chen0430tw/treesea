from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import requests
from PIL import Image


DEFAULT_DATASETS = ("O-C0042-002", "O-C0042-006")
DEFAULT_AUTH = "rdec-key-123-45678-011121314"
DEFAULT_OUT_DIR = "weather_sat/cwa_latest_taipei"

# Taipei-area crop used in the manual workflow.
DEFAULT_BBOX = {
    "lon_min": 121.2,
    "lon_max": 122.0,
    "lat_min": 24.8,
    "lat_max": 25.4,
}


@dataclass(frozen=True)
class BBox:
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float


@dataclass
class SatelliteArtifact:
    code: str
    desc: str
    obs_time: str
    image_url: str
    full_image: str
    taipei_crop: str
    feature_npz: str
    full_lon_range: List[float]
    full_lat_range: List[float]
    full_size: List[int]
    crop_pixels: Dict[str, int]
    crop_size: List[int]
    brightness_mean: float
    contrast_std: float
    edge_mean: float
    gray_p75: float
    gray_p90: float
    cloud_frac_ge_p75: float
    cloud_frac_ge_p90: float
    shape: List[int]


def _dataset_url(code: str, auth: str) -> str:
    return (
        "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/"
        f"{code}?Authorization={auth}&format=JSON"
    )


def _fetch_json(url: str) -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _fetch_image(url: str) -> Image.Image:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def _lonlat_to_pixels(
    bbox: BBox,
    lon_range: Tuple[float, float],
    lat_range: Tuple[float, float],
    width: int,
    height: int,
) -> Dict[str, int]:
    x0 = round((bbox.lon_min - lon_range[0]) / (lon_range[1] - lon_range[0]) * (width - 1))
    x1 = round((bbox.lon_max - lon_range[0]) / (lon_range[1] - lon_range[0]) * (width - 1))
    y0 = round((lat_range[1] - bbox.lat_max) / (lat_range[1] - lat_range[0]) * (height - 1))
    y1 = round((lat_range[1] - bbox.lat_min) / (lat_range[1] - lat_range[0]) * (height - 1))
    return {
        "x0": max(0, min(width - 1, min(x0, x1))),
        "x1": max(0, min(width - 1, max(x0, x1))),
        "y0": max(0, min(height - 1, min(y0, y1))),
        "y1": max(0, min(height - 1, max(y0, y1))),
    }


def _extract_basic_features(rgb: np.ndarray) -> Dict[str, float]:
    gray = 0.2989 * rgb[:, :, 0] + 0.5870 * rgb[:, :, 1] + 0.1140 * rgb[:, :, 2]
    gx = np.diff(gray, axis=1, prepend=gray[:, :1])
    gy = np.diff(gray, axis=0, prepend=gray[:1, :])
    edge = np.sqrt(gx * gx + gy * gy)
    p75 = float(np.quantile(gray, 0.75))
    p90 = float(np.quantile(gray, 0.90))
    return {
        "brightness_mean": float(gray.mean()),
        "contrast_std": float(gray.std()),
        "edge_mean": float(edge.mean()),
        "gray_p75": p75,
        "gray_p90": p90,
        "cloud_frac_ge_p75": float((gray >= p75).mean()),
        "cloud_frac_ge_p90": float((gray >= p90).mean()),
        "shape": [int(gray.shape[0]), int(gray.shape[1])],
        "gray": gray,
        "edge": edge,
    }


def fetch_cwa_satellite(
    out_dir: Path,
    datasets: Iterable[str],
    bbox: BBox,
    auth: str = DEFAULT_AUTH,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "CWA opendata satellite Taiwan",
        "bbox": asdict(bbox),
        "files": [],
    }

    for code in datasets:
        payload = _fetch_json(_dataset_url(code, auth))["cwaopendata"]["dataset"]
        lon_range = tuple(map(float, payload["GeoInfo"]["LongitudeRange"].split("-")))
        lat_range = tuple(map(float, payload["GeoInfo"]["LatitudeRange"].split("-")))
        obs_time = payload["ObsTime"]["Datetime"]
        desc = payload["Resource"]["ResourceDesc"]
        image_url = payload["Resource"]["ProductURL"]

        image = _fetch_image(image_url)
        width, height = image.size
        crop_pixels = _lonlat_to_pixels(bbox, lon_range, lat_range, width, height)
        crop = image.crop(
            (
                crop_pixels["x0"],
                crop_pixels["y0"],
                crop_pixels["x1"],
                crop_pixels["y1"],
            )
        )

        full_path = out_dir / f"{code}.jpg"
        crop_path = out_dir / f"{code}_taipei.jpg"
        feature_path = out_dir / f"{code}_taipei_features.npz"
        meta_path = out_dir / f"{code}.json"

        image.save(full_path, quality=95)
        crop.save(crop_path, quality=95)

        rgb = np.asarray(crop, dtype=np.float32) / 255.0
        feature_stats = _extract_basic_features(rgb)
        np.savez_compressed(
            feature_path,
            rgb=rgb,
            gray=feature_stats["gray"],
            edge=feature_stats["edge"],
        )

        artifact = SatelliteArtifact(
            code=code,
            desc=desc,
            obs_time=obs_time,
            image_url=image_url,
            full_image=str(full_path),
            taipei_crop=str(crop_path),
            feature_npz=str(feature_path),
            full_lon_range=[float(lon_range[0]), float(lon_range[1])],
            full_lat_range=[float(lat_range[0]), float(lat_range[1])],
            full_size=[width, height],
            crop_pixels=crop_pixels,
            crop_size=[crop.size[0], crop.size[1]],
            brightness_mean=feature_stats["brightness_mean"],
            contrast_std=feature_stats["contrast_std"],
            edge_mean=feature_stats["edge_mean"],
            gray_p75=feature_stats["gray_p75"],
            gray_p90=feature_stats["gray_p90"],
            cloud_frac_ge_p75=feature_stats["cloud_frac_ge_p75"],
            cloud_frac_ge_p90=feature_stats["cloud_frac_ge_p90"],
            shape=feature_stats["shape"],
        )
        meta_path.write_text(json.dumps(asdict(artifact), ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["files"].append(asdict(artifact))

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download latest CWA Taiwan satellite images, crop Taipei, and export basic feature arrays.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / DEFAULT_OUT_DIR,
        help="Output directory for images, metadata, and .npz feature arrays.",
    )
    parser.add_argument(
        "--dataset",
        nargs="+",
        default=list(DEFAULT_DATASETS),
        help="CWA dataset codes to fetch.",
    )
    parser.add_argument("--auth", default=DEFAULT_AUTH, help="CWA open-data authorization key.")
    parser.add_argument("--lon-min", type=float, default=DEFAULT_BBOX["lon_min"])
    parser.add_argument("--lon-max", type=float, default=DEFAULT_BBOX["lon_max"])
    parser.add_argument("--lat-min", type=float, default=DEFAULT_BBOX["lat_min"])
    parser.add_argument("--lat-max", type=float, default=DEFAULT_BBOX["lat_max"])
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the final manifest JSON to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bbox = BBox(
        lon_min=args.lon_min,
        lon_max=args.lon_max,
        lat_min=args.lat_min,
        lat_max=args.lat_max,
    )
    manifest = fetch_cwa_satellite(
        out_dir=args.out_dir,
        datasets=args.dataset,
        bbox=bbox,
        auth=args.auth,
    )
    if args.print_json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"saved to {args.out_dir}")
        for item in manifest["files"]:
            print(
                f"{item['code']} {item['obs_time']} "
                f"crop={item['crop_size'][0]}x{item['crop_size'][1]} "
                f"brightness={item['brightness_mean']:.4f} "
                f"edge={item['edge_mean']:.4f}"
            )


if __name__ == "__main__":
    main()
