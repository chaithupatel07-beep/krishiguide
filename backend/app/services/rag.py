from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.services.vector_search import VectorSearchService
from app.services.gemini_service import gemini_service
from app.core.logging import logger

INSUFFICIENT_CONTEXT_MESSAGES = {
    "English": (
        "I could not find verified agricultural guidelines in the AI Smart Farming Assistant knowledge repository to answer your specific question accurately. "
        "To avoid crop damage or incorrect chemical application, please consult your local Krishi Vigyan Kendra (KVK) or an agricultural university specialist."
    ),
    "Telugu": (
        "మీ ప్రశ్నకు సమాధానం ఇవ్వడానికి ఏఐ స్మార్ట్ ఫార్మింగ్ అసిస్టెంట్ పత్రాలలో సరిపడా ప్రామాణిక సమాచారం లభించలేదు. "
        "పంట రక్షణ మరియు సరైన సలహాల కోసం దయచేసి సమీపంలోని కృషి విజ్ఞాన కేంద్రం (KVK) లేదా స్థానిక వ్యవసాయ అధికారిని సంప్రదించండి."
    ),
    "Hindi": (
        "आपके प्रश्न का सटीक उत्तर देने के लिए एआई स्मार्ट फार्मिंग असिस्टेंट रिपोजिटरी में पर्याप्त प्रमाणित दिशा-निर्देश उपलब्ध नहीं हैं। "
        "फसल सुरक्षा और सही सलाह के लिए कृपया अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या कृषि विशेषज्ञ से संपर्क करें।"
    ),
}


class RAGPipeline:
    @staticmethod
    async def query(
        question: str,
        user_id: int,
        user_role: str,
        db: AsyncSession,
        language: str = "English",
        limit: int = 4,
        similarity_threshold: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Executes the complete Retrieval-Augmented Generation (RAG) pipeline:
        1. Validates the question
        2. Retrieves permission-verified agricultural chunks from Qdrant
        3. Tests context sufficiency
        4. Queries Gemini API with grounded context
        5. Formulates source citations with real document names and page numbers
        """
        clean_q = (question or "").strip()
        if len(clean_q) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question must be at least 3 characters long.",
            )

        # 1. Retrieve relevant agricultural chunks
        chunks = await VectorSearchService.search_agricultural_context(
            query=clean_q,
            user_id=user_id,
            user_role=user_role,
            db=db,
            limit=limit,
            threshold=similarity_threshold,
        )

        # 2. Check if context was retrieved and sufficient
        if not chunks:
            logger.info(f"RAG: Insufficient context for question: '{clean_q[:50]}'")
            answer = INSUFFICIENT_CONTEXT_MESSAGES.get(language, INSUFFICIENT_CONTEXT_MESSAGES["English"])
            return {
                "answer": answer,
                "sources": [],
                "language": language,
                "context_found": False,
                "chunks": [],
            }

        # 3. Generate grounded answer via Gemini API
        answer = await gemini_service.generate_response(
            question=clean_q,
            context_chunks=chunks,
            language=language,
        )

        # 4. Compile real source citations with document name and page number
        sources: List[Dict[str, Any]] = []
        seen_citations = set()

        for c in chunks:
            citation_key = (c["document_name"], c["page_number"])
            if citation_key not in seen_citations:
                seen_citations.add(citation_key)
                snippet = c["text"][:160].replace("\n", " ").strip() + "..."
                sources.append({
                    "document_id": c["document_id"],
                    "document_name": c["document_name"],
                    "page_number": c["page_number"],
                    "similarity_score": c["similarity_score"],
                    "snippet": snippet,
                })

        return {
            "answer": answer,
            "sources": sources,
            "language": language,
            "context_found": True,
            "chunks": chunks,
        }

