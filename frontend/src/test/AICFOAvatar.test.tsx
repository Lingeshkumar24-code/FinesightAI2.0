import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FloatingAssistant } from "../components/ai/FloatingAssistant";
import { AICFOAvatar } from "../components/ai/AICFOAvatar";
import { api } from "../lib/api";

describe("AI CFO assistant", () => {
  it("renders an animated SVG avatar with cursor-following eyes", () => {
    render(<AICFOAvatar size={64} expression="happy" />);
    const avatar = screen.getByTestId("finsight-avatar");
    expect(avatar).toBeInTheDocument();
    expect(avatar.querySelectorAll("[data-eye=\"white\"]").length).toBe(2);
    fireEvent.mouseMove(window, { clientX: 200, clientY: 100 });
  });

  it("opens the floating chat and sends a question", async () => {
    vi.spyOn(api, "askAdvisor").mockResolvedValue({
      intent: "financial_statement",
      route: "engine:financial_statement",
      is_valid: true,
      tool_result: { net_margin_pct: 18.7 },
      citations: [],
      validation_notes: [],
      answer: "Your net margin is 18.7%.",
    });
    render(<FloatingAssistant />);
    fireEvent.click(screen.getByTestId("assistant-launcher"));
    expect(screen.getByTestId("assistant-panel")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("assistant-input"), { target: { value: "What is my margin?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Your net margin is 18.7%.")).toBeInTheDocument();
    expect(screen.getByText(/verified computation/i)).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
