import os
import asyncio
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

SYSTEM_INSTRUCTION = (
    "You are KrishiGuide AI, a trustworthy agricultural assistant and agronomy expert advising farmers.\n\n"
    "CRITICAL RULES:\n"
    "1. Answer strictly using the verified agricultural evidence provided in the context.\n"
    "2. DO NOT invent chemical dosages, pesticide recommendations, fertilizer quantities, or disease diagnoses not present in the context.\n"
    "3. DO NOT fabricate or hallucinate document citations.\n"
    "4. If the retrieved evidence is insufficient or does not address the question, clearly state that the available documents "
    "do not contain verified information on this topic, and recommend contacting a local Krishi Vigyan Kendra (KVK) or agricultural extension officer.\n"
    "5. Keep your tone empathetic, clear, and actionable for farmers.\n"
    "6. Answer in the requested language (English, Telugu, or Hindi)."
)


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.client = None
        if self.api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google Gemini client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

    def is_configured(self) -> bool:
        """Returns True if Gemini API key and client are active."""
        return self.client is not None

    async def generate_response(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        language: str = "English",
        model_name: str = "gemini-2.5-flash",
    ) -> str:
        """
        Sends the question and grounded agricultural context to Gemini API.
        Handles rate limits, timeouts, and provides resilient agronomic fallback.
        """
        # Format context excerpts
        context_text = "\n\n".join([
            f"--- Document: {c['document_name']} (Page {c['page_number']}) ---\n{c['text']}"
            for c in context_chunks
        ])

        user_prompt = (
            f"FARMER QUESTION: {question}\n\n"
            f"LANGUAGE PREFERENCE: {language}\n\n"
            f"VERIFIED AGRICULTURAL CONTEXT:\n{context_text}\n\n"
            f"INSTRUCTION: Answer the farmer's question based strictly on the context above in {language}. "
            f"Cite the source document and page number. If the context does not address the question, clearly state so."
        )

        # If Gemini client is active, attempt live generation with retry
        if self.client:
            for attempt in range(1, 4):
                try:
                    logger.info(f"Calling Gemini API ({model_name}) - attempt {attempt}...")
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model_name,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.2,
                            max_output_tokens=1000,
                        ),
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception as e:
                    err_msg = str(e).lower()
                    logger.warning(f"Gemini API attempt {attempt} failed: {e}")
                    if "rate" in err_msg or "429" in err_msg:
                        await asyncio.sleep(2 * attempt)
                        continue
                    elif "timeout" in err_msg or "503" in err_msg:
                        await asyncio.sleep(1 * attempt)
                        continue
                    else:
                        break

        # Grounded Fallback Synthesis if Gemini API key is missing or encounters network errors
        logger.info("Using grounded synthesis from retrieved document context.")
        return self._synthesize_grounded_fallback(question, context_chunks, language)

    def _synthesize_grounded_fallback(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        language: str = "English",
    ) -> str:
        """
        Resilient, hallucination-free answer synthesized directly from retrieved verified chunks.
        """
        if not context_chunks:
            if language == "Telugu":
                return (
                    "అందుబాటులో ఉన్న వ్యవసాయ పత్రాలలో మీ ప్రశ్నకు తగిన సమాచారం లభించలేదు. "
                    "ఖచ్చితమైన మరియు సురక్షితమైన సలహా కోసం దయచేసి సమీపంలోని కృషి విజ్ఞాన కేంద్రం (KVK) లేదా స్థానిక వ్యవసాయ అధికారిని సంప్రదించండి."
                )
            elif language == "Hindi":
                return (
                    "उपलब्ध कृषि दस्तावेजों में आपके प्रश्न के लिए पर्याप्त प्रमाणित जानकारी उपलब्ध नहीं है। "
                    "सटीक और सुरक्षित सलाह के लिए कृपया अपने स्थानीय कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से संपर्क करें।"
                )
            else:
                return (
                    "The available agricultural documentation in KrishiGuide does not contain verified guidelines for this specific query. "
                    "For accurate dosage and crop safety, we recommend consulting your local Krishi Vigyan Kendra (KVK) or agricultural extension officer."
                )

        # Compile evidence from top chunks
        excerpts = []
        for i, c in enumerate(context_chunks[:2]):
            excerpts.append(f"• According to **{c['document_name']}** (Page {c['page_number']}):\n  \"{c['text']}\"")

        header = f"Based on verified agricultural documentation for **{question}**:"
        if language == "Telugu":
            header = f"**{question}** కి సంబంధించి ప్రామాణిక వ్యవసాయ పత్రాల నుండి లభించిన సమాచారం:"
        elif language == "Hindi":
            header = f"**{question}** के संबंध में प्रमाणित कृषि दस्तावेजों से प्राप्त जानकारी:"

        return (
            f"{header}\n\n"
            + "\n\n".join(excerpts)
            + "\n\n*(Note: Grounded in KrishiGuide agricultural manual records. Always follow local agricultural guidelines before chemical application.)*"
        )


# Singleton instance
gemini_service = GeminiService()

