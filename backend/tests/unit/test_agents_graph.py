import pytest

from app.agents.graph import build_graph, route_task, understand_query
from app.rag.ingestion import chunk_document
from app.rag.retriever import Retriever
from app.rag.vectorstore import InMemoryVectorStore


# ---------------------------------------------------------------------------
# Node-level unit tests (no graph needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("Why did we go over budget on marketing this month?", "budget_variance"),
        ("What's our current ratio and net margin?", "financial_statement"),
        ("What's our WACC given our new debt load?", "capital_structure"),
        ("Are there any red flags in our cash position?", "risk_detection"),
        ("Can you forecast revenue for the next 3 months?", "forecasting"),
        ("What if we hire two more engineers?", "what_if_simulation"),
        ("Tell me something about our business", "general_rag"),
    ],
)
def test_understand_query_classifies_intent(query, expected_intent):
    result = understand_query({"user_query": query})
    assert result["intent"] == expected_intent


def test_understand_query_extracts_period_from_text():
    result = understand_query({"user_query": "forecast the next 2 quarters"})
    assert result["extracted_params"]["periods_ahead"] == 6


def test_understand_query_does_not_false_positive_on_substring():
    # "concentration" contains the literal substring "ratio" (conCENTRATIOn) —
    # regression test for word-boundary keyword matching.
    result = understand_query({"user_query": "Tell me about customer concentration risk exposure."})
    assert result["intent"] != "financial_statement"


def test_route_task_maps_intent_to_engine():
    assert route_task({"intent": "risk_detection"})["route"] == "engine:risk_detection"
    assert route_task({"intent": "general_rag"})["route"] == "rag:retrieve"


# ---------------------------------------------------------------------------
# End-to-end graph tests (no LLM configured -> deterministic template path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_computes_budget_variance_end_to_end():
    graph = build_graph()  # no retriever, no llm -> fully deterministic
    final_state = await graph.ainvoke(
        {
            "user_query": "Did we overspend our marketing budget?",
            "extracted_params": {
                "budget": {"marketing": 10_000},
                "actual": {"marketing": 13_000},
            },
        }
    )
    assert final_state["intent"] == "budget_variance"
    assert final_state["is_valid"] is True
    assert "marketing" in final_state["tool_result"]["breaches"]
    assert "marketing" in final_state["final_response"]


@pytest.mark.asyncio
async def test_graph_handles_missing_params_gracefully():
    graph = build_graph()
    final_state = await graph.ainvoke(
        {"user_query": "What's our WACC?", "extracted_params": {}}
    )
    assert final_state["is_valid"] is False
    assert "missing required field" in final_state["final_response"]


@pytest.mark.asyncio
async def test_graph_general_rag_uses_retriever():
    store = InMemoryVectorStore()
    store.upsert(
        chunk_document(
            "Our biggest customer concentration issue: one client is 40% of revenue.",
            source="q3_risk_memo.pdf",
        )
    )
    retriever = Retriever(store)
    graph = build_graph(retriever=retriever)

    # Deliberately avoid any engine keyword (e.g. "budget", "risk", "forecast")
    # so the Query Understanding Agent falls through to general_rag.
    final_state = await graph.ainvoke({"user_query": "Tell me about our customer concentration last quarter."})

    assert final_state["route"] == "rag:retrieve"
    assert "q3_risk_memo.pdf" in "".join(final_state["rag_citations"])
    assert "Sources:" in final_state["final_response"]


@pytest.mark.asyncio
async def test_graph_flags_critical_risk_in_validation_notes():
    graph = build_graph()
    final_state = await graph.ainvoke(
        {
            "user_query": "Any risk flags I should know about?",
            "extracted_params": {"cash_runway_months": 0.2, "current_ratio": 0.2, "debt_to_equity": 5.0},
        }
    )
    assert final_state["is_valid"] is True
    assert any("CRITICAL" in n for n in final_state["validation_notes"])
