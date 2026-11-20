import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Simulator } from "../pages/Simulator";
import { api } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: { ...actual.api, simulateWhatIf: vi.fn() },
  };
});

describe("Simulator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("runs a simulation and renders the ending cash result", async () => {
    vi.mocked(api.simulateWhatIf).mockResolvedValue({
      periods: [
        { period_index: 0, revenue: 20000, costs: 16000, net_income: 4000, cash_balance: 19000 },
      ],
      ending_cash: 19000,
      breakeven_period: 0,
    });

    const user = userEvent.setup();
    render(<Simulator />);

    await user.click(screen.getByRole("button", { name: "Run simulation" }));

    await waitFor(() => expect(screen.getByText(/Ending cash after/)).toBeInTheDocument());
    expect(screen.getByText("$19,000", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText(/Breakeven at month 0/)).toBeInTheDocument();
  });

  it("shows an error message when the simulation request fails", async () => {
    const { ApiError } = await vi.importActual<typeof import("../lib/api")>("../lib/api");
    vi.mocked(api.simulateWhatIf).mockRejectedValue(new ApiError(422, "periods must be >= 1"));

    const user = userEvent.setup();
    render(<Simulator />);
    await user.click(screen.getByRole("button", { name: "Run simulation" }));

    await waitFor(() => expect(screen.getByText("periods must be >= 1")).toBeInTheDocument());
  });
});
