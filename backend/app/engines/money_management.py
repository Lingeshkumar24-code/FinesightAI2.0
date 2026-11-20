from __future__ import annotations

from collections import defaultdict

CATEGORY_RULES = {
    "Payroll": ("salary", "payroll", "wage", "employee", "pf", "esi"),
    "Rent": ("rent", "lease", "office space"),
    "Utilities": ("electricity", "water", "internet", "broadband", "mobile", "gas"),
    "Marketing": ("ads", "advertis", "campaign", "google", "facebook", "meta"),
    "Travel": ("travel", "flight", "hotel", "cab", "fuel", "petrol"),
    "Software": ("saas", "software", "subscription", "license", "cloud"),
    "Professional Fees": ("legal", "audit", "consult", "accountant", "fee"),
    "Supplies": ("office", "stationery", "raw material", "inventory", "purchase"),
    "Loan Payment": ("emi", "loan", "interest", "debit"),
}


def categorize_transaction(vendor: str, description: str, amount: float = 0.0) -> tuple[str, float, bool]:
    if amount > 0:
        return "Income", 0.9, True
    text = f"{vendor} {description}".lower()
    if not text.strip():
        return "Operations", 0.5, False
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in text for keyword in keywords):
            return category, 0.85, True
    return "Operations", 0.6, True


def analyze_budget_variance(budgets: list[dict], expenses: list[dict]) -> dict:
    actuals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        category = expense.get("category") or categorize_transaction(
            expense.get("vendor", ""), expense.get("description", ""), -abs(float(expense.get("amount", 0)))
        )[0]
        actuals[category] += abs(float(expense.get("amount", 0)))

    items = []
    for budget in budgets:
        category = budget.get("category") or "Uncategorized"
        budgeted = float(budget.get("budgeted_amount", 0))
        actual = actuals.get(category, 0.0)
        variance = budgeted - actual
        variance_pct = (variance / budgeted * 100) if budgeted else 0.0
        if budgeted == 0 and actual > 0:
            severity = "breach"
        elif variance_pct >= 10:
            severity = "favorable"
        elif variance_pct >= -5:
            severity = "on_track"
        elif variance_pct >= -15:
            severity = "watch"
        else:
            severity = "breach"
        items.append(
            {
                "category": category,
                "budgeted": round(budgeted, 2),
                "actual": round(actual, 2),
                "variance_abs": round(variance, 2),
                "variance_pct": round(variance_pct, 2),
                "severity": severity,
                "favorable": variance >= 0,
                "explanation": (
                    f"Spend was {abs(variance_pct):.1f}% {'below' if variance >= 0 else 'above'} budget for {category}."
                ),
            }
        )

    total_budgeted = sum(item["budgeted"] for item in items)
    total_actual = sum(item["actual"] for item in items)
    total_variance_pct = ((total_budgeted - total_actual) / total_budgeted * 100) if total_budgeted else 0.0
    breaches = [item["category"] for item in items if item["severity"] == "breach"]
    narrative = (
        f"Overall spend is {abs(total_variance_pct):.1f}% {'below' if total_variance_pct >= 0 else 'above'} budget. "
        + (f"Review {', '.join(breaches)}." if breaches else "All categories are within tolerance.")
    )
    return {
        "items": items,
        "total_budgeted": round(total_budgeted, 2),
        "total_actual": round(total_actual, 2),
        "total_variance_pct": round(total_variance_pct, 2),
        "narrative": narrative,
    }


def analyze_cashflow(records: list[dict]) -> dict:
    ordered = sorted(records, key=lambda row: row.get("period", ""))
    normalized = []
    for row in ordered:
        item = dict(row)
        inflow = sum(float(item.get(key, 0) or 0) for key in ("operating_inflow", "investing_inflow", "financing_inflow"))
        outflow = sum(float(item.get(key, 0) or 0) for key in ("operating_outflow", "investing_outflow", "financing_outflow"))
        opening = float(item.get("opening_cash", 0) or 0)
        item["net_cash_flow"] = round(inflow - outflow, 2)
        item["closing_cash"] = round(float(item.get("closing_cash", opening + inflow - outflow)), 2)
        normalized.append(item)

    latest = normalized[-1] if normalized else None
    if not latest:
        return {
            "records": [],
            "latest": None,
            "runway_months": None,
            "runway_note": "No cash-flow records available.",
            "average_monthly_burn": 0.0,
            "liquidity_note": "Add cash-flow records to assess liquidity.",
            "monthly": [],
        }

    monthly = [
        {
            "period": row.get("period"),
            "inflow": round(sum(float(row.get(key, 0) or 0) for key in ("operating_inflow", "investing_inflow", "financing_inflow")), 2),
            "outflow": round(sum(float(row.get(key, 0) or 0) for key in ("operating_outflow", "investing_outflow", "financing_outflow")), 2),
            "net": row["net_cash_flow"],
        }
        for row in normalized
    ]
    net_flows = [row["net_cash_flow"] for row in normalized]
    burn = -sum(net_flows) / len(net_flows) if net_flows and sum(net_flows) < 0 else 0.0
    runway = (float(latest["closing_cash"]) / burn) if burn > 0 else None
    runway_note = (
        f"At the observed average monthly net burn of {burn:,.2f}, cash lasts approximately {runway:.1f} months."
        if runway is not None
        else "Cash flow is positive on average; runway constraint is not active."
    )
    liquidity_note = (
        "Liquidity is sufficient under the observed trend."
        if runway is None or runway >= 6
        else "Liquidity requires attention: runway is below six months under the observed trend."
    )
    return {
        "records": normalized,
        "latest": latest,
        "runway_months": round(runway, 2) if runway is not None else None,
        "runway_note": runway_note,
        "average_monthly_burn": round(burn, 2),
        "liquidity_note": liquidity_note,
        "monthly": monthly,
    }


def analyze_capital_structure(records: list[dict]) -> dict:
    ordered = sorted(records, key=lambda row: row.get("period", ""))
    normalized = []
    for row in ordered:
        equity = float(row.get("shareholders_equity", 0) or 0)
        debt = float(row.get("total_debt", 0) or 0)
        assets = float(row.get("total_assets", 0) or 0)
        ebit = row.get("ebit")
        interest = row.get("interest_expense")
        item = dict(row)
        item["debt_to_equity"] = round(debt / equity, 4) if equity else None
        item["debt_to_assets"] = round(debt / assets, 4) if assets else None
        item["interest_coverage"] = round(float(ebit) / float(interest), 2) if ebit and interest and float(interest) else None
        normalized.append(item)

    latest = normalized[-1] if normalized else {}
    cost_equity = float(latest.get("cost_of_equity_pct", 10) or 10) / 100
    cost_debt = float(latest.get("cost_of_debt_pct", 6) or 6) / 100
    tax = float(latest.get("tax_rate_pct", 25) or 25) / 100
    debt = float(latest.get("total_debt", 0) or 0)
    equity = float(latest.get("shareholders_equity", 0) or 0)
    total = debt + equity
    after_tax_debt = cost_debt * (1 - tax)
    wacc = ((equity / total) * cost_equity + (debt / total) * after_tax_debt) if total else 0
    d_e = latest.get("debt_to_equity")
    if d_e is None:
        recommendation = "Add capital structure data to receive a financing recommendation."
    elif d_e > 2:
        recommendation = "Debt is high relative to equity. Prioritise deleveraging or equity funding."
    elif d_e > 1:
        recommendation = "Leverage is moderate. New debt should be tied to cash-generating assets."
    else:
        recommendation = "Leverage is conservative. Debt capacity may support selective growth investment."
    metrics = {
        "debt_to_equity": d_e,
        "debt_to_assets": latest.get("debt_to_assets"),
        "interest_coverage": latest.get("interest_coverage"),
        "wacc_pct": round(wacc * 100, 2),
        "after_tax_cost_of_debt_pct": round(after_tax_debt * 100, 2),
    }
    explanations = {
        "debt_to_equity": "Debt divided by shareholders' equity; higher values indicate more financial leverage.",
        "interest_coverage": "EBIT divided by interest expense; values below 1.5 indicate pressure on debt servicing.",
        "wacc_pct": "Weighted average cost of capital using the supplied equity, debt and tax assumptions.",
    }
    return {
        "records": normalized,
        "metrics": metrics,
        "explanations": explanations,
        "recommendation": recommendation,
    }


def analyze_working_capital(record: dict, trend: list[dict]) -> dict:
    current_assets = float(record.get("total_current_assets", 0) or 0)
    current_liabilities = float(record.get("total_current_liabilities", 0) or 0)
    receivables = float(record.get("accounts_receivable", 0) or 0)
    inventory = float(record.get("inventory", 0) or 0)
    cash = float(record.get("cash", 0) or 0)
    working_capital = current_assets - current_liabilities
    return {
        "period": record.get("period", ""),
        "working_capital": round(working_capital, 2),
        "current_ratio": round(current_assets / current_liabilities, 4) if current_liabilities else None,
        "quick_ratio": round((current_assets - inventory) / current_liabilities, 4) if current_liabilities else None,
        "receivables": round(receivables, 2),
        "payables": round(current_liabilities - float(record.get("short_term_debt", 0) or 0), 2),
        "inventory": round(inventory, 2),
        "trend": trend,
        "cash": round(cash, 2),
    }
