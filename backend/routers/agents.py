"""에이전트 추천 라우터"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.post("/agents")
async def recommend_agents():
    """Phase 3: 에이전트 추천"""
    pass
