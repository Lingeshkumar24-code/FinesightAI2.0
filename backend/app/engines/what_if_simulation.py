"""
What-If Simulation Engine
---------------------------
Projects N periods forward under adjustable business "levers" (revenue
growth rate, cost inflation, one-off cost changes, hiring cost, pricing
change). Used by the Simulator page and by the LangGraph tool-execution
node when a user asks "what if" questions.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationLevers:
    monthly_revenue_growth_pct: float = 0.0  # e.g. 2.0 = +2%/month
    monthly_cost_growth_pct: float = 0.0
    one_time_cost_change: float = 0.0  # applied in period 0 only
    new_monthly_fixed_cost: float = 0.0  # e.g. a new hire's burdened cost
    price_change_pct: float = 0.0  # applied to revenue immediately, period 0+


@dataclass
class SimulationPeriod:
    period_index: int
    revenue: float
    costs: float
    net_income: float
    cash_balance: float


@dataclass
class SimulationResult:
    periods: list[SimulationPeriod] = field(default_factory=list)
    ending_cash: float = 0.0
    breakeven_period: int | None = None


class WhatIfSimulationEngine:
    def simulate(
        self,
        starting_revenue: float,
        starting_costs: float,
        starting_cash: float,
        levers: SimulationLevers,
        periods: int = 12,
    ) -> SimulationResult:
        if periods < 1:
            raise ValueError("periods must be >= 1")

        price_multiplier = 1 + (levers.price_change_pct / 100.0)
        revenue = starting_revenue * price_multiplier
        costs = starting_costs + levers.new_monthly_fixed_cost

        cash = starting_cash
        results: list[SimulationPeriod] = []
        breakeven_period: int | None = None

        for i in range(periods):
            if i > 0:
                revenue *= 1 + (levers.monthly_revenue_growth_pct / 100.0)
                costs *= 1 + (levers.monthly_cost_growth_pct / 100.0)

            period_costs = costs + (levers.one_time_cost_change if i == 0 else 0.0)
            net_income = revenue - period_costs
            cash += net_income

            if breakeven_period is None and net_income >= 0:
                breakeven_period = i

            results.append(
                SimulationPeriod(
                    period_index=i,
                    revenue=round(revenue, 2),
                    costs=round(period_costs, 2),
                    net_income=round(net_income, 2),
                    cash_balance=round(cash, 2),
                )
            )

        return SimulationResult(
            periods=results,
            ending_cash=round(cash, 2),
            breakeven_period=breakeven_period,
        )
