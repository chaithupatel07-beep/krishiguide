from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.chat import Conversation, ChatMessage, MessageSource
from app.models.expert import ExpertCase
from app.models.audit import AuditLog
from app.services.rag import RAGPipeline
from app.core.logging import logger


class ChatService:
    @staticmethod
    async def get_or_create_conversation(
        db: AsyncSession,
        user_id: int,
        conversation_id: Optional[int],
        initial_question: str,
        language: str = "English",
    ) -> Conversation:
        """Retrieves an existing conversation owned by the user, or creates a new one."""
        if conversation_id is not None:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            result = await db.execute(stmt)
            conversation = result.scalars().first()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation #{conversation_id} not found or access denied.",
                )
            return conversation

        # Generate concise conversation title from initial question
        clean_title = initial_question.strip().replace("\n", " ")
        if len(clean_title) > 60:
            clean_title = clean_title[:57] + "..."

        conversation = Conversation(
            user_id=user_id,
            title=clean_title or "Agricultural Consultation",
            language=language,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    @staticmethod
    async def process_chat_query(
        db: AsyncSession,
        user: User,
        question: str,
        conversation_id: Optional[int] = None,
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Processes a farmer's question:
        1. Resolves/creates conversation
        2. Records farmer's user message
        3. Retrieves conversational context for follow-up questions
        4. Runs RAG pipeline
        5. Records assistant's response and citations
        6. Returns complete chat payload
        """
        clean_q = question.strip()
        if not clean_q:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty.",
            )

        # 1. Resolve conversation
        conversation = await ChatService.get_or_create_conversation(
            db=db,
            user_id=user.id,
            conversation_id=conversation_id,
            initial_question=clean_q,
            language=language,
        )

        # 2. Record user message
        user_msg = ChatMessage(
            conversation_id=conversation.id,
            sender_role="user",
            content=clean_q,
            language=language,
            is_reported=False,
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # 3. Execute RAG retrieval and generation
        rag_result = await RAGPipeline.query(
            question=clean_q,
            user_id=user.id,
            user_role=user.role,
            db=db,
            language=language,
        )

        # 4. Record assistant message
        assistant_msg = ChatMessage(
            conversation_id=conversation.id,
            sender_role="assistant",
            content=rag_result["answer"],
            language=language,
            is_reported=False,
            meta_info={
                "context_found": rag_result.get("context_found", False),
                "sources_count": len(rag_result.get("sources", [])),
            },
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # 5. Persist real citations into message_sources
        persisted_sources = []
        for src in rag_result.get("sources", []):
            sim_score = src.get("similarity_score")
            score_decimal = Decimal(str(round(sim_score, 4))) if sim_score is not None else None

            db_source = MessageSource(
                message_id=assistant_msg.id,
                document_id=src.get("document_id"),
                document_name=src["document_name"],
                page_number=src.get("page_number"),
                similarity_score=score_decimal,
                snippet=src.get("snippet"),
            )
            db.add(db_source)
            persisted_sources.append({
                "document_id": src.get("document_id"),
                "document_name": src["document_name"],
                "page_number": src.get("page_number"),
                "similarity_score": sim_score,
                "snippet": src.get("snippet"),
            })

        # Touch conversation updated_at
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "conversation_id": conversation.id,
            "message_id": assistant_msg.id,
            "answer": assistant_msg.content,
            "sources": persisted_sources,
            "context_found": rag_result.get("context_found", False),
            "language": language,
            "created_at": assistant_msg.created_at,
        }

    @staticmethod
    async def get_user_conversations(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Returns paginated conversations owned strictly by the requesting user."""
        offset = (max(page, 1) - 1) * max(size, 1)

        # Total count
        count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        total = (await db.execute(count_stmt)).scalar() or 0

        # Query items with message counts
        msg_count_subq = (
            select(
                ChatMessage.conversation_id,
                func.count(ChatMessage.id).label("msg_count"),
            )
            .group_by(ChatMessage.conversation_id)
            .subquery()
        )

        stmt = (
            select(
                Conversation,
                func.coalesce(msg_count_subq.c.msg_count, 0).label("message_count"),
            )
            .outerjoin(msg_count_subq, Conversation.id == msg_count_subq.c.conversation_id)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(size)
        )

        rows = (await db.execute(stmt)).all()
        items = [
            {
                "id": conv.id,
                "title": conv.title,
                "language": conv.language,
                "message_count": msg_count,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
            for conv, msg_count in rows
        ]

        return {
            "total": total,
            "page": page,
            "size": size,
            "items": items,
        }

    @staticmethod
    async def get_conversation_details(
        db: AsyncSession,
        user: User,
        conversation_id: int,
    ) -> Dict[str, Any]:
        """
        Retrieves complete conversation thread including all messages and citations.
        Enforces strict farmer data isolation (farmers can only view their own).
        """
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.messages).selectinload(ChatMessage.sources)
            )
            .where(Conversation.id == conversation_id)
        )
        result = await db.execute(stmt)
        conversation = result.scalars().first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation #{conversation_id} not found.",
            )

        # Role-based access check: farmer can only view their own
        if user.role == "farmer" and conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own conversations.",
            )

        messages = []
        for m in conversation.messages:
            sources = [
                {
                    "document_id": s.document_id,
                    "document_name": s.document_name,
                    "page_number": s.page_number,
                    "similarity_score": float(s.similarity_score) if s.similarity_score is not None else None,
                    "snippet": s.snippet,
                }
                for s in m.sources
            ]
            messages.append({
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_role": m.sender_role,
                "content": m.content,
                "language": m.language,
                "is_reported": m.is_reported,
                "meta_info": m.meta_info,
                "sources": sources,
                "created_at": m.created_at,
            })

        return {
            "id": conversation.id,
            "title": conversation.title,
            "language": conversation.language,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "messages": messages,
        }

    @staticmethod
    async def report_chat_message(
        db: AsyncSession,
        user: User,
        message_id: int,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Allows farmer or user to report an inaccurate AI advice message:
        1. Validates message existence and user permission
        2. Sets message is_reported = True
        3. Creates an ExpertCase for agricultural expert escalation
        4. Logs to AuditLog
        """
        stmt = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.conversation))
            .where(ChatMessage.id == message_id)
        )
        result = await db.execute(stmt)
        message = result.scalars().first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message #{message_id} not found.",
            )

        # Verify access: if user is farmer, conversation must belong to them
        if user.role == "farmer" and message.conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only report messages in your own conversations.",
            )

        if message.sender_role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only AI assistant answers can be reported for expert verification.",
            )

        message.is_reported = True

        # Find farmer's original question if prior message exists
        prev_q_stmt = (
            select(ChatMessage.content)
            .where(
                ChatMessage.conversation_id == message.conversation_id,
                ChatMessage.id < message.id,
                ChatMessage.sender_role == "user",
            )
            .order_by(desc(ChatMessage.id))
            .limit(1)
        )
        prev_q = (await db.execute(prev_q_stmt)).scalar() or "Reported AI answer verification required"

        # Create ExpertCase for agronomy team review
        case = ExpertCase(
            farmer_id=message.conversation.user_id,
            message_id=message.id,
            title=f"Reported AI Advice [Msg #{message.id}]: {reason or 'Inaccuracy reported'}",
            farmer_question=prev_q,
            ai_response_snapshot=message.content,
            status="pending",
        )
        db.add(case)

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action="REPORT_CHAT_MESSAGE",
            resource_type="chat_message",
            resource_id=str(message.id),
            details={"reason": reason, "conversation_id": message.conversation_id},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(case)

        return {
            "message_id": message.id,
            "is_reported": True,
            "case_id": case.id,
            "detail": "AI response successfully reported. An agricultural expert case has been opened for agronomic review.",
        }

    @staticmethod
    async def delete_conversation(
        db: AsyncSession,
        user: User,
        conversation_id: int,
    ) -> None:
        """Deletes a conversation and its messages. Farmers can only delete their own."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(stmt)
        conversation = result.scalars().first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation #{conversation_id} not found.",
            )

        if user.role == "farmer" and conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only delete your own conversations.",
            )

        await db.delete(conversation)
        await db.commit()
        logger.info(f"User #{user.id} deleted conversation #{conversation_id}.")

