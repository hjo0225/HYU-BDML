"""토큰 사용량 조회 라우터"""
from fastapi import APIRouter
from services.usage_tracker import tracker

router = APIRouter()


@router.get("/api/usage")
async def get_usage():
    """누적 토큰 사용량 조회"""
    return tracker.summary()


@router.post("/api/usage/reset")
async def reset_usage():
    """사용량 기록 초기화"""
    tracker.reset()
    return {"status": "reset"}
