import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api, type Portfolio, type PredictionResult, type StockHistory, type StockInfo, type IndicatorsResponse, type WatchlistItem } from "../lib/api";
import { MarketIntelligence } from "../pages/MarketIntelligence";
import { PaperTrading } from "../pages/PaperTrading";

const quote: StockInfo = {
  symbol: "TCS.NS",
  name: "Tata Consultancy Services Limited",
  exchange: "NSE",
  currency: "INR",
  source: "demo",
  data_status: "DEMO",
  as_of: "2026-11-19",
  latest_price: 1000,
  daily_change: 12,
  daily_change_pct: 1.2,
  volume: 2_000_000,
  trend: "uptrend",
};

const history: StockHistory = {
  symbol: "TCS.NS",
  source: "demo",
  data_status: "DEMO",
  as_of: "2026-11-19",
  points: [
    { date: "2026-11-16", open: 980, high: 995, low: 975, close: 988, volume: 1_000_000 },
    { date: "2026-11-17", open: 988, high: 1005, low: 984, close: 1000, volume: 1_200_000 },
    { date: "2026-11-18", open: 1000, high: 1010, low: 996, close: 1004, volume: 1_100_000 },
  ],
};

const indicators: IndicatorsResponse = {
  symbol: "TCS.NS",
  source: "demo",
  data_status: "DEMO",
  indicators: [
    { indicator: "rsi_14", description: "Momentum oscillator", values: [{ date: "2026-11-18", value: 58.2 }] },
    { indicator: "crossover", description: "Moving-average crossover", values: [{ date: "2026-11-15", value: 1, signal: "bullish_cross" }] },
  ],
};

const prediction: PredictionResult = {
  id: "pred-1",
  symbol: "TCS.NS",
  model: "linear_regression",
  horizon_days: 1,
  predicted_price: 1040,
  predicted_direction: "up",
  lower_bound: 1000,
  upper_bound: 1080,
  last_actual_price: 1004,
  metrics: { mae: 0.004, rmse: 0.006, directional_accuracy: 62.5, sample_size: 40 },
  created_at: "2026-11-19T00:00:00Z",
  target_date: "2026-11-20",
  actual_price: null,
  data_source: "demo",
};

const portfolio: Portfolio = {
  id: "portfolio-1",
  business_id: "demo-business-001",
  name: "Growth Model",
  initial_cash: 100000,
  cash: 90000,
  invested: 10000,
  total_value: 10200,
  unrealized_pnl: 200,
  realized_pnl: 0,
  total_return_pct: 2,
  holdings: [{ symbol: "TCS.NS", quantity: 10, average_cost: 1000, last_price: 1020, market_value: 10200 }],
  created_at: "2026-11-19T00:00:00Z",
};

describe("Phase 2 pages", () => {
  it("renders market intelligence and runs a forecast", async () => {
    const runPrediction = vi.spyOn(api, "runPrediction").mockResolvedValue(prediction);
    vi.spyOn(api, "getQuote").mockResolvedValue(quote);
    vi.spyOn(api, "getMarketHistory").mockResolvedValue(history);
    vi.spyOn(api, "getIndicators").mockResolvedValue(indicators);
    vi.spyOn(api, "getPredictions").mockResolvedValue([prediction]);
    vi.spyOn(api, "getWatchlist").mockResolvedValue([] as WatchlistItem[]);
    vi.spyOn(api, "addWatchlist").mockResolvedValue({ id: "w1", business_id: "demo-business-001", symbol: "INFY.NS", threshold_pct: 3, enabled: true });

    render(<MarketIntelligence />);
    expect(await screen.findByTestId("market-page")).toBeInTheDocument();
    expect(screen.getByTestId("prediction-result")).toHaveTextContent("₹1,040");
    expect(screen.getByText(/rsi 14/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Run forecast" }));
    await waitFor(() => expect(runPrediction).toHaveBeenCalledWith({
      symbol: "TCS.NS",
      horizon_days: 1,
      model: "linear_regression",
      store: true,
    }));
    vi.restoreAllMocks();
  });

  it("renders paper trading and submits a virtual order", async () => {
    const executeTrade = vi.spyOn(api, "executeTrade").mockResolvedValue({
      id: "trade-1",
      portfolio_id: "portfolio-1",
      symbol: "TCS.NS",
      side: "buy",
      quantity: 5,
      price: 1000,
      amount: 5000,
      fee: 0,
      realized_pnl: 0,
      executed_at: "2026-11-19T00:00:00Z",
    });
    vi.spyOn(api, "listPortfolios").mockResolvedValue([portfolio]);
    vi.spyOn(api, "getTransactions").mockResolvedValue([]);
    vi.spyOn(api, "getSnapshots").mockResolvedValue([]);
    vi.spyOn(api, "createPortfolio").mockResolvedValue(portfolio);
    vi.spyOn(api, "takeSnapshot").mockResolvedValue({
      id: "snap-1",
      portfolio_id: "portfolio-1",
      snapshot_date: "2026-11-19",
      cash: 90000,
      invested: 10000,
      total_value: 10200,
      unrealized_pnl: 200,
      realized_pnl: 0,
    });

    render(<PaperTrading />);
    expect(await screen.findByTestId("paper-trading-page")).toBeInTheDocument();
    expect(screen.getAllByText("Growth Model").length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit buy" }));
    await waitFor(() => expect(executeTrade).toHaveBeenCalledWith(
      "portfolio-1",
      expect.objectContaining({ symbol: "TCS.NS", side: "buy", quantity: 5 })
    ));
    vi.restoreAllMocks();
  });
});
