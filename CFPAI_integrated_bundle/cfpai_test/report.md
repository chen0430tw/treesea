# CFPAI toy test report

## Data
- Source file: `spy_stooq.csv`
- Asset: SPY
- Frequency: Daily OHLCV
- Test method: one-day-ahead exposure decision based on rolling features

## Model sketch
This is a toy CFPAI-style prototype:
1. State representation from momentum, trend gap, volatility, drawdown, and volume z-score
2. Reverse-MOROZ-style anchor scoring into `risk_on / neutral / risk_off`
3. Chain search over 2-step regime paths using rolling transition estimates
4. Tree Diagram-style local grid evaluation over exposure grid `[0.0, 0.5, 1.0]`
5. Output next-day exposure

## Performance summary
|             |   Total Return |   Annualized Return |   Annualized Vol |   Sharpe_like |   Max Drawdown |
|:------------|---------------:|--------------------:|-----------------:|--------------:|---------------:|
| CFPAI_toy   |         1.0462 |              0.0347 |           0.1189 |        0.2916 |        -0.3788 |
| BuyHold_SPY |         6.0686 |              0.0976 |           0.1906 |        0.512  |        -0.5647 |

## Notes
- This is only a structural toy test, not a production trading system.
- It uses one asset (SPY) and a very small action grid.
- It is suitable only for checking whether the **CFPAI logic chain** can be turned into a backtestable workflow.
