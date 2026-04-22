from __future__ import annotations

import ftplib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .himawari_extract import GeoBBox, extract_himawari_features


JST = timezone(timedelta(hours=9))
PTREE_HOST = "ftp.ptree.jaxa.jp"
PTREE_SUBDIR = "/jma/netcdf/{yyyymm}/{dd}"


@dataclass
class HimawariAmvSummary:
    previous_path: str
    current_path: str
    bbox: dict[str, float]
    crop_shape: tuple[int, int]
    dt_seconds: float
    mean_u_ms: float
    mean_v_ms: float
    mean_speed_ms: float
    mean_direction_deg: float
    global_shift_yx: tuple[float, float]
    tile_shape: tuple[int, int]
    grid_shape: tuple[int, int]
    valid_fraction: float
    mean_quality: float


def _phase_correlation_shift(prev_field: np.ndarray, curr_field: np.ndarray) -> tuple[float, float, float]:
    a = np.asarray(prev_field, dtype=np.float64)
    b = np.asarray(curr_field, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("prev_field and curr_field must share 2-D shape")
    a = a - float(a.mean())
    b = b - float(b.mean())
    if np.allclose(a.std(), 0.0) or np.allclose(b.std(), 0.0):
        return 0.0, 0.0, 0.0
    win_y = np.hanning(a.shape[0])[:, None]
    win_x = np.hanning(a.shape[1])[None, :]
    w = win_y * win_x
    fa = np.fft.fft2(a * w)
    fb = np.fft.fft2(b * w)
    cps = fa * np.conj(fb)
    denom = np.maximum(np.abs(cps), 1.0e-12)
    corr = np.fft.ifft2(cps / denom)
    corr_abs = np.abs(corr)
    peak = np.unravel_index(int(np.argmax(corr_abs)), corr_abs.shape)
    py, px = int(peak[0]), int(peak[1])
    H, W = a.shape
    dy = py if py <= H // 2 else py - H
    dx = px if px <= W // 2 else px - W
    peak_val = float(corr_abs[py, px])
    mean_val = float(corr_abs.mean())
    quality = peak_val / max(1.0e-12, mean_val)
    # shift needed to move prev -> curr
    return float(-dy), float(-dx), quality


def _meters_per_degree_lat() -> float:
    return 111_320.0


def _meters_per_degree_lon(lat_deg: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat_deg))


def _shift_to_uv(dx_pix: float, dy_pix: float, lat: np.ndarray, lon: np.ndarray, dt_seconds: float) -> tuple[float, float]:
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    mean_lat = float(lat.mean())
    dlat = float(abs(np.diff(lat).mean())) if lat.size > 1 else 0.02
    dlon = float(abs(np.diff(lon).mean())) if lon.size > 1 else 0.02
    meters_x = dx_pix * dlon * _meters_per_degree_lon(mean_lat)
    # array y grows southward; north+ must flip sign
    meters_y = -dy_pix * dlat * _meters_per_degree_lat()
    return float(meters_x / dt_seconds), float(meters_y / dt_seconds)


def _wind_direction_from_uv(u_ms: float, v_ms: float) -> float:
    return float((math.degrees(math.atan2(-u_ms, -v_ms)) + 360.0) % 360.0)


def _tile_bounds(n: int, parts: int) -> list[tuple[int, int]]:
    edges = np.linspace(0, n, parts + 1, dtype=int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(parts)]


def compute_pseudo_amv(
    prev_field: np.ndarray,
    curr_field: np.ndarray,
    latitude: np.ndarray,
    longitude: np.ndarray,
    *,
    dt_seconds: float,
    tile_rows: int = 3,
    tile_cols: int = 4,
) -> dict[str, Any]:
    prev = np.asarray(prev_field, dtype=np.float32)
    curr = np.asarray(curr_field, dtype=np.float32)
    if prev.shape != curr.shape or prev.ndim != 2:
        raise ValueError("prev_field and curr_field must share 2-D shape")
    H, W = prev.shape
    dy, dx, quality = _phase_correlation_shift(prev, curr)
    mean_u, mean_v = _shift_to_uv(dx, dy, latitude, longitude, dt_seconds)

    tile_u = np.full((tile_rows, tile_cols), np.nan, dtype=np.float32)
    tile_v = np.full((tile_rows, tile_cols), np.nan, dtype=np.float32)
    tile_quality = np.zeros((tile_rows, tile_cols), dtype=np.float32)
    tile_shift = np.zeros((tile_rows, tile_cols, 2), dtype=np.float32)

    y_bins = _tile_bounds(H, tile_rows)
    x_bins = _tile_bounds(W, tile_cols)
    valid = 0
    for iy, (y0, y1) in enumerate(y_bins):
        for ix, (x0, x1) in enumerate(x_bins):
            if (y1 - y0) < 4 or (x1 - x0) < 4:
                continue
            p = prev[y0:y1, x0:x1]
            c = curr[y0:y1, x0:x1]
            ddy, ddx, q = _phase_correlation_shift(p, c)
            u, v = _shift_to_uv(ddx, ddy, latitude[y0:y1], longitude[x0:x1], dt_seconds)
            tile_u[iy, ix] = u
            tile_v[iy, ix] = v
            tile_quality[iy, ix] = q
            tile_shift[iy, ix, 0] = ddy
            tile_shift[iy, ix, 1] = ddx
            valid += 1

    mean_speed = float(math.hypot(mean_u, mean_v))
    mean_dir = _wind_direction_from_uv(mean_u, mean_v)
    return {
        "mean_u_ms": float(mean_u),
        "mean_v_ms": float(mean_v),
        "mean_speed_ms": mean_speed,
        "mean_direction_deg": mean_dir,
        "global_shift_yx": [float(dy), float(dx)],
        "global_quality": float(quality),
        "tile_u_ms": tile_u,
        "tile_v_ms": tile_v,
        "tile_quality": tile_quality,
        "tile_shift_yx": tile_shift,
        "tile_rows": int(tile_rows),
        "tile_cols": int(tile_cols),
        "valid_fraction": float(valid / max(1, tile_rows * tile_cols)),
        "mean_quality": float(np.nanmean(tile_quality)) if valid else 0.0,
    }


def extract_himawari_amv(
    previous_path: Path,
    current_path: Path,
    bbox: GeoBBox,
    *,
    tile_rows: int = 3,
    tile_cols: int = 4,
) -> tuple[HimawariAmvSummary, dict[str, Any]]:
    prev_summary, prev_field, prev_lat, prev_lon = extract_himawari_features(previous_path, bbox)
    curr_summary, curr_field, curr_lat, curr_lon = extract_himawari_features(current_path, bbox)
    if prev_summary.crop_shape != curr_summary.crop_shape:
        raise ValueError("previous and current crops must share the same shape")
    start_prev = np.datetime64(prev_summary.obs_start_time)
    start_curr = np.datetime64(curr_summary.obs_start_time)
    dt_seconds = float((start_curr - start_prev) / np.timedelta64(1, "s"))
    if dt_seconds <= 0.0:
        raise ValueError("current frame must be later than previous frame")
    amv = compute_pseudo_amv(
        prev_field,
        curr_field,
        curr_lat,
        curr_lon,
        dt_seconds=dt_seconds,
        tile_rows=tile_rows,
        tile_cols=tile_cols,
    )
    summary = HimawariAmvSummary(
        previous_path=str(previous_path),
        current_path=str(current_path),
        bbox=asdict(bbox),
        crop_shape=curr_summary.crop_shape,
        dt_seconds=dt_seconds,
        mean_u_ms=float(amv["mean_u_ms"]),
        mean_v_ms=float(amv["mean_v_ms"]),
        mean_speed_ms=float(amv["mean_speed_ms"]),
        mean_direction_deg=float(amv["mean_direction_deg"]),
        global_shift_yx=(float(amv["global_shift_yx"][0]), float(amv["global_shift_yx"][1])),
        tile_shape=(int(curr_summary.crop_shape[0]), int(curr_summary.crop_shape[1])),
        grid_shape=(int(tile_rows), int(tile_cols)),
        valid_fraction=float(amv["valid_fraction"]),
        mean_quality=float(amv["mean_quality"]),
    )
    return summary, amv


def _full_disk_filename(ts_utc: datetime) -> str:
    return f"NC_H09_{ts_utc:%Y%m%d_%H%M}_R21_FLDK.02801_02401.nc"


def fetch_ptree_full_disk(
    ts_utc: datetime,
    out_dir: Path,
    *,
    user: str,
    password: str,
    host: str = PTREE_HOST,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = _full_disk_filename(ts_utc)
    local_path = out_dir / filename
    if local_path.exists():
        return local_path
    remote_dir = PTREE_SUBDIR.format(yyyymm=ts_utc.strftime("%Y%m"), dd=ts_utc.strftime("%d"))
    with ftplib.FTP(host) as ftp:
        ftp.login(user=user, passwd=password)
        ftp.cwd(remote_dir)
        with local_path.open("wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write)
    return local_path


def save_himawari_amv_outputs(
    out_dir: Path,
    stem: str,
    summary: HimawariAmvSummary,
    amv: dict[str, Any],
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}_amv.json"
    npz_path = out_dir / f"{stem}_amv.npz"
    json_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(
        npz_path,
        tile_u_ms=amv["tile_u_ms"],
        tile_v_ms=amv["tile_v_ms"],
        tile_quality=amv["tile_quality"],
        tile_shift_yx=amv["tile_shift_yx"],
    )
    return {"json": str(json_path), "npz": str(npz_path)}
