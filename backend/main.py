"""애플리케이션 진입점.

라우터를 등록하고, 프론트엔드와 통신하기 위한 CORS 정책을 구성한다.
"""
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import research, agents, meeting, minutes, usage
from routers import auth, projects
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB 초기화 (Alembic 마이그레이션 또는 create_all)."""
    await init_db()
    yield


app = FastAPI(title="빅마랩 API", version="2.0.0", lifespan=lifespan)

local_dev_origins = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}

raw_origins = os.getenv("CORS_ORIGINS", "")
env_origins = {origin.strip() for origin in raw_origins.split(",") if origin.strip()}
allowed_origins = sorted(local_dev_origins | env_origins)

# 로컬 개발 주소는 기본 허용하고, 배포 환경 주소는 CORS_ORIGINS에서 추가로 받는다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,   # httpOnly 쿠키(refresh_token) 전송에 필요
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기능별 라우터를 `/api/*` 아래에 연결한다.
app.include_router(research.router)
app.include_router(agents.router)
app.include_router(meeting.router)
app.include_router(minutes.router)
app.include_router(usage.router)
app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/api/health")
async def health_check():
    """배포 환경에서 서버 생존 여부를 확인하는 간단한 헬스체크."""
    return {"status": "ok", "version": "2.0.0"}
