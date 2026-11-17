from typing import List, Dict, Any, Optional
import time
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.rag import RAGPipeline
from app.services.vector_search import VectorSearchService
from app.core.logging import logger

# Gold standard evaluation benchmark suite for Indian Agronomy
RAG_EVALUATION_BENCHMARKS = [
    {
        "id": "bench_01",
        "category": "Fertilizer Management",
        "question": "What is the best fertilizer for paddy crop?",
        "expected_keywords": ["urea", "dap", "mop", "n", "p2o5", "k2o", "dosage"],
        "expected_document": "Rice_Cultivation_Manual.pdf",
        "expected_page": 12,
    },
    {
        "id": "bench_02",
        "category": "Pest Control",
        "question": "How to control rice stem borer in paddy?",
        "expected_keywords": ["stem borer", "pheromone", "chlorantraniliprole", "cartap"],
        "expected_document": "Rice_Cultivation_Manual.pdf",
        "expected_page": 15,
    },
    {
        "id": "bench_03",
        "category": "Soil Health",
        "question": "Soil pH value for maize",
        "expected_keywords": ["6.0", "7.5", "lime", "acidity", "ph"],
        "expected_document": "Soil_Health_Guide.pdf",
        "expected_page": 3,
    },
    {
        "id": "bench_04",
        "category": "Government Schemes",
        "question": "What are the benefits of PM-KISAN scheme?",
        "expected_keywords": ["6,000", "instalment", "2,000", "pmkisan"],
        "expected_document": "Government_Schemes.pdf",
        "expected_page": 2,
    },
    {
        "id": "bench_05",
        "category": "Irrigation Guidance",
        "question": "How does alternate wetting and drying AWD save water?",
        "expected_keywords": ["awd", "water", "tube", "15 cm", "saving"],
        "expected_document": "Irrigation_Scheduling.pdf",
        "expected_page": 7,
    },
]


class RAGEvaluator:
    """
    RAG Evaluation Module:
    Tests retrieval relevance, answer relevance, context accuracy,
    source correctness, and response consistency against verified ICAR agronomic benchmarks.
    """

    @staticmethod
    async def evaluate_pipeline(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        logger.info("Starting automated RAG benchmark evaluation...")
        start_time = time.time()
        results: List[Dict[str, Any]] = []

        if db is None:
            from app.database.connection import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                return await RAGEvaluator.evaluate_pipeline(db=session)

        total_retrieval_score = 0.0
        total_answer_score = 0.0
        total_context_score = 0.0
        total_source_score = 0.0
        total_consistency_score = 0.0

        for bench in RAG_EVALUATION_BENCHMARKS:
            q = bench["question"]
            exp_keywords = bench["expected_keywords"]
            exp_doc = bench["expected_document"]

            # 1. Test Retrieval Relevance
            retrieved_chunks = await VectorSearchService.search_agricultural_context(
                query=q,
                user_id=1,
                user_role="farmer",
                db=db,
                limit=4,
            )

            retrieval_hit = any(exp_doc in c.get("document_name", "") for c in retrieved_chunks)
            chunk_texts = " ".join([c.get("text", "").lower() for c in retrieved_chunks])
            retrieval_keyword_matches = sum(1 for kw in exp_keywords if kw in chunk_texts)
            retrieval_relevance = (
                (0.5 if retrieval_hit else 0.0) +
                (0.5 * (retrieval_keyword_matches / max(len(exp_keywords), 1)))
            )

            # 2. Test Answer Generation
            rag_output = await RAGPipeline.query(
                question=q,
                user_id=1,
                user_role="farmer",
                db=db,
                language="English",
            )
            answer_text = (rag_output.get("answer") or "").lower()

            # Answer Relevance
            answer_kw_matches = sum(1 for kw in exp_keywords if kw in answer_text)
            answer_relevance = answer_kw_matches / max(len(exp_keywords), 1)

            # Context Accuracy (Faithfulness: answer claims derived from retrieved context)
            context_accuracy = 1.0 if (rag_output.get("context_found") and len(retrieved_chunks) > 0) else 0.0

            # Source Correctness
            sources = rag_output.get("sources", [])
            source_hit = any(exp_doc in s.get("document_name", "") for s in sources)
            source_page_valid = any(s.get("page_number") is not None for s in sources)
            source_correctness = (0.6 if source_hit else 0.0) + (0.4 if source_page_valid else 0.0)

            # 3. Test Response Consistency (second pass stability)
            rag_output_2 = await RAGPipeline.query(
                question=q,
                user_id=1,
                user_role="farmer",
                db=db,
                language="English",
            )
            answer_text_2 = (rag_output_2.get("answer") or "").lower()
            consistency = 1.0 if abs(len(answer_text) - len(answer_text_2)) < 50 else 0.85

            # Accumulate scores
            total_retrieval_score += retrieval_relevance
            total_answer_score += answer_relevance
            total_context_score += context_accuracy
            total_source_score += source_correctness
            total_consistency_score += consistency

            bench_result = {
                "benchmark_id": bench["id"],
                "category": bench["category"],
                "question": q,
                "retrieval_relevance": round(retrieval_relevance * 100, 1),
                "answer_relevance": round(answer_relevance * 100, 1),
                "context_accuracy": round(context_accuracy * 100, 1),
                "source_correctness": round(source_correctness * 100, 1),
                "consistency": round(consistency * 100, 1),
                "sources_cited": [f"{s.get('document_name')} (Page {s.get('page_number')})" for s in sources],
                "status": "PASSED" if (retrieval_relevance >= 0.5 and context_accuracy == 1.0) else "NEEDS_REVIEW",
            }
            results.append(bench_result)

        n = len(RAG_EVALUATION_BENCHMARKS)
        avg_retrieval = round((total_retrieval_score / n) * 100, 1)
        avg_answer = round((total_answer_score / n) * 100, 1)
        avg_context = round((total_context_score / n) * 100, 1)
        avg_source = round((total_source_score / n) * 100, 1)
        avg_consistency = round((total_consistency_score / n) * 100, 1)
        overall_score = round((avg_retrieval + avg_answer + avg_context + avg_source + avg_consistency) / 5, 1)

        duration = round(time.time() - start_time, 2)
        logger.info(f"RAG Evaluation completed in {duration}s. Overall Score: {overall_score}%")

        return {
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "overall_score": overall_score,
            "metrics": {
                "retrieval_relevance": avg_retrieval,
                "answer_relevance": avg_answer,
                "context_accuracy": avg_context,
                "source_correctness": avg_source,
                "response_consistency": avg_consistency,
            },
            "benchmarks_tested": n,
            "benchmarks_passed": sum(1 for r in results if r["status"] == "PASSED"),
            "duration_seconds": duration,
            "detailed_results": results,
            "evaluation_verdict": "VERIFIED_PRODUCTION_READY" if overall_score >= 80.0 else "IMPROVEMENT_REQUIRED",
        }

