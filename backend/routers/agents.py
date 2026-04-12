"""에이전트 추천 라우터"""
import json
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from models.schemas import AgentRequest, SynthesizePromptRequest
from services.auth_service import get_current_user
from services.agent_service import (
    recommend_agents,
    build_system_prompt_from_persona,
)
from services.persona_builder import build_personas_stream

router = APIRouter(prefix="/api")


@router.post("/agents")
async def recommend_agents_endpoint(
    req: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 3 (레거시): LLM 기반 에이전트 추천 — 하위 호환용."""
    try:
        agents = await recommend_agents(req)
        return [agent.model_dump() for agent in agents]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/stream")
async def recommend_agents_stream(
    req: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 3 (RAG): 실제 패널 데이터 기반 에이전트 선정 — SSE 스트리밍."""

    async def event_stream():
        try:
            async for event in build_personas_stream(
                target_customer=req.brief.target_customer,
                n_agents=5,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            traceback.print_exc()
            error_event = {
                "type": "build_progress",
                "step": "error",
                "current": 0,
                "total": 5,
                "panel_id": None,
                "message": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agents/synthesize-prompt")
async def synthesize_prompt(
    req: SynthesizePromptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        system_prompt = build_system_prompt_from_persona(
            req.name, req.type, req.persona_profile
        )
        return {"system_prompt": system_prompt}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
