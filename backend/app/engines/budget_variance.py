"""
Budget Variance Engine
-----------------------
Pure, deterministic financial logic — no I/O, no LLM calls. Kept this way
on purpose so it is trivially unit-testable and safe to call from the
LangGraph "Tool Execution" node without any network dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VarianceSeverity(str, Enum):
    ON_TRACK = "on_track"
    WATCH = "watch"
    BREACH = "breach"


@dataclass
class LineItemVariance:
    category: str
    budgeted: float
    actual: float
    variance_abs: float
    variance_pct: float
    severity: VarianceSeverity
    favorable: bool


@dataclass
class VarianceReport:
    period: str
    items: list[LineItemVariance] = field(default_factory=list)
    total_budgeted: float = 0.0
    total_actual: float = 0.0
    total_variance_pct: float = 0.0

    def breaches(self) -> list[LineItemVariance]:
        return [i for i in self.items if i.severity == VarianceSeverity.BREACH]


class BudgetVarianceEngine:
    """
    Computes per-line-item and total budget-vs-actual variance.

    `expense_categories` tells the engine which categories are costs
    (where spending *more* than budget is unfavorable) vs revenue-like
    categories (where earning *more* than budget is favorable). Defaults
    to treating everything as an expense, which is the conservative
    choice for a generic P&L line.
    """

    def __init__(
        self,
        watch_threshold_pct: float = 5.0,
        breach_threshold_pct: float = 10.0,
    ) -> None:
        if watch_threshold_pct < 0 or breach_threshold_pct < 0:
            raise ValueError("Thresholds must be non-negative")
        if breach_threshold_pct < watch_threshold_pct:
            raise ValueError("breach_threshold_pct must be >= watch_threshold_pct")
        self.watch_threshold_pct = watch_threshold_pct
        self.breach_threshold_pct = breach_threshold_pct

    def _severity(self, abs_variance_pct: float) -> VarianceSeverity:
        if abs_variance_pct >= self.breach_threshold_pct:
            return VarianceSeverity.BREACH
        if abs_variance_pct >= self.watch_threshold_pct:
            return VarianceSeverity.WATCH
        return VarianceSeverity.ON_TRACK

    def evaluate(
        self,
        period: str,
        budget: dict[str, float],
        actual: dict[str, float],
        revenue_categories: set[str] | None = None,
    ) -> VarianceReport:
        revenue_categories = revenue_categories or set()
        categories = sorted(set(budget) | set(actual))
        items: list[LineItemVariance] = []

        total_budgeted = 0.0
        total_actual = 0.0

        for category in categories:
            budgeted = float(budget.get(category, 0.0))
            actual_val = float(actual.get(category, 0.0))
            variance_abs = actual_val - budgeted

            if budgeted == 0:
                # Avoid div-by-zero; treat any nonzero actual against a
                # zero budget as a full (100%+) variance, scaled by magnitude.
                variance_pct = 0.0 if actual_val == 0 else 100.0
            else:
                variance_pct = (variance_abs / abs(budgeted)) * 100.0

            is_revenue = category in revenue_categories
            # For revenue: actual > budget is favorable (positive variance good).
            # For expense: actual < budget is favorable (negative variance good).
            favorable = variance_abs >= 0 if is_revenue else variance_abs <= 0

            items.append(
                LineItemVariance(
                    category=category,
                    budgeted=budgeted,
                    actual=actual_val,
                    variance_abs=round(variance_abs, 2),
                    variance_pct=round(variance_pct, 2),
                    severity=self._severity(abs(variance_pct)),
                    favorable=favorable,
                )
            )
            total_budgeted += budgeted
            total_actual += actual_val

        total_variance_pct = (
            0.0
            if total_budgeted == 0
            else round(((total_actual - total_budgeted) / abs(total_budgeted)) * 100.0, 2)
        )

        return VarianceReport(
            period=period,
            items=items,
            total_budgeted=round(total_budgeted, 2),
            total_actual=round(total_actual, 2),
            total_variance_pct=total_variance_pct,
        )
