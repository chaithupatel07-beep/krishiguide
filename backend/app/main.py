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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and graceful shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    db_status = await check_db_connection()
    if db_status.get("connected"):
        logger.info(f"Connected to MySQL successfully. Version: {db_status.get('version')}")
    else:
        logger.warning(f"MySQL connection warning at startup: {db_status.get('error')}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for KrishiGuide AI - Smart Farming Assistant & Agronomic Advisory",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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


# Include API Routers
app.include_router(auth_router, prefix="/api")
app.include_router(rbac_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router)
app.include_router(farm_router)
app.include_router(admin_router)
app.include_router(expert_router)

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

