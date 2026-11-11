import asyncio
import os
from pathlib import Path
import docx
from app.database.connection import AsyncSessionLocal
from app.models.document import Document, DocumentChunk
from app.workers.document_worker import ingest_document
from app.services.rag import RAGPipeline


async def test_docx_and_txt_ingestion():
    temp_dir = Path("uploads/test_docs")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create a sample DOCX file
    docx_path = temp_dir / "Groundnut_Cultivation_Guide.docx"
    doc_file = docx.Document()
    doc_file.add_heading("Groundnut Cultivation and Gypsum Application", level=1)
    doc_file.add_paragraph(
        "For groundnut crop, application of gypsum @ 400 kg/ha at 40-45 days after sowing (flowering/pegging stage) "
        "is critical for pod development and kernel filling. Gypsum provides essential calcium and sulfur. "
        "Maintain adequate soil moisture during the pegging stage."
    )
    doc_file.save(str(docx_path))

    # 2. Create a sample TXT file
    txt_path = temp_dir / "Cotton_Pink_Bollworm_Advisory.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(
            "Cotton Pink Bollworm (Pectinophora gossypiella) Advisory:\n\n"
            "Install yellow sticky traps and pheromone traps (Gossyplure) @ 5 traps per acre at 45 days after sowing. "
            "If rosette flowers exceed 5-10%, spray Profenofos 50% EC @ 2 ml/L or Emamectin Benzoate 5% SG @ 5 g/10 L water."
        )

    async with AsyncSessionLocal() as session:
        # Register docx in DB
        db_docx = Document(
            document_name="Groundnut_Cultivation_Guide.docx",
            file_path=str(docx_path),
            file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=os.path.getsize(docx_path),
            is_public=True,
            processing_status="pending",
        )
        session.add(db_docx)

        # Register txt in DB
        db_txt = Document(
            document_name="Cotton_Pink_Bollworm_Advisory.txt",
            file_path=str(txt_path),
            file_type="text/plain",
            file_size=os.path.getsize(txt_path),
            is_public=True,
            processing_status="pending",
        )
        session.add(db_txt)
        await session.commit()
        await session.refresh(db_docx)
        await session.refresh(db_txt)

        docx_id = db_docx.id
        txt_id = db_txt.id

    # Run background ingestion worker
    print(f"Ingesting DOCX (ID={docx_id})...")
    res1 = await ingest_document(docx_id)
    assert res1 is True, "DOCX ingestion succeeded"

    print(f"Ingesting TXT (ID={txt_id})...")
    res2 = await ingest_document(txt_id)
    assert res2 is True, "TXT ingestion succeeded"

    # Verify RAG queries retrieve new documents
    async with AsyncSessionLocal() as session:
        print("Testing RAG query on ingested DOCX...")
        rag_res = await RAGPipeline.query(
            question="When should gypsum be applied for groundnut crop?",
            user_id=1,
            user_role="farmer",
            db=session,
        )
        print("Answer:", rag_res["answer"])
        print("Sources:", rag_res["sources"])
        assert rag_res["context_found"] is True
        assert any("Groundnut" in s["document_name"] for s in rag_res["sources"])

        print("Testing RAG query on ingested TXT...")
        rag_res2 = await RAGPipeline.query(
            question="How to control pink bollworm in cotton?",
            user_id=1,
            user_role="farmer",
            db=session,
        )
        print("Answer:", rag_res2["answer"])
        print("Sources:", rag_res2["sources"])
        assert rag_res2["context_found"] is True
        assert any("Cotton" in s["document_name"] for s in rag_res2["sources"])

    print("\nALL INGESTION & RAG RETRIEVAL TESTS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_docx_and_txt_ingestion())
