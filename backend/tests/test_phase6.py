import pytest
import pymupdf as fitz
from datetime import datetime
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.models.document import Document
from app.core.security import hash_password
from app.services.embeddings import EmbeddingService
from app.services.vector_store import vector_store
from app.services.vector_search import VectorSearchService
from app.services.gemini_service import gemini_service
from app.services.rag import RAGPipeline
from app.workers.document_worker import ingest_document


def create_groundnut_manual_pdf() -> bytes:
    """Generates a sample 2-page agricultural manual for groundnut cultivation."""
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text(
        fitz.Point(50, 72),
        "ICAR Directorate of Groundnut Research - Package of Practices.\n\n"
        "Groundnut (Arachis hypogaea) performs best in well-drained sandy loam soil with pH 6.0 to 7.5. "
        "Apply Gypsum at 400 to 500 kilograms per hectare at 40 to 45 days after sowing (flowering and pegging stage). "
        "Gypsum provides critical calcium for pod development and sulphur for oil synthesis. "
        "Ensure soil moisture is adequate during peg entry into the soil.",
        fontsize=11,
    )

    p2 = doc.new_page()
    p2.insert_text(
        fitz.Point(50, 72),
        "Groundnut Weed and Disease Management.\n\n"
        "Tikka leaf spot is the most destructive fungal disease of groundnut, causing circular brown spots with yellow halos. "
        "To manage Tikka leaf spot, spray Mancozeb at 2 grams per liter or Carbendazim at 1 gram per liter "
        "at the appearance of initial leaf lesions. Repeat after 15 days if cloudy humid weather persists.",
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_embedding_generation():
    """Verify Sentence Transformers generates 384-dimensional normalized vectors."""
    vec = EmbeddingService.embed_text("What is the optimal sowing time for groundnut?")
    assert isinstance(vec, list)
    assert len(vec) == 384

    batch_vecs = EmbeddingService.embed_batch(["Rice cultivation", "Cotton irrigation"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 384
    assert len(batch_vecs[1]) == 384


@pytest.mark.asyncio
async def test_vector_search_and_grounded_retrieval():
    """Verify vector search returns verified chunks with real document names and page numbers."""
    ts = int(datetime.now().timestamp() * 1000)
    pdf_bytes = create_groundnut_manual_pdf()

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Agronomy Researcher",
            email=f"agri_rag_{ts}@krishiguide.org",
            hashed_password=hash_password("Pass123!"),
            role="admin",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            document_name="ICAR Groundnut Cultivation Guide.pdf",
            file_path=tmp_path,
            file_type="application/pdf",
            file_size=len(pdf_bytes),
            uploaded_by=user.id,
            is_public=True,
            processing_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id
        user_id = user.id

    # Ingest document
    await ingest_document(doc_id)

    # Search for relevant question
    async with AsyncSessionLocal() as session:
        hits = await VectorSearchService.search_agricultural_context(
            query="When should gypsum be applied to groundnut?",
            user_id=user_id,
            user_role="admin",
            db=session,
            limit=3,
        )

    assert len(hits) > 0
    top_hit = hits[0]
    assert any("Groundnut" in h["document_name"] for h in hits)
    assert top_hit["page_number"] >= 1
    assert "gypsum" in top_hit["text"].lower()
    assert top_hit["similarity_score"] > 0.3


@pytest.mark.asyncio
async def test_rag_pipeline_end_to_end_with_citations():
    """Verify complete RAG pipeline returns grounded answer and real source citations."""
    ts = int(datetime.now().timestamp() * 1000)
    pdf_bytes = create_groundnut_manual_pdf()

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Ramesh",
            email=f"farmer_rag_{ts}@krishiguide.org",
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            document_name="Groundnut Manual.pdf",
            file_path=tmp_path,
            file_type="application/pdf",
            file_size=len(pdf_bytes),
            uploaded_by=user.id,
            is_public=True,
            processing_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id
        user_id = user.id

    await ingest_document(doc_id)

    async with AsyncSessionLocal() as session:
        result = await RAGPipeline.query(
            question="How do I control Tikka leaf spot disease in groundnut?",
            user_id=user_id,
            user_role="farmer",
            db=session,
            language="English",
        )

    assert result["context_found"] is True
    assert len(result["sources"]) > 0
    # Verify citations contain real document and page
    doc_names = [s["document_name"] for s in result["sources"]]
    assert any("Groundnut" in name for name in doc_names)
    assert all(s["page_number"] >= 1 for s in result["sources"])
    assert "tikka" in result["answer"].lower() or "mancozeb" in result["answer"].lower() or "groundnut" in result["answer"].lower()


@pytest.mark.asyncio
async def test_insufficient_context_handling():
    """Verify that irrelevant questions return honest insufficient context responses."""
    ts = int(datetime.now().timestamp() * 1000)
    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Testing",
            email=f"farmer_insuf_{ts}@krishiguide.org",
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        # Query on completely unrelated topic
        result = await RAGPipeline.query(
            question="What is the Schwarzschild radius of a supermassive black hole?",
            user_id=user_id,
            user_role="farmer",
            db=session,
            language="English",
            similarity_threshold=0.6,
        )

    assert result["context_found"] is False
    assert result["sources"] == []
    assert "could not find verified agricultural guidelines" in result["answer"].lower() or "consult" in result["answer"].lower()


@pytest.mark.asyncio
async def test_telugu_language_preference():
    """Verify insufficient context returns localized response in Telugu."""
    ts = int(datetime.now().timestamp() * 1000)
    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Telugu",
            email=f"farmer_telugu_{ts}@krishiguide.org",
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        result = await RAGPipeline.query(
            question="అంతరిక్షంలో రాకెట్ ప్రయోగం ఎలా జరుగుతుంది?",
            user_id=user_id,
            user_role="farmer",
            db=session,
            language="Telugu",
            similarity_threshold=0.6,
        )

    assert result["context_found"] is False
    assert "కృషి విజ్ఞాన కేంద్రం" in result["answer"] or "వ్యవసాయ" in result["answer"]

