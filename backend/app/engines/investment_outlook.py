"""
Investment Outlook Engine
--------------------------
Answers the owner's question "if I put ₹X into this company/asset for N
months, how much could I gain and how much could I lose?" with plain,
auditable statistics over the asset's own price history:

  * drift (annualised return) and volatility from daily log returns,
  * an 80% central range for the horizon (10th-90th percentile),
  * the 5th-percentile outcome (value at risk, 95%),
  * probability of ending below the amount invested,
  * the worst peak-to-trough drawdown in the sample,
  * a few business-context notes (cash available, runway, concentration).

All of it is deterministic math on prices the caller already fetched, so
the result can be unit-tested and explained line by line. The LLM only
narrates it afterwards - it never produces the numbers.

Model assumptions (kept deliberately simple and stated in the notes):
log returns are independent and normally distributed, and the drift and
volatility observed over the last year persist for the whole horizon.
That is the standard first-order approximation, not a promise.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

# Trading days per year / per month, the usual equity-market convention.
TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21
# z-score for the 10th/90th percentile of a normal distribution (80% band).
Z_80 = 1.2816
# z-score for the 5th percentile (95% one-sided VaR).
Z_95 = 1.6449

MIN_RETURN_OBSERVATIONS = 20


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _max_drawdown(closes: list[float]) -> float:
    """Largest peak-to-trough decline, as a positive percentage."""
    peak = closes[0]
    worst = 0.0
    for value in closes[1:]:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst * 100.0


@dataclass
class InvestmentOutlook:
    symbol: str = ""
    investment: float = 0.0
    horizon_months: int = 0
    horizon_days: int = 0

    annualized_return_pct: float = 0.0
    annualized_volatility_pct: float = 0.0
    sharpe_like: float | None = None

    expected_value: float = 0.0
    expected_profit: float = 0.0
    expected_profit_pct: float = 0.0

    best_case_value: float = 0.0
    best_case_profit: float = 0.0
    worst_case_value: float = 0.0
    worst_case_profit: float = 0.0

    var_95_value: float = 0.0
    var_95_loss: float = 0.0
    probability_of_loss_pct: float = 0.0

    max_drawdown_pct: float = 0.0
    observations: int = 0
    notes: list[str] = field(default_factory=list)


class InvestmentOutlookEngine:
    def __init__(
        self,
        min_observations: int = MIN_RETURN_OBSERVATIONS,
    ) -> None:
        self.min_observations = min_observations

    def analyze(
        self,
        closes: list[float],
        investment: float,
        horizon_months: int,
        *,
        symbol: str = "",
        cash_available: float | None = None,
        monthly_net_income: float | None = None,
    ) -> InvestmentOutlook:
        if investment <= 0:
            raise ValueError("investment must be greater than zero")
        if horizon_months <= 0:
            raise ValueError("horizon_months must be greater than zero")

        series = [float(c) for c in closes if c is not None and float(c) > 0]
        returns = [
            math.log(curr / prev)
            for prev, curr in zip(series, series[1:])
            if prev > 0 and curr > 0
        ]
        if len(returns) < self.min_observations:
            raise ValueError(
                "not enough price history for a reliable outlook "
                f"({len(returns)} observations, need {self.min_observations})"
            )

        mu_daily = statistics.fmean(returns)
        sigma_daily = statistics.stdev(returns)
        days = horizon_months * TRADING_DAYS_PER_MONTH

        drift = mu_daily * days
        shock = sigma_daily * math.sqrt(days)

        expected_value = investment * math.exp(drift)
        best_value = investment * math.exp(drift + Z_80 * shock)
        worst_value = investment * math.exp(drift - Z_80 * shock)
        var_value = investment * math.exp(drift - Z_95 * shock)

        if sigma_daily > 0:
            probability_of_loss = _normal_cdf(-mu_daily * math.sqrt(days) / sigma_daily)
        else:
            probability_of_loss = 0.0 if mu_daily >= 0 else 1.0

        annualized_return = math.exp(mu_daily * TRADING_DAYS_PER_YEAR) - 1.0
        annualized_vol = sigma_daily * math.sqrt(TRADING_DAYS_PER_YEAR)
        sharpe_like = (
            annualized_return / annualized_vol if annualized_vol > 0 else None
        )

        outlook = InvestmentOutlook(
            symbol=symbol.strip().upper(),
            investment=investment,
            horizon_months=horizon_months,
            horizon_days=days,
            annualized_return_pct=annualized_return * 100.0,
            annualized_volatility_pct=annualized_vol * 100.0,
            sharpe_like=sharpe_like,
            expected_value=expected_value,
            expected_profit=expected_value - investment,
            expected_profit_pct=(expected_value / investment - 1.0) * 100.0,
            best_case_value=best_value,
            best_case_profit=best_value - investment,
            worst_case_value=worst_value,
            worst_case_profit=worst_value - investment,
            var_95_value=var_value,
            var_95_loss=max(0.0, investment - var_value),
            probability_of_loss_pct=probability_of_loss * 100.0,
            max_drawdown_pct=_max_drawdown(series),
            observations=len(returns),
        )
        outlook.notes = self._notes(outlook, cash_available, monthly_net_income)
        return outlook

    # --- business context, in plain sentences -----------------------------

    def _notes(
        self,
        outlook: InvestmentOutlook,
        cash_available: float | None,
        monthly_net_income: float | None,
    ) -> list[str]:
        notes: list[str] = []
        investment = outlook.investment

        if cash_available is not None and cash_available > 0:
            share = investment / cash_available * 100.0
            if investment > cash_available:
                notes.append(
                    f"This is more than the ₹{cash_available:,.0f} of cash you have on hand "
                    f"(it is {share:.0f}% of it). You would need outside funding or a smaller position."
                )
            else:
                notes.append(
                    f"This uses {share:.0f}% of your ₹{cash_available:,.0f} available cash."
                )
            if monthly_net_income and monthly_net_income > 0:
                months = investment / monthly_net_income
                notes.append(
                    f"It is equal to {months:.1f} month(s) of your current net income of "
                    f"₹{monthly_net_income:,.0f}/month."
                )

        if outlook.annualized_volatility_pct >= 40:
            notes.append(
                f"Volatility is high ({outlook.annualized_volatility_pct:.0f}% a year); "
                "size the position so a bad year does not break your operating cash."
            )
        if outlook.probability_of_loss_pct >= 40:
            notes.append(
                f"There is a {outlook.probability_of_loss_pct:.0f}% modelled chance of ending "
                "below the amount invested over this horizon."
            )
        if outlook.max_drawdown_pct >= 20:
            notes.append(
                f"In the past year this asset fell as much as {outlook.max_drawdown_pct:.0f}% "
                "peak-to-trough. Expect similar swings while you hold it."
            )
        if outlook.sharpe_like is not None and outlook.sharpe_like < 0:
            notes.append(
                "Return per unit of risk is negative over the sample: the recent trend has "
                "been down, so the expected gain leans on a recovery."
            )

        notes.append(
            "Modelled from past prices (normal returns, last year's drift and volatility "
            "assumed to persist). Not investment advice."
        )
        return notes
