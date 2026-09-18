from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth, branches, roles, employees


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="MADO Checklist API",
    version="1.0.0",
    description="Система контроля операционных стандартов ресторанов MADO",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(branches.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mado-checklist-backend"}
