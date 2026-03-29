"""회의록 생성 라우터"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")

@router.post("/minutes")
async def generate_minutes():
    """Phase 5: 회의록 생성"""
    pass
