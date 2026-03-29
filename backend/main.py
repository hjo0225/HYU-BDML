"""빅마랩 FastAPI 백엔드 메인 앱"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import research, agents, meeting, minutes

app = FastAPI(title="빅마랩 API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(research.router)
app.include_router(agents.router)
app.include_router(meeting.router)
app.include_router(minutes.router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
