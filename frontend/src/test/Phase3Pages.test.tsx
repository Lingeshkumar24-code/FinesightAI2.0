import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  api,
  type BusinessForecast,
  type CapitalAnalysis,
  type CashFlowAnalysis,
  type MoneyTransaction,
  type SavedScenario,
  type VarianceAnalysis,
  type WorkingCapital,
} from "../lib/api";
import { MoneyManagement } from "../pages/MoneyManagement";

const cashflow: CashFlowAnalysis = {
  records: [],
  latest: {
    id: "cf-1", business_id: "demo-business-001", period: "2026-Q4",
    opening_cash: 10000, operating_inflow: 8000, operating_outflow: 12000,
    investing_inflow: 0, investing_outflow: 1000, financing_inflow: 0, financing_outflow: 0,
    closing_cash: 5000, net_cash_flow: -5000, notes: "", created_at: "2026-11-19T00:00:00Z",
  },
  runway_months: 1.25,
  runway_note: "Runway below six months",
  average_monthly_burn: 4000,
  liquidity_note: "Cash is declining",
  monthly: [],
};

const capital: CapitalAnalysis = {
  records: [],
  metrics: { debt_to_equity: 0.5, debt_to_assets: 0.28, interest_coverage: 6, wacc_pct: 10.2, after_tax_cost_of_debt_pct: 6 },
  explanations: {},
  recommendation: "Maintain current leverage",
};

const working: WorkingCapital = {
  period: "2026-Q3", working_capital: 60000, current_ratio: 2, quick_ratio: 1.67,
  receivables: 30000, payables: 20000, inventory: 20000, trend: [],
};

const transaction: MoneyTransaction = {
  id: "tx-1", business_id: "demo-business-001", date: "2026-11-19",
  amount: -500, category: "Marketing", description: "campaign", vendor: "Google Ads",
  department: "Sales", reference: "", source: "manual", ai_categorized: false, created_at: "2026-11-19T00:00:00Z",
};

const variance: VarianceAnalysis = {
  period: "2026-Q4",
  items: [{ category: "Marketing", budgeted: 1000, actual: 1200, variance_abs: -200, variance_pct: -20, severity: "breach", favorable: false, explanation: "spend above budget" }],
  total_budgeted: 1000, total_actual: 1200, total_variance_pct: -20,
  narrative: "Marketing spend above budget",
  revenue_context: { revenue: 0, spend_as_pct_of_revenue: null },
};

const forecast: BusinessForecast = {
  metric: "revenue", method: "linear",
  history: [],
  forecast: [
    { step: 1, value: 140, lower: 139, upper: 141 },
    { step: 2, value: 150, lower: 148, upper: 152 },
  ],
  assumptions: ["Linear trend fitted with least squares"],
  uncertainty: [],
};

const savedScenario: SavedScenario = {
  id: "sc-1", business_id: "demo-business-001", name: "revenue forecast",
  payload: {}, result: {}, created_at: "2026-11-19T00:00:00Z",
};

function mockPageApis() {
  vi.spyOn(api, "getCashFlowAnalysis").mockResolvedValue(cashflow);
  vi.spyOn(api, "getCapitalAnalysis").mockResolvedValue(capital);
  vi.spyOn(api, "getWorkingCapital").mockResolvedValue(working);
  vi.spyOn(api, "listMoneyTransactions").mockResolvedValue([]);
  vi.spyOn(api, "listBudgets").mockResolvedValue([]);
  vi.spyOn(api, "listLoans").mockResolvedValue([]);
  vi.spyOn(api, "listBusinessForecasts").mockResolvedValue([]);
  vi.spyOn(api, "listScenarios").mockResolvedValue([]);
}

describe("Phase 3 money management page", () => {
  it("renders liquidity and capital overview", async () => {
    mockPageApis();
    render(<MoneyManagement />);
    expect(await screen.findByTestId("money-page")).toBeInTheDocument();
    expect(screen.getByText("₹5,000")).toBeInTheDocument();
    expect(screen.getByText(/1.25 mo/)).toBeInTheDocument();
    expect(screen.getByText("Maintain current leverage")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("records a transaction and analyses a budget", async () => {
    mockPageApis();
    const addTransaction = vi.spyOn(api, "addMoneyTransaction").mockResolvedValue(transaction);
    const addBudget = vi.spyOn(api, "addBudget").mockResolvedValue({
      id: "b-1", business_id: "demo-business-001", period: "2026-Q4", scope: "category",
      category: "Marketing", department: "", project: "", budgeted_amount: 1000, created_at: "2026-11-19T00:00:00Z",
    });
    const getVariance = vi.spyOn(api, "getVariance").mockResolvedValue(variance);

    render(<MoneyManagement />);
    expect(await screen.findByTestId("money-page")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Transactions" }));
    fireEvent.change(screen.getByLabelText("Amount (negative = expense)"), { target: { value: "-750" } });
    fireEvent.click(screen.getByRole("button", { name: "Add transaction" }));
    await waitFor(() => expect(addTransaction).toHaveBeenCalledWith(
      expect.objectContaining({ amount: -750, vendor: "Office Depot" })
    ));

    fireEvent.click(screen.getByRole("tab", { name: "Budgets" }));
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));
    await waitFor(() => expect(addBudget).toHaveBeenCalledWith(
      expect.objectContaining({ period: "2026-Q4", category: "Marketing", budgeted_amount: 10000 })
    ));
    await waitFor(() => expect(getVariance).toHaveBeenCalledWith("2026-Q4"));
    expect(await screen.findByText("Marketing spend above budget")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("runs a deterministic business forecast and saves a scenario", async () => {
    mockPageApis();
    const runForecast = vi.spyOn(api, "runBusinessForecast").mockResolvedValue(forecast);
    const saveScenario = vi.spyOn(api, "saveScenario").mockResolvedValue(savedScenario);

    render(<MoneyManagement />);
    expect(await screen.findByTestId("money-page")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Forecasts" }));
    fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));

    await waitFor(() => expect(runForecast).toHaveBeenCalledWith(
      expect.objectContaining({ metric: "revenue", series: [100, 110, 120, 130], periods_ahead: 3 })
    ));
    expect(await screen.findByText("₹140")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save as scenario" }));
    await waitFor(() => expect(saveScenario).toHaveBeenCalledWith(
      "revenue forecast", expect.any(Object), expect.any(Object)
    ));
    vi.restoreAllMocks();
  });
});
