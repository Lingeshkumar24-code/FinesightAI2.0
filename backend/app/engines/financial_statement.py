"""
Financial Statement Engine
---------------------------
Computes standard liquidity, leverage, and profitability ratios from a
business's raw statement figures. All inputs are plain floats so this
engine has zero dependency on the ORM layer or any particular document
format — the RAG/ingestion layer is responsible for getting numbers into
this shape.
"""
from __future__ import annotations

from dataclasses import dataclass


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


@dataclass
class BalanceSheet:
    cash: float
    accounts_receivable: float
    inventory: float
    other_current_assets: float
    total_current_assets: float
    total_assets: float
    total_current_liabilities: float
    total_liabilities: float
    total_equity: float


@dataclass
class IncomeStatement:
    revenue: float
    cogs: float
    operating_expenses: float
    net_income: float


@dataclass
class RatioResult:
    name: str
    value: float | None
    interpretation: str


class FinancialStatementEngine:
    """Computes a standard ratio pack used across the dashboard & AI advisor."""

    def compute(
        self, balance_sheet: BalanceSheet, income_statement: IncomeStatement
    ) -> list[RatioResult]:
        bs, inc = balance_sheet, income_statement
        gross_profit = inc.revenue - inc.cogs

        results: list[RatioResult] = []

        def add(name: str, value: float | None, good_if: str):
            results.append(RatioResult(name=name, value=_round(value), interpretation=good_if))

        add(
            "current_ratio",
            _safe_div(bs.total_current_assets, bs.total_current_liabilities),
            "higher is more liquid; below 1.0 signals short-term cash risk",
        )
        add(
            "quick_ratio",
            _safe_div(
                bs.total_current_assets - bs.inventory, bs.total_current_liabilities
            ),
            "higher is better; excludes inventory from liquid assets",
        )
        add(
            "debt_to_equity",
            _safe_div(bs.total_liabilities, bs.total_equity),
            "lower means less leveraged; above 2.0 is commonly considered high",
        )
        add(
            "debt_to_assets",
            _safe_div(bs.total_liabilities, bs.total_assets),
            "share of assets financed by debt; lower is more conservative",
        )
        add(
            "gross_margin_pct",
            _pct(_safe_div(gross_profit, inc.revenue)),
            "higher means more revenue retained after direct costs",
        )
        add(
            "net_margin_pct",
            _pct(_safe_div(inc.net_income, inc.revenue)),
            "higher means more revenue converts to bottom-line profit",
        )
        add(
            "operating_margin_pct",
            _pct(
                _safe_div(
                    gross_profit - inc.operating_expenses, inc.revenue
                )
            ),
            "profitability from core operations before financing effects",
        )
        add(
            "return_on_assets_pct",
            _pct(_safe_div(inc.net_income, bs.total_assets)),
            "how efficiently assets generate profit",
        )
        add(
            "return_on_equity_pct",
            _pct(_safe_div(inc.net_income, bs.total_equity)),
            "return generated on owners' invested capital",
        )
        add(
            "working_capital",
            _round(bs.total_current_assets - bs.total_current_liabilities),
            "positive working capital means short-term obligations are covered",
        )
        return results


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _pct(value: float | None) -> float | None:
    return None if value is None else round(value * 100.0, 2)
