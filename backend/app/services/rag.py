from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.farm_profile import FarmProfile
from app.services.vector_search import VectorSearchService
from app.services.gemini_service import gemini_service
from app.services.security_service import SecurityService
from app.core.config import settings
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
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        category: Optional[str] = None,
        crop: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the complete Retrieval-Augmented Generation (RAG) pipeline:
        1. Security validation (Prompt injection protection & input sanitization)
        2. Rate limiting check
        3. Farmer profile context retrieval
        4. Hybrid semantic + lexical retrieval with metadata filtering
        5. Sufficiency check
        6. Grounded LLM response generation with page attribution
        """
        # 1. Security & Input Validation
        clean_q = SecurityService.validate_and_sanitize_query(question)

        # 2. Rate Limiting
        client_tag = f"user_{user_id}" if user_id > 0 else "guest_farmer"
        SecurityService.check_rate_limit(client_tag)

        top_k = limit or settings.RAG_TOP_K
        threshold = similarity_threshold or settings.RAG_SIMILARITY_THRESHOLD

        # 3. Retrieve Farmer Profile Context if available
        farmer_context = None
        if user_id > 0:
            try:
                prof_stmt = select(FarmProfile).where(FarmProfile.user_id == user_id)
                prof = (await db.execute(prof_stmt)).scalars().first()
                if prof:
                    crops_str = ", ".join(prof.crop_details) if isinstance(prof.crop_details, list) else str(prof.crop_details or "")
                    irrigation_str = ", ".join(prof.irrigation_details) if isinstance(prof.irrigation_details, list) else str(prof.irrigation_details or "")
                    farmer_context = (
                        f"Location: {prof.farm_location}, District: {prof.district or 'N/A'}, "
                        f"Farm Size: {prof.farm_size} acres, Soil Type: {prof.soil_type}, "
                        f"Current Crops: {crops_str or 'Not specified'}, Irrigation: {irrigation_str or 'Not specified'}"
                    )
            except Exception as e:
                logger.debug(f"Could not load farmer profile context: {e}")

        # 4. Retrieve verified agricultural chunks using Hybrid Search
        chunks = await VectorSearchService.search_agricultural_context(
            query=clean_q,
            user_id=user_id,
            user_role=user_role,
            db=db,
            limit=top_k,
            threshold=threshold,
            category=category,
            crop=crop,
        )

        # 5. Check if context was retrieved and sufficient
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

        # 6. Generate grounded answer via Gemini API with fallback
        answer = await gemini_service.generate_response(
            question=clean_q,
            context_chunks=chunks,
            language=language,
            farmer_context=farmer_context,
        )

        # 7. Compile real source citations with document name and page number
        sources: List[Dict[str, Any]] = []
        seen_citations = set()

        for c in chunks:
            doc_name = c.get("document_name") or "Verified Agricultural Guide"
            page_no = c.get("page_number", 1)
            citation_key = (doc_name, page_no)
            if citation_key not in seen_citations:
                seen_citations.add(citation_key)
                text_content = (c.get("text") or c.get("chunk_text") or "").strip()
                snippet = text_content[:160].replace("\n", " ").strip() + "..."
                sources.append({
                    "document_id": c.get("document_id"),
                    "document_name": doc_name,
                    "page_number": page_no,
                    "similarity_score": round(float(c.get("score") or c.get("similarity_score") or 0.0), 3),
                    "snippet": snippet,
                })

        return {
            "answer": answer,
            "sources": sources,
            "language": language,
            "context_found": True,
            "chunks": chunks,
        }
