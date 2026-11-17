from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import logger
from app.database.connection import check_db_connection, close_db
from app.api.auth import router as auth_router
from app.api.rbac_test import router as rbac_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.farm import router as farm_router
from app.api.admin import router as admin_router
from app.api.expert import router as expert_router
from app.api.farmer_expert import router as farmer_expert_router
from app.api.notifications import router as notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup, pgvector check, table setup, and graceful shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    db_status = await check_db_connection()
    if db_status.get("connected"):
        logger.info(f"Connected to database successfully ({db_status.get('database')})")
        try:
            from app.database.base import Base
            import app.models  # noqa
            from app.database.connection import engine, AsyncSessionLocal
            from app.services.seed_service import (
                seed_verified_agricultural_documents,
                seed_expert_and_demo_cases,
            )
            from sqlalchemy import text

            async with engine.begin() as conn:
                if conn.dialect.name == "postgresql":
                    try:
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                        logger.info("PostgreSQL pgvector extension active.")
                    except Exception as ve:
                        logger.info(f"PostgreSQL pgvector extension check: {ve}")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("SQL database schema verified/created.")

            async with AsyncSessionLocal() as session:
                await seed_verified_agricultural_documents(session)
                await seed_expert_and_demo_cases(session)
        except Exception as e:
            logger.warning(f"Database auto-setup step notice: {e}")
    else:
        logger.warning(f"Database connection warning at startup: {db_status.get('error')}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for AI Smart Farming Assistant - Intelligent Agronomic Advisory & Farm Management",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [str(settings.CORS_ORIGINS)],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$|^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing and structured logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - status={response.status_code} - duration={duration:.4f}s"
    )
    return response


# Centralized Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "HTTPException",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
        content={
            "success": False,
            "error": {
                "code": 422,
                "message": "Validation error in request parameters",
                "details": exc.errors(),
                "type": "RequestValidationError",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": "A database error occurred while processing your request.",
                "type": "DatabaseError",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": "An unexpected internal server error occurred.",
                "type": "InternalServerError",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


from app.services.agronomy_service import AgronomyService
from app.services.rag import RAGPipeline
from app.services.vector_search import VectorSearchService

# Direct Root API Aliases for Frontend & System Integrations
@app.post("/api/pest/diagnose", tags=["Pest & Disease Control"])
async def direct_pest_diagnose(data: dict, db=Depends(check_db_connection)):
    from app.database.connection import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        return await AgronomyService.diagnose_pest_disease(
            crop=data.get("crop") or "Rice",
            affected_part=data.get("affected_part") or data.get("affectedPart") or "Leaves",
            symptoms=data.get("symptoms") or data.get("observed_symptoms") or "",
            variety=data.get("variety") or data.get("crop_variety"),
            growth_stage=data.get("growth_stage") or data.get("growthStage"),
            location=data.get("location") or data.get("farm_location"),
            language=data.get("language") or "English",
            db=session,
        )

@app.post("/api/fertilizer/calculate", tags=["Fertilizer Guidance"])
async def direct_fertilizer_calculate(data: dict):
    return AgronomyService.calculate_fertilizer_plan(
        crop=data.get("crop") or data.get("target_crop") or "Rice",
        growth_stage=data.get("growth_stage") or data.get("growthStage") or "Basal / Sowing",
        soil_type=data.get("soil_type") or data.get("soilType") or "Clay loam",
        soil_ph=float(data.get("soil_ph") or data.get("soilPh") or 6.8),
        soil_test_npk=data.get("soil_test_npk") or data.get("soilTestNPK"),
        cultivation_area=float(data.get("cultivation_area") or data.get("land_area") or data.get("area") or 1.0),
        area_unit=data.get("area_unit") or data.get("areaUnit") or "acre",
        farm_location=data.get("farm_location") or data.get("location") or "Telangana",
        variety=data.get("variety") or data.get("crop_variety"),
        irrigation_method=data.get("irrigation_method") or data.get("irrigationMethod") or "Surface / Furrow",
        previous_fertilizer=data.get("previous_fertilizer"),
        language=data.get("language") or "English",
    )

@app.post("/api/irrigation/schedule", tags=["Irrigation Advice"])
async def direct_irrigation_schedule(data: dict):
    return AgronomyService.calculate_irrigation_schedule(
        crop=data.get("crop") or "Rice",
        growth_stage=data.get("growth_stage") or data.get("growthStage") or "Vegetative Stage",
        soil_type=data.get("soil_type") or data.get("soilType") or "Loamy",
        soil_moisture=data.get("soil_moisture") or data.get("soilMoisture") or "Normal",
        farm_location=data.get("farm_location") or data.get("location") or "Telangana",
        cultivation_area=float(data.get("cultivation_area") or data.get("land_area") or data.get("area") or 1.0),
        irrigation_method=data.get("irrigation_method") or data.get("irrigationMethod") or "Drip Irrigation",
        weather_condition=data.get("weather_condition") or data.get("weatherCondition") or "Partly Cloudy",
        rainfall_info=data.get("rainfall_info") or data.get("rainfall") or "0 mm (Normal dry spell)",
        language=data.get("language") or "English",
    )

@app.post("/api/rag/retrieve", tags=["RAG & Knowledge"])
async def direct_rag_retrieve(data: dict):
    from app.database.connection import AsyncSessionLocal
    q = data.get("query") or data.get("question") or ""
    limit = int(data.get("limit") or 5)
    threshold = float(data.get("threshold") or 0.3)
    async with AsyncSessionLocal() as session:
        chunks = await VectorSearchService.search_agricultural_context(
            query=q,
            user_id=0,
            user_role="farmer",
            db=session,
            limit=limit,
            threshold=threshold,
        )
        return {
            "success": True,
            "query": q,
            "count": len(chunks),
            "chunks": chunks,
        }

# Include API Routers
app.include_router(auth_router, prefix="/api")
app.include_router(rbac_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router)
app.include_router(farm_router)
app.include_router(admin_router)
app.include_router(expert_router)
app.include_router(farmer_expert_router)
app.include_router(notifications_router)

# Required Core Phase 1 Endpoints
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health-check endpoint returning server operational status."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/ready", tags=["Health"])
async def database_readiness():
    """Database readiness endpoint verifying asynchronous MySQL connectivity."""
    db_check = await check_db_connection()
    if not db_check.get("connected"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unready",
                "service": settings.PROJECT_NAME,
                "database": db_check,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
        "database": db_check,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint welcoming clients and directing them to docs."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "ready_url": "/api/ready",
    }

