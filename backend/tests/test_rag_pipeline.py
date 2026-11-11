import asyncio
import pytest
from app.database.connection import AsyncSessionLocal, engine
from app.database.base import Base
import app.models  # noqa
from app.services.seed_service import seed_verified_agricultural_documents
from app.services.rag import RAGPipeline
from app.services.vector_search import VectorSearchService


@pytest.mark.asyncio
async def test_database_init_and_seeding():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        seeded_count = await seed_verified_agricultural_documents(session)
        assert seeded_count >= 0, "Seeding executed without errors"


@pytest.mark.asyncio
async def test_rag_paddy_query():
    async with AsyncSessionLocal() as session:
        # Query matching the reference dashboard
        result = await RAGPipeline.query(
            question="What is the best fertilizer for paddy crop?",
            user_id=1,
            user_role="farmer",
            db=session,
            language="English",
        )

        assert result["context_found"] is True
        assert len(result["sources"]) > 0
        assert "paddy" in result["answer"].lower() or "rice" in result["answer"].lower()
        # Verify source citation
        source_names = [s["document_name"] for s in result["sources"]]
        assert any("Rice_Cultivation" in s or "Paddy" in s for s in source_names)


@pytest.mark.asyncio
async def test_rag_maize_soil_query():
    async with AsyncSessionLocal() as session:
        result = await RAGPipeline.query(
            question="Soil pH value for maize",
            user_id=1,
            user_role="farmer",
            db=session,
            language="English",
        )

        assert result["context_found"] is True
        assert len(result["sources"]) > 0
        source_names = [s["document_name"] for s in result["sources"]]
        assert any("Soil_Health" in s for s in source_names)


if __name__ == "__main__":
    async def run_all():
        print("Testing DB initialization...")
        await test_database_init_and_seeding()
        print("Testing Paddy fertilizer RAG query...")
        await test_rag_paddy_query()
        print("Testing Maize soil RAG query...")
        await test_rag_maize_soil_query()
        print("\nALL RAG PIPELINE TESTS PASSED SUCCESSFULLY!")

    asyncio.run(run_all())
