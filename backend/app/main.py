import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger("skogsplan")
db_init_error = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_init_error
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting SkogsplanSaaS backend...")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")

    # Ensure extensions and tables exist
    import app.models  # noqa: F401 — ensure all models are imported
    from sqlalchemy import text as sa_text
    try:
        # Each extension in its own transaction to avoid aborted-transaction cascade
        for ext in ['"uuid-ossp"', 'pg_trgm']:
            try:
                async with engine.begin() as conn:
                    await conn.execute(sa_text(f'CREATE EXTENSION IF NOT EXISTS {ext}'))
                    logger.info(f"Extension {ext} OK")
            except Exception as ext_err:
                logger.warning(f"Extension {ext} failed: {ext_err}")

        # Try PostGIS separately — Railway Postgres doesn't have it
        try:
            async with engine.begin() as conn:
                await conn.execute(sa_text('CREATE EXTENSION IF NOT EXISTS postgis'))
                logger.info("Extension postgis OK")
        except Exception:
            logger.warning("PostGIS not available — geometry stored as GeoJSON text")

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created.")
    except Exception as e:
        db_init_error = str(e)
        logger.error(f"Database initialization failed: {e}")
        # Don't raise — let the app start so we can debug via /debug/db-error

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


@app.get("/debug/db", tags=["debug"])
async def debug_db():
    from sqlalchemy import text as sa_text
    info = {"startup_error": db_init_error}
    try:
        async with engine.connect() as conn:
            result = await conn.execute(sa_text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            ))
            info["tables"] = [row[0] for row in result]
            ext_result = await conn.execute(sa_text(
                "SELECT extname FROM pg_extension ORDER BY extname"
            ))
            info["extensions"] = [row[0] for row in ext_result]
    except Exception as e:
        info["query_error"] = str(e)
    return info


@app.get("/", tags=["root"])
async def root():
    return {
        "message": "SkogsplanSaaS API",
        "version": settings.VERSION,
        "docs": "/docs",
    }
