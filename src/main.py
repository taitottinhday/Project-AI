from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import get_settings
from src.services.knowledge_base import get_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    knowledge = get_knowledge_base(reload=True)
    if not knowledge.ready:
        print(f"Knowledge base degraded: {knowledge.load_errors}")
    yield
    print("Shutting down...")


app = FastAPI(
    title="VinUni Admissions Assistant",
    description="Accuracy-first grounded admissions assistant with citations and human handover",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    # Vercel creates a distinct URL for each deployment. Keep preview links
    # usable without weakening CORS to every arbitrary origin.
    allow_origin_regex=r"^https://project-[a-z0-9-]+-taitottinhdays-projects\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/ready")
async def readiness():
    knowledge = get_knowledge_base()
    try:
        age = (datetime.now(UTC).date() - date.fromisoformat(knowledge.verified_as_of or "")).days
    except ValueError:
        age = -1
    if not knowledge.ready or not 0 <= age <= settings.knowledge_max_age_days:
        raise HTTPException(503, "Kho dữ liệu chưa sẵn sàng hoặc đã đến hạn kiểm chứng lại")
    return {"status": "ready", "dataset_fingerprint": knowledge.fingerprint, "verified_as_of": knowledge.verified_as_of}
