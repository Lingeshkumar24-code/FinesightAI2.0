from __future__ import annotations


def loan_quote(principal: float, annual_rate_pct: float, tenure_months: int) -> dict:
    if principal <= 0:
        raise ValueError("principal must be positive")
    if annual_rate_pct < 0:
        raise ValueError("annual_rate_pct must be non-negative")
    if tenure_months < 1:
        raise ValueError("tenure_months must be at least 1")

    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate == 0:
        emi = principal / tenure_months
    else:
        factor = (1 + monthly_rate) ** tenure_months
        emi = principal * monthly_rate * factor / (factor - 1)

    balance = principal
    schedule = []
    total_interest = 0.0
    for month in range(1, tenure_months + 1):
        interest = balance * monthly_rate
        principal_component = emi - interest
        if month == tenure_months:
            principal_component = balance
        closing = max(0.0, balance - principal_component)
        payment = principal_component + interest
        schedule.append(
            {
                "month": month,
                "opening_balance": round(balance, 2),
                "interest": round(interest, 2),
                "principal": round(principal_component, 2),
                "closing_balance": round(closing, 2),
                "payment": round(payment, 2),
            }
        )
        total_interest += interest
        balance = closing

    return {
        "monthly_emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_repayment": round(principal + total_interest, 2),
        "schedule": schedule,
    }
