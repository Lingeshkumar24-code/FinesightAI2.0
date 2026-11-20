"""
Capital Structure Engine
-------------------------
Weighted Average Cost of Capital (WACC) and related leverage metrics.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CapitalStructureInput:
    market_value_equity: float
    market_value_debt: float
    cost_of_equity_pct: float  # e.g. 12.0 for 12%
    cost_of_debt_pct: float  # pre-tax, e.g. 6.0 for 6%
    tax_rate_pct: float  # e.g. 25.0 for 25%


@dataclass
class CapitalStructureResult:
    equity_weight: float
    debt_weight: float
    after_tax_cost_of_debt_pct: float
    wacc_pct: float
    leverage_ratio: float  # debt / (debt + equity)


class CapitalStructureEngine:
    def compute(self, data: CapitalStructureInput) -> CapitalStructureResult:
        if data.market_value_equity < 0 or data.market_value_debt < 0:
            raise ValueError("Market values must be non-negative")

        total_capital = data.market_value_equity + data.market_value_debt
        if total_capital == 0:
            raise ValueError("Total capital (debt + equity) cannot be zero")

        equity_weight = data.market_value_equity / total_capital
        debt_weight = data.market_value_debt / total_capital

        after_tax_kd = data.cost_of_debt_pct * (1 - data.tax_rate_pct / 100.0)

        wacc = (equity_weight * data.cost_of_equity_pct) + (debt_weight * after_tax_kd)

        return CapitalStructureResult(
            equity_weight=round(equity_weight, 4),
            debt_weight=round(debt_weight, 4),
            after_tax_cost_of_debt_pct=round(after_tax_kd, 4),
            wacc_pct=round(wacc, 4),
            leverage_ratio=round(debt_weight, 4),
        )
