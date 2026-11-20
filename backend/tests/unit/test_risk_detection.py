from app.engines.risk_detection import RiskDetectionEngine, RiskInputs, RiskLevel


def test_healthy_business_has_low_risk():
    engine = RiskDetectionEngine()
    report = engine.evaluate(
        RiskInputs(
            current_ratio=2.1,
            debt_to_equity=0.5,
            net_margin_pct=12.0,
            cash_runway_months=8.0,
            revenue_mom_change_pct=3.0,
        )
    )
    assert report.overall_level == RiskLevel.LOW
    assert report.flags == []


def test_low_liquidity_flag_raised():
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs(current_ratio=0.8))
    codes = [f.code for f in report.flags]
    assert "LOW_LIQUIDITY" in codes


def test_severe_liquidity_crisis_is_high_severity():
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs(current_ratio=0.3))
    flag = next(f for f in report.flags if f.code == "LOW_LIQUIDITY")
    assert flag.level == RiskLevel.HIGH


def test_short_runway_is_critical_when_under_one_month():
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs(cash_runway_months=0.5))
    flag = next(f for f in report.flags if f.code == "SHORT_RUNWAY")
    # A single near-zero-runway flag is itself scored CRITICAL at the
    # line-item level, even though the blended overall score (which can
    # mix in healthy metrics elsewhere) only crosses into MODERATE/HIGH.
    assert flag.level == RiskLevel.CRITICAL
    assert report.overall_level in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_negative_margin_flagged():
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs(net_margin_pct=-5.0))
    codes = [f.code for f in report.flags]
    assert "NEGATIVE_MARGIN" in codes


def test_multiple_flags_increase_overall_score_monotonically():
    engine = RiskDetectionEngine()
    one_flag = engine.evaluate(RiskInputs(current_ratio=0.8))
    two_flags = engine.evaluate(RiskInputs(current_ratio=0.8, debt_to_equity=3.5))
    assert two_flags.overall_score > one_flag.overall_score


def test_score_is_capped_at_100():
    engine = RiskDetectionEngine()
    report = engine.evaluate(
        RiskInputs(
            current_ratio=0.1,
            debt_to_equity=10.0,
            net_margin_pct=-50.0,
            cash_runway_months=0.1,
            revenue_mom_change_pct=-90.0,
        )
    )
    assert report.overall_score <= 100
    assert report.overall_level == RiskLevel.CRITICAL


def test_none_inputs_produce_no_flags():
    engine = RiskDetectionEngine()
    report = engine.evaluate(RiskInputs())
    assert report.flags == []
    assert report.overall_score == 0
