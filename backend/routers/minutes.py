"""회의록 생성 라우터"""
from fastapi import APIRouter
from models.schemas import MinutesRequest
from services.minutes_service import generate_minutes

router = APIRouter(prefix="/api")


@router.post("/minutes")
async def generate_minutes_endpoint(req: MinutesRequest):
    """Phase 5: 회의록 생성"""
    minutes = await generate_minutes(req)
    return {"minutes": minutes}
