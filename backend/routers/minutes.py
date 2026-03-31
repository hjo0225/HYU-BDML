"""회의록 생성 라우터"""
import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from models.schemas import MinutesRequest
from services.minutes_service import generate_minutes

router = APIRouter(prefix="/api")


@router.post("/minutes")
async def generate_minutes_endpoint(req: MinutesRequest):
    """Phase 5: 회의록 생성"""
    try:
        minutes = await generate_minutes(req)
        return {"minutes": minutes}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"회의록 생성 오류: {type(e).__name__}: {str(e)[:300]}"},
        )
