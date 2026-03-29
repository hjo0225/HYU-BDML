"""회의 시뮬레이션 라우터"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.post("/meeting")
async def run_meeting():
    """Phase 4: 회의 시뮬레이션 (SSE)"""
    pass
