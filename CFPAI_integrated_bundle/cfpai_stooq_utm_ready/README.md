# CFPAI Stooq 多资产现成版（带 UTM 自动调参）

## 依赖
```bash
pip install pandas numpy matplotlib requests
```

## 最小运行
```bash
python cfpai_stooq_multiasset_utm_ready.py --out-folder ./cfpai_out
```

## 自定义参数
```bash
python cfpai_stooq_multiasset_utm_ready.py \
  --symbols SPY.US QQQ.US TLT.US GLD.US XLF.US XLK.US XLE.US \
  --start 2010-01-01 \
  --end 2026-03-13 \
  --generations 6 \
  --population 12 \
  --elite-k 4 \
  --seed 430 \
  --out-folder ./cfpai_out
```

## 输出
- `multiasset_signals.csv`
- `anchor_scores.csv`
- `weights.csv`
- `utm_search_history.csv`
- `utm_performance_summary.csv`
- `best_params.json`
- `symbols.json`
- `utm_equity_curve.png`
- `utm_contraction_curve.png`
- `latest_weights.png`
- `report.md`
