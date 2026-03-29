"""시장조사 라우터"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models.schemas import ResearchBrief
from services.research_service import run_research

router = APIRouter(prefix="/api")


@router.post("/research")
async def research_endpoint(brief: ResearchBrief):
    """Phase 2: 시장조사 + 연구 정보 고도화 (SSE)"""
    return StreamingResponse(
        run_research(brief),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
