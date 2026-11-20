import { useState, type FormEvent } from "react";
import { api, ApiError, type AdvisorResponse } from "../../lib/api";
import { AICFOAvatar, type AssistantExpression } from "./AICFOAvatar";

interface ChatEntry {
  role: "user" | "assistant";
  text: string;
  meta?: AdvisorResponse;
}

const QUICK_PROMPTS = [
  "Summarize our financial position",
  "Why is profitability changing?",
  "Which transactions require investigation?",
  "Explain our latest stock prediction",
];

function expressionFor(meta: AdvisorResponse | undefined): AssistantExpression {
  if (!meta) return "neutral";
  if (!meta.is_valid) return "alert";
  if (meta.intent === "forecasting" || meta.intent === "what_if_simulation") return "explaining";
  if (meta.citations.length > 0) return "happy";
  return "neutral";
}

export function FloatingAssistant() {
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatEntry[]>([
    {
      role: "assistant",
      text: "I'm your AI CFO. Ask about profitability, budgets, cash runway, risk alerts, predictions or your paper portfolio. I use verified figures and label every estimate.",
    },
  ]);

  async function submit(query: string) {
    const cleaned = query.trim();
    if (!cleaned || sending) return;
    setMessages((prev) => [...prev, { role: "user", text: cleaned }]);
    setInput("");
    setSending(true);
    try {
      const response = await api.askAdvisor(cleaned);
      setMessages((prev) => [...prev, { role: "assistant", text: response.answer, meta: response }]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `I could not complete that request: ${error instanceof ApiError ? error.message : "unknown error"}.`,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(input);
  }

  return (
    <div className="floating-assistant" data-testid="floating-assistant">
      {open && (
        <section className="assistant-panel" aria-label="AI CFO chat" data-testid="assistant-panel">
          <header className="assistant-panel-head">
            <AICFOAvatar size={42} expression={sending ? "thinking" : "happy"} compact />
            <div>
              <strong>AI CFO</strong>
              <span>Analyze · Predict · Protect · Optimize</span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close assistant chat" className="assistant-close">
              ×
            </button>
          </header>

          <div className="assistant-log" data-testid="assistant-log">
            {messages.map((message, index) => (
              <div key={index} className={`assistant-message ${message.role}`}>
                <div className="assistant-message-body">{message.text}</div>
                {message.meta && (
                  <div className="provenance">
                    <span className="provenance-tag">{message.meta.is_valid ? "Verified computation" : "Needs data"}</span>
                    <span className="provenance-tag">{message.meta.intent.replace(/_/g, " ")}</span>
                    {message.meta.citations.map((citation) => (
                      <span className="provenance-tag is-source" key={citation}>
                        source: {citation}
                      </span>
                    ))}
                    {message.meta.validation_notes.slice(0, 2).map((note) => (
                      <span className="provenance-tag is-note" key={note}>
                        {note}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div className="assistant-message assistant">
                <div className="assistant-typing"><i /><i /><i /></div>
              </div>
            )}
          </div>

          <div className="assistant-prompts">
            {QUICK_PROMPTS.map((prompt) => (
              <button type="button" key={prompt} onClick={() => void submit(prompt)} disabled={sending}>
                {prompt}
              </button>
            ))}
          </div>

          <form className="assistant-form" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask your AI CFO…"
              aria-label="Ask your AI CFO"
              data-testid="assistant-input"
            />
            <button className="btn btn-primary" type="submit" disabled={sending || !input.trim()}>
              Send
            </button>
          </form>
          <p className="assistant-disclaimer">
            Explanations are AI-generated from the figures shown. Forecasts and predictions are estimates, not guarantees.
          </p>
        </section>
      )}

      <button
        type="button"
        className="assistant-launcher"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Close AI CFO assistant" : "Open AI CFO assistant"}
        aria-expanded={open}
        data-testid="assistant-launcher"
      >
        <AICFOAvatar size={56} expression={expressionFor(messages[messages.length - 1]?.meta)} compact />
        {!open && <span className="assistant-launcher-pulse" aria-hidden="true" />}
      </button>
    </div>
  );
}
