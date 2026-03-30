"""에이전트 추천 라우터"""
import traceback
from fastapi import APIRouter, HTTPException
from models.schemas import AgentRequest
from services.agent_service import recommend_agents

router = APIRouter(prefix="/api")


@router.post("/agents")
async def recommend_agents_endpoint(req: AgentRequest):
    """Phase 3: 연구 정보 기반 에이전트 추천"""
    try:
        agents = await recommend_agents(req)
        return [agent.model_dump() for agent in agents]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
