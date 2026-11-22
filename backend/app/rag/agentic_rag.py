"""
FinSight AI — Agentic RAG Module (Showcase Edition)
---------------------------------------------------
This public repository showcases system interfaces, screenshots, and architecture.
The proprietary agentic retrieval pipeline, multi-pass sheet extractors, and
custom embedding rankers are maintained in the private production repository.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from app.rag.retriever import RetrievedContext, Retriever


class FinancialIntent(str, Enum):
    SUMMARY = "summary"
    LOAN_DECISION = "loan_decision"
    STOCK_INVESTMENT = "stock_investment"
    REVENUE = "revenue"
    EXPENSES = "expenses"
    RISK = "risk"
    GENERAL = "general"


def classify_financial_intent(query: str) -> FinancialIntent:
    q = query.lower()
    if any(k in q for k in ["loan", "borrow", "debt", "emi"]):
        return FinancialIntent.LOAN_DECISION
    if any(k in q for k in ["stock", "invest", "portfolio"]):
        return FinancialIntent.STOCK_INVESTMENT
    if any(k in q for k in ["revenue", "sales"]):
        return FinancialIntent.REVENUE
    return FinancialIntent.SUMMARY


class AgenticFinancialRAG:
    """Showcase agentic RAG interface for financial queries."""

    def __init__(self, retriever: Retriever | None = None, llm_router: Any = None):
        self.retriever = retriever
        self.llm_router = llm_router

    async def answer(self, query: str, business_id: str, company_name: str = "Company") -> dict[str, Any]:
        return {
            "answer": (
                f"Financial analysis completed for {company_name}. "
                "All metric figures are verified against uploaded corporate filings."
            ),
            "intent": classify_financial_intent(query).value,
            "citations": ["Financial Statements (verified source)"],
            "model_used": "deterministic-showcase",
        }
