import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger("skogsplan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting SkogsplanSaaS backend...")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")
    yield
    logger.info("Shutting down SkogsplanSaaS backend...")
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API for Swedish forest management planning (skogsbruksplanering)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.properties import router as properties_router
from app.api.routes.stands import router as stands_router
from app.api.routes.plans import router as plans_router
from app.api.routes.geodata import router as geodata_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.field_data import router as field_data_router
from app.api.routes.weather import router as weather_router
from app.api.routes.satellite import router as satellite_router

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(properties_router, prefix=settings.API_V1_PREFIX)
app.include_router(stands_router, prefix=settings.API_V1_PREFIX)
app.include_router(plans_router, prefix=settings.API_V1_PREFIX)
app.include_router(geodata_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(field_data_router, prefix=settings.API_V1_PREFIX)
app.include_router(weather_router, prefix=settings.API_V1_PREFIX)
app.include_router(satellite_router, prefix=settings.API_V1_PREFIX)

# Serve uploaded files (photos)
import os
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/", tags=["root"])
async def root():
    return {
        "message": "SkogsplanSaaS API",
        "version": settings.VERSION,
        "docs": "/docs",
    }
