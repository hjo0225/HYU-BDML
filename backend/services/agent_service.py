"""에이전트 추천 서비스 — OpenAI Agents SDK"""
from pydantic import BaseModel
from agents import Agent, Runner
from models.schemas import AgentRequest, AgentSchema
from prompts.agent_recommend import AGENT_RECOMMEND_PROMPT

# Agents SDK 환경 로드
import services.openai_client  # noqa: F401


# 구조화 출력 타입
class AgentOutput(BaseModel):
    id: str
    type: str
    name: str
    emoji: str
    description: str
    tags: list[str]
    system_prompt: str
    color: str


class AgentListOutput(BaseModel):
    agents: list[AgentOutput]


# 에이전트 추천 에이전트
recommender_agent = Agent(
    name="에이전트 설계자",
    instructions=AGENT_RECOMMEND_PROMPT,
    model="gpt-4o",
    output_type=AgentListOutput,
)


async def recommend_agents(req: AgentRequest) -> list[AgentSchema]:
    """연구 정보 + 시장조사를 기반으로 에이전트 5명 추천"""

    user_message = (
        f"[고도화된 연구 정보]\n"
        f"- 배경: {req.refined.refined_background}\n"
        f"- 목적: {req.refined.refined_objective}\n"
        f"- 활용방안: {req.refined.refined_usage_plan}\n\n"
        f"[시장조사 보고서]\n"
        f"- 시장 개요: {req.report.market_overview}\n"
        f"- 경쟁 환경: {req.report.competitive_landscape}\n"
        f"- 타깃 고객 분석: {req.report.target_analysis}\n"
        f"- 트렌드: {req.report.trends}\n"
        f"- 시사점: {req.report.implications}\n"
    )

    result = await Runner.run(recommender_agent, user_message)
    output: AgentListOutput = result.final_output

    return [AgentSchema(**agent.model_dump()) for agent in output.agents]
