"""
CFPAI ↔ LASA Bridge — 資金語義分層會計整合。

LASA 告訴你有多少錢能用，CFPAI 告訴你怎麼用。

整合方向：
1. LASA → CFPAI：可支配 + 已實現 + 自由資產 → CFPAI 投入總額
2. CFPAI → LASA：槓桿部位 → 標記為借入 + 受限 + 未實現
3. 循環加槓桿防護
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LASAPortfolioInput:
    """LASA 匯出的可投資額度。"""
    disposable_cash: float       # 可支配現金（ASSET.cash - RESERVE.emergency）
    realized_income: float       # 已實現收入（INCOME.tradeRealized + broker）
    free_net_assets: float       # 自由淨資產（total_assets - total_liabilities - restricted）
    restricted_amount: float     # 受限資金總額
    risk_reserve: float          # 風險準備金
    pending_amount: float        # 待確認金額


@dataclass
class CFPAILeverageReport:
    """CFPAI 回報給 LASA 的槓桿部位。"""
    borrowed_amount: float       # 借入總額
    unrealized_pnl: float        # 未實現損益
    margin_used: float           # 已用保證金
    leverage_ratio: float        # 槓桿比率
    positions: dict[str, float]  # 各資產的名義金額


def lasa_to_cfpai_budget(lasa_input: LASAPortfolioInput) -> dict[str, float]:
    """將 LASA 資產分類轉換為 CFPAI 可用預算。

    Returns
    -------
    dict with keys:
        investable: 可投資總額
        max_leverage_base: 槓桿計算基數
        cash_reserve: 保留現金
    """
    # 可投資 = 可支配現金 + 自由淨資產的可用部分
    investable = max(0.0, lasa_input.disposable_cash + lasa_input.realized_income)

    # 槓桿基數 = 自由淨資產（不含受限和待確認）
    leverage_base = max(0.0, lasa_input.free_net_assets)

    # 保留 = 風險準備金 + 受限
    reserve = lasa_input.risk_reserve + lasa_input.restricted_amount

    return {
        "investable": round(investable, 2),
        "max_leverage_base": round(leverage_base, 2),
        "cash_reserve": round(reserve, 2),
        "pending": round(lasa_input.pending_amount, 2),
    }


def cfpai_to_lasa_tags(
    weights: dict[str, float],
    total_investment: float,
    leverage_ratio: float = 1.0,
) -> list[dict[str, Any]]:
    """將 CFPAI 配置結果轉換為 LASA 資金標記。

    Parameters
    ----------
    weights : dict
        CFPAI 輸出的資產權重（可能有負值=做空）
    total_investment : float
        投入總額
    leverage_ratio : float
        槓桿比率（>1 表示使用了槓桿）

    Returns
    -------
    list of LASA event dicts
    """
    events = []
    nominal_total = total_investment * leverage_ratio

    for symbol, weight in weights.items():
        nominal = nominal_total * weight
        if abs(nominal) < 0.01:
            continue

        if weight > 0:
            # 多頭部位
            if leverage_ratio > 1.0:
                # 超過自有資金部分標記為借入
                own_portion = min(nominal, total_investment * weight)
                borrowed = max(0, nominal - own_portion)
                events.append({
                    "symbol": symbol,
                    "accountClass": "ASSET",
                    "subClass": "tradeable",
                    "amount": round(own_portion, 2),
                    "riskTags": ["NORMAL"],
                    "description": f"CFPAI 配置 {symbol} 多頭（自有資金）",
                })
                if borrowed > 0:
                    events.append({
                        "symbol": symbol,
                        "accountClass": "LIABILITY",
                        "subClass": "shortTerm",
                        "amount": round(borrowed, 2),
                        "riskTags": ["RESTRICTED_USE", "VALUATION_RISK"],
                        "description": f"CFPAI 配置 {symbol} 多頭（借入資金，槓桿={leverage_ratio:.1f}x）",
                    })
            else:
                events.append({
                    "symbol": symbol,
                    "accountClass": "ASSET",
                    "subClass": "tradeable",
                    "amount": round(nominal, 2),
                    "riskTags": ["NORMAL"],
                    "description": f"CFPAI 配置 {symbol} 多頭",
                })
        else:
            # 空頭部位（做空）
            events.append({
                "symbol": symbol,
                "accountClass": "LIABILITY",
                "subClass": "shortTerm",
                "amount": round(abs(nominal), 2),
                "riskTags": ["HIGH_RISK", "VALUATION_RISK"],
                "description": f"CFPAI 配置 {symbol} 空頭",
            })

    return events


def check_leverage_safety(
    lasa_input: LASAPortfolioInput,
    requested_leverage: float,
    max_leverage: float = 2.0,
) -> dict[str, Any]:
    """槓桿安全檢查：防止循環加槓桿。

    Parameters
    ----------
    lasa_input : LASAPortfolioInput
        LASA 報告的當前資產狀態
    requested_leverage : float
        請求的槓桿比率
    max_leverage : float
        最大允許槓桿

    Returns
    -------
    dict with keys: approved, actual_leverage, reason
    """
    if requested_leverage <= 1.0:
        return {"approved": True, "actual_leverage": 1.0, "reason": "無槓桿"}

    # 自由淨資產必須為正
    if lasa_input.free_net_assets <= 0:
        return {
            "approved": False,
            "actual_leverage": 1.0,
            "reason": "自由淨資產 ≤ 0，無法加槓桿",
        }

    # 受限資金佔比過高 → 降低槓桿
    total = lasa_input.disposable_cash + lasa_input.realized_income + lasa_input.free_net_assets
    if total > 0:
        restricted_ratio = lasa_input.restricted_amount / total
    else:
        restricted_ratio = 1.0

    # 受限 > 30% → 最多 1.2x
    if restricted_ratio > 0.3:
        effective_max = min(1.2, max_leverage)
    else:
        effective_max = max_leverage

    actual = min(requested_leverage, effective_max)

    # 待確認金額過高 → 額外警告
    warning = ""
    if lasa_input.pending_amount > lasa_input.disposable_cash * 0.2:
        warning = "⚠ 待確認金額較高，建議確認後再加槓桿"

    return {
        "approved": actual > 1.0,
        "actual_leverage": round(actual, 2),
        "max_allowed": round(effective_max, 2),
        "restricted_ratio": round(restricted_ratio, 3),
        "reason": warning or "槓桿已核准",
    }
