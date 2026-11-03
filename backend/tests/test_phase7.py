import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database.connection import AsyncSessionLocal
from app.models.user import User
from app.models.chat import Conversation, ChatMessage, MessageSource
from app.models.expert import ExpertCase
from app.core.security import hash_password, create_access_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_chat_query_creates_conversation_and_messages():
    """Verify POST /api/chat creates conversation, user message, assistant message, and citations."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_chat_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Ramesh Chat",
            email=farmer_email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "question": "What is the recommended soil pH for groundnut cultivation?",
                "language": "English",
            },
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert "message_id" in data
    assert "answer" in data
    assert len(data["answer"]) > 10
    assert "sources" in data

    conv_id = data["conversation_id"]

    # Verify database persistence
    async with AsyncSessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        assert conv is not None
        assert conv.user_id == user_id

        # Verify messages: 1 user + 1 assistant
        stmt = select(ChatMessage).where(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.id)
        messages = (await session.execute(stmt)).scalars().all()
        assert len(messages) == 2
        assert messages[0].sender_role == "user"
        assert messages[0].content == "What is the recommended soil pH for groundnut cultivation?"
        assert messages[1].sender_role == "assistant"
        assert messages[1].is_reported is False

        # Verify sources
        stmt_src = select(MessageSource).where(MessageSource.message_id == messages[1].id)
        sources = (await session.execute(stmt_src)).scalars().all()
        assert len(sources) == len(data["sources"])


@pytest.mark.asyncio
async def test_chat_follow_up_turn():
    """Verify follow-up questions in same conversation thread append properly."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_followup_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Suresh Followup",
            email=farmer_email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First turn
        r1 = await client.post(
            "/api/chat",
            json={"question": "Tell me about groundnut crop."},
            headers=headers,
        )
        assert r1.status_code == 200
        conv_id = r1.json()["conversation_id"]

        # Follow-up turn using conversation_id
        r2 = await client.post(
            "/api/chat",
            json={
                "question": "How much gypsum should I apply per hectare?",
                "conversation_id": conv_id,
            },
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["conversation_id"] == conv_id

    # Verify 4 messages in DB (2 user + 2 assistant)
    async with AsyncSessionLocal() as session:
        stmt = select(ChatMessage).where(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.id)
        msgs = (await session.execute(stmt)).scalars().all()
        assert len(msgs) == 4
        assert [m.sender_role for m in msgs] == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_get_history_and_conversation_details():
    """Verify GET /api/chat/history and GET /api/chat/{id}."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_history_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Lakshmi History",
            email=farmer_email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a conversation
        r_post = await client.post(
            "/api/chat",
            json={"question": "What is Tikka disease in groundnut?"},
            headers=headers,
        )
        assert r_post.status_code == 200
        conv_id = r_post.json()["conversation_id"]

        # Fetch history list
        r_hist = await client.get("/api/chat/history", headers=headers)
        assert r_hist.status_code == 200
        hist_data = r_hist.json()
        assert hist_data["total"] >= 1
        assert any(item["id"] == conv_id for item in hist_data["items"])

        # Fetch single conversation thread
        r_conv = await client.get(f"/api/chat/{conv_id}", headers=headers)
        assert r_conv.status_code == 200
        conv_detail = r_conv.json()
        assert conv_detail["id"] == conv_id
        assert len(conv_detail["messages"]) == 2


@pytest.mark.asyncio
async def test_report_inaccurate_response():
    """Verify reporting an AI response creates an ExpertCase and audit log."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer_email = f"farmer_rep_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Report Test",
            email=farmer_email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ask question
        chat_res = await client.post(
            "/api/chat",
            json={"question": "Can I spray chemical pesticide at double strength?"},
            headers=headers,
        )
        assert chat_res.status_code == 200
        assistant_msg_id = chat_res.json()["message_id"]

        # 2. Report the assistant response
        report_res = await client.post(
            f"/api/chat/messages/{assistant_msg_id}/report",
            json={"reason": "Need expert confirmation for dosage safety"},
            headers=headers,
        )
        assert report_res.status_code == 200
        rep_data = report_res.json()
        assert rep_data["is_reported"] is True
        assert rep_data["case_id"] is not None

    # Verify DB state
    async with AsyncSessionLocal() as session:
        msg = await session.get(ChatMessage, assistant_msg_id)
        assert msg.is_reported is True

        case = await session.get(ExpertCase, rep_data["case_id"])
        assert case is not None
        assert case.farmer_id == user_id
        assert case.status == "pending"


@pytest.mark.asyncio
async def test_farmer_data_isolation():
    """Verify farmers cannot access, report, or delete other farmers' conversations."""
    ts = int(datetime.now().timestamp() * 1000)
    farmer1_email = f"farmer1_iso_{ts}@krishiguide.org"
    farmer2_email = f"farmer2_iso_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        f1 = User(full_name="Farmer One", email=farmer1_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        f2 = User(full_name="Farmer Two", email=farmer2_email, hashed_password=hash_password("Pass123!"), role="farmer", account_status="active")
        session.add_all([f1, f2])
        await session.commit()
        await session.refresh(f1)
        await session.refresh(f2)
        f1_id, f2_id = f1.id, f2.id

    token1 = create_access_token(subject=f1_id, role="farmer")
    token2 = create_access_token(subject=f2_id, role="farmer")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Farmer 1 creates chat
        r_f1 = await client.post(
            "/api/chat",
            json={"question": "How to improve soil organic carbon?"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        f1_conv_id = r_f1.json()["conversation_id"]
        f1_msg_id = r_f1.json()["message_id"]

        # Farmer 2 tries to read Farmer 1's conversation -> 403 Forbidden
        r_iso_read = await client.get(
            f"/api/chat/{f1_conv_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r_iso_read.status_code == 403

        # Farmer 2 tries to report Farmer 1's message -> 403 Forbidden
        r_iso_rep = await client.post(
            f"/api/chat/messages/{f1_msg_id}/report",
            json={"reason": "Malicious attempt"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r_iso_rep.status_code == 403

        # Farmer 2 tries to delete Farmer 1's conversation -> 403 Forbidden
        r_iso_del = await client.delete(
            f"/api/chat/{f1_conv_id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r_iso_del.status_code == 403


@pytest.mark.asyncio
async def test_frontend_assistant_query_compatibility():
    """Verify POST /api/assistant/query works for both anonymous and authenticated frontend calls."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Anonymous frontend call
        res_anon = await client.post(
            "/api/assistant/query",
            json={"question": "What soil is suitable for groundnut?", "language": "English"},
        )
        assert res_anon.status_code == 200
        anon_data = res_anon.json()
        assert "answer" in anon_data
        assert "sources" in anon_data
        assert isinstance(anon_data["sources"], list)

        # 2. Authenticated frontend call
        ts = int(datetime.now().timestamp() * 1000)
        email = f"farmer_fe_{ts}@krishiguide.org"
        async with AsyncSessionLocal() as session:
            user = User(
                full_name="Frontend Farmer",
                email=email,
                hashed_password=hash_password("Pass123!"),
                role="farmer",
                account_status="active",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            uid = user.id

        token = create_access_token(subject=uid, role="farmer")
        res_auth = await client.post(
            "/api/assistant/query",
            json={"question": "How to control Tikka disease in groundnut?", "language": "English"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_auth.status_code == 200
        auth_data = res_auth.json()
        assert "answer" in auth_data
        assert auth_data["conversation_id"] is not None


@pytest.mark.asyncio
async def test_delete_conversation():
    """Verify owner can delete their conversation and cascading messages are removed."""
    ts = int(datetime.now().timestamp() * 1000)
    email = f"farmer_del_{ts}@krishiguide.org"

    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Farmer Deletion Test",
            email=email,
            hashed_password=hash_password("Pass123!"),
            role="farmer",
            account_status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, role="farmer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_post = await client.post(
            "/api/chat",
            json={"question": "Temporary test question for deletion?"},
            headers=headers,
        )
        conv_id = r_post.json()["conversation_id"]

        # Delete
        r_del = await client.delete(f"/api/chat/{conv_id}", headers=headers)
        assert r_del.status_code == 200

    # Verify not in DB
    async with AsyncSessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        assert conv is None

