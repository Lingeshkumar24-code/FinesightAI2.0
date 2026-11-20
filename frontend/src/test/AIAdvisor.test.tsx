import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AIAdvisor } from "../pages/AIAdvisor";
import { api } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    api: { ...actual.api, askAdvisor: vi.fn() },
  };
});

describe("AIAdvisor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the greeting message on load", () => {
    render(<AIAdvisor />);
    expect(screen.getByTestId("chat-log")).toHaveTextContent("Ask me about your budget");
  });

  it("sends the user's message and renders the assistant's reply", async () => {
    vi.mocked(api.askAdvisor).mockResolvedValue({
      intent: "budget_variance",
      route: "engine:budget_variance",
      is_valid: true,
      tool_result: {},
      citations: [],
      validation_notes: [],
      answer: "Marketing overspent by 30%.",
    });

    const user = userEvent.setup();
    render(<AIAdvisor />);

    await user.type(screen.getByLabelText("Message"), "Did we overspend on marketing?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByTestId("chat-log")).toHaveTextContent("Did we overspend on marketing?");
    await waitFor(() =>
      expect(screen.getByTestId("chat-log")).toHaveTextContent("Marketing overspent by 30%.")
    );
    expect(api.askAdvisor).toHaveBeenCalledWith("Did we overspend on marketing?");
  });

  it("shows a graceful error message if the request fails", async () => {
    const { ApiError } = await vi.importActual<typeof import("../lib/api")>("../lib/api");
    vi.mocked(api.askAdvisor).mockRejectedValue(new ApiError(500, "Server error"));

    const user = userEvent.setup();
    render(<AIAdvisor />);

    await user.type(screen.getByLabelText("Message"), "Anything?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(screen.getByTestId("chat-log")).toHaveTextContent("Error: Server error")
    );
  });

  it("does not send an empty message", async () => {
    const user = userEvent.setup();
    render(<AIAdvisor />);
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(api.askAdvisor).not.toHaveBeenCalled();
  });
});
