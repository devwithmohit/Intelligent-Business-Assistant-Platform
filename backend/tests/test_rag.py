from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.models.knowledge_models import KnowledgeChunk, KnowledgeDocument
from backend.models.user_models import User
from backend.services import memory_service, rag_service
from backend.agents.customer_service.agent import CustomerServiceAgent


@pytest.fixture(scope="module")
def test_db_session():
    """Create isolated in-memory SQLite database for testing knowledge models."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test users
    u1 = User(id=101, email="tenant1@example.com", name="Tenant One", password="hash1", is_active=True)
    u2 = User(id=102, email="tenant2@example.com", name="Tenant Two", password="hash2", is_active=True)
    session.add_all([u1, u2])
    session.commit()

    yield session

    session.close()


def test_text_chunking():
    """Verify recursive character text chunker splits text with overlap."""
    text = (
        "Paragraph 1 contains general platform introduction details.\n\n"
        "Paragraph 2 discusses agent orchestration and multi-agent coordination capabilities.\n\n"
        "Paragraph 3 covers vector embeddings, semantic retrieval, and memory management.\n\n"
        "Paragraph 4 outlines security boundaries, tenant isolation, and cryptographic storage."
    )
    chunks = rag_service.chunk_text(text, chunk_size=120, chunk_overlap=20)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) > 0


def test_text_extraction():
    """Verify text extraction handles plain text and structured JSON."""
    raw_txt = b"Plain text content with instructions."
    extracted = rag_service.extract_text_from_file(raw_txt, filename="notes.txt")
    assert "Plain text content" in extracted

    json_bytes = b'{"company": "Acme Inc", "revenue": 1000000, "status": "active"}'
    extracted_json = rag_service.extract_text_from_file(json_bytes, filename="data.json")
    assert "Acme Inc" in extracted_json
    assert "1000000" in extracted_json


@pytest.mark.asyncio
async def test_document_ingestion_and_chunking(test_db_session):
    """Verify document ingestion creates DB records and vector embeddings."""
    content = (
        "Project Architecture Overview: The platform is built on FastAPI with PostgreSQL for tenancy.\n\n"
        "Vector Memory Module: Uses Chroma for indexing and semantic similarity queries.\n\n"
        "Integration Manager: Encrypts external tool secrets using symmetric Fernet encryption."
    )
    doc = await rag_service.ingest_document(
        db=test_db_session,
        user_id=101,
        title="Architecture Guide",
        content=content,
        filename="architecture.md",
        content_type="text/markdown",
        chunk_size=100,
        chunk_overlap=15,
    )

    assert doc.id is not None
    assert doc.chunk_count > 0
    assert doc.user_id == 101

    # Verify chunks in database
    chunks = (
        test_db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.document_id == doc.id)
        .all()
    )
    assert len(chunks) == doc.chunk_count
    for c in chunks:
        assert c.user_id == 101
        assert c.vector_id is not None


@pytest.mark.asyncio
async def test_cross_tenant_retrieval_isolation(test_db_session):
    """
    CRITICAL SECURITY TEST:
    Verify that User 2 (tenant 102) CANNOT retrieve documents uploaded by User 1 (tenant 101).
    """
    # Tenant 1 ingests confidential document
    confidential_text = (
        "Confidential Financial Report 2026: Q3 gross margin reached 82% with 50M EBITDA. "
        "Strictly confidential to Acme Holdings board members."
    )
    doc = await rag_service.ingest_document(
        db=test_db_session,
        user_id=101,
        title="Confidential Q3 Financials",
        content=confidential_text,
    )
    assert doc.id is not None

    # Tenant 2 queries for the exact confidential keywords
    tenant2_hits = await rag_service.retrieve_knowledge(
        user_id=102,
        query="Confidential Financial Report EBITDA gross margin",
        top_k=5,
    )
    # Tenant 2 must receive zero hits
    assert len(tenant2_hits) == 0, "Security violation: Cross-tenant document leaked to tenant 102!"

    # Tenant 1 queries for their own document
    tenant1_hits = await rag_service.retrieve_knowledge(
        user_id=101,
        query="Confidential Financial Report EBITDA gross margin",
        top_k=5,
    )
    assert len(tenant1_hits) > 0
    assert "Confidential Financial Report" in tenant1_hits[0]["content"]
    assert tenant1_hits[0]["document_id"] == doc.id


@pytest.mark.asyncio
async def test_document_deletion_purges_vectors(test_db_session):
    """Verify document deletion removes records and purges vector search results."""
    doc = await rag_service.ingest_document(
        db=test_db_session,
        user_id=101,
        title="Temporary Policy",
        content="Temporary holiday operating hours: closed on December 25th.",
    )
    doc_id = doc.id

    # Verify retrieval works initially
    hits_before = await rag_service.retrieve_knowledge(
        user_id=101,
        query="holiday operating hours December",
        document_id=doc_id,
    )
    assert len(hits_before) > 0

    # Delete document
    deleted = await rag_service.delete_document(
        db=test_db_session,
        user_id=101,
        document_id=doc_id,
    )
    assert deleted is True

    # Verify DB record is gone
    doc_in_db = test_db_session.query(KnowledgeDocument).filter_by(id=doc_id).first()
    assert doc_in_db is None

    # Verify chunks in DB are gone
    chunks_in_db = test_db_session.query(KnowledgeChunk).filter_by(document_id=doc_id).all()
    assert len(chunks_in_db) == 0

    # Verify retrieval no longer returns deleted content
    hits_after = await rag_service.retrieve_knowledge(
        user_id=101,
        query="holiday operating hours December",
        document_id=doc_id,
    )
    assert len(hits_after) == 0


@pytest.mark.asyncio
async def test_vector_memory_service_tenant_isolation():
    """Verify memory_service.upsert_vector and query_vector strictly partition by user_id."""
    # Store vector memory for user 201
    mem_id = await memory_service.store_vector_memory(
        key="customer_note",
        text="Customer VIP Alpha preferences: express shipping and email invoicing.",
        user_id=201,
        agent_id="customer_service",
    )
    assert mem_id is not None

    # User 202 searches for VIP Alpha preferences
    user202_hits = await memory_service.query_vector_memory(
        query="Customer VIP Alpha preferences shipping",
        user_id=202,
    )
    assert len(user202_hits) == 0, "Security violation: Cross-tenant memory leak to user 202!"

    # User 201 searches
    user201_hits = await memory_service.query_vector_memory(
        query="Customer VIP Alpha preferences shipping",
        user_id=201,
    )
    assert len(user201_hits) > 0
    assert "VIP Alpha preferences" in user201_hits[0].get("document", "")


@pytest.mark.asyncio
async def test_agent_rag_context_injection(test_db_session, monkeypatch):
    """Verify CustomerServiceAgent queries tenant RAG knowledge and injects it into prompt."""
    # Seed refund policy knowledge for user 101
    await rag_service.ingest_document(
        db=test_db_session,
        user_id=101,
        title="Return Policy",
        content="Acme Policy: Customers are eligible for a 100% full refund within 30 days of purchase with receipt.",
    )

    captured_prompts = []

    async def mock_llm_generate(req):
        captured_prompts.append(req.prompt or "")

        class MockResp:
            text = "Thank you for contacting us. Under our 30-day return policy, you are eligible for a full refund."
            raw = None

        return MockResp()

    agent = CustomerServiceAgent(
        name="customer_service",
        config={"user_id": 101},
    )
    monkeypatch.setattr(agent.llm, "generate", mock_llm_generate)

    result = await agent.run(
        customer_message="Can I get my money back for an item bought 5 days ago?",
        user_id=101,
    )

    assert result.success is True
    # Verify that knowledge base context was retrieved and injected into the draft_response prompt
    draft_prompts = [p for p in captured_prompts if "return policy" in p.lower() or "knowledge base" in p.lower()]
    assert len(draft_prompts) > 0, "Knowledge base context was not injected into agent LLM prompt!"
    assert "30 days" in draft_prompts[0]
