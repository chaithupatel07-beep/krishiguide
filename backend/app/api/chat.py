from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user import User
from app.api.deps import get_current_user, get_optional_current_user
from app.schemas.chat import (
    ChatQueryRequest,
    ChatResponse,
    PaginatedConversationsResponse,
    ConversationDetailResponse,
    ReportMessageRequest,
    ReportMessageResponse,
    FrontendQueryRequest,
    FrontendQueryResponse,
)
from app.services.chat_service import ChatService
from app.services.rag import RAGPipeline

router = APIRouter(tags=["AI Chat & Conversations"])


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit agricultural question to AI Smart Farming Assistant RAG assistant",
)
async def submit_chat_message(
    payload: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a farmer question to the RAG pipeline.
    - Creates or appends to user's conversation thread
    - Searches verified agricultural documents in Qdrant with permission filtering
    - Answers using grounded Gemini AI synthesis
    - Persists query, answer, and real document source references
    """
    return await ChatService.process_chat_query(
        db=db,
        user=current_user,
        question=payload.question,
        conversation_id=payload.conversation_id,
        language=payload.language or "English",
    )


@router.get(
    "/api/chat/history",
    response_model=PaginatedConversationsResponse,
    summary="Get authenticated farmer's chat conversation history",
)
async def get_chat_history(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves paginated list of conversations owned by the authenticated farmer."""
    return await ChatService.get_user_conversations(
        db=db,
        user_id=current_user.id,
        page=page,
        size=size,
    )


@router.get(
    "/api/chat/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get full conversation messages and document citations",
)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves full message history with citations for a specific conversation.
    Enforces strict farmer data isolation.
    """
    return await ChatService.get_conversation_details(
        db=db,
        user=current_user,
        conversation_id=conversation_id,
    )


@router.post(
    "/api/chat/messages/{message_id}/report",
    response_model=ReportMessageResponse,
    summary="Report inaccurate or unverified AI answer",
)
async def report_ai_response(
    message_id: int,
    payload: ReportMessageRequest = ReportMessageRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Marks an AI assistant response as reported and creates an ExpertCase
    for agricultural specialist review.
    """
    return await ChatService.report_chat_message(
        db=db,
        user=current_user,
        message_id=message_id,
        reason=payload.reason,
    )


@router.delete(
    "/api/chat/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation and message thread",
)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes conversation thread. Farmers can only delete their own conversations."""
    await ChatService.delete_conversation(
        db=db,
        user=current_user,
        conversation_id=conversation_id,
    )
    return {"detail": f"Conversation #{conversation_id} deleted successfully."}


@router.post(
    "/api/assistant/query",
    response_model=FrontendQueryResponse,
    summary="Direct React frontend compatibility query endpoint",
)
async def frontend_assistant_query(
    payload: FrontendQueryRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compatibility alias for existing React frontend (`POST /api/assistant/query`).
    Accepts requests from authenticated users (with JWT) or guest farmers (anonymous).
    Returns `{ answer: str, sources: list, conversation_id: int }` perfectly matching frontend state.
    """
    if current_user:
        result = await ChatService.process_chat_query(
            db=db,
            user=current_user,
            question=payload.question,
            conversation_id=payload.conversation_id,
            language=payload.language or "English",
        )
        # Format sources as clean readable strings/objects for frontend
        formatted_sources = [
            f"{s['document_name']} (Page {s['page_number']})" if s.get("page_number") else s["document_name"]
            for s in result.get("sources", [])
        ]
        return {
            "answer": result["answer"],
            "sources": formatted_sources,
            "conversation_id": result["conversation_id"],
        }
    else:
        # Anonymous guest query - search public documents
        rag_res = await RAGPipeline.query(
            question=payload.question,
            user_id=0,
            user_role="farmer",
            db=db,
            language=payload.language or "English",
        )
        formatted_sources = [
            f"{s['document_name']} (Page {s['page_number']})" if s.get("page_number") else s["document_name"]
            for s in rag_res.get("sources", [])
        ]
        return {
            "answer": rag_res["answer"],
            "sources": formatted_sources,
            "conversation_id": None,
        }

