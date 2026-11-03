from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.document import Document
from app.models.chat import Conversation, ChatMessage
from app.models.expert import ExpertCase
from app.models.farm_tool import FarmExpense, CropTask
from app.models.feedback import Feedback
from app.models.audit import AuditLog
from app.schemas.admin_expert import (
    AdminDashboardStats,
    AdminUserUpdateRequest,
    FeedbackCreate,
    ExpertCaseRespondRequest,
)
from app.core.logging import logger


class AdminService:
    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> AdminDashboardStats:
        """Executes real SQL aggregations across all system tables for admin monitoring."""
        # User counts
        u_total = (await db.execute(select(func.count(User.id)))).scalar() or 0
        u_farmers = (await db.execute(select(func.count(User.id)).where(User.role == "farmer"))).scalar() or 0
        u_experts = (await db.execute(select(func.count(User.id)).where(User.role == "expert"))).scalar() or 0
        u_admins = (await db.execute(select(func.count(User.id)).where(User.role == "admin"))).scalar() or 0

        # Document counts
        d_total = (await db.execute(select(func.count(Document.id)))).scalar() or 0
        d_completed = (await db.execute(select(func.count(Document.id)).where(Document.processing_status == "completed"))).scalar() or 0
        d_pending = (await db.execute(select(func.count(Document.id)).where(Document.processing_status.in_(["pending", "processing"])))).scalar() or 0
        d_failed = (await db.execute(select(func.count(Document.id)).where(Document.processing_status == "failed"))).scalar() or 0

        # Conversation & Chat message counts
        c_total = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
        m_total = (await db.execute(select(func.count(ChatMessage.id)))).scalar() or 0
        m_reported = (await db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.is_reported == True))).scalar() or 0

        # Expert case counts
        ec_total = (await db.execute(select(func.count(ExpertCase.id)))).scalar() or 0
        ec_pending = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.status == "pending"))).scalar() or 0
        ec_resolved = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.status.in_(["resolved", "closed"])))).scalar() or 0

        # Farm tool stats
        exp_res = (await db.execute(select(func.count(FarmExpense.id), func.coalesce(func.sum(FarmExpense.amount), Decimal("0.00"))))).first()
        exp_count = exp_res[0] or 0
        exp_amount = exp_res[1] or Decimal("0.00")

        t_total = (await db.execute(select(func.count(CropTask.id)))).scalar() or 0
        t_completed = (await db.execute(select(func.count(CropTask.id)).where(CropTask.is_completed == True))).scalar() or 0

        return AdminDashboardStats(
            total_users=u_total,
            farmers_count=u_farmers,
            experts_count=u_experts,
            admins_count=u_admins,
            total_documents=d_total,
            processed_documents_count=d_completed,
            pending_documents_count=d_pending,
            failed_documents_count=d_failed,
            total_conversations=c_total,
            total_messages=m_total,
            reported_messages_count=m_reported,
            total_cases=ec_total,
            pending_cases_count=ec_pending,
            resolved_cases_count=ec_resolved,
            total_expenses_recorded=exp_count,
            total_expenses_amount=exp_amount,
            total_tasks_scheduled=t_total,
            completed_tasks_count=t_completed,
        )

    @staticmethod
    async def list_users(
        db: AsyncSession,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = []
        if search:
            filters.append(or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            ))
        if role:
            filters.append(User.role == role.lower())
        if status_filter:
            filters.append(User.account_status == status_filter.lower())

        count_stmt = select(func.count(User.id)).where(and_(*filters)) if filters else select(func.count(User.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(User)
            .where(and_(*filters))
            .order_by(desc(User.created_at))
            .offset(offset)
            .limit(size)
        ) if filters else (
            select(User)
            .order_by(desc(User.created_at))
            .offset(offset)
            .limit(size)
        )

        items = (await db.execute(stmt)).scalars().all()
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    async def update_user(
        db: AsyncSession,
        admin_user: User,
        target_user_id: int,
        payload: AdminUserUpdateRequest,
    ) -> User:
        target = await db.get(User, target_user_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User #{target_user_id} not found.")

        # Protection: admin cannot demote or deactivate their own account
        if admin_user.id == target_user_id:
            if payload.role and payload.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot modify own administrator role. Another administrator must perform this action.",
                )
            if payload.account_status and payload.account_status != "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate or suspend your own administrator account.",
                )

        if payload.role:
            valid_roles = ["farmer", "expert", "admin"]
            if payload.role.lower() not in valid_roles:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role. Must be one of: {valid_roles}")
            target.role = payload.role.lower()

        if payload.account_status:
            valid_statuses = ["active", "suspended", "inactive"]
            if payload.account_status.lower() not in valid_statuses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {valid_statuses}")
            target.account_status = payload.account_status.lower()

        target.updated_at = datetime.now(timezone.utc)

        # Audit log
        audit = AuditLog(
            user_id=admin_user.id,
            action="ADMIN_UPDATE_USER",
            resource_type="user",
            resource_id=str(target.id),
            details={"new_role": payload.role, "new_status": payload.account_status},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(target)
        logger.info(f"Admin #{admin_user.id} updated user #{target.id} (role={target.role}, status={target.account_status}).")
        return target

    @staticmethod
    async def list_feedback(
        db: AsyncSession,
        is_reviewed: Optional[bool] = None,
        feedback_type: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = []
        if is_reviewed is not None:
            filters.append(Feedback.is_reviewed == is_reviewed)
        if feedback_type:
            filters.append(Feedback.feedback_type == feedback_type)

        count_stmt = select(func.count(Feedback.id)).where(and_(*filters)) if filters else select(func.count(Feedback.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(and_(*filters))
            .order_by(desc(Feedback.created_at))
            .offset(offset)
            .limit(size)
        ) if filters else (
            select(Feedback)
            .options(selectinload(Feedback.user))
            .order_by(desc(Feedback.created_at))
            .offset(offset)
            .limit(size)
        )

        rows = (await db.execute(stmt)).scalars().all()
        items = [
            {
                "id": f.id,
                "user_id": f.user_id,
                "user_name": f.user.full_name if f.user else "Anonymous",
                "user_email": f.user.email if f.user else "",
                "message_id": f.message_id,
                "feedback_type": f.feedback_type,
                "rating": f.rating,
                "comments": f.comments,
                "is_reviewed": f.is_reviewed,
                "created_at": f.created_at,
            }
            for f in rows
        ]
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    async def create_feedback(
        db: AsyncSession,
        user: User,
        payload: FeedbackCreate,
    ) -> Feedback:
        feedback = Feedback(
            user_id=user.id,
            message_id=payload.message_id,
            feedback_type=payload.feedback_type or "general",
            rating=payload.rating,
            comments=payload.comments,
            is_reviewed=False,
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        logger.info(f"User #{user.id} submitted feedback #{feedback.id} ({feedback.feedback_type}).")
        return feedback

    @staticmethod
    async def list_audit_logs(
        db: AsyncSession,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Dict[str, Any]:
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)

        count_stmt = select(func.count(AuditLog.id)).where(and_(*filters)) if filters else select(func.count(AuditLog.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(AuditLog)
            .where(and_(*filters))
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(size)
        ) if filters else (
            select(AuditLog)
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(size)
        )

        items = (await db.execute(stmt)).scalars().all()
        return {"total": total, "page": page, "size": size, "items": items}


class ExpertService:
    @staticmethod
    async def list_cases(
        db: AsyncSession,
        user: User,
        status_filter: Optional[str] = None,
        assigned_to_me: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """
        Retrieves cases accessible to an expert:
        - If admin: can view all cases
        - If expert and assigned_to_me=True: cases assigned strictly to expert
        - If expert and assigned_to_me=False: unassigned queue (expert_id IS NULL) + cases assigned to expert
        """
        filters = []
        if user.role == "expert":
            if assigned_to_me:
                filters.append(ExpertCase.expert_id == user.id)
            else:
                filters.append(or_(ExpertCase.expert_id == user.id, ExpertCase.expert_id.is_(None)))

        if status_filter:
            filters.append(ExpertCase.status == status_filter.lower())

        count_stmt = select(func.count(ExpertCase.id)).where(and_(*filters)) if filters else select(func.count(ExpertCase.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(ExpertCase)
            .options(
                selectinload(ExpertCase.farmer),
                selectinload(ExpertCase.expert),
            )
            .where(and_(*filters))
            .order_by(desc(ExpertCase.created_at))
            .offset(offset)
            .limit(size)
        ) if filters else (
            select(ExpertCase)
            .options(
                selectinload(ExpertCase.farmer),
                selectinload(ExpertCase.expert),
            )
            .order_by(desc(ExpertCase.created_at))
            .offset(offset)
            .limit(size)
        )

        rows = (await db.execute(stmt)).scalars().all()
        items = [
            {
                "id": c.id,
                "farmer_id": c.farmer_id,
                "farmer_name": c.farmer.full_name if c.farmer else "Farmer",
                "farmer_email": c.farmer.email if c.farmer else "",
                "expert_id": c.expert_id,
                "expert_name": c.expert.full_name if c.expert else None,
                "message_id": c.message_id,
                "title": c.title,
                "farmer_question": c.farmer_question,
                "ai_response_snapshot": c.ai_response_snapshot,
                "expert_response": c.expert_response,
                "status": c.status,
                "recommendations": c.recommendations,
                "resolved_at": c.resolved_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in rows
        ]

        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    async def respond_to_case(
        db: AsyncSession,
        expert_user: User,
        case_id: int,
        payload: ExpertCaseRespondRequest,
    ) -> Dict[str, Any]:
        stmt = (
            select(ExpertCase)
            .options(selectinload(ExpertCase.farmer), selectinload(ExpertCase.expert))
            .where(ExpertCase.id == case_id)
        )
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expert case #{case_id} not found.")

        # If already assigned to another expert, prevent collision unless admin
        if case.expert_id and case.expert_id != expert_user.id and expert_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This case is currently assigned to another agronomy specialist (ID #{case.expert_id}).",
            )

        # Assign to this expert
        case.expert_id = expert_user.id
        case.expert_response = payload.expert_response
        case.recommendations = payload.recommendations
        now = datetime.now(timezone.utc)

        if payload.mark_resolved:
            case.status = "resolved"
            case.resolved_at = now
        else:
            case.status = "in_review"

        case.updated_at = now

        # Create audit entry
        audit = AuditLog(
            user_id=expert_user.id,
            action="EXPERT_RESPOND_CASE",
            resource_type="expert_case",
            resource_id=str(case.id),
            details={"status": case.status, "mark_resolved": payload.mark_resolved},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(case)
        logger.info(f"Expert #{expert_user.id} responded to case #{case.id} (status={case.status}).")

        return {
            "id": case.id,
            "farmer_id": case.farmer_id,
            "farmer_name": case.farmer.full_name if case.farmer else "Farmer",
            "farmer_email": case.farmer.email if case.farmer else "",
            "expert_id": case.expert_id,
            "expert_name": expert_user.full_name,
            "message_id": case.message_id,
            "title": case.title,
            "farmer_question": case.farmer_question,
            "ai_response_snapshot": case.ai_response_snapshot,
            "expert_response": case.expert_response,
            "status": case.status,
            "recommendations": case.recommendations,
            "resolved_at": case.resolved_at,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }

    @staticmethod
    async def update_status(
        db: AsyncSession,
        expert_user: User,
        case_id: int,
        new_status: str,
    ) -> Dict[str, Any]:
        valid_statuses = ["pending", "assigned", "in_review", "resolved", "closed"]
        clean_status = new_status.lower()
        if clean_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{new_status}'. Allowed statuses: {valid_statuses}",
            )

        stmt = (
            select(ExpertCase)
            .options(selectinload(ExpertCase.farmer), selectinload(ExpertCase.expert))
            .where(ExpertCase.id == case_id)
        )
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expert case #{case_id} not found.")

        if case.expert_id and case.expert_id != expert_user.id and expert_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Case is assigned to another specialist.")

        case.status = clean_status
        now = datetime.now(timezone.utc)
        if clean_status in ["resolved", "closed"]:
            case.resolved_at = now
        elif clean_status == "assigned" and case.expert_id is None:
            case.expert_id = expert_user.id

        case.updated_at = now
        await db.commit()
        await db.refresh(case)

        return {
            "id": case.id,
            "farmer_id": case.farmer_id,
            "farmer_name": case.farmer.full_name if case.farmer else "Farmer",
            "farmer_email": case.farmer.email if case.farmer else "",
            "expert_id": case.expert_id,
            "expert_name": case.expert.full_name if case.expert else None,
            "message_id": case.message_id,
            "title": case.title,
            "farmer_question": case.farmer_question,
            "ai_response_snapshot": case.ai_response_snapshot,
            "expert_response": case.expert_response,
            "status": case.status,
            "recommendations": case.recommendations,
            "resolved_at": case.resolved_at,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }

