import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.connection import check_db_connection


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /api/health returns 200 and healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "KrishiGuide AI"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_database_readiness_endpoint():
    """Verify GET /api/ready connects to MySQL and returns readiness status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"]["connected"] is True
    assert data["database"]["database"] == "MySQL"
    assert "version" in data["database"]


@pytest.mark.asyncio
async def test_openapi_json_endpoint():
    """Verify GET /openapi.json returns valid OpenAPI specification."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "KrishiGuide AI"
    assert "/api/health" in schema["paths"]
    assert "/api/ready" in schema["paths"]


@pytest.mark.asyncio
async def test_docs_endpoint():
    """Verify GET /docs returns HTML documentation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_cors_headers():
    """Verify CORS middleware handles preflight/origin correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_centralized_error_handling_404():
    """Verify centralized exception handler formats 404 responses cleanly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == 404
    assert data["error"]["type"] == "HTTPException"


@pytest.mark.asyncio
async def test_direct_mysql_connection():
    """Verify direct MySQL async connection helper."""
    result = await check_db_connection()
    assert result["connected"] is True
    assert result["database"] == "MySQL"
    assert "version" in result

