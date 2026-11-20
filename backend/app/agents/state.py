from __future__ import annotations

from typing import Any, Literal, TypedDict

Intent = Literal[
    "budget_variance",
    "financial_statement",
    "capital_structure",
    "risk_detection",
    "forecasting",
    "what_if_simulation",
    "general_rag",
]


class AgentState(TypedDict, total=False):
    # --- input ---
    business_id: str
    user_query: str

    # 1. Query Understanding Agent output
    intent: Intent
    intent_confidence: float
    extracted_params: dict[str, Any]

    # 2. Task Routing Agent output
    route: str  # which tool/engine to call

    # 3. Tool Execution Agent output (financial engine result or RAG context)
    tool_result: dict[str, Any]
    rag_citations: list[str]

    # 4. Validation & Reconciliation Agent output
    is_valid: bool
    validation_notes: list[str]

    # 5. Response Generation Agent output
    final_response: str

    # cross-cutting
    errors: list[str]
