import pytest
import io
import pymupdf as fitz
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.core.security import hash_password, create_access_token
from app.services.pdf_extractor import extract_pdf_pages
from app.services.chunking import create_document_chunks
from app.services.vector_store import vector_store
from app.workers.document_worker import ingest_document


def create_sample_agri_pdf() -> bytes:
    """Creates an in-memory sample 2-page agricultural PDF using PyMuPDF."""
    doc = fitz.open()
    
    # Page 1: Rice Cultivation & Soil Health
    page1 = doc.new_page()
    page1.insert_text(
        fitz.Point(50, 72),
        "KrishiGuide Agricultural Manual - Section 1: Rice and Paddy Cultivation.\n\n"
        "Rice requires deep clayey or loamy soils with high moisture retention capacity. "
        "The ideal soil pH range is between 5.5 and 7.0. Field preparation requires deep summer ploughing "
        "followed by two passes of harrowing to ensure a fine tilth. Incorporate 10 tonnes per hectare "
        "of well-rotted farmyard manure (FYM) or compost at least 15 to 20 days prior to transplanting. "
        "Maintain standing water depth of 2 to 5 centimeters during early tillering.",
        fontsize=11,
    )

    # Page 2: Pest Management & Irrigation Timing
    page2 = doc.new_page()
    page2.insert_text(
        fitz.Point(50, 72),
        "KrishiGuide Agricultural Manual - Section 2: Integrated Pest Management in Cotton.\n\n"
        "Cotton is susceptible to sucking pests such as aphids, jassids, and whiteflies during early vegetative growth. "
        "Install yellow sticky traps at 15 to 20 traps per hectare to monitor whitefly populations. "
        "For pink bollworm management, install gossyplure pheromone traps at 5 traps per acre. "
        "Spray 5% neem seed kernel extract (NSKE) at the first sign of nymph emergence to conserve natural predators.",
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def get_test_admin() -> tuple[User, str]:
    ts = int(datetime.now().timestamp() * 1000)
    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Agri Admin",
            email=f"admin_doc_{ts}@krishiguide.org",
            hashed_password=hash_password("AdminPass123!"),
            role="admin",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = create_access_token(subject=user.id, role=user.role)
        return user, token


@pytest.mark.asyncio
async def test_pdf_extraction_and_chunking():
    """Verify PyMuPDF extracts pages accurately and chunking preserves page numbers and text."""
    pdf_bytes = create_sample_agri_pdf()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    # 1. Extraction test
    pages = extract_pdf_pages(tmp_path)
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Rice requires deep clayey or loamy soils" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "Integrated Pest Management in Cotton" in pages[1]["text"]

    # 2. Chunking test
    chunks = create_document_chunks(pages, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 2
    # Check page numbers are preserved
    page_numbers = {c["page_number"] for c in chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert chunks[0]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_document_upload_and_invalid_format_rejection():
    """Verify valid PDF upload returns 201 and non-PDF upload is rejected with 400."""
    admin, token = await get_test_admin()
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    pdf_bytes = create_sample_agri_pdf()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Reject invalid file format
        bad_files = {"file": ("malicious.exe", b"binarycontent", "application/octet-stream")}
        bad_res = await ac.post("/api/documents/upload", files=bad_files, headers=headers)
        assert bad_res.status_code == 400
        assert "only pdf" in bad_res.json()["error"]["message"].lower()

        # 2. Accept valid PDF upload
        valid_files = {"file": ("icar_agri_manual.pdf", pdf_bytes, "application/pdf")}
        data = {"is_public": "true"}
        res = await ac.post("/api/documents/upload", files=valid_files, data=data, headers=headers)
        assert res.status_code == 201
        doc_info = res.json()
        assert doc_info["document_name"] == "icar_agri_manual.pdf"
        assert doc_info["processing_status"] in ["pending", "processing", "completed"]
        assert doc_info["is_public"] is True
        doc_id = doc_info["id"]

        # 3. Verify retrieval by ID
        get_res = await ac.get(f"/api/documents/{doc_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_ingest_document_worker_and_vector_indexing():
    """Verify document worker extracts text, indexes vectors in Qdrant, and stores chunks in MySQL."""
    admin, token = await get_test_admin()
    pdf_bytes = create_sample_agri_pdf()
    
    # Create document record
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    async with AsyncSessionLocal() as session:
        doc = Document(
            document_name="Test Soil & Cotton Guide.pdf",
            file_path=tmp_path,
            file_type="application/pdf",
            file_size=len(pdf_bytes),
            uploaded_by=admin.id,
            is_public=True,
            processing_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    # Run ingestion worker directly
    success = await ingest_document(doc_id)
    assert success is True

    # Verify status in database
    async with AsyncSessionLocal() as session:
        updated_doc = await session.get(Document, doc_id)
        assert updated_doc.processing_status == "completed"
        assert updated_doc.processing_error is None
        assert updated_doc.meta_info["total_pages"] == 2
        assert updated_doc.meta_info["total_chunks"] >= 2

        # Verify chunks exist in MySQL
        from sqlalchemy import select
        result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        chunks = result.scalars().all()
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.vector_reference is not None
            assert len(chunk.vector_reference) > 0
            assert chunk.page_number in [1, 2]

    # Verify vector search retrieves the chunk from Qdrant
    from app.services.embeddings import EmbeddingService
    query_vec = EmbeddingService.embed_text("How to prepare soil for rice cultivation?")
    search_hits = vector_store.search_chunks(query_vec, limit=3, allowed_doc_ids=[doc_id])
    assert len(search_hits) > 0
    assert any("rice" in hit["text"].lower() or "clayey" in hit["text"].lower() for hit in search_hits)


@pytest.mark.asyncio
async def test_failed_processing_and_retry():
    """Verify failed document status when PDF is invalid, and verify retry endpoint works."""
    admin, token = await get_test_admin()
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    # Create dummy invalid doc pointing to non-existent file
    async with AsyncSessionLocal() as session:
        doc = Document(
            document_name="broken_file.pdf",
            file_path="uploads/non_existent_file_xyz123.pdf",
            file_type="application/pdf",
            uploaded_by=admin.id,
            is_public=True,
            processing_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    # Ingest should fail cleanly without crashing
    success = await ingest_document(doc_id)
    assert success is False

    async with AsyncSessionLocal() as session:
        failed_doc = await session.get(Document, doc_id)
        assert failed_doc.processing_status == "failed"
        assert failed_doc.processing_error is not None
        assert "not found" in failed_doc.processing_error.lower()

    # Test retry endpoint
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        retry_res = await ac.post(f"/api/documents/{doc_id}/process", headers=headers)
        assert retry_res.status_code == 200
        assert retry_res.json()["processing_status"] == "processing"


@pytest.mark.asyncio
async def test_delete_document_and_vectors():
    """Verify DELETE /api/documents/{id} removes MySQL records, file, and Qdrant vectors."""
    admin, token = await get_test_admin()
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    pdf_bytes = create_sample_agri_pdf()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        upload_res = await ac.post(
            "/api/documents/upload",
            files={"file": ("to_delete.pdf", pdf_bytes, "application/pdf")},
            headers=headers,
        )
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["id"]

        # Run ingestion
        await ingest_document(doc_id)

        # Delete document
        del_res = await ac.delete(f"/api/documents/{doc_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # Verify 404 on subsequent get
        get_res = await ac.get(f"/api/documents/{doc_id}", headers=headers)
        assert get_res.status_code == 404
