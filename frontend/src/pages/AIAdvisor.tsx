import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { Card } from "../components/ui/Card";
import { AICFOAvatar, type AssistantExpression } from "../components/ai/AICFOAvatar";

const SUGGESTIONS = [
  "Summarize our financial position",
  "Why is profitability changing?",
  "Which transactions require investigation?",
  "What is our cash runway?",
];

interface ChatEntry {
  role: "user" | "assistant";
  text: string;
}

export function AIAdvisor() {
  const [messages, setMessages] = useState<ChatEntry[]>([
    {
      role: "assistant",
      text: "Ask me about your budget, ratios, risk, forecasts, or \"what if\" scenarios — or anything in an uploaded document.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [mood, setMood] = useState<AssistantExpression>("neutral");

  async function ask(query: string) {
    if (!query || sending) return;
    setMood("loading");

    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setInput("");
    setSending(true);

    try {
      const resp = await api.askAdvisor(query);
      setMessages((prev) => [...prev, { role: "assistant", text: resp.answer }]);
      setMood(resp.is_valid ? "success" : "alert");
    } catch (err) {
      const text = err instanceof ApiError ? err.message : "Something went wrong.";
      setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${text}` }]);
      setMood("error");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input.trim());
  }

  return (
    <div style={{ maxWidth: 840, display: "flex", flexDirection: "column", height: "calc(100vh - 140px)" }}>
      <div className="advisor-head">
        <AICFOAvatar size={84} expression={mood} label="FinSight AI advisor" />
        <div>
          <h1>AI Financial Advisor</h1>
          <p className="page-lead">
            Intelligent multi-agent financial deliberation over uploaded corporate filings and live computations.
          </p>
        </div>
      </div>

      <Card style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: 16 }}>
        <div className="chat-log" style={{ flex: 1, overflowY: "auto", border: "none", background: "transparent", padding: 0 }} data-testid="chat-log">
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.text}
            </div>
          ))}
          {sending && (
            <div className="chat-bubble assistant" style={{ fontStyle: "italic", color: "var(--ink-muted)" }}>
              Consulting financial models and deliberating…
            </div>
          )}
        </div>

        <div className="advisor-prompts">
          {SUGGESTIONS.map((q) => (
            <button type="button" key={q} onClick={() => void ask(q)} disabled={sending}>
              {q}
            </button>
          ))}
        </div>
        <form className="chat-form" onSubmit={handleSubmit} style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question (e.g. Did we overspend on marketing this quarter?)"
            aria-label="Message"
            style={{ borderRadius: "var(--radius-soft)" }}
          />
          <button className="btn btn-primary" type="submit" disabled={sending}>
            Send
          </button>
        </form>
      </Card>
    </div>
  );
}
