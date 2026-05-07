"""회의록 생성 라우터"""
import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from models.schemas import MinutesRequest
from services.auth_service import get_current_user
from services.minutes_service import generate_minutes

router = APIRouter(prefix="/api")


@router.post("/minutes")
async def generate_minutes_endpoint(
    req: MinutesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
