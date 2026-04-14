from __future__ import annotations

def build_path_label(anchor_asset: str, secondary_asset: str, previous_asset: str | None) -> str:
    if previous_asset == anchor_asset:
        return f"{anchor_asset} -> {anchor_asset}"
    return f"{anchor_asset} -> {secondary_asset}"
