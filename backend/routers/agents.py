"""에이전트 추천 라우터"""
import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from models.schemas import AgentRequest, SynthesizePromptRequest
from services.auth_service import get_current_user
from services.agent_service import (
    recommend_agents,
    build_system_prompt_from_persona,
)

router = APIRouter(prefix="/api")


@router.post("/agents")
async def recommend_agents_endpoint(
    req: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 3: 연구 정보 기반 에이전트 추천"""
    try:
        agents = await recommend_agents(req)
        return [agent.model_dump() for agent in agents]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
