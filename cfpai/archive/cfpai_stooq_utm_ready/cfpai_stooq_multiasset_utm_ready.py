from __future__ import annotations

import argparse
import io
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

DEFAULT_SYMBOLS = ["SPY.US", "QQQ.US", "TLT.US", "GLD.US", "XLF.US", "XLK.US", "XLE.US"]


def download_stooq_csv(symbol: str, start: str | None = None, end: str | None = None, session: requests.Session | None = None) -> pd.DataFrame:
    sess = session or requests.Session()
    url = "https://stooq.com/q/d/l/"
    params = {"s": symbol.lower(), "i": "d"}
    if start:
        params["d1"] = pd.to_datetime(start).strftime("%Y%m%d")
    if end:
        params["d2"] = pd.to_datetime(end).strftime("%Y%m%d")
    r = sess.get(url, params=params, timeout=30)
    r.raise_for_status()
    text = r.text.strip()
    if not text or text.lower().startswith("no data"):
        raise ValueError(f"No data returned for {symbol}")
    df = pd.read_csv(io.StringIO(text))
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


@dataclass
class CFPAIParams:
    w_mom: float = 0.9
    w_trend: float = 0.2
    w_vol: float = 0.33
    w_volume: float = 0.12
    w_dd: float = 0.36
    lambda_risk: float = 0.42
    persistence_bonus: float = 0.13
    max_assets: int = 3
    cash_floor: float = 0.0


def perf_stats(returns: pd.Series) -> tuple[dict, pd.Series]:
    returns = returns.fillna(0.0)
    equity = (1 + returns).cumprod()
    total_return = equity.iloc[-1] - 1
    ann_return = equity.iloc[-1] ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else np.nan
    dd = equity / equity.cummax() - 1
    max_dd = dd.min()
    return {
        "total_return": float(total_return),
        "ann_return": float(ann_return),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe) if np.isfinite(sharpe) else np.nan,
        "max_dd": float(max_dd),
    }, equity


class CFPAIMultiAssetStooqUTM:
    def __init__(self, symbols: list[str], start: str | None = None, end: str | None = None):
        self.symbols = [s.upper() for s in symbols]
        self.start = start
        self.end = end
        self.raw = self._download_merge()

    def _download_merge(self) -> pd.DataFrame:
        merged = None
        with requests.Session() as sess:
            for symbol in self.symbols:
                df = download_stooq_csv(symbol, self.start, self.end, sess)
                keep = ["Date", "Open", "High", "Low", "Close", "Volume"]
                df = df[keep].copy()
                df = df.rename(columns={c: f"{symbol}_{c}" for c in keep if c != "Date"})
                merged = df if merged is None else merged.merge(df, on="Date", how="inner")
        return merged.sort_values("Date").reset_index(drop=True)

    def build_features(self, data: pd.DataFrame | None = None) -> pd.DataFrame:
        x = (data if data is not None else self.raw).copy()
        for a in self.symbols:
            close = x[f"{a}_Close"]
            volm = x[f"{a}_Volume"]
            x[f"{a}_ret_1d"] = close.pct_change()
            x[f"{a}_mom_20"] = close.pct_change(20)
            x[f"{a}_ma_50"] = close.rolling(50).mean()
            x[f"{a}_ma_200"] = close.rolling(200).mean()
            x[f"{a}_trend_gap"] = x[f"{a}_ma_50"] / x[f"{a}_ma_200"] - 1
            x[f"{a}_vol_20"] = x[f"{a}_ret_1d"].rolling(20).std() * np.sqrt(252)
            x[f"{a}_roll_max_63"] = close.rolling(63).max()
            x[f"{a}_drawdown_63"] = close / x[f"{a}_roll_max_63"] - 1
            vol_mean = volm.rolling(20).mean()
            vol_std = volm.rolling(20).std()
            x[f"{a}_volume_z"] = (volm - vol_mean) / vol_std
        return x.dropna().reset_index(drop=True)

    def score_assets(self, x: pd.DataFrame, p: CFPAIParams) -> pd.DataFrame:
        rows = []
        for _, row in x.iterrows():
            scores = {"Date": row["Date"]}
            for a in self.symbols:
                s = (
                    p.w_mom * row[f"{a}_mom_20"]
                    + p.w_trend * row[f"{a}_trend_gap"]
                    - p.w_vol * row[f"{a}_vol_20"]
                    + p.w_volume * np.clip(row[f"{a}_volume_z"], -3, 3)
                    + p.w_dd * row[f"{a}_drawdown_63"]
                )
                scores[a] = float(s)
            rows.append(scores)
        return pd.DataFrame(rows)

    def choose_weights(self, score_df: pd.DataFrame, feat_df: pd.DataFrame, p: CFPAIParams) -> pd.DataFrame:
        out = []
        prev_top = None
        for i in range(len(score_df)):
            scores = score_df.iloc[i].drop(labels=["Date"]).to_dict()
            adjusted = {}
            for a in self.symbols:
                risk_pen = p.lambda_risk * float(feat_df.at[i, f"{a}_vol_20"])
                bonus = p.persistence_bonus if prev_top == a else 0.0
                adjusted[a] = scores[a] - risk_pen + bonus
            ranked = sorted(adjusted.items(), key=lambda kv: kv[1], reverse=True)
            prev_top = ranked[0][0]
            chosen = ranked[:p.max_assets]
            positive = np.array([max(v, 0.0) for _, v in chosen], dtype=float)
            w = {a: 0.0 for a in self.symbols}
            if positive.sum() > 1e-12:
                positive = positive / positive.sum()
                cash_scale = max(0.0, 1.0 - p.cash_floor)
                for (a, _), ww in zip(chosen, positive):
                    w[a] = float(ww * cash_scale)
            out.append({"Date": score_df.at[i, "Date"], **w})
        return pd.DataFrame(out)

    def backtest(self, x: pd.DataFrame, p: CFPAIParams) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
        scores = self.score_assets(x, p)
        weights = self.choose_weights(scores, x, p)

        result = x[["Date"]].copy()
        for a in self.symbols:
            result[f"{a}_weight"] = weights[a].values
            result[f"{a}_ret_1d"] = x[f"{a}_ret_1d"].values

        pret = np.zeros(len(result))
        for a in self.symbols:
            pret += result[f"{a}_weight"].shift(1).fillna(0.0).to_numpy() * result[f"{a}_ret_1d"].fillna(0.0).to_numpy()
        result["portfolio_ret"] = pret
        result["equity"] = (1 + result["portfolio_ret"]).cumprod()
        stats, _ = perf_stats(result["portfolio_ret"])
        return result, stats, scores, weights


def objective(stats: dict) -> float:
    sharpe = 0.0 if np.isnan(stats["sharpe"]) else stats["sharpe"]
    return stats["ann_return"] + 0.30 * sharpe - 0.50 * abs(stats["max_dd"])


def tune_params(train_x: pd.DataFrame, val_x: pd.DataFrame, model: CFPAIMultiAssetStooqUTM, generations: int, population: int, elite_k: int, seed: int) -> tuple[CFPAIParams, pd.DataFrame]:
    param_names = ["w_mom", "w_trend", "w_vol", "w_volume", "w_dd", "lambda_risk", "persistence_bonus", "max_assets", "cash_floor"]
    means = np.array([0.9, 0.2, 0.33, 0.12, 0.36, 0.42, 0.13, 3.0, 0.0], dtype=float)
    scales = np.array([0.45, 0.18, 0.18, 0.08, 0.18, 0.20, 0.08, 0.9, 0.2], dtype=float)
    lower = np.array([0.1, -0.2, 0.01, -0.2, 0.01, 0.01, 0.0, 1.0, 0.0], dtype=float)
    upper = np.array([2.5, 1.2, 1.0, 0.5, 1.5, 1.5, 0.4, 5.0, 0.6], dtype=float)

    rng = np.random.default_rng(seed)
    history = []
    best_global = None

    for gen in range(generations):
        candidates = []
        for _ in range(population):
            vec = np.clip(rng.normal(means, scales), lower, upper)
            d = {k: float(v) for k, v in zip(param_names, vec)}
            d["max_assets"] = int(round(d["max_assets"]))
            p = CFPAIParams(**d)

            train_res, train_stats, _, _ = model.backtest(train_x, p)
            val_res, val_stats, _, _ = model.backtest(val_x, p)

            score = 0.4 * objective(train_stats) + 0.6 * objective(val_stats)
            row = {"generation": gen, "score": score, **asdict(p)}
            row.update({f"train_{k}": v for k, v in train_stats.items()})
            row.update({f"val_{k}": v for k, v in val_stats.items()})
            candidates.append((score, vec, row, p))

        candidates.sort(key=lambda z: z[0], reverse=True)
        elites = candidates[:elite_k]
        elite_vecs = np.array([v for _, v, _, _ in elites])

        means = elite_vecs.mean(axis=0)
        elite_std = elite_vecs.std(axis=0)
        scales = np.maximum(0.03 * (upper - lower), 0.85 * elite_std + 0.15 * scales)

        best_score, best_vec, best_row, best_p = elites[0]
        history.append(best_row)
        if best_global is None or best_score > best_global[0]:
            best_global = (best_score, best_p, best_row)

    return best_global[1], pd.DataFrame(history)


def parse_args():
    ap = argparse.ArgumentParser(description="CFPAI Stooq multi-asset ready version with UTM auto tuning")
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--out-folder", required=True)
    ap.add_argument("--generations", type=int, default=6)
    ap.add_argument("--population", type=int, default=12)
    ap.add_argument("--elite-k", type=int, default=4)
    ap.add_argument("--seed", type=int, default=430)
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    model = CFPAIMultiAssetStooqUTM(args.symbols, args.start, args.end)
    feat = model.build_features()

    split = int(len(feat) * 0.7)
    train_x = feat.iloc[:split].reset_index(drop=True)
    val_x = feat.iloc[split:].reset_index(drop=True)

    best_params, hist = tune_params(train_x, val_x, model, args.generations, args.population, args.elite_k, args.seed)

    full_result, full_stats, full_scores, full_weights = model.backtest(feat, best_params)
    train_result, train_stats, _, _ = model.backtest(train_x, best_params)
    val_result, val_stats, _, _ = model.backtest(val_x, best_params)

    out = Path(args.out_folder)
    out.mkdir(parents=True, exist_ok=True)

    # Save raw outputs
    full_result.to_csv(out / "multiasset_signals.csv", index=False, encoding="utf-8-sig")
    full_scores.to_csv(out / "anchor_scores.csv", index=False, encoding="utf-8-sig")
    full_weights.to_csv(out / "weights.csv", index=False, encoding="utf-8-sig")
    hist.to_csv(out / "utm_search_history.csv", index=False, encoding="utf-8-sig")

    summary = pd.DataFrame([
        {"set": "Train_CFPAI_UTM", **train_stats},
        {"set": "Val_CFPAI_UTM", **val_stats},
        {"set": "Full_CFPAI_UTM", **full_stats},
    ])
    summary.to_csv(out / "utm_performance_summary.csv", index=False, encoding="utf-8-sig")

    (out / "best_params.json").write_text(json.dumps(asdict(best_params), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "symbols.json").write_text(json.dumps(args.symbols, indent=2, ensure_ascii=False), encoding="utf-8")

    # Plots
    plt.figure(figsize=(10, 6))
    plt.plot(full_result["Date"], full_result["equity"], label="CFPAI_multiasset_UTM")
    plt.yscale("log")
    plt.legend()
    plt.title("CFPAI Stooq Multi-Asset with UTM Auto Tuning")
    plt.xlabel("Date")
    plt.ylabel("Equity (log scale)")
    plt.tight_layout()
    plt.savefig(out / "utm_equity_curve.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(hist["generation"], hist["score"], marker="o")
    plt.title("UTM contraction sequence: best score by generation")
    plt.xlabel("Generation t_n")
    plt.ylabel("Objective score")
    plt.tight_layout()
    plt.savefig(out / "utm_contraction_curve.png", dpi=160)
    plt.close()

    weight_cols = [c for c in full_weights.columns if c != "Date"]
    last_w = full_weights.iloc[-1][weight_cols].sort_values(ascending=False)
    plt.figure(figsize=(10, 5))
    plt.bar(last_w.index, last_w.values)
    plt.xticks(rotation=45, ha="right")
    plt.title("Latest CFPAI Asset Weights")
    plt.tight_layout()
    plt.savefig(out / "latest_weights.png", dpi=160)
    plt.close()

    report = f"""# CFPAI Stooq Multi-Asset Ready + UTM Auto Tuning

## Symbols
{", ".join(args.symbols)}

## Search setup
- Start: {args.start}
- End: {args.end}
- Generations: {args.generations}
- Population: {args.population}
- Elite k: {args.elite_k}
- Seed: {args.seed}

## Best params
```json
{json.dumps(asdict(best_params), indent=2, ensure_ascii=False)}
```

## Performance summary
{summary.round(4).to_markdown(index=False)}
"""
    (out / "report.md").write_text(report, encoding="utf-8")

    print(json.dumps({
        "best_params": asdict(best_params),
        "full_stats": full_stats,
        "out_folder": str(out),
    }, indent=2, ensure_ascii=False))
