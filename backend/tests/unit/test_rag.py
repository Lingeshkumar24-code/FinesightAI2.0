import pytest

from app.rag.ingestion import chunk_document
from app.rag.retriever import Retriever
from app.rag.vectorstore import InMemoryVectorStore


def test_chunking_respects_paragraph_boundaries_when_possible():
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_document(text, source="doc.txt", max_chars=1000)
    assert len(chunks) == 1
    assert "Paragraph one." in chunks[0].text
    assert "Paragraph three." in chunks[0].text


def test_chunking_splits_when_over_max_chars():
    text = "A" * 50 + "\n\n" + "B" * 50
    chunks = chunk_document(text, source="doc.txt", max_chars=60, overlap=0)
    assert len(chunks) >= 2


def test_chunking_tracks_source_and_index():
    text = "Para one.\n\nPara two."
    chunks = chunk_document(text, source="budget.pdf", max_chars=8, overlap=0)
    for chunk in chunks:
        assert chunk.source == "budget.pdf"
        assert "source" in chunk.metadata


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_document("text", source="x.txt", max_chars=100, overlap=200)


def test_retriever_returns_most_relevant_chunk():
    store = InMemoryVectorStore()
    chunks = chunk_document(
        "Marketing budget overspend was driven by a paid social campaign.\n\n"
        "Office rent remained flat quarter over quarter with no variance.",
        source="q3_report.pdf",
        max_chars=200,
    )
    store.upsert(chunks)

    retriever = Retriever(store)
    result = retriever.retrieve("why did marketing overspend this quarter?")

    assert "marketing" in result.combined_text.lower()
    assert len(result.citations) >= 1
    assert "q3_report.pdf" in result.citations[0]


def test_retriever_returns_empty_context_for_unrelated_query():
    store = InMemoryVectorStore()
    store.upsert(chunk_document("Cats are fluffy mammals.", source="unrelated.txt"))

    retriever = Retriever(store, min_score=0.3)
    result = retriever.retrieve("quarterly capital structure WACC analysis")

    assert result.combined_text == ""
    assert result.citations == []


def test_retriever_applies_tenant_metadata_filter():
    store = InMemoryVectorStore()
    store.upsert([
        *chunk_document(
            "Acme revenue was 100.",
            source="acme.xlsx",
            metadata={"business_id": "acme"},
        ),
        *chunk_document(
            "OtherCo revenue was 900.",
            source="other.xlsx",
            metadata={"business_id": "other"},
        ),
    ])

    result = Retriever(store, metadata_filter={"business_id": "acme"}).retrieve("revenue")

    assert "Acme" in result.combined_text
    assert "OtherCo" not in result.combined_text
    assert all("other.xlsx" not in citation for citation in result.citations)


def test_agentic_rag_intent_classification():
    from app.rag.agentic_rag import FinancialIntent, classify_financial_intent

    assert classify_financial_intent("should we take a loan?") == FinancialIntent.LOAN_DECISION
    assert classify_financial_intent("in which stock can we invest surplus cash?") == FinancialIntent.STOCK_INVESTMENT
    assert classify_financial_intent("give me an executive summary") == FinancialIntent.SUMMARY
    assert classify_financial_intent("what are our operating expenses?") == FinancialIntent.EXPENSES
    assert classify_financial_intent("tell me total invoiced revenue") == FinancialIntent.REVENUE


def test_agentic_rag_loan_and_stock_decision_synthesis():
    from app.rag.agentic_rag import AgenticRAGEngine
    store = InMemoryVectorStore()
    text = (
        "=== [Sheet: Loan Register] ===\n"
        "Loan LN-001 Demo National Bank Term Loan 3000000 11.5% 82000 1680000 Active\n"
        "Loan LN-002 Demo Urban Finance Working Capital 1000000 12.5% 26500 520000 Active\n"
        "Loan LN-003 Demo Co-operative Bank Equipment Loan 800000 10.5% 17500 610000 Active\n\n"
        "=== [Sheet: Balance Sheet] ===\n"
        "Cash and Cash Equivalents: 2350000. Total Debt: 2810000.\n"
    )
    store.upsert(chunk_document(text, source="dataset.xlsx"))
    retriever = Retriever(store)
    agentic = AgenticRAGEngine(retriever)

    # Test loan decision
    loan_res = agentic.retrieve_and_reason("should we take a loan or not?")
    assert "DO NOT TAKE AN ADDITIONAL COMMERCIAL LOAN" in loan_res.reasoned_decision
    assert "28,10,000" in loan_res.reasoned_decision
    assert "1,26,000" in loan_res.reasoned_decision

    # Test stock investment decision
    stock_res = agentic.retrieve_and_reason("in which stock can we invest?")
    assert "DO NOT INVEST IN EQUITY STOCKS" in stock_res.reasoned_decision
    assert "Overnight Liquid Mutual Funds" in stock_res.reasoned_decision
