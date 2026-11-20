import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type Portfolio, type Snapshot, type Trade } from "../lib/api";
import { Card } from "../components/ui/Card";

function rupees(value: number): string {
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function PaperTrading() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<Trade[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [portfolioName, setPortfolioName] = useState("Growth Model");
  const [initialCash, setInitialCash] = useState(100000);
  const [symbol, setSymbol] = useState("TCS.NS");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState(10);
  const [price, setPrice] = useState<string>("");
  const [fee, setFee] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refreshPortfolios = useCallback(async () => {
    const list = await api.listPortfolios();
    setPortfolios(list);
    setSelectedId((current) => (current && list.some((item) => item.id === current) ? current : (list[0]?.id ?? null)));
    return list;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const list = await refreshPortfolios();
        if (!cancelled) setSelectedId(list[0]?.id ?? null);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Failed to load portfolios");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [refreshPortfolios]);

  useEffect(() => {
    if (!selectedId) {
      setTransactions([]);
      setSnapshots([]);
      return;
    }
    let cancelled = false;
    async function loadDetails() {
      if (!selectedId) return;
      try {
        const [tradeList, snapshotList] = await Promise.all([
          api.getTransactions(selectedId),
          api.getSnapshots(selectedId),
        ]);
        if (!cancelled) {
          setTransactions(tradeList);
          setSnapshots(snapshotList);
        }
      } catch (err) {
        if (!cancelled) setActionError(err instanceof ApiError ? err.message : "Failed to load portfolio history");
      }
    }
    void loadDetails();
    return () => { cancelled = true; };
  }, [selectedId]);

  const selected = portfolios.find((item) => item.id === selectedId) ?? null;

  async function createPortfolio(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setActionError(null);
    try {
      const created = await api.createPortfolio(portfolioName, initialCash);
      await refreshPortfolios();
      setSelectedId(created.id);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not create portfolio");
    } finally {
      setBusy(false);
    }
  }

  async function submitTrade(event: FormEvent) {
    event.preventDefault();
    if (!selectedId) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.executeTrade(selectedId, {
        symbol,
        side,
        quantity,
        fee,
        ...(price.trim() ? { price: Number(price) } : {}),
      });
      const [list, tradeList] = await Promise.all([refreshPortfolios(), api.getTransactions(selectedId)]);
      setTransactions(tradeList);
      const updated = list.find((item) => item.id === selectedId);
      if (updated) setPortfolios(list);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Trade rejected");
    } finally {
      setBusy(false);
    }
  }

  async function captureSnapshot() {
    if (!selectedId) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.takeSnapshot(selectedId);
      setSnapshots(await api.getSnapshots(selectedId));
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not capture snapshot");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <div className="skeleton" style={{ height: 320 }} data-testid="paper-trading-page" />;
  if (error) return <div className="page-state is-error"><p className="error-text">{error}</p></div>;

  return (
    <div className="page-enter flex flex-col gap-5 w-full" data-testid="paper-trading-page">
      <div className="page-header">
        <div>
          <div className="page-kicker">
            <h1>Paper Trading Simulator</h1>
            <span className="data-badge is-demo">virtual capital</span>
          </div>
          <p className="page-lead">
            Practice execution logic with virtual cash. Prices are delayed or demo data; no real orders are placed.
          </p>
        </div>
        <button className="btn btn-secondary" type="button" onClick={() => void captureSnapshot()} disabled={!selectedId || busy}>
          Capture snapshot
        </button>
      </div>

      {actionError && <div className="page-state is-error"><p className="error-text">{actionError}</p></div>}

      <div className="trading-grid">
        <div className="flex flex-col gap-5">
          <Card>
            <div className="section-header">
              <h2>Virtual Portfolios</h2>
              <span className="section-run">{portfolios.length} active</span>
            </div>
            <div className="portfolio-list" data-testid="portfolio-list">
              {portfolios.length === 0 && <p className="muted-note">Create a portfolio to begin.</p>}
              {portfolios.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`portfolio-row ${item.id === selectedId ? "is-active" : ""}`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <span>{item.name}</span>
                  <strong className="num">{rupees(item.total_value)}</strong>
                  <small>{item.total_return_pct >= 0 ? "+" : ""}{item.total_return_pct}%</small>
                </button>
              ))}
            </div>
            <form className="form-grid-2 mt-3" onSubmit={createPortfolio}>
              <div>
                <label htmlFor="portfolio-name">Name</label>
                <input id="portfolio-name" value={portfolioName} onChange={(event) => setPortfolioName(event.target.value)} />
              </div>
              <div>
                <label htmlFor="initial-cash">Virtual cash</label>
                <input id="initial-cash" type="number" value={initialCash} onChange={(event) => setInitialCash(Number(event.target.value))} />
              </div>
              <div className="form-action">
                <button className="btn btn-primary" type="submit" disabled={busy}>Create portfolio</button>
              </div>
            </form>
          </Card>

          <Card>
            <div className="section-header">
              <h2>Place Virtual Order</h2>
              <span className="section-run">No real settlement</span>
            </div>
            <form className="form-grid-2" onSubmit={submitTrade} data-testid="trade-form">
              <div>
                <label htmlFor="trade-symbol">Symbol</label>
                <input id="trade-symbol" value={symbol} onChange={(event) => setSymbol(event.target.value)} />
              </div>
              <div>
                <label htmlFor="trade-side">Side</label>
                <select id="trade-side" value={side} onChange={(event) => setSide(event.target.value)}>
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div>
                <label htmlFor="trade-quantity">Quantity</label>
                <input id="trade-quantity" type="number" min="1" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} />
              </div>
              <div>
                <label htmlFor="trade-price">Price (blank = latest)</label>
                <input id="trade-price" type="number" min="0" step="0.01" placeholder="Market" value={price} onChange={(event) => setPrice(event.target.value)} />
              </div>
              <div>
                <label htmlFor="trade-fee">Fee</label>
                <input id="trade-fee" type="number" min="0" value={fee} onChange={(event) => setFee(Number(event.target.value))} />
              </div>
              <div className="form-action">
                <button className="btn btn-primary" type="submit" disabled={!selectedId || busy}>
                  {busy ? "Processing…" : `Submit ${side}`}
                </button>
              </div>
            </form>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          {selected ? (
            <>
              <Card>
                <div className="section-header">
                  <h2>{selected.name}</h2>
                  <span className="section-run">Marked to delayed prices</span>
                </div>
                <div className="kpi-grid">
                  <div className="metric"><div className="metric-label">Total Value</div><div className="metric-value num">{rupees(selected.total_value)}</div></div>
                  <div className="metric"><div className="metric-label">Cash</div><div className="metric-value num">{rupees(selected.cash)}</div></div>
                  <div className="metric"><div className="metric-label">Unrealized P&amp;L</div><div className="metric-value num" style={{ color: selected.unrealized_pnl >= 0 ? "#047857" : "#B91C1C" }}>{rupees(selected.unrealized_pnl)}</div></div>
                  <div className="metric"><div className="metric-label">Realized P&amp;L</div><div className="metric-value num" style={{ color: selected.realized_pnl >= 0 ? "#047857" : "#B91C1C" }}>{rupees(selected.realized_pnl)}</div></div>
                </div>
                <div className="data-table mt-4">
                  <table>
                    <thead><tr><th>Holding</th><th className="num">Qty</th><th className="num">Avg Cost</th><th className="num">Last</th><th className="num">Value</th></tr></thead>
                    <tbody>
                      {selected.holdings.length === 0 && <tr><td colSpan={5} className="muted-note">No open positions.</td></tr>}
                      {selected.holdings.map((holding) => (
                        <tr key={holding.symbol}>
                          <td style={{ fontWeight: 600 }}>{holding.symbol}</td>
                          <td className="num">{holding.quantity}</td>
                          <td className="num">{rupees(holding.average_cost)}</td>
                          <td className="num">{rupees(holding.last_price)}</td>
                          <td className="num">{rupees(holding.market_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <div className="section-header"><h2>Order History</h2><span className="section-run">{transactions.length} fills</span></div>
                <div className="data-table">
                  <table>
                    <thead><tr><th>Time</th><th>Side</th><th>Symbol</th><th className="num">Qty</th><th className="num">Price</th><th className="num">P&amp;L</th></tr></thead>
                    <tbody>
                      {transactions.length === 0 && <tr><td colSpan={6} className="muted-note">No virtual orders yet.</td></tr>}
                      {transactions.map((trade) => (
                        <tr key={trade.id}>
                          <td>{new Date(trade.executed_at).toLocaleString()}</td>
                          <td><span className={`pill ${trade.side === "buy" ? "is-good" : "is-watch"}`}>{trade.side}</span></td>
                          <td>{trade.symbol}</td>
                          <td className="num">{trade.quantity}</td>
                          <td className="num">{rupees(trade.price)}</td>
                          <td className="num">{rupees(trade.realized_pnl)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <div className="section-header"><h2>Portfolio Snapshots</h2><span className="section-run">{snapshots.length} saved</span></div>
                <div className="data-table">
                  <table>
                    <thead><tr><th>Date</th><th className="num">Cash</th><th className="num">Invested</th><th className="num">Total</th></tr></thead>
                    <tbody>
                      {snapshots.length === 0 && <tr><td colSpan={4} className="muted-note">No snapshots captured.</td></tr>}
                      {snapshots.map((snapshot) => (
                        <tr key={snapshot.id}>
                          <td>{snapshot.snapshot_date}</td>
                          <td className="num">{rupees(snapshot.cash)}</td>
                          <td className="num">{rupees(snapshot.invested)}</td>
                          <td className="num">{rupees(snapshot.total_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          ) : (
            <Card style={{ minHeight: 320, display: "grid", placeItems: "center", textAlign: "center" }}>
              <div>
                <h3>No portfolio selected</h3>
                <p className="muted-note">Create a virtual portfolio to start simulating trades.</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
