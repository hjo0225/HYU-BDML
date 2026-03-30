"""에이전트 추천 서비스 — OpenAI Agents SDK"""
from pydantic import BaseModel
from agents import Agent, Runner
from models.schemas import (
    AgentRequest,
    AgentSchema,
    PersonaProfile,
    ResearchBrief,
    MarketReport,
)
from prompts.agent_recommend import AGENT_RECOMMEND_PROMPT

# Agents SDK 환경 로드
import services.openai_client  # noqa: F401


# 구조화 출력 타입
class PersonaProfileOutput(BaseModel):
    age: int
    gender: str
    occupation: str
    personality: str
    consumption_style: str
    experience: str
    pain_points: str
    communication_style: str


class AgentOutput(BaseModel):
    id: str
    type: str
    name: str
    emoji: str
    description: str
    tags: list[str]
    system_prompt: str = ""
    color: str
    persona_profile: PersonaProfileOutput | None = None


class AgentListOutput(BaseModel):
    agents: list[AgentOutput]


# 에이전트 추천 에이전트
recommender_agent = Agent(
    name="에이전트 설계자",
    instructions=AGENT_RECOMMEND_PROMPT,
    model="gpt-4o",
    output_type=AgentListOutput,
)


def build_system_prompt_from_persona(name: str, type: str, profile: PersonaProfile) -> str:
    """페르소나 프로필을 기반으로 시스템 프롬프트를 생성한다."""
    gender_map = {
        "male": "남성",
        "female": "여성",
        "other": "",
    }
    gender_kr = gender_map.get(profile.gender, "")

    if type == "customer":
        intro_parts = [f"당신은 {name}입니다.", f"{profile.age}세"]
        if gender_kr:
            intro_parts.append(gender_kr)
        intro_parts.append(f"{profile.occupation}입니다.")
        intro = " ".join(intro_parts)
    elif type == "expert":
        intro = f"당신은 {name}입니다. {profile.occupation} 분야의 전문가입니다."
    else:
        intro = f"당신은 {name}입니다."

    sections = [
        ("성격 및 성향", profile.personality),
        ("소비 스타일", profile.consumption_style),
        ("관련 경험", profile.experience),
        ("불만/니즈", profile.pain_points),
        ("말투와 표현 방식", profile.communication_style),
    ]

    lines = [intro]
    for label, value in sections:
        text = value.strip()
        if text:
            lines.append(f"{label}: {text}")

    return "\n".join(lines)


def check_agent_fitness(
    agents: list[AgentSchema],
    brief: ResearchBrief,
    report: MarketReport,
) -> dict:
    """에이전트 구성 적합성 검증 결과를 반환한다."""
    persona_agents = [agent for agent in agents if agent.persona_profile]
    expert_count = sum(1 for agent in agents if agent.type == "expert")

    strengths: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    score = 100

    if persona_agents:
        age_groups = {
            (agent.persona_profile.age // 10) * 10
            for agent in persona_agents
        }
        if len(age_groups) >= 3:
            strengths.append("연령대가 3개 이상으로 분산되어 타깃 세그먼트를 폭넓게 커버합니다.")
        elif len(age_groups) == 2:
            warnings.append("연령대 분산은 일부 확보됐지만 추가 세그먼트가 있으면 더 좋습니다.")
            suggestions.append("타깃과 인접한 다른 연령대 페르소나를 1명 더 추가해 비교 관점을 넓혀보세요.")
            score -= 10
        else:
            warnings.append("연령대가 한 그룹에 몰려 있어 시뮬레이션 관점이 단조롭습니다.")
            suggestions.append("다른 연령대의 고객 페르소나를 추가해 반응 차이를 확인하세요.")
            score -= 20

        genders = {agent.persona_profile.gender for agent in persona_agents}
        if len(genders) >= 2:
            strengths.append("성별 구성이 최소 두 종류 이상 포함되어 편향을 줄였습니다.")
        else:
            warnings.append("성별 구성이 제한적이라 일부 사용자 관점이 빠질 수 있습니다.")
            suggestions.append("다른 성별의 페르소나를 추가해 반응 다양성을 확보하세요.")
            score -= 10
    else:
        warnings.append("페르소나 정보가 없는 에이전트가 많아 타깃 적합성 판단 근거가 약합니다.")
        suggestions.append("각 에이전트에 구체적인 persona_profile을 채워 분석 품질을 높이세요.")
        score -= 25

    if expert_count >= 1:
        strengths.append(f"{brief.category} 카테고리를 해석할 expert 에이전트가 포함되어 있습니다.")
    else:
        warnings.append("전문가 에이전트가 없어 시장/카테고리 해석이 약할 수 있습니다.")
        suggestions.append(f"{brief.category} 분야 전문가 또는 실무자를 1명 이상 포함하세요.")
        score -= 15

    if report.target_analysis.strip():
        strengths.append("시장조사 보고서의 타깃 분석을 바탕으로 에이전트 구성을 해석할 수 있습니다.")
    else:
        warnings.append("시장조사 보고서의 타깃 분석 정보가 약해 세부 적합성 판단이 어렵습니다.")
        score -= 10

    if not strengths:
        strengths.append("기본적인 에이전트 구성은 완료되어 추가 개선의 출발점으로 사용할 수 있습니다.")

    score = max(0, min(100, score))
    summary = (
        f"{len(agents)}명의 에이전트 구성을 기준으로 타깃 고객 적합성, 전문가 포함 여부, "
        f"페르소나 다양성을 종합 평가했습니다."
    )

    return {
        "score": score,
        "summary": summary,
        "strengths": strengths,
        "warnings": warnings,
        "suggestions": suggestions,
    }


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

    agents: list[AgentSchema] = []
    for agent in output.agents:
        if agent.persona_profile:
            profile = PersonaProfile(**agent.persona_profile.model_dump())
            agent.system_prompt = build_system_prompt_from_persona(
                agent.name, agent.type, profile
            )

        agents.append(AgentSchema(**agent.model_dump()))

    return agents
