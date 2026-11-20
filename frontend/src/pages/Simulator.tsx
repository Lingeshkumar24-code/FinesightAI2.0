import { useState, type FormEvent } from "react";
import { api, ApiError, type WhatIfResponse } from "../lib/api";
import { Card } from "../components/ui/Card";

export function Simulator() {
  const [startingRevenue, setStartingRevenue] = useState(20000);
  const [startingCosts, setStartingCosts] = useState(16000);
  const [startingCash, setStartingCash] = useState(15000);
  const [revenueGrowth, setRevenueGrowth] = useState(2);
  const [newFixedCost, setNewFixedCost] = useState(0);
  const [periods, setPeriods] = useState(12);

  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setRunning(true);
    setError(null);
    try {
      const resp = await api.simulateWhatIf({
        starting_revenue: startingRevenue,
        starting_costs: startingCosts,
        starting_cash: startingCash,
        levers: {
          monthly_revenue_growth_pct: revenueGrowth,
          monthly_cost_growth_pct: 0,
          one_time_cost_change: 0,
          new_monthly_fixed_cost: newFixedCost,
          price_change_pct: 0,
        },
        periods,
      });
      setResult(resp);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Simulation failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1>What-If Scenario Modeling</h1>
        <p className="page-lead">
          Forecast the impact of revenue trajectories, operating expenses, and headcount investments on terminal cash runway.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 24, alignItems: "start" }}>
        {/* Input Parameters Form */}
        <Card>
          <div className="section-header">
            <h2>Simulation Parameters</h2>
            <span className="section-run">Financial Levers</span>
          </div>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 14 }}>
              <label htmlFor="rev">Starting monthly revenue ($)</label>
              <input id="rev" type="number" value={startingRevenue} onChange={(e) => setStartingRevenue(Number(e.target.value))} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label htmlFor="costs">Starting monthly costs ($)</label>
              <input id="costs" type="number" value={startingCosts} onChange={(e) => setStartingCosts(Number(e.target.value))} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label htmlFor="cash">Starting cash reserves ($)</label>
              <input id="cash" type="number" value={startingCash} onChange={(e) => setStartingCash(Number(e.target.value))} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label htmlFor="growth">Monthly revenue growth rate (%)</label>
              <input id="growth" type="number" step="0.1" value={revenueGrowth} onChange={(e) => setRevenueGrowth(Number(e.target.value))} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label htmlFor="newcost">New monthly fixed cost (e.g. strategic hire)</label>
              <input id="newcost" type="number" value={newFixedCost} onChange={(e) => setNewFixedCost(Number(e.target.value))} />
            </div>
            <div style={{ marginBottom: 18 }}>
              <label htmlFor="periods">Months to project</label>
              <input id="periods" type="number" value={periods} onChange={(e) => setPeriods(Number(e.target.value))} />
            </div>
            <button className="btn btn-primary" type="submit" disabled={running} style={{ width: "100%" }}>
              {running ? "Simulating Model…" : "Run simulation"}
            </button>
            {error && <p className="error-text">{error}</p>}
          </form>
        </Card>

        {/* Results Panel */}
        {result ? (
          <Card>
            <div className="section-header">
              <h2>Projected Financial Trajectory</h2>
              <span className="section-run">Monte Carlo Engine</span>
            </div>
            <div style={{ padding: "12px 0 16px", display: "flex", gap: "16px", flexWrap: "wrap" }}>
              <div
                style={{
                  flex: 1,
                  padding: "12px 16px",
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-soft)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--ink-muted)", letterSpacing: "0.05em" }}>
                  Terminal Cash Position
                </div>
                <p style={{ margin: "4px 0 0" }}>
                  {`Ending cash after ${periods} months: `}
                  <strong className="num" style={{ fontSize: "20px", color: result.ending_cash >= 0 ? "#047857" : "#B91C1C" }}>
                    {`$${result.ending_cash.toLocaleString()}`}
                  </strong>
                </p>
              </div>

              <div
                style={{
                  flex: 1,
                  padding: "12px 16px",
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-soft)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--ink-muted)", letterSpacing: "0.05em" }}>
                  Breakeven Horizon
                </div>
                <p style={{ margin: "4px 0 0", fontSize: "14px", fontWeight: 600 }}>
                  {result.breakeven_period !== null
                    ? `Breakeven at month ${result.breakeven_period}.`
                    : "Does not break even in this window."}
                </p>
              </div>
            </div>

            <div className="data-table" style={{ maxHeight: 360, overflowY: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th className="num">Revenue</th>
                    <th className="num">Costs</th>
                    <th className="num">Net Income</th>
                    <th className="num">Cash Reserve</th>
                  </tr>
                </thead>
                <tbody>
                  {result.periods.map((p) => (
                    <tr key={p.period_index}>
                      <td style={{ fontWeight: 600 }}>Month {p.period_index + 1}</td>
                      <td className="num">${p.revenue.toLocaleString()}</td>
                      <td className="num">${p.costs.toLocaleString()}</td>
                      <td className="num" style={{ color: p.net_income >= 0 ? "#047857" : "#B91C1C", fontWeight: 600 }}>
                        ${p.net_income.toLocaleString()}
                      </td>
                      <td className="num" style={{ fontWeight: 700 }}>
                        ${p.cash_balance.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ) : (
          <Card style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 320, textAlign: "center" }}>
            <div style={{ maxWidth: 280 }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>📊</div>
              <h3 style={{ marginBottom: 6 }}>Ready to Simulate</h3>
              <p style={{ color: "var(--ink-muted)", fontSize: 13, margin: 0 }}>
                Adjust revenue growth or expenses on the left and run the deterministic model to project outcomes.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
