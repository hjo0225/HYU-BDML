"""연구 정제와 시장조사 스트림을 노출하는 라우터."""
import json
import traceback
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from models.schemas import ResearchBrief
from services.auth_service import get_current_user
from services.research_service import run_research_stream, refine_research_simple

router = APIRouter(prefix="/api")


@router.post("/research/refine")
async def refine_endpoint(
    brief: ResearchBrief,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """브리프만 사용해 빠르게 정제본을 반환한다."""
    result = await refine_research_simple(brief)
    return result.model_dump()


@router.post("/research")
async def research_endpoint(
    brief: ResearchBrief,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """시장조사 파이프라인을 NDJSON 스트림으로 전달한다.

    각 라인은 독립적인 JSON 객체:
      {"step": "pre_refine"}
      {"step": "keywords"}
      {"step": "section", "field": "market_overview", "content": "..."}
      {"step": "done", "refined": {...}, "report": {...}}
      {"step": "error", "message": "..."}   ← 오류 시
    """
    async def generate():
        try:
            async for chunk in run_research_stream(brief):
                yield chunk
        except Exception as e:
            traceback.print_exc()
            yield json.dumps(
                {"step": "error", "message": f"{type(e).__name__}: {str(e)[:300]}"},
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
