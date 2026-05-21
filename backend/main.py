"""Ditto 애플리케이션 진입점.

라우터를 등록하고 CORS 정책을 구성한다.
로컬 개발에서는 `.env`를 먼저 로드하고, Cloud Run에서는 시스템 환경변수가 우선한다.
"""
import os

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import agents, auth, conversations, demo, evaluation, fgi, projects, usage
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB 초기화 (Alembic 마이그레이션 또는 create_all)."""
    await init_db()
    yield


app = FastAPI(title="Ditto API", version="1.0.0", lifespan=lifespan)

local_dev_origins = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}

raw_origins = os.getenv("CORS_ORIGINS", "")
env_origins = {o.strip() for o in raw_origins.split(",") if o.strip()}
allowed_origins = sorted(local_dev_origins | env_origins)

# dev 환경에서는 포트가 자주 충돌해 3002/3003 으로 떠밀리므로 localhost
# 모든 포트를 정규식으로 허용. ENVIRONMENT=production 일 때는 적용 안 됨.
_is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
cors_kwargs: dict = {
    "allow_origins": allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if not _is_prod:
    cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1):\d+"

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(auth.router)
app.include_router(usage.router)
app.include_router(projects.router)
app.include_router(agents.router)
app.include_router(conversations.router)
app.include_router(evaluation.router)
app.include_router(fgi.router)
app.include_router(demo.router)


@app.get("/api/health")
async def health_check():
    """서버 생존 여부를 확인하는 헬스체크."""
    return {"status": "ok", "version": "1.0.0", "service": "ditto"}
