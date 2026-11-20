"""
Risk Detection Engine
-----------------------
A transparent, rule-based risk scorer. Deliberately NOT an LLM call:
risk flags that drive alerts/notifications need to be deterministic,
explainable, and auditable. The AI Advisor can narrate these results in
natural language, but the scoring itself must not depend on a model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskFlag:
    code: str
    message: str
    level: RiskLevel
    metric_value: float | None = None


@dataclass
class RiskReport:
    overall_score: int  # 0 (best) - 100 (worst)
    overall_level: RiskLevel
    flags: list[RiskFlag] = field(default_factory=list)


@dataclass
class RiskInputs:
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    net_margin_pct: float | None = None
    cash_runway_months: float | None = None
    revenue_mom_change_pct: float | None = None  # month-over-month


class RiskDetectionEngine:
    """
    Rule thresholds are intentionally conservative defaults for a generic
    SMB. In production these would be configurable per business/industry.
    """

    def __init__(
        self,
        min_current_ratio: float = 1.0,
        max_debt_to_equity: float = 2.0,
        min_net_margin_pct: float = 0.0,
        min_cash_runway_months: float = 3.0,
        max_revenue_drop_pct: float = -15.0,
    ) -> None:
        self.min_current_ratio = min_current_ratio
        self.max_debt_to_equity = max_debt_to_equity
        self.min_net_margin_pct = min_net_margin_pct
        self.min_cash_runway_months = min_cash_runway_months
        self.max_revenue_drop_pct = max_revenue_drop_pct

    def evaluate(self, inputs: RiskInputs) -> RiskReport:
        flags: list[RiskFlag] = []
        score = 0

        if inputs.current_ratio is not None and inputs.current_ratio < self.min_current_ratio:
            severity = 25 if inputs.current_ratio < 0.5 else 15
            score += severity
            flags.append(
                RiskFlag(
                    code="LOW_LIQUIDITY",
                    message=(
                        f"Current ratio of {inputs.current_ratio:.2f} is below the "
                        f"{self.min_current_ratio:.2f} minimum — short-term obligations "
                        "may not be covered by current assets."
                    ),
                    level=RiskLevel.HIGH if severity >= 25 else RiskLevel.MODERATE,
                    metric_value=inputs.current_ratio,
                )
            )

        if (
            inputs.debt_to_equity is not None
            and inputs.debt_to_equity > self.max_debt_to_equity
        ):
            severity = 20 if inputs.debt_to_equity > 3.0 else 10
            score += severity
            flags.append(
                RiskFlag(
                    code="HIGH_LEVERAGE",
                    message=(
                        f"Debt-to-equity of {inputs.debt_to_equity:.2f} exceeds the "
                        f"{self.max_debt_to_equity:.2f} threshold."
                    ),
                    level=RiskLevel.HIGH if severity >= 20 else RiskLevel.MODERATE,
                    metric_value=inputs.debt_to_equity,
                )
            )

        if (
            inputs.net_margin_pct is not None
            and inputs.net_margin_pct < self.min_net_margin_pct
        ):
            score += 20
            flags.append(
                RiskFlag(
                    code="NEGATIVE_MARGIN",
                    message=(
                        f"Net margin is {inputs.net_margin_pct:.2f}% — the business is "
                        "operating at a loss."
                    ),
                    level=RiskLevel.HIGH,
                    metric_value=inputs.net_margin_pct,
                )
            )

        if (
            inputs.cash_runway_months is not None
            and inputs.cash_runway_months < self.min_cash_runway_months
        ):
            severity = 30 if inputs.cash_runway_months < 1.0 else 18
            score += severity
            flags.append(
                RiskFlag(
                    code="SHORT_RUNWAY",
                    message=(
                        f"Cash runway of {inputs.cash_runway_months:.1f} months is below "
                        f"the {self.min_cash_runway_months:.1f}-month minimum buffer."
                    ),
                    level=RiskLevel.CRITICAL if severity >= 30 else RiskLevel.HIGH,
                    metric_value=inputs.cash_runway_months,
                )
            )

        if (
            inputs.revenue_mom_change_pct is not None
            and inputs.revenue_mom_change_pct < self.max_revenue_drop_pct
        ):
            score += 15
            flags.append(
                RiskFlag(
                    code="REVENUE_DROP",
                    message=(
                        f"Revenue fell {inputs.revenue_mom_change_pct:.1f}% month-over-month, "
                        f"beyond the {self.max_revenue_drop_pct:.1f}% watch threshold."
                    ),
                    level=RiskLevel.MODERATE,
                    metric_value=inputs.revenue_mom_change_pct,
                )
            )

        score = min(score, 100)
        overall_level = self._level_for_score(score)
        return RiskReport(overall_score=score, overall_level=overall_level, flags=flags)

    @staticmethod
    def _level_for_score(score: int) -> RiskLevel:
        if score >= 60:
            return RiskLevel.CRITICAL
        if score >= 35:
            return RiskLevel.HIGH
        if score >= 15:
            return RiskLevel.MODERATE
        return RiskLevel.LOW
