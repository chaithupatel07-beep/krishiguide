from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.document import Document
from app.models.chat import Conversation, ChatMessage
from app.models.expert import (
    AgriculturalExpert,
    ExpertCase,
    ExpertResponse,
    ExpertCaseFollowup,
    ExpertCaseHistory,
)
from app.models.notification import Notification
from app.models.farm_profile import FarmProfile
from app.models.farm_tool import FarmExpense, CropTask
from app.models.feedback import Feedback
from app.models.audit import AuditLog
from app.core.security import get_password_hash
from app.schemas.admin_expert import (
    AdminDashboardStats,
    AdminUserUpdateRequest,
    FeedbackCreate,
    ExpertCaseRespondRequest,
    ExpertProfileUpdateRequest,
    FarmerExpertCaseCreateRequest,
    AdminExpertCreateRequest,
    AdminExpertUpdateRequest,
)
from app.core.logging import logger


class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        title: str,
        message: str,
        type: str = "system",
        link: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link,
            is_read=False,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = [Notification.user_id == user_id]
        if unread_only:
            filters.append(Notification.is_read == False)

        count_stmt = select(func.count(Notification.id)).where(and_(*filters))
        total = (await db.execute(count_stmt)).scalar() or 0

        unread_count_stmt = select(func.count(Notification.id)).where(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        )
        unread_total = (await db.execute(unread_count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(Notification)
            .where(and_(*filters))
            .order_by(desc(Notification.created_at))
            .offset(offset)
            .limit(size)
        )
        items = (await db.execute(stmt)).scalars().all()
        return {
            "total": total,
            "unread_count": unread_total,
            "page": page,
            "size": size,
            "items": items,
        }

    @staticmethod
    async def mark_as_read(db: AsyncSession, user_id: int, notification_id: int) -> bool:
        stmt = select(Notification).where(
            and_(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notif = (await db.execute(stmt)).scalars().first()
        if not notif:
            return False
        notif.is_read = True
        await db.commit()
        return True

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: int) -> int:
        stmt = (
            update(Notification)
            .where(and_(Notification.user_id == user_id, Notification.is_read == False))
            .values(is_read=True)
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0


class AdminService:
    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> AdminDashboardStats:
        u_total = (await db.execute(select(func.count(User.id)))).scalar() or 0
        u_farmers = (await db.execute(select(func.count(User.id)).where(User.role == "farmer"))).scalar() or 0
        u_experts = (await db.execute(select(func.count(User.id)).where(User.role == "expert"))).scalar() or 0
        u_admins = (await db.execute(select(func.count(User.id)).where(User.role == "admin"))).scalar() or 0

        d_total = (await db.execute(select(func.count(Document.id)))).scalar() or 0
        d_completed = (await db.execute(select(func.count(Document.id)).where(Document.processing_status == "completed"))).scalar() or 0
        d_pending = (await db.execute(select(func.count(Document.id)).where(Document.processing_status.in_(["pending", "processing"])))).scalar() or 0
        d_failed = (await db.execute(select(func.count(Document.id)).where(Document.processing_status == "failed"))).scalar() or 0

        c_total = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
        m_total = (await db.execute(select(func.count(ChatMessage.id)))).scalar() or 0
        m_reported = (await db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.is_reported == True))).scalar() or 0

        ec_total = (await db.execute(select(func.count(ExpertCase.id)))).scalar() or 0
        ec_pending = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.status == "pending"))).scalar() or 0
        ec_resolved = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.status.in_(["resolved", "closed", "answered"])))).scalar() or 0

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
    async def create_expert(db: AsyncSession, payload: AdminExpertCreateRequest) -> Dict[str, Any]:
        existing = (await db.execute(select(User).where(User.email == payload.email))).scalars().first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

        user = User(
            full_name=payload.full_name,
            email=payload.email,
            phone_number=payload.phone_number,
            hashed_password=get_password_hash(payload.password),
            role="expert",
            account_status="active",
        )
        db.add(user)
        await db.flush()

        expert = AgriculturalExpert(
            user_id=user.id,
            qualification=payload.qualification,
            specialization=payload.specialization,
            experience=payload.experience,
            state=payload.state,
            district=payload.district,
            areas_of_expertise=payload.areas_of_expertise or [payload.specialization],
            approval_status=payload.approval_status,
            availability_status="available",
        )
        db.add(expert)
        await db.commit()
        await db.refresh(expert)
        await db.refresh(user)

        return {
            "id": expert.id,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "qualification": expert.qualification,
            "specialization": expert.specialization,
            "experience": expert.experience,
            "state": expert.state,
            "district": expert.district,
            "approval_status": expert.approval_status,
            "availability_status": expert.availability_status,
            "created_at": expert.created_at,
        }

    @staticmethod
    async def list_experts(
        db: AsyncSession,
        search: Optional[str] = None,
        specialization: Optional[str] = None,
        approval_status: Optional[str] = None,
        availability_status: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = []
        if search:
            filters.append(or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                AgriculturalExpert.qualification.ilike(f"%{search}%"),
            ))
        if specialization:
            filters.append(AgriculturalExpert.specialization.ilike(f"%{specialization}%"))
        if approval_status:
            filters.append(AgriculturalExpert.approval_status == approval_status.lower())
        if availability_status:
            filters.append(AgriculturalExpert.availability_status == availability_status.lower())

        base_stmt = select(AgriculturalExpert).join(User, AgriculturalExpert.user_id == User.id)
        if filters:
            base_stmt = base_stmt.where(and_(*filters))

        count_stmt = select(func.count(AgriculturalExpert.id)).join(User, AgriculturalExpert.user_id == User.id)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = base_stmt.options(selectinload(AgriculturalExpert.user)).order_by(desc(AgriculturalExpert.created_at)).offset(offset).limit(size)
        rows = (await db.execute(stmt)).scalars().all()

        items = [
            {
                "id": exp.id,
                "user_id": exp.user_id,
                "full_name": exp.user.full_name if exp.user else "Expert",
                "email": exp.user.email if exp.user else "",
                "phone_number": exp.user.phone_number if exp.user else None,
                "qualification": exp.qualification,
                "specialization": exp.specialization,
                "experience": exp.experience,
                "state": exp.state,
                "district": exp.district,
                "areas_of_expertise": exp.areas_of_expertise,
                "profile_image": exp.profile_image,
                "approval_status": exp.approval_status,
                "availability_status": exp.availability_status,
                "created_at": exp.created_at,
                "updated_at": exp.updated_at,
            }
            for exp in rows
        ]
        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    async def update_expert(db: AsyncSession, expert_id: int, payload: AdminExpertUpdateRequest) -> Dict[str, Any]:
        stmt = select(AgriculturalExpert).options(selectinload(AgriculturalExpert.user)).where(AgriculturalExpert.id == expert_id)
        expert = (await db.execute(stmt)).scalars().first()
        if not expert:
            raise HTTPException(status_code=404, detail="Agricultural Expert not found.")

        if payload.qualification is not None:
            expert.qualification = payload.qualification
        if payload.specialization is not None:
            expert.specialization = payload.specialization
        if payload.experience is not None:
            expert.experience = payload.experience
        if payload.state is not None:
            expert.state = payload.state
        if payload.district is not None:
            expert.district = payload.district
        if payload.areas_of_expertise is not None:
            expert.areas_of_expertise = payload.areas_of_expertise
        if payload.approval_status is not None:
            expert.approval_status = payload.approval_status.lower()
        if payload.availability_status is not None:
            expert.availability_status = payload.availability_status.lower()

        expert.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(expert)

        return {
            "id": expert.id,
            "user_id": expert.user_id,
            "full_name": expert.user.full_name if expert.user else "",
            "qualification": expert.qualification,
            "specialization": expert.specialization,
            "approval_status": expert.approval_status,
            "availability_status": expert.availability_status,
        }

    @staticmethod
    async def assign_case_to_expert(db: AsyncSession, case_id: int, expert_id: int, admin_user: User) -> Dict[str, Any]:
        stmt = select(ExpertCase).options(selectinload(ExpertCase.farmer)).where(ExpertCase.id == case_id)
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail=f"Case #{case_id} not found.")

        # Expert can be user_id or agricultural_experts.id
        exp_stmt = select(User).where(and_(User.id == expert_id, User.role == "expert"))
        expert = (await db.execute(exp_stmt)).scalars().first()
        if not expert:
            # Check by AgriculturalExpert.id
            ae = (await db.execute(select(AgriculturalExpert).options(selectinload(AgriculturalExpert.user)).where(AgriculturalExpert.id == expert_id))).scalars().first()
            if ae and ae.user:
                expert = ae.user
            else:
                raise HTTPException(status_code=404, detail=f"Expert #{expert_id} not found.")

        prev_status = case.status
        case.expert_id = expert.id
        case.status = "assigned"
        case.updated_at = datetime.now(timezone.utc)

        history = ExpertCaseHistory(
            case_id=case.id,
            previous_status=prev_status,
            new_status="assigned",
            changed_by=admin_user.id,
        )
        db.add(history)

        # Notify expert
        await NotificationService.create_notification(
            db=db,
            user_id=expert.id,
            title="New Case Assigned",
            message=f"Administrator assigned you case #{case.id} regarding '{case.crop_name}' ({case.category}).",
            type="expert_assigned",
            link=f"/expert/cases/{case.id}",
        )

        # Notify farmer
        await NotificationService.create_notification(
            db=db,
            user_id=case.farmer_id,
            title="Expert Assigned to Your Case",
            message=f"Agricultural Specialist {expert.full_name} has been assigned to your case #{case.id}.",
            type="case_status",
            link=f"/farmer/cases/{case.id}",
        )

        await db.commit()
        await db.refresh(case)
        return {"case_id": case.id, "expert_id": expert.id, "expert_name": expert.full_name, "status": case.status}


class ExpertService:
    @staticmethod
    async def get_dashboard_stats(db: AsyncSession, expert_user: User) -> Dict[str, int]:
        total_assigned = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.expert_id == expert_user.id))).scalar() or 0
        pending = (await db.execute(select(func.count(ExpertCase.id)).where(ExpertCase.status == "pending"))).scalar() or 0
        in_progress = (await db.execute(select(func.count(ExpertCase.id)).where(and_(ExpertCase.expert_id == expert_user.id, ExpertCase.status == "in_progress")))).scalar() or 0
        resolved = (await db.execute(select(func.count(ExpertCase.id)).where(and_(ExpertCase.expert_id == expert_user.id, ExpertCase.status.in_(["answered", "resolved", "closed"]))))).scalar() or 0
        total_responses = (await db.execute(select(func.count(ExpertResponse.id)).where(ExpertResponse.expert_id == expert_user.id))).scalar() or 0

        return {
            "total_assigned_cases": total_assigned,
            "pending_cases": pending,
            "in_progress_cases": in_progress,
            "resolved_cases": resolved,
            "total_responses_provided": total_responses,
        }

    @staticmethod
    async def list_cases(
        db: AsyncSession,
        user: User,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to_me: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = []
        if user.role == "expert":
            if assigned_to_me:
                filters.append(ExpertCase.expert_id == user.id)
            else:
                filters.append(or_(ExpertCase.expert_id == user.id, ExpertCase.expert_id.is_(None)))

        if status_filter:
            filters.append(ExpertCase.status == status_filter.lower())
        if priority:
            filters.append(ExpertCase.priority == priority.lower())
        if search:
            filters.append(or_(
                ExpertCase.crop_name.ilike(f"%{search}%"),
                ExpertCase.category.ilike(f"%{search}%"),
                ExpertCase.question.ilike(f"%{search}%"),
            ))

        count_stmt = select(func.count(ExpertCase.id)).where(and_(*filters)) if filters else select(func.count(ExpertCase.id))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(ExpertCase)
            .options(
                selectinload(ExpertCase.farmer).selectinload(User.farm_profile),
                selectinload(ExpertCase.expert),
            )
            .where(and_(*filters)) if filters else (
                select(ExpertCase)
                .options(
                    selectinload(ExpertCase.farmer).selectinload(User.farm_profile),
                    selectinload(ExpertCase.expert),
                )
            )
        )
        stmt = stmt.order_by(desc(ExpertCase.created_at)).offset(offset).limit(size)
        rows = (await db.execute(stmt)).scalars().all()

        items = []
        for c in rows:
            loc = None
            if c.farmer and c.farmer.farm_profile:
                loc = c.farmer.farm_profile.farm_location
            items.append({
                "id": c.id,
                "farmer_id": c.farmer_id,
                "farmer_name": c.farmer.full_name if c.farmer else "Farmer",
                "farmer_email": c.farmer.email if c.farmer else "",
                "farmer_location": loc,
                "expert_id": c.expert_id,
                "expert_name": c.expert.full_name if c.expert else None,
                "message_id": c.message_id,
                "conversation_id": c.conversation_id,
                "crop_name": c.crop_name,
                "category": c.category,
                "question": c.question or c.farmer_question or "",
                "priority": c.priority,
                "status": c.status,
                "title": c.title or f"{c.crop_name} - {c.category}",
                "farmer_question": c.farmer_question or c.question,
                "ai_response_snapshot": c.ai_response_snapshot,
                "source_references": c.source_references,
                "expert_response": c.expert_response,
                "recommendations": c.recommendations,
                "resolved_at": c.resolved_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            })

        return {"total": total, "page": page, "size": size, "items": items}

    @staticmethod
    async def get_case_detail(db: AsyncSession, user: User, case_id: int) -> Dict[str, Any]:
        stmt = (
            select(ExpertCase)
            .options(
                selectinload(ExpertCase.farmer).selectinload(User.farm_profile),
                selectinload(ExpertCase.expert),
                selectinload(ExpertCase.responses).selectinload(ExpertResponse.expert),
                selectinload(ExpertCase.followups).selectinload(ExpertCaseFollowup.sender),
                selectinload(ExpertCase.history).selectinload(ExpertCaseHistory.changer),
            )
            .where(ExpertCase.id == case_id)
        )
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail=f"Case #{case_id} not found.")

        # Permission check: Farmers can only see their own cases
        if user.role == "farmer" and case.farmer_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied. You can only view your own cases.")

        fp = case.farmer.farm_profile if case.farmer else None

        responses = [
            {
                "id": r.id,
                "case_id": r.case_id,
                "expert_id": r.expert_id,
                "expert_name": r.expert.full_name if r.expert else "Specialist",
                "response": r.response,
                "diagnosis": r.diagnosis,
                "recommended_actions": r.recommended_actions,
                "precautions": r.precautions,
                "additional_suggestions": r.additional_suggestions,
                "supporting_references": r.supporting_references,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in case.responses
        ]

        followups = [
            {
                "id": f.id,
                "case_id": f.case_id,
                "sender_id": f.sender_id,
                "sender_name": f.sender.full_name if f.sender else "User",
                "sender_role": f.sender.role if f.sender else "user",
                "message": f.message,
                "created_at": f.created_at,
            }
            for f in case.followups
        ]

        history = [
            {
                "id": h.id,
                "case_id": h.case_id,
                "previous_status": h.previous_status,
                "new_status": h.new_status,
                "changed_by": h.changed_by,
                "changer_name": h.changer.full_name if h.changer else "User",
                "created_at": h.created_at,
            }
            for h in case.history
        ]

        return {
            "id": case.id,
            "farmer_id": case.farmer_id,
            "farmer_name": case.farmer.full_name if case.farmer else "Farmer",
            "farmer_email": case.farmer.email if case.farmer else "",
            "farmer_phone": case.farmer.phone_number if case.farmer else None,
            "farmer_location": fp.farm_location if fp else "Telangana",
            "farmer_farm_size": f"{fp.farm_size} Acres" if fp and fp.farm_size else "3.5 Acres",
            "farmer_soil_type": fp.soil_type if fp else "Clay Loam",
            "farmer_crops": fp.crop_details if fp else [case.crop_name],
            "expert_id": case.expert_id,
            "expert_name": case.expert.full_name if case.expert else None,
            "crop_name": case.crop_name,
            "category": case.category,
            "question": case.question or case.farmer_question or "",
            "priority": case.priority,
            "status": case.status,
            "title": case.title or f"{case.crop_name} - {case.category}",
            "ai_response_snapshot": case.ai_response_snapshot,
            "source_references": case.source_references,
            "expert_response": case.expert_response,
            "recommendations": case.recommendations,
            "resolved_at": case.resolved_at,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "responses": responses,
            "followups": followups,
            "history": history,
        }

    @staticmethod
    async def assign_self(db: AsyncSession, expert_user: User, case_id: int) -> Dict[str, Any]:
        stmt = select(ExpertCase).where(ExpertCase.id == case_id)
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        if case.expert_id and case.expert_id != expert_user.id and expert_user.role != "admin":
            raise HTTPException(status_code=403, detail="Case is already assigned to another expert.")

        prev_status = case.status
        case.expert_id = expert_user.id
        case.status = "in_progress"
        case.updated_at = datetime.now(timezone.utc)

        history = ExpertCaseHistory(
            case_id=case.id,
            previous_status=prev_status,
            new_status="in_progress",
            changed_by=expert_user.id,
        )
        db.add(history)

        # Notify farmer
        await NotificationService.create_notification(
            db=db,
            user_id=case.farmer_id,
            title="Expert Assigned to Your Request",
            message=f"{expert_user.full_name} is now reviewing your case #{case.id}.",
            type="case_status",
            link=f"/farmer/cases/{case.id}",
        )

        await db.commit()
        await db.refresh(case)
        return {"case_id": case.id, "expert_id": expert_user.id, "status": case.status}

    @staticmethod
    async def respond_to_case(
        db: AsyncSession,
        expert_user: User,
        case_id: int,
        payload: ExpertCaseRespondRequest,
    ) -> Dict[str, Any]:
        stmt = select(ExpertCase).options(selectinload(ExpertCase.farmer)).where(ExpertCase.id == case_id)
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        if case.expert_id and case.expert_id != expert_user.id and expert_user.role != "admin":
            raise HTTPException(status_code=403, detail="Case is assigned to another specialist.")

        prev_status = case.status
        new_status = "answered" if not payload.mark_resolved else "resolved"
        now = datetime.now(timezone.utc)

        case.expert_id = expert_user.id
        case.expert_response = payload.expert_response
        case.recommendations = payload.recommendations or payload.recommended_actions
        case.status = new_status
        case.updated_at = now
        if payload.mark_resolved:
            case.resolved_at = now

        # Create structured ExpertResponse record
        resp = ExpertResponse(
            case_id=case.id,
            expert_id=expert_user.id,
            response=payload.expert_response,
            diagnosis=payload.diagnosis,
            recommended_actions=payload.recommended_actions,
            precautions=payload.precautions,
            additional_suggestions=payload.additional_suggestions,
            supporting_references=payload.supporting_references,
        )
        db.add(resp)

        # Add history record
        hist = ExpertCaseHistory(
            case_id=case.id,
            previous_status=prev_status,
            new_status=new_status,
            changed_by=expert_user.id,
        )
        db.add(hist)

        # In-app notification to farmer
        await NotificationService.create_notification(
            db=db,
            user_id=case.farmer_id,
            title="Agricultural Expert Response Received",
            message=f"Specialist {expert_user.full_name} provided verified agronomic recommendations for your case #{case.id}.",
            type="expert_response",
            link=f"/farmer/cases/{case.id}",
        )

        await db.commit()
        await db.refresh(case)
        return {
            "id": case.id,
            "case_id": case.id,
            "status": case.status,
            "expert_id": expert_user.id,
            "expert_name": expert_user.full_name,
            "expert_response": case.expert_response,
            "diagnosis": payload.diagnosis,
            "recommended_actions": payload.recommended_actions,
            "precautions": payload.precautions,
            "updated_at": case.updated_at,
        }

    @staticmethod
    async def add_followup(db: AsyncSession, user: User, case_id: int, message: str) -> Dict[str, Any]:
        stmt = select(ExpertCase).options(selectinload(ExpertCase.farmer), selectinload(ExpertCase.expert)).where(ExpertCase.id == case_id)
        case = (await db.execute(stmt)).scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        # Permission: user must be either the farmer, the assigned expert, or admin
        if user.role == "farmer" and case.farmer_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied.")
        if user.role == "expert" and case.expert_id and case.expert_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied.")

        followup = ExpertCaseFollowup(
            case_id=case.id,
            sender_id=user.id,
            message=message,
        )
        db.add(followup)

        # Send notification to the opposite party
        if user.role == "farmer" and case.expert_id:
            await NotificationService.create_notification(
                db=db,
                user_id=case.expert_id,
                title="New Farmer Follow-up",
                message=f"Farmer {user.full_name} sent a follow-up query on Case #{case.id}.",
                type="case_status",
                link=f"/expert/cases/{case.id}",
            )
        elif user.role in ["expert", "admin"]:
            await NotificationService.create_notification(
                db=db,
                user_id=case.farmer_id,
                title="Expert Follow-up Message",
                message=f"Specialist {user.full_name} replied to your Case #{case.id}.",
                type="case_status",
                link=f"/farmer/cases/{case.id}",
            )

        case.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(followup)

        return {
            "id": followup.id,
            "case_id": case.id,
            "sender_id": user.id,
            "sender_name": user.full_name,
            "sender_role": user.role,
            "message": followup.message,
            "created_at": followup.created_at,
        }

    @staticmethod
    async def get_expert_profile(db: AsyncSession, expert_user: User) -> Dict[str, Any]:
        stmt = select(AgriculturalExpert).where(AgriculturalExpert.user_id == expert_user.id)
        expert = (await db.execute(stmt)).scalars().first()
        if not expert:
            # Auto-create default profile for expert user
            expert = AgriculturalExpert(
                user_id=expert_user.id,
                qualification="B.Sc. Agriculture / Agronomy Specialist",
                specialization="Agronomy & Crop Management",
                experience=6,
                state="Telangana",
                district="Hyderabad",
                areas_of_expertise=["Rice", "Paddy", "Maize", "Cotton", "Pest Diagnosis"],
                approval_status="approved",
                availability_status="available",
            )
            db.add(expert)
            await db.commit()
            await db.refresh(expert)

        return {
            "id": expert.id,
            "user_id": expert_user.id,
            "full_name": expert_user.full_name,
            "email": expert_user.email,
            "phone_number": expert_user.phone_number,
            "qualification": expert.qualification,
            "specialization": expert.specialization,
            "experience": expert.experience,
            "state": expert.state,
            "district": expert.district,
            "areas_of_expertise": expert.areas_of_expertise,
            "profile_image": expert.profile_image,
            "approval_status": expert.approval_status,
            "availability_status": expert.availability_status,
            "created_at": expert.created_at,
            "updated_at": expert.updated_at,
        }

    @staticmethod
    async def update_expert_profile(db: AsyncSession, expert_user: User, payload: ExpertProfileUpdateRequest) -> Dict[str, Any]:
        stmt = select(AgriculturalExpert).where(AgriculturalExpert.user_id == expert_user.id)
        expert = (await db.execute(stmt)).scalars().first()
        if not expert:
            expert = AgriculturalExpert(
                user_id=expert_user.id,
                qualification=payload.qualification or "Agricultural Specialist",
                specialization=payload.specialization or "Agronomy",
                experience=payload.experience or 5,
                state=payload.state or "Telangana",
                district=payload.district or "Hyderabad",
                approval_status="approved",
                availability_status=payload.availability_status or "available",
            )
            db.add(expert)
        else:
            if payload.qualification is not None:
                expert.qualification = payload.qualification
            if payload.specialization is not None:
                expert.specialization = payload.specialization
            if payload.experience is not None:
                expert.experience = payload.experience
            if payload.state is not None:
                expert.state = payload.state
            if payload.district is not None:
                expert.district = payload.district
            if payload.areas_of_expertise is not None:
                expert.areas_of_expertise = payload.areas_of_expertise
            if payload.availability_status is not None:
                expert.availability_status = payload.availability_status.lower()

        expert.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(expert)
        return await ExpertService.get_expert_profile(db, expert_user)


class FarmerExpertService:
    @staticmethod
    async def create_expert_request(
        db: AsyncSession,
        farmer_user: User,
        payload: FarmerExpertCaseCreateRequest,
    ) -> Dict[str, Any]:
        title = f"{payload.crop_name} - {payload.category}"
        case = ExpertCase(
            farmer_id=farmer_user.id,
            crop_name=payload.crop_name,
            category=payload.category,
            question=payload.question,
            farmer_question=payload.question,
            title=title,
            priority=payload.priority or "medium",
            status="pending",
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            ai_response_snapshot=payload.ai_response_snapshot,
            source_references=payload.source_references,
        )
        db.add(case)
        await db.flush()

        # Add initial case history
        hist = ExpertCaseHistory(
            case_id=case.id,
            previous_status=None,
            new_status="pending",
            changed_by=farmer_user.id,
        )
        db.add(hist)

        # Notify Farmer of submission
        await NotificationService.create_notification(
            db=db,
            user_id=farmer_user.id,
            title="Expert Consultation Submitted",
            message=f"Your consultation request for {payload.crop_name} has been submitted (Case #{case.id}). An expert will review it shortly.",
            type="case_status",
            link=f"/farmer/cases/{case.id}",
        )

        # Notify active administrators
        admin_users = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
        for adm in admin_users:
            await NotificationService.create_notification(
                db=db,
                user_id=adm.id,
                title="New Expert Case Pending Assignment",
                message=f"Farmer {farmer_user.full_name} submitted Case #{case.id} ({payload.crop_name} - {payload.category}).",
                type="expert_assigned",
                link=f"/admin/cases/{case.id}",
            )

        await db.commit()
        await db.refresh(case)

        return {
            "id": case.id,
            "farmer_id": farmer_user.id,
            "crop_name": case.crop_name,
            "category": case.category,
            "question": case.question,
            "priority": case.priority,
            "status": case.status,
            "title": case.title,
            "ai_response_snapshot": case.ai_response_snapshot,
            "source_references": case.source_references,
            "created_at": case.created_at,
        }

    @staticmethod
    async def list_farmer_requests(
        db: AsyncSession,
        farmer_user: User,
        status_filter: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        filters = [ExpertCase.farmer_id == farmer_user.id]
        if status_filter:
            filters.append(ExpertCase.status == status_filter.lower())

        count_stmt = select(func.count(ExpertCase.id)).where(and_(*filters))
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (max(page, 1) - 1) * max(size, 1)
        stmt = (
            select(ExpertCase)
            .options(
                selectinload(ExpertCase.expert),
                selectinload(ExpertCase.responses),
            )
            .where(and_(*filters))
            .order_by(desc(ExpertCase.created_at))
            .offset(offset)
            .limit(size)
        )
        rows = (await db.execute(stmt)).scalars().all()

        items = [
            {
                "id": c.id,
                "farmer_id": c.farmer_id,
                "farmer_name": farmer_user.full_name,
                "expert_id": c.expert_id,
                "expert_name": c.expert.full_name if c.expert else None,
                "crop_name": c.crop_name,
                "category": c.category,
                "question": c.question or c.farmer_question or "",
                "priority": c.priority,
                "status": c.status,
                "title": c.title or f"{c.crop_name} - {c.category}",
                "ai_response_snapshot": c.ai_response_snapshot,
                "source_references": c.source_references,
                "expert_response": c.expert_response,
                "resolved_at": c.resolved_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in rows
        ]
        return {"total": total, "page": page, "size": size, "items": items}
