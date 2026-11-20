import pytest

from app.engines.budget_variance import BudgetVarianceEngine, VarianceSeverity


@pytest.fixture
def engine() -> BudgetVarianceEngine:
    return BudgetVarianceEngine(watch_threshold_pct=5.0, breach_threshold_pct=10.0)


def test_on_track_when_within_threshold(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"marketing": 10_000},
        actual={"marketing": 10_200},  # +2% -> on track
    )
    item = report.items[0]
    assert item.severity == VarianceSeverity.ON_TRACK
    assert item.variance_pct == pytest.approx(2.0)


def test_watch_band(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"marketing": 10_000},
        actual={"marketing": 10_700},  # +7% -> watch
    )
    assert report.items[0].severity == VarianceSeverity.WATCH


def test_breach_band(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"marketing": 10_000},
        actual={"marketing": 12_000},  # +20% -> breach
    )
    item = report.items[0]
    assert item.severity == VarianceSeverity.BREACH
    assert report.breaches() == [item]


def test_expense_overspend_is_unfavorable(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"rent": 5_000},
        actual={"rent": 6_000},
    )
    assert report.items[0].favorable is False


def test_revenue_overperformance_is_favorable(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"sales": 50_000},
        actual={"sales": 55_000},
        revenue_categories={"sales"},
    )
    assert report.items[0].favorable is True


def test_zero_budget_handles_without_division_error(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"new_category": 0},
        actual={"new_category": 500},
    )
    assert report.items[0].variance_pct == 100.0


def test_totals_are_aggregated(engine: BudgetVarianceEngine):
    report = engine.evaluate(
        period="2026-10",
        budget={"a": 1_000, "b": 2_000},
        actual={"a": 1_100, "b": 1_900},
    )
    assert report.total_budgeted == 3_000
    assert report.total_actual == 3_000
    assert report.total_variance_pct == 0.0


def test_invalid_thresholds_raise():
    with pytest.raises(ValueError):
        BudgetVarianceEngine(watch_threshold_pct=10.0, breach_threshold_pct=5.0)
    with pytest.raises(ValueError):
        BudgetVarianceEngine(watch_threshold_pct=-1.0)
