"""시장조사 라우터"""
import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from models.schemas import ResearchBrief
from services.research_service import run_research

router = APIRouter(prefix="/api")


@router.post("/research")
async def research_endpoint(brief: ResearchBrief):
    """Phase 2: 시장조사 + 연구 정보 고도화"""
    try:
        result = await run_research(brief)
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"시장조사 오류: {type(e).__name__}: {str(e)[:300]}"},
        )
