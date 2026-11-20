"""
LangGraph Orchestration Layer
--------------------------------
Implements the five-agent workflow from the architecture diagram:

    1. Query Understanding Agent   -> classify intent
    2. Task Routing Agent          -> pick the engine/tool for that intent
    3. Tool Execution Agent        -> run a financial engine, or RAG retrieval
    4. Validation & Reconciliation -> sanity-check the result before it ships
    5. Response Generation Agent   -> narrate the result (LLM, with a
                                       deterministic template fallback so
                                       the advisor never goes fully silent
                                       if every LLM provider is down)

Each node is a small, independently-testable async function. The graph
itself is just wiring; almost all of the logic lives in functions you
can unit test without building a graph at all (see
tests/unit/test_agents_graph.py).
"""
from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.state import AgentState, Intent
from app.engines.budget_variance import BudgetVarianceEngine
from app.engines.capital_structure import CapitalStructureEngine, CapitalStructureInput
from app.engines.financial_statement import BalanceSheet, FinancialStatementEngine, IncomeStatement
from app.engines.forecasting import ForecastingEngine
from app.engines.risk_detection import RiskDetectionEngine, RiskInputs
from app.engines.what_if_simulation import SimulationLevers, WhatIfSimulationEngine
from app.llm.providers.base import CompletionRequest
from app.llm.router import AllProvidersFailedError, LLMRouter
from app.rag.retriever import Retriever

# ---------------------------------------------------------------------------
# 1. Query Understanding Agent
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "budget_variance": ("budget", "variance", "overspend", "underspend", "spend vs", "over budget", "under budget"),
    "capital_structure": ("wacc", "capital structure", "cost of capital", "debt-to-equity", "leverage", "weighted average"),
    "risk_detection": ("risk", "danger", "red flag", "warning sign", "exposure", "breach"),
    "forecasting": ("forecast", "predict", "projection", "trend", "next quarter", "next month", "future revenue"),
    "what_if_simulation": ("what if", "simulate", "scenario", "suppose we", "if we hire", "if we raise prices", "run simulation"),
    "financial_statement": ("ratio", "margin", "balance sheet", "income statement", "liquidity", "profitability", "roa", "roe", "current ratio", "quick ratio", "gross margin"),
}

# Topics that are explicitly off-domain for FinSight AI — used by the
# query-understanding node to short-circuit irrelevant questions.
_OFF_TOPIC_KEYWORDS = (
    "cricket", "football", "soccer", "sports", "movie", "recipe", "cook",
    "weather", "politics", "election", "music", "game", "celebrity",
    "dating", "travel", "tourist", "hotel", "restaurant", "joke", "poem",
    "news", "stock tip", "cryptocurrency", "nft", "bitcoin", "ethereum",
)

_PERIOD_RE = re.compile(r"next (\d+) (month|quarter)s?")

# Finance-domain positive signals — if none of these appear AND the query hits
# general_rag, we treat it as off-topic (second-pass domain gate).
_FINANCE_SIGNALS = (
    "revenue", "cost", "expense", "profit", "loss", "margin", "cash",
    "budget", "spend", "invoice", "payable", "receivable", "asset",
    "liability", "equity", "debt", "loan", "interest", "tax",
    "quarter", "annual", "fiscal", "financial", "income", "salary",
    "hire", "headcount", "capex", "opex", "break even", "breakeven",
    "report", "statement", "document", "uploaded", "forecast",
    "ratio", "liquidity", "solvency", "risk", "rate",
    "borrow", "borrowing", "lending", "credit", "plan", "fund", "funds",
    "invest", "investment", "investing", "stock", "stocks", "market", "portfolio", "shares",
)


def _keyword_present(query: str, keyword: str) -> bool:
    """Word-boundary match for single-word keywords (so "ratio" doesn't
    false-positive inside "concentration"); plain substring match for
    multi-word phrases, which are specific enough not to need it."""
    if " " in keyword or "-" in keyword:
        return keyword in query
    return re.search(rf"\b{re.escape(keyword)}\b", query) is not None


def understand_query(state: AgentState) -> dict[str, Any]:
    query = state.get("user_query", "").lower()

    # -- Off-topic guard pass 1: explicit non-financial keyword blocklist --
    off_topic_hit = next((kw for kw in _OFF_TOPIC_KEYWORDS if kw in query), None)
    if off_topic_hit:
        return {
            "intent": "general_rag",
            "intent_confidence": 1.0,
            "extracted_params": {"_off_topic": True},
            "errors": [
                "off_topic: FinSight AI is a financial intelligence tool. "
                "Please ask questions about budgets, ratios, cash flow, risk, "
                "forecasting, or the financial documents you have uploaded."
            ],
        }

    best_intent: Intent = "general_rag"
    best_score = 0
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if _keyword_present(query, kw))
        if score > best_score:
            best_score = score
            best_intent = intent

    confidence = min(1.0, 0.4 + 0.2 * best_score) if best_score else 0.3

    params: dict[str, Any] = dict(state.get("extracted_params", {}))
    match = _PERIOD_RE.search(query)
    if match:
        n, unit = int(match.group(1)), match.group(2)
        params["periods_ahead"] = n * (3 if unit == "quarter" else 1)

    # -- Off-topic guard pass 2: for general_rag (no strong financial intent),
    # check at least one finance signal is present in the query. If none, it's
    # almost certainly an off-domain question. --
    if best_intent == "general_rag" and best_score == 0:
        has_finance_signal = any(sig in query for sig in _FINANCE_SIGNALS)
        if not has_finance_signal:
            return {
                "intent": "general_rag",
                "intent_confidence": 1.0,
                "extracted_params": {"_off_topic": True},
                "errors": [
                    "off_topic: That question does not appear to be about business finance. "
                    "FinSight AI can only answer questions about budgets, financial ratios, "
                    "cash flow, risk, forecasting, capital structure, or uploaded financial documents."
                ],
            }

    return {"intent": best_intent, "intent_confidence": confidence, "extracted_params": params}


# ---------------------------------------------------------------------------
# 2. Task Routing Agent
# ---------------------------------------------------------------------------

_INTENT_TO_ROUTE: dict[Intent, str] = {
    "budget_variance": "engine:budget_variance",
    "financial_statement": "engine:financial_statement",
    "capital_structure": "engine:capital_structure",
    "risk_detection": "engine:risk_detection",
    "forecasting": "engine:forecasting",
    "what_if_simulation": "engine:what_if_simulation",
    "general_rag": "rag:retrieve",
}


def route_task(state: AgentState) -> dict[str, Any]:
    intent = state.get("intent", "general_rag")
    return {"route": _INTENT_TO_ROUTE.get(intent, "rag:retrieve")}


# ---------------------------------------------------------------------------
# 3. Tool Execution Agent
# ---------------------------------------------------------------------------


def _require(params: dict[str, Any], *keys: str) -> list[str]:
    return [k for k in keys if k not in params]


def _exec_budget_variance(params: dict[str, Any]) -> tuple[dict, list[str]]:
    missing = _require(params, "budget", "actual")
    if missing:
        return {}, [f"missing required field(s): {', '.join(missing)}"]
    engine = BudgetVarianceEngine()
    report = engine.evaluate(
        period=params.get("period", "current"),
        budget=params["budget"],
        actual=params["actual"],
        revenue_categories=set(params.get("revenue_categories", [])),
    )
    return {
        "total_variance_pct": report.total_variance_pct,
        "breaches": [b.category for b in report.breaches()],
        "items": [
            {
                "category": i.category,
                "variance_pct": i.variance_pct,
                "severity": i.severity.value,
            }
            for i in report.items
        ],
    }, []


def _exec_financial_statement(params: dict[str, Any]) -> tuple[dict, list[str]]:
    missing = _require(params, "balance_sheet", "income_statement")
    if missing:
        return {}, [f"missing required field(s): {', '.join(missing)}"]
    engine = FinancialStatementEngine()
    bs = BalanceSheet(**params["balance_sheet"])
    inc = IncomeStatement(**params["income_statement"])
    ratios = engine.compute(bs, inc)
    return {r.name: r.value for r in ratios}, []


def _exec_capital_structure(params: dict[str, Any]) -> tuple[dict, list[str]]:
    missing = _require(
        params,
        "market_value_equity",
        "market_value_debt",
        "cost_of_equity_pct",
        "cost_of_debt_pct",
        "tax_rate_pct",
    )
    if missing:
        return {}, [f"missing required field(s): {', '.join(missing)}"]
    engine = CapitalStructureEngine()
    result = engine.compute(CapitalStructureInput(**{k: params[k] for k in (
        "market_value_equity", "market_value_debt", "cost_of_equity_pct",
        "cost_of_debt_pct", "tax_rate_pct",
    )}))
    return result.__dict__, []


def _exec_risk_detection(params: dict[str, Any]) -> tuple[dict, list[str]]:
    engine = RiskDetectionEngine()
    inputs = RiskInputs(
        current_ratio=params.get("current_ratio"),
        debt_to_equity=params.get("debt_to_equity"),
        net_margin_pct=params.get("net_margin_pct"),
        cash_runway_months=params.get("cash_runway_months"),
        revenue_mom_change_pct=params.get("revenue_mom_change_pct"),
    )
    report = engine.evaluate(inputs)
    return {
        "overall_score": report.overall_score,
        "overall_level": report.overall_level.value,
        "flags": [{"code": f.code, "message": f.message, "level": f.level.value} for f in report.flags],
    }, []


def _exec_forecasting(params: dict[str, Any]) -> tuple[dict, list[str]]:
    missing = _require(params, "series")
    if missing:
        return {}, [f"missing required field(s): {', '.join(missing)}"]
    engine = ForecastingEngine()
    result = engine.forecast_linear(params["series"], periods_ahead=params.get("periods_ahead", 3))
    return {
        "slope": result.slope,
        "r_squared": result.r_squared,
        "forecast": [{"period": p.period_index, "value": p.value} for p in result.forecast],
    }, []


def _exec_what_if(params: dict[str, Any]) -> tuple[dict, list[str]]:
    missing = _require(params, "starting_revenue", "starting_costs", "starting_cash")
    if missing:
        return {}, [f"missing required field(s): {', '.join(missing)}"]
    engine = WhatIfSimulationEngine()
    levers = SimulationLevers(**params.get("levers", {}))
    result = engine.simulate(
        starting_revenue=params["starting_revenue"],
        starting_costs=params["starting_costs"],
        starting_cash=params["starting_cash"],
        levers=levers,
        periods=params.get("periods", 12),
    )
    return {
        "ending_cash": result.ending_cash,
        "breakeven_period": result.breakeven_period,
        "periods": [p.__dict__ for p in result.periods],
    }, []


_ROUTE_EXECUTORS = {
    "engine:budget_variance": _exec_budget_variance,
    "engine:financial_statement": _exec_financial_statement,
    "engine:capital_structure": _exec_capital_structure,
    "engine:risk_detection": _exec_risk_detection,
    "engine:forecasting": _exec_forecasting,
    "engine:what_if_simulation": _exec_what_if,
}


def make_execute_tool(retriever: Retriever | None):
    def execute_tool(state: AgentState) -> dict[str, Any]:
        route = state.get("route", "rag:retrieve")
        params = state.get("extracted_params", {})
        errors = list(state.get("errors", []))

        if route == "rag:retrieve":
            if retriever is None:
                return {"tool_result": {}, "rag_citations": [], "errors": errors + ["no retriever configured"]}
            from app.rag.agentic_rag import AgenticRAGEngine
            agentic_rag = AgenticRAGEngine(retriever)
            result = agentic_rag.retrieve_and_reason(state.get("user_query", ""))
            return {
                "tool_result": {
                    "context": result.context.combined_text,
                    "agentic_decision": result.reasoned_decision,
                    "structured_metrics": result.structured_metrics,
                    "intent": result.intent.value,
                },
                "rag_citations": result.context.citations,
                "errors": errors,
            }

        executor = _ROUTE_EXECUTORS.get(route)
        if executor is None:
            return {"tool_result": {}, "errors": errors + [f"no executor for route '{route}'"]}

        result, exec_errors = executor(params)
        # If the financial calculation engine is missing structured parameters,
        # but documents have been indexed and a retriever is active, fall back to RAG
        # so questions like "What does the Q3 memo state about revenue?" get answered
        # from document context instead of stalling on empty engine inputs.
        rag_requested = any(
            term in state.get("user_query", "").lower()
            for term in ("document", "uploaded", "file", "report", "memo", "according to")
        )
        if exec_errors and retriever is not None and rag_requested:
            context = retriever.retrieve(state.get("user_query", ""))
            if context.combined_text:
                return {
                    "tool_result": {"context": context.combined_text},
                    "rag_citations": context.citations,
                    "errors": errors,
                }

        return {"tool_result": result, "errors": errors + exec_errors}

    return execute_tool


# ---------------------------------------------------------------------------
# 4. Validation & Reconciliation Agent
# ---------------------------------------------------------------------------


def validate_result(state: AgentState) -> dict[str, Any]:
    tool_result = state.get("tool_result", {})
    errors = state.get("errors", [])
    notes: list[str] = []

    # Propagate off-topic errors from understand_query — no further validation needed.
    if any(e.startswith("off_topic:") for e in errors):
        return {"is_valid": False, "validation_notes": errors}

    if errors:
        notes.extend(errors)
        return {"is_valid": False, "validation_notes": notes}

    if not tool_result:
        notes.append("tool execution returned no data")
        return {"is_valid": False, "validation_notes": notes}

    if state.get("route") == "engine:risk_detection" and tool_result.get("overall_level") == "critical":
        notes.append("CRITICAL risk level detected — flag for immediate business-owner attention")

    if state.get("route") == "engine:financial_statement":
        none_ratios = [k for k, v in tool_result.items() if v is None]
        if none_ratios:
            notes.append(f"ratios undefined due to zero denominator: {', '.join(none_ratios)}")

    return {"is_valid": True, "validation_notes": notes}


# ---------------------------------------------------------------------------
# 5. Response Generation Agent
# ---------------------------------------------------------------------------


def _template_response(state: AgentState) -> str:
    """Deterministic fallback used when no LLM is configured, or every
    provider in the router failed. The advisor degrades to "accurate but
    terse" rather than ever going silent."""
    if not state.get("is_valid", False):
        notes = "; ".join(state.get("validation_notes", [])) or "unable to compute a result"
        return f"I couldn't fully answer that: {notes}."

    result = state.get("tool_result", {})
    lines: list[str] = []
    context = result.get("context") if isinstance(result, dict) else None
    outlook = state.get("extracted_params", {}).get("investment_outlook")
    if isinstance(outlook, dict) and outlook.get("symbol"):
        try:
            amount = float(outlook.get("amount") or 0)
            expected = float(outlook.get("expected_profit") or 0)
            worst = float(outlook.get("worst_case_profit") or 0)
            var_loss = float(outlook.get("var_95_loss") or 0)
            chance = float(outlook.get("probability_of_loss_pct") or 0)
            lines.append(
                f"- {outlook['symbol']} over {outlook.get('horizon_months', '?')} months on "
                f"₹{amount:,.0f}: expected ₹{expected:+,.0f}, worst case ₹{worst:+,.0f} in the "
                f"80% band, 95% value-at-risk loss ₹{var_loss:,.0f}, "
                f"modelled chance of loss {chance:.0f}%."
            )
            lines.append(
                "- The numbers are deterministic projections from the asset's own price "
                "history, not recommendations. Size the position so the 95% loss does not "
                "breach your operating cash buffer."
            )
        except (TypeError, ValueError):
            pass
    for k, v in result.items():
        if k == "context":
            continue
        if isinstance(v, list):
            if v and not isinstance(v[0], dict):
                lines.append(f"- {k}: {', '.join(str(x) for x in v)}")
        elif isinstance(v, dict):
            continue
        else:
            lines.append(f"- {k}: {v}")
    agentic_decision = result.get("agentic_decision") if isinstance(result, dict) else None
    if isinstance(agentic_decision, str) and agentic_decision.strip():
        body = agentic_decision.strip()
    elif lines:
        body = "\n".join(lines)
    elif isinstance(context, str) and context.strip():
        # RAG-only answers: quote the retrieved passages rather than
        # returning "See structured result for details."
        body = "From your uploaded documents:\n" + context.strip()[:800]
    else:
        body = "See structured result for details."
    citations = state.get("rag_citations", [])
    if citations:
        body += "\n\nSources: " + "; ".join(citations)
    return body


def make_generate_response(llm_router: LLMRouter | None):
    async def generate_response(state: AgentState) -> dict[str, Any]:
        # Hard gate: off-topic queries must be refused, no LLM call needed.
        errors = state.get("errors", [])
        is_off_topic = any(e.startswith("off_topic:") for e in errors)
        if is_off_topic:
            refusal = (
                "I'm FinSight AI — a business financial intelligence assistant. "
                "That question falls outside my domain. I can help you with: "
                "budget variance, financial ratios, risk detection, cash-flow forecasting, "
                "what-if scenario modeling, or questions about financial documents you've uploaded. "
                "Please ask a business finance question."
            )
            return {"final_response": refusal}

        if llm_router is None:
            return {"final_response": _template_response(state)}

        rag_context = state.get("tool_result", {}).get("context", "")
        context_section = f"\nRetrieved document context:\n{rag_context}\n" if rag_context else ""
        business_context = state.get("extracted_params", {}).get("_business_context", "")
        business_section = (
            f"\nRecorded business data (latest ledger periods):\n{business_context}\n"
            if isinstance(business_context, str) and business_context.strip()
            else ""
        )
        agentic_decision = state.get("tool_result", {}).get("agentic_decision", "")
        agentic_section = f"\nExpert Agentic Decision & Verified Figures:\n{agentic_decision}\n" if agentic_decision else ""

        prompt = (
            f"User question: {state.get('user_query', '')}\n"
            f"Computed result (JSON-like): {state.get('tool_result', {})}\n"
            f"{business_section}"
            f"{agentic_section}"
            f"{context_section}"
            f"Validation notes: {state.get('validation_notes', [])}\n\n"
            "Write a concise, plain-language answer for a business owner. "
            "Only use the numbers given above; do not invent or estimate figures. "
            "If the data is insufficient, say so clearly and specify exactly what is needed. "
            "Reply in plain chat text: no markdown formatting, no **emphasis**, "
            "no # headings, no backticks."
        )
        system = (
            "You are FinSight AI, an expert business financial intelligence advisor. "
            "You ONLY answer questions about business finance: budgets, P&L, balance sheets, "
            "cash flow, financial ratios, risk, forecasting, and what-if scenarios. "
            "If a question is unrelated to business finance, politely decline and redirect "
            "the user to ask a financial question. "
            "Never fabricate financial figures. If data is missing, ask for it specifically. "
            "Be concise, accurate, and professional. Format every monetary amount in Indian "
            "Rupees using ₹; never use the $ symbol or USD labels."
        )
        try:
            router_result = await llm_router.complete(
                CompletionRequest(
                    prompt=prompt,
                    system=system,
                )
            )
            text = (router_result.response.text or "").strip()
            if not text:
                return {"final_response": _template_response(state)}
            citations = state.get("rag_citations", [])
            if citations:
                text += "\n\nSources: " + "; ".join(citations)
            return {"final_response": text}
        except AllProvidersFailedError:
            return {"final_response": _template_response(state)}

    return generate_response


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph(retriever: Retriever | None = None, llm_router: LLMRouter | None = None):
    """Compile the 5-node LangGraph workflow. Pass `retriever`/`llm_router`
    to wire in RAG and an LLM; omit either for a fully deterministic,
    network-free graph (used heavily in tests)."""
    graph = StateGraph(AgentState)

    graph.add_node("understand_query", understand_query)
    graph.add_node("route_task", route_task)
    graph.add_node("execute_tool", make_execute_tool(retriever))
    graph.add_node("validate_result", validate_result)
    graph.add_node("generate_response", make_generate_response(llm_router))

    graph.set_entry_point("understand_query")
    graph.add_edge("understand_query", "route_task")
    graph.add_edge("route_task", "execute_tool")
    graph.add_edge("execute_tool", "validate_result")
    graph.add_edge("validate_result", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()
