from __future__ import annotations

import bz2
import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np


@dataclass(frozen=True)
class GeoBBox:
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float


@dataclass
class HimawariFeatureSummary:
    source_path: str
    variable: str
    units: str
    obs_start_time: str
    obs_end_time: str
    bbox: Dict[str, float]
    crop_shape: Tuple[int, int]
    latitude_range: Tuple[float, float]
    longitude_range: Tuple[float, float]
    field_mean: float
    field_std: float
    field_min: float
    field_max: float
    edge_mean: float
    edge_p90: float
    cold_frac_p10: float
    warm_frac_p90: float


def _open_dataset(path: Path):
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError(
            "xarray is required for Himawari NetCDF extraction. "
            "Use the WSL environment where xarray/netCDF4 are installed."
        ) from exc

    if path.suffix == ".bz2":
        with bz2.open(path, "rb") as src, tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
            tmp.write(src.read())
            tmp_path = Path(tmp.name)
        try:
            ds = xr.open_dataset(tmp_path)
            ds.load()
        finally:
            tmp_path.unlink(missing_ok=True)
        return ds

    ds = xr.open_dataset(path)
    ds.load()
    return ds


def _pick_primary_variable(var_names: Iterable[str]) -> str:
    names = tuple(var_names)
    preferred_exact = (
        "tbb_13",
        "tbb_14",
        "tbb_15",
        "tbb_07",
        "tbb",
    )
    for name in preferred_exact:
        if name in names:
            return name
    preferred_prefix = ("tbb_", "albedo_", "radiance")
    for prefix in preferred_prefix:
        for name in names:
            if name.startswith(prefix):
                return name
    if not names:
        raise ValueError("dataset contains no data variables")
    return names[0]


def _nearest_slice(values: np.ndarray, vmin: float, vmax: float) -> slice:
    idx = np.where((values >= min(vmin, vmax)) & (values <= max(vmin, vmax)))[0]
    if idx.size:
        return slice(int(idx[0]), int(idx[-1]) + 1)
    raise ValueError(
        f"requested range [{min(vmin, vmax)}, {max(vmin, vmax)}] is outside "
        f"available coordinate range [{float(values.min())}, {float(values.max())}]"
    )


def bbox_slices(latitude: np.ndarray, longitude: np.ndarray, bbox: GeoBBox) -> Tuple[slice, slice]:
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    return _nearest_slice(lat, bbox.lat_min, bbox.lat_max), _nearest_slice(lon, bbox.lon_min, bbox.lon_max)


def compute_field_features(field: np.ndarray) -> Dict[str, float]:
    arr = np.asarray(field, dtype=float)
    gy = np.diff(arr, axis=0, prepend=arr[:1, :])
    gx = np.diff(arr, axis=1, prepend=arr[:, :1])
    edge = np.sqrt(gx * gx + gy * gy)
    p10 = float(np.quantile(arr, 0.10))
    p90 = float(np.quantile(arr, 0.90))
    return {
        "field_mean": float(arr.mean()),
        "field_std": float(arr.std()),
        "field_min": float(arr.min()),
        "field_max": float(arr.max()),
        "edge_mean": float(edge.mean()),
        "edge_p90": float(np.quantile(edge, 0.90)),
        "cold_frac_p10": float((arr <= p10).mean()),
        "warm_frac_p90": float((arr >= p90).mean()),
    }


def extract_himawari_features(path: Path, bbox: GeoBBox) -> Tuple[HimawariFeatureSummary, np.ndarray, np.ndarray, np.ndarray]:
    ds = _open_dataset(path)
    try:
        var_name = _pick_primary_variable(ds.data_vars.keys())
        lat = np.asarray(ds["latitude"].values, dtype=float)
        lon = np.asarray(ds["longitude"].values, dtype=float)
        lat_slice, lon_slice = bbox_slices(lat, lon, bbox)

        field = np.asarray(ds[var_name].values, dtype=np.float32)[lat_slice, lon_slice]
        crop_lat = lat[lat_slice]
        crop_lon = lon[lon_slice]

        if field.ndim != 2:
            raise ValueError(f"expected a 2-D field for {var_name}, got shape {field.shape}")

        stats = compute_field_features(field)
        units = str(ds[var_name].attrs.get("units", ""))
        start_time = str(np.asarray(ds["start_time"].values).reshape(-1)[0]) if "start_time" in ds else ""
        end_time = str(np.asarray(ds["end_time"].values).reshape(-1)[0]) if "end_time" in ds else ""

        summary = HimawariFeatureSummary(
            source_path=str(path),
            variable=var_name,
            units=units,
            obs_start_time=start_time,
            obs_end_time=end_time,
            bbox=asdict(bbox),
            crop_shape=(int(field.shape[0]), int(field.shape[1])),
            latitude_range=(float(crop_lat.min()), float(crop_lat.max())),
            longitude_range=(float(crop_lon.min()), float(crop_lon.max())),
            **stats,
        )
        return summary, field, crop_lat, crop_lon
    finally:
        ds.close()


def save_himawari_outputs(
    out_dir: Path,
    stem: str,
    summary: HimawariFeatureSummary,
    field: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    npz_path = out_dir / f"{stem}.npz"

    json_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(npz_path, field=field, latitude=latitude, longitude=longitude)
    return {"json": str(json_path), "npz": str(npz_path)}
