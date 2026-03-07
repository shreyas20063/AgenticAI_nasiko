"""
Nasiko HR Automation Platform - Main Application Entry Point.
Multi-agent AI system for enterprise HR automation.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db, close_db
from api.auth import router as auth_router
from api.chat import router as chat_router
from api.recruitment import router as recruitment_router
from api.compliance import router as compliance_router
from api.admin import router as admin_router
from api.helpdesk import router as helpdesk_router
from api.onboarding_routes import router as onboarding_router
from api.interviews import router as interviews_router
from security.tenant_isolation import TenantContext
from config import get_settings
import structlog
import time

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("starting_hr_platform", env=settings.app_env)
    await init_db()
    await _seed_demo_data()
    logger.info("hr_platform_ready")
    yield
    await close_db()
    logger.info("hr_platform_shutdown")


app = FastAPI(
    title="Nasiko HR Automation Platform",
    description=(
        "Enterprise AI-powered HR platform with multi-agent architecture. "
        "Automates recruitment, onboarding, HR helpdesk, and compliance workflows."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - restrict to known frontend origins
_allowed_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  # dev frontend
    "http://127.0.0.1:3000",
]
if settings.app_env == "development":
    # Expand dev origins instead of "*" (wildcard + credentials is invalid per CORS spec)
    _allowed_origins.extend([
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5500",  # Live Server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Process-Time"] = f"{duration:.3f}s"
    # Clean up tenant context after request
    TenantContext.clear()
    return response


# Register API routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(recruitment_router)
app.include_router(compliance_router)
app.include_router(admin_router)
app.include_router(helpdesk_router)
app.include_router(onboarding_router)
app.include_router(interviews_router)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main frontend application."""
    return FileResponse("frontend/index.html")


async def _seed_demo_data():
    """Seed demo data on first startup if DB is empty."""
    from database import async_session_factory
    from sqlalchemy import select
    from models.tenant import Tenant

    async with async_session_factory() as db:
        result = await db.execute(select(Tenant).limit(1))
        if result.scalar_one_or_none():
            return  # Already seeded

        logger.info("seeding_demo_data")
        from data.seed_data import seed_all
        await seed_all(db)
        await db.commit()
        logger.info("demo_data_seeded")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_debug,
    )
