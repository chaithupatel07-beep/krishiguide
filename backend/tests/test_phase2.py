import pytest
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy import select, inspect
from app.database.connection import AsyncSessionLocal, engine
from app.models import (
    User,
    FarmProfile,
    Document,
    DocumentChunk,
    Conversation,
    ChatMessage,
    MessageSource,
    FarmExpense,
    CropTask,
    ExpertCase,
    Feedback,
    AuditLog,
)


@pytest.mark.asyncio
async def test_table_existence():
    """Verify all 12 tables exist in MySQL."""
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        
    expected_tables = {
        "users",
        "farm_profiles",
        "documents",
        "document_chunks",
        "conversations",
        "chat_messages",
        "message_sources",
        "farm_expenses",
        "crop_tasks",
        "expert_cases",
        "feedback",
        "audit_logs",
    }
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' not found in database."


@pytest.mark.asyncio
async def test_crud_and_relationships():
    """Test comprehensive CRUD operations and foreign key relationships."""
    async with AsyncSessionLocal() as session:
        # 1. Create Farmer User
        unique_email = f"farmer_{int(datetime.now().timestamp() * 1000)}@krishiguide.org"
        user = User(
            full_name="Ramesh Patel",
            email=unique_email,
            phone_number="+919876543210",
            hashed_password="secure_hashed_password_example",
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        assert user.role == "farmer"

        # 2. Create Farm Profile
        profile = FarmProfile(
            user_id=user.id,
            farm_location="Warangal, Telangana",
            farm_size=Decimal("5.50"),
            soil_type="Black soil",
            crop_details={"active": ["Cotton", "Chilli"], "season": "Kharif"},
            irrigation_details={"method": "Drip irrigation", "source": "Borewell"},
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        assert profile.id is not None
        assert profile.farm_size == Decimal("5.50")
        assert profile.soil_type == "Black soil"

        # 3. Create Document and Chunks
        doc = Document(
            document_name="ICAR Cotton Management Guide.pdf",
            file_path="uploads/icar_cotton_guide.pdf",
            file_type="application/pdf",
            file_size=2048500,
            uploaded_by=user.id,
            is_public=True,
            processing_status="completed",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        assert doc.id is not None

        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            chunk_text="Cotton thrives in deep black soils with good drainage and irrigation control.",
            page_number=1,
            vector_reference="qdrant-chunk-uuid-12345",
        )
        session.add(chunk)
        await session.commit()
        await session.refresh(chunk)
        assert chunk.id is not None
        assert chunk.page_number == 1

        # 4. Create Conversation & Chat Message & Source
        conv = Conversation(
            user_id=user.id,
            title="Cotton Pest Management",
            language="English",
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        msg = ChatMessage(
            conversation_id=conv.id,
            sender_role="assistant",
            content="For pink bollworm control in cotton, install pheromone traps at 5 per acre.",
            language="English",
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

        source = MessageSource(
            message_id=msg.id,
            document_id=doc.id,
            chunk_id=chunk.id,
            document_name=doc.document_name,
            page_number=1,
            similarity_score=Decimal("0.8950"),
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)
        assert source.id is not None

        # 5. Create Farm Expense
        expense = FarmExpense(
            user_id=user.id,
            category="Seeds",
            amount=Decimal("3500.00"),
            crop_name="Cotton",
            description="Purchased Bt Cotton hybrid seeds",
            expense_date=date.today(),
        )
        session.add(expense)
        await session.commit()
        await session.refresh(expense)
        assert expense.id is not None
        assert expense.amount == Decimal("3500.00")

        # 6. Create Crop Task
        task = CropTask(
            user_id=user.id,
            task_title="Apply neem oil spray",
            crop_name="Cotton",
            description="Scout field and spray NSKE 5% for sucking pests",
            scheduled_date=date.today(),
            is_completed=False,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        assert task.id is not None
        assert task.is_completed is False

        # 7. Create Expert Case
        case = ExpertCase(
            farmer_id=user.id,
            message_id=msg.id,
            title="Severe leaf curl observation",
            farmer_question="Whiteflies are spreading leaf curl. What is the recommended treatment?",
            ai_response_snapshot=msg.content,
            status="pending",
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        assert case.id is not None
        assert case.status == "pending"

        # 8. Create Feedback
        fb = Feedback(
            user_id=user.id,
            message_id=msg.id,
            feedback_type="ai_accuracy",
            rating=5,
            comments="Very clear and practical advice.",
        )
        session.add(fb)
        await session.commit()
        await session.refresh(fb)
        assert fb.id is not None
        assert fb.rating == 5

        # 9. Create Audit Log
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            resource_type="auth",
            resource_id=str(user.id),
            details={"ip": "127.0.0.1", "device": "Mobile Browser"},
        )
        session.add(audit)
        await session.commit()
        await session.refresh(audit)
        assert audit.id is not None
        assert audit.action == "USER_LOGIN"

        # 10. Test Updates
        task.is_completed = True
        case.status = "in_review"
        profile.farm_size = Decimal("6.00")
        await session.commit()

        # Re-fetch and verify updates
        updated_task = await session.get(CropTask, task.id)
        assert updated_task.is_completed is True

        updated_case = await session.get(ExpertCase, case.id)
        assert updated_case.status == "in_review"

        updated_profile = await session.get(FarmProfile, profile.id)
        assert updated_profile.farm_size == Decimal("6.00")

        # 11. Test Cascading Deletion
        # Deleting the conversation should automatically delete its chat messages and sources
        conv_id = conv.id
        msg_id = msg.id
        await session.delete(conv)
        await session.commit()

        # Verify message and source are gone
        deleted_msg = await session.get(ChatMessage, msg_id)
        assert deleted_msg is None

        result_source = await session.execute(
            select(MessageSource).where(MessageSource.message_id == msg_id)
        )
        assert result_source.scalars().first() is None


@pytest.mark.asyncio
async def test_migration_version():
    """Verify that the alembic_version table has the applied head revision."""
    async with engine.connect() as conn:
        from sqlalchemy import text
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar_one_or_none()
        assert version is not None
        assert len(version) > 0

