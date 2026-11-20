import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  ApiError,
  type Budget,
  type BusinessForecast,
  type CapitalAnalysis,
  type CashFlowAnalysis,
  type LoanQuote,
  type LoanScenario,
  type MoneyTransaction,
  type SavedForecast,
  type SavedScenario,
  type VarianceAnalysis,
  type WorkingCapital,
} from "../lib/api";
import { Card } from "../components/ui/Card";

type Tab = "overview" | "transactions" | "budgets" | "loans" | "forecasts";
const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "transactions", label: "Transactions" },
  { id: "budgets", label: "Budgets" },
  { id: "loans", label: "Loans" },
  { id: "forecasts", label: "Forecasts" },
];

function rupees(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function MoneyManagement() {
  const [tab, setTab] = useState<Tab>("overview");
  const [cashflow, setCashflow] = useState<CashFlowAnalysis | null>(null);
  const [capital, setCapital] = useState<CapitalAnalysis | null>(null);
  const [working, setWorking] = useState<WorkingCapital | null>(null);
  const [transactions, setTransactions] = useState<MoneyTransaction[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [loans, setLoans] = useState<LoanScenario[]>([]);
  const [forecasts, setForecasts] = useState<SavedForecast[]>([]);
  const [scenarios, setScenarios] = useState<SavedScenario[]>([]);
  const [variance, setVariance] = useState<VarianceAnalysis | null>(null);
  const [quote, setQuote] = useState<LoanQuote | null>(null);
  const [forecast, setForecast] = useState<BusinessForecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [txDate, setTxDate] = useState("2026-11-19");
  const [txAmount, setTxAmount] = useState(-500);
  const [txVendor, setTxVendor] = useState("Office Depot");
  const [txDescription, setTxDescription] = useState("stationery purchase");
  const [budgetPeriod, setBudgetPeriod] = useState("2026-Q4");
  const [budgetCategory, setBudgetCategory] = useState("Marketing");
  const [budgetAmount, setBudgetAmount] = useState(10000);
  const [loanName, setLoanName] = useState("Growth Loan");
  const [loanPrincipal, setLoanPrincipal] = useState(100000);
  const [loanRate, setLoanRate] = useState(10);
  const [loanMonths, setLoanMonths] = useState(12);
  const [forecastMetric, setForecastMetric] = useState("revenue");
  const [forecastSeries, setForecastSeries] = useState("100, 110, 120, 130");
  const [forecastPeriods, setForecastPeriods] = useState(3);
  const [forecastMethod, setForecastMethod] = useState("auto");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [cashResult, capitalResult, workingResult, txResult, budgetResult, loanResult, forecastResult, scenarioResult] =
        await Promise.allSettled([
          api.getCashFlowAnalysis(),
          api.getCapitalAnalysis(),
          api.getWorkingCapital(),
          api.listMoneyTransactions(),
          api.listBudgets(),
          api.listLoans(),
          api.listBusinessForecasts(),
          api.listScenarios(),
        ]);
      if (cancelled) return;
      if (cashResult.status === "fulfilled") setCashflow(cashResult.value);
      if (capitalResult.status === "fulfilled") setCapital(capitalResult.value);
      if (workingResult.status === "fulfilled") setWorking(workingResult.value);
      if (txResult.status === "fulfilled") setTransactions(txResult.value);
      if (budgetResult.status === "fulfilled") setBudgets(budgetResult.value);
      if (loanResult.status === "fulfilled") setLoans(loanResult.value);
      if (forecastResult.status === "fulfilled") setForecasts(forecastResult.value);
      if (scenarioResult.status === "fulfilled") setScenarios(scenarioResult.value);
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  function message(error: unknown, fallback: string) {
    setError(error instanceof ApiError ? error.message : fallback);
  }

  async function refreshTransactions() {
    setTransactions(await api.listMoneyTransactions());
  }

  async function submitTransaction(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addMoneyTransaction({
        date: txDate,
        amount: txAmount,
        vendor: txVendor,
        description: txDescription,
      });
      await refreshTransactions();
    } catch (err) {
      message(err, "Could not save transaction");
    } finally {
      setBusy(false);
    }
  }

  async function importFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await api.importMoneyTransactions(file);
      await refreshTransactions();
    } catch (err) {
      message(err, "CSV import failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitBudget(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.addBudget({ period: budgetPeriod, category: budgetCategory, budgeted_amount: budgetAmount });
      setBudgets(await api.listBudgets());
      setVariance(await api.getVariance(budgetPeriod));
    } catch (err) {
      message(err, "Could not save budget");
    } finally {
      setBusy(false);
    }
  }

  async function submitLoanQuote(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setQuote(await api.quoteLoan({ name: loanName, principal: loanPrincipal, annual_rate_pct: loanRate, tenure_months: loanMonths }));
    } catch (err) {
      message(err, "Could not calculate loan quote");
    } finally {
      setBusy(false);
    }
  }

  async function saveLoan() {
    setBusy(true);
    setError(null);
    try {
      await api.saveLoan({ name: loanName, principal: loanPrincipal, annual_rate_pct: loanRate, tenure_months: loanMonths });
      setLoans(await api.listLoans());
    } catch (err) {
      message(err, "Could not save loan scenario");
    } finally {
      setBusy(false);
    }
  }

  async function runForecast(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const series = forecastSeries.split(",").map((value) => Number(value.trim())).filter(Number.isFinite);
      setForecast(await api.runBusinessForecast({
        metric: forecastMetric,
        series,
        periods_ahead: forecastPeriods,
        method: forecastMethod,
        store: true,
      }));
      setForecasts(await api.listBusinessForecasts());
    } catch (err) {
      message(err, "Forecast failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveForecastScenario() {
    if (!forecast) return;
    setBusy(true);
    setError(null);
    try {
      await api.saveScenario(
        `${forecast.metric} forecast`,
        { metric: forecast.metric, method: forecast.method },
        { points: forecast.forecast }
      );
      setScenarios(await api.listScenarios());
    } catch (err) {
      message(err, "Could not save scenario");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="money-page">
      <div className="page-header">
        <div>
          <h1>Money Management</h1>
          <p className="page-lead">
            Transaction categorisation, budget control, liquidity, capital structure, term loans and deterministic forecasting.
          </p>
        </div>
        <span className="data-badge is-live">persistent records</span>
      </div>

      {error && <div className="page-state is-error"><p className="error-text">{error}</p></div>}

      <div className="tab-bar" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`tab-btn ${tab === item.id ? "is-active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="split-grid">
          <Card>
            <div className="section-header"><h2>Cash-Flow Outlook</h2><span className="section-run">Deterministic runway</span></div>
            <div className="stat-strip">
              <div><span>Latest Closing Cash</span><strong className="num">{rupees(cashflow?.latest?.closing_cash)}</strong></div>
              <div><span>Average Monthly Burn</span><strong className="num">{rupees(cashflow?.average_monthly_burn)}</strong></div>
              <div><span>Runway</span><strong className="num">{cashflow?.runway_months === null || cashflow?.runway_months === undefined ? "N/A" : `${cashflow.runway_months} mo`}</strong></div>
            </div>
            <p className="muted-note">{cashflow?.liquidity_note ?? "No cash-flow records loaded."}</p>
          </Card>
          <Card>
            <div className="section-header"><h2>Capital Structure</h2><span className="section-run">Cost of capital</span></div>
            <div className="stat-strip">
              <div><span>Debt / Equity</span><strong className="num">{capital?.metrics.debt_to_equity ?? "—"}</strong></div>
              <div><span>Interest Coverage</span><strong className="num">{capital?.metrics.interest_coverage ?? "—"}</strong></div>
              <div><span>WACC</span><strong className="num">{capital?.metrics.wacc_pct ?? "—"}%</strong></div>
            </div>
            <p className="muted-note">{capital?.recommendation ?? "Add capital structure records to see a recommendation."}</p>
          </Card>
          <Card>
            <div className="section-header"><h2>Working Capital</h2><span className="section-run">{working?.period ?? "latest period"}</span></div>
            <div className="stat-strip">
              <div><span>Net Working Capital</span><strong className="num">{rupees(working?.working_capital)}</strong></div>
              <div><span>Current Ratio</span><strong className="num">{working?.current_ratio ?? "—"}</strong></div>
              <div><span>Quick Ratio</span><strong className="num">{working?.quick_ratio ?? "—"}</strong></div>
            </div>
          </Card>
        </div>
      )}

      {tab === "transactions" && (
        <div className="split-grid">
          <Card>
            <div className="section-header"><h2>Record Transaction</h2><span className="section-run">Auto-categorised when blank</span></div>
            <form className="form-grid-2" onSubmit={submitTransaction}>
              <div><label htmlFor="tx-date">Date</label><input id="tx-date" type="date" value={txDate} onChange={(e) => setTxDate(e.target.value)} /></div>
              <div><label htmlFor="tx-amount">Amount (negative = expense)</label><input id="tx-amount" type="number" step="0.01" value={txAmount} onChange={(e) => setTxAmount(Number(e.target.value))} /></div>
              <div><label htmlFor="tx-vendor">Vendor</label><input id="tx-vendor" value={txVendor} onChange={(e) => setTxVendor(e.target.value)} /></div>
              <div><label htmlFor="tx-description">Description</label><input id="tx-description" value={txDescription} onChange={(e) => setTxDescription(e.target.value)} /></div>
              <div className="form-action"><button className="btn btn-primary" type="submit" disabled={busy}>Add transaction</button></div>
            </form>
            <div className="mt-4">
              <label htmlFor="tx-import">Import CSV</label>
              <input id="tx-import" type="file" accept=".csv,text/csv" onChange={(e) => void importFile(e)} />
            </div>
          </Card>
          <Card>
            <div className="section-header"><h2>Recent Transactions</h2><span className="section-run">{transactions.length} records</span></div>
            <div className="data-table" style={{ maxHeight: 460, overflowY: "auto" }}>
              <table>
                <thead><tr><th>Date</th><th>Vendor</th><th>Category</th><th className="num">Amount</th></tr></thead>
                <tbody>
                  {transactions.map((item) => (
                    <tr key={item.id}>
                      <td>{item.date}</td><td>{item.vendor || item.description}</td><td>{item.category}</td>
                      <td className="num" style={{ color: item.amount >= 0 ? "#047857" : "#B91C1C" }}>{rupees(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {tab === "budgets" && (
        <div className="split-grid">
          <Card>
            <div className="section-header"><h2>Budget Setup</h2><span className="section-run">{budgets.length} budgets · {budgetPeriod}</span></div>
            <form className="form-grid-2" onSubmit={submitBudget}>
              <div><label htmlFor="budget-period">Period</label><input id="budget-period" value={budgetPeriod} onChange={(e) => setBudgetPeriod(e.target.value)} /></div>
              <div><label htmlFor="budget-category">Category</label><input id="budget-category" value={budgetCategory} onChange={(e) => setBudgetCategory(e.target.value)} /></div>
              <div><label htmlFor="budget-amount">Budgeted amount</label><input id="budget-amount" type="number" value={budgetAmount} onChange={(e) => setBudgetAmount(Number(e.target.value))} /></div>
              <div className="form-action"><button className="btn btn-primary" type="submit" disabled={busy}>Save budget</button></div>
            </form>
            <p className="muted-note mt-3">{variance?.narrative ?? "Save a budget to generate variance analysis."}</p>
          </Card>
          <Card>
            <div className="section-header"><h2>Variance Analysis</h2><span className="section-run">Actual vs budget</span></div>
            <div className="data-table">
              <table>
                <thead><tr><th>Category</th><th className="num">Budget</th><th className="num">Actual</th><th className="num">Variance</th><th>Status</th></tr></thead>
                <tbody>
                  {(variance?.items ?? []).map((item) => (
                    <tr key={item.category}>
                      <td>{item.category}</td><td className="num">{rupees(item.budgeted)}</td><td className="num">{rupees(item.actual)}</td>
                      <td className="num">{rupees(item.variance_abs)}</td>
                      <td><span className={`pill ${item.favorable ? "is-good" : "is-bad"}`}>{item.severity}</span></td>
                    </tr>
                  ))}
                  {!variance && <tr><td colSpan={5} className="muted-note">No analysis yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {tab === "loans" && (
        <div className="split-grid">
          <Card>
            <div className="section-header"><h2>Loan Scenario</h2><span className="section-run">EMI and amortisation</span></div>
            <form className="form-grid-2" onSubmit={submitLoanQuote}>
              <div><label htmlFor="loan-name">Name</label><input id="loan-name" value={loanName} onChange={(e) => setLoanName(e.target.value)} /></div>
              <div><label htmlFor="loan-principal">Principal</label><input id="loan-principal" type="number" value={loanPrincipal} onChange={(e) => setLoanPrincipal(Number(e.target.value))} /></div>
              <div><label htmlFor="loan-rate">Annual rate (%)</label><input id="loan-rate" type="number" step="0.1" value={loanRate} onChange={(e) => setLoanRate(Number(e.target.value))} /></div>
              <div><label htmlFor="loan-months">Tenure (months)</label><input id="loan-months" type="number" value={loanMonths} onChange={(e) => setLoanMonths(Number(e.target.value))} /></div>
              <div className="form-action"><button className="btn btn-primary" type="submit" disabled={busy}>Calculate EMI</button></div>
            </form>
            {quote && (
              <div className="stat-strip mt-4">
                <div><span>Monthly EMI</span><strong className="num">{rupees(quote.monthly_emi)}</strong></div>
                <div><span>Total Interest</span><strong className="num">{rupees(quote.total_interest)}</strong></div>
                <div><span>Total Repayment</span><strong className="num">{rupees(quote.total_repayment)}</strong></div>
              </div>
            )}
            {quote && <button className="btn btn-secondary mt-3" type="button" onClick={() => void saveLoan()} disabled={busy}>Save scenario</button>}
          </Card>
          <Card>
            <div className="section-header"><h2>Saved Loans</h2><span className="section-run">{loans.length} scenarios</span></div>
            <div className="data-table">
              <table>
                <thead><tr><th>Name</th><th className="num">Principal</th><th className="num">Rate</th><th className="num">Months</th></tr></thead>
                <tbody>
                  {loans.map((loan) => (
                    <tr key={loan.id}>
                      <td>{loan.name}</td><td className="num">{rupees(loan.principal)}</td>
                      <td className="num">{loan.annual_rate_pct}%</td><td className="num">{loan.tenure_months}</td>
                    </tr>
                  ))}
                  {loans.length === 0 && <tr><td colSpan={4} className="muted-note">No saved loans.</td></tr>}
                </tbody>
              </table>
            </div>
            {quote && (
              <div className="data-table mt-4" style={{ maxHeight: 280, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Month</th><th className="num">Opening</th><th className="num">Interest</th><th className="num">Principal</th><th className="num">Closing</th></tr></thead>
                  <tbody>
                    {quote.schedule.map((row) => (
                      <tr key={row.month}>
                        <td>{row.month}</td><td className="num">{rupees(row.opening_balance)}</td><td className="num">{rupees(row.interest)}</td>
                        <td className="num">{rupees(row.principal)}</td><td className="num">{rupees(row.closing_balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === "forecasts" && (
        <div className="split-grid">
          <Card>
            <div className="section-header"><h2>Business Forecast</h2><span className="section-run">Linear or mean-reverting</span></div>
            <form className="form-grid-2" onSubmit={runForecast}>
              <div><label htmlFor="forecast-metric">Metric</label><input id="forecast-metric" value={forecastMetric} onChange={(e) => setForecastMetric(e.target.value)} /></div>
              <div><label htmlFor="forecast-series">Historical series (comma separated)</label><input id="forecast-series" value={forecastSeries} onChange={(e) => setForecastSeries(e.target.value)} /></div>
              <div><label htmlFor="forecast-periods">Periods ahead</label><input id="forecast-periods" type="number" value={forecastPeriods} onChange={(e) => setForecastPeriods(Number(e.target.value))} /></div>
              <div><label htmlFor="forecast-method">Method</label>
                <select id="forecast-method" value={forecastMethod} onChange={(e) => setForecastMethod(e.target.value)}>
                  <option value="auto">Auto</option><option value="linear">Linear</option><option value="average">Average</option>
                </select>
              </div>
              <div className="form-action"><button className="btn btn-primary" type="submit" disabled={busy}>Run forecast</button></div>
            </form>
            {forecast && (
              <div className="data-table mt-4">
                <table>
                  <thead><tr><th>Step</th><th className="num">Forecast</th><th className="num">Lower</th><th className="num">Upper</th></tr></thead>
                  <tbody>
                    {forecast.forecast.map((point) => (
                      <tr key={point.step}>
                        <td>{point.step}</td><td className="num">{rupees(point.value)}</td>
                        <td className="num">{rupees(point.lower)}</td><td className="num">{rupees(point.upper)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {forecast && <button className="btn btn-secondary mt-3" type="button" onClick={() => void saveForecastScenario()} disabled={busy}>Save as scenario</button>}
            <ul className="assumption-list mt-3">
              {(forecast?.assumptions ?? []).map((item) => <li key={item}>{item}</li>)}
            </ul>
          </Card>
          <Card>
            <div className="section-header"><h2>Saved History</h2><span className="section-run">{forecasts.length} forecasts · {scenarios.length} scenarios</span></div>
            <div className="data-table" style={{ maxHeight: 520, overflowY: "auto" }}>
              <table>
                <thead><tr><th>Type</th><th>Name / Metric</th><th>Method</th><th>Date</th></tr></thead>
                <tbody>
                  {forecasts.map((item) => (
                    <tr key={item.id}><td>Forecast</td><td>{item.metric}</td><td>{item.method}</td><td>{item.created_at.slice(0, 10)}</td></tr>
                  ))}
                  {scenarios.map((item) => (
                    <tr key={item.id}><td>Scenario</td><td>{item.name}</td><td>saved</td><td>{item.created_at.slice(0, 10)}</td></tr>
                  ))}
                  {forecasts.length === 0 && scenarios.length === 0 && <tr><td colSpan={4} className="muted-note">No saved forecasts or scenarios.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
