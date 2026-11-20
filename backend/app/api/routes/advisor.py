from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_graph
from app.api.deps import get_llm_router, get_retriever
from app.core.security import TokenPayload, get_current_user
from app.db.session import get_session
from app.llm.router import LLMRouter
from app.models.schemas import AdvisorRequest, AdvisorResponse
from app.rag.retriever import Retriever
from app.services.financial_context import build_context

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/ask", response_model=AdvisorResponse)
async def ask(
    payload: AdvisorRequest,
    user: TokenPayload = Depends(get_current_user),
    retriever: Retriever = Depends(get_retriever),
    llm_router: LLMRouter | None = Depends(get_llm_router),
    session: AsyncSession = Depends(get_session),
) -> AdvisorResponse:
    # Give every answer the owner's ledger snapshot (latest revenue, cash,
    # budgets, transactions), so "how does this investment fit my business?"
    # is answered from real recorded data and not just the uploaded docs.
    extracted = dict(payload.extracted_params)
    try:
        context = await build_context(session, user.business_id)
        extracted.setdefault("_business_context", context.prompt_context)
    except Exception:  # never fail an advisory answer because context is unavailable
        pass

    # Scope retrieval to the authenticated tenant. The dependency remains
    # overrideable in tests, but uploaded evidence from another business can
    # never enter this graph.
    retriever = Retriever(
        retriever.store,
        min_score=retriever.min_score,
        metadata_filter={"business_id": user.business_id},
    )
    graph = build_graph(retriever=retriever, llm_router=llm_router)
    final_state = await graph.ainvoke(
        {"user_query": payload.query, "extracted_params": extracted}
    )
    return AdvisorResponse(
        intent=final_state.get("intent", "general_rag"),
        route=final_state.get("route", ""),
        is_valid=final_state.get("is_valid", False),
        tool_result=final_state.get("tool_result", {}),
        citations=final_state.get("rag_citations", []),
        validation_notes=final_state.get("validation_notes", []),
        answer=final_state.get("final_response") or "",
    )
