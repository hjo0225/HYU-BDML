"""에이전트 추천 서비스 — OpenAI Agents SDK"""
from pydantic import BaseModel
from agents import Agent, Runner
from models.schemas import (
    AgentRequest,
    AgentSchema,
    PersonaProfile,
    ResearchBrief,
)
from prompts.agent_recommend import AGENT_RECOMMEND_PROMPT

# Agents SDK 환경 로드
import services.openai_client  # noqa: F401
from services.usage_tracker import tracker


def _log_runner_usage(result, service_label: str):
    """Runner.run() 결과에서 토큰 사용량 추출·기록"""
    for resp in getattr(result, "raw_responses", []):
        usage = getattr(resp, "usage", None)
        if usage:
            tracker.log(
                service=service_label,
                model="gpt-4o-mini",
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            )


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
    model="gpt-4o-mini",
    output_type=AgentListOutput,
)

# 단일 소비자 에이전트 재생성용 에이전트
_single_regen_agent = Agent(
    name="소비자 에이전트 재생성",
    instructions="""
주어진 조건으로 소비자 페르소나 에이전트 1명을 생성하세요.

■ 필수 제약:
- type은 반드시 "customer"
- persona_profile.age는 반드시 요청된 연령 범위 내 정수
- occupation, experience 등 모든 필드는 age와 일관성 있게 작성
- experience: 제품/서비스 관련 구체적 에피소드 최소 80자
- system_prompt는 빈 문자열로 응답 (서버에서 자동 생성)
""".strip(),
    model="gpt-4o-mini",
    output_type=AgentOutput,
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




async def _regenerate_customer_agent(
    original: AgentOutput,
    age_range: tuple[int, int],
    req: AgentRequest,
) -> AgentOutput:
    """연령 범위를 벗어난 소비자 에이전트를 올바른 연령으로 재생성"""
    min_age, max_age = age_range
    regen_message = (
        f"[원본 연구 입력]\n"
        f"- 타깃 고객: {req.brief.target_customer}\n"
        f"- 연구 카테고리: {req.brief.category}\n"
        f"- 연구 목적: {req.brief.objective}\n\n"
        f"[연령 제약 — 필수 준수]\n"
        f"persona_profile.age는 반드시 {min_age}~{max_age} 사이 정수여야 합니다.\n\n"
        f"[유지할 필드]\n"
        f"id: {original.id}, color: {original.color}, type: customer\n\n"
        f"위 id·color·type을 그대로 사용하고 나머지 필드를 새로 생성하세요."
    )
    result = await Runner.run(_single_regen_agent, regen_message)
    _log_runner_usage(result, "agents/regen_single")
    return result.final_output


async def recommend_agents(req: AgentRequest) -> list[AgentSchema]:
    """연구 정보 + 시장조사를 기반으로 에이전트 5명 추천"""

    # 타깃 연령 범위를 명시적 제약으로 전달
    age_range = _parse_age_range(req.brief.target_customer)
    age_constraint = ""
    if age_range:
        min_age, max_age = age_range
        age_constraint = (
            f"\n\n⚠️ 연령 제약 (반드시 준수): 소비자(customer) 페르소나의 age는 "
            f"반드시 {min_age}~{max_age} 사이 정수여야 합니다. 이 범위를 벗어난 나이는 절대 허용되지 않습니다."
        )

    user_message = (
        f"[원본 연구 입력]\n"
        f"- 타깃 고객: {req.brief.target_customer}\n"
        f"- 연구 카테고리: {req.brief.category}\n"
        f"- 연구 목적: {req.brief.objective}\n\n"
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
        f"{age_constraint}"
    )

    result = await Runner.run(recommender_agent, user_message)
    _log_runner_usage(result, "agents/recommend")
    output: AgentListOutput = result.final_output

    agents: list[AgentSchema] = []
    for agent in output.agents:
        # 소비자 에이전트 연령 범위 이탈 시 페르소나 전체 재생성
        if agent.type == "customer" and age_range and agent.persona_profile:
            min_age, max_age = age_range
            if not (min_age <= agent.persona_profile.age <= max_age):
                agent = await _regenerate_customer_agent(agent, age_range, req)

        if agent.persona_profile:
            profile = PersonaProfile(**agent.persona_profile.model_dump())
            agent.system_prompt = build_system_prompt_from_persona(
                agent.name, agent.type, profile
            )

        agents.append(AgentSchema(**agent.model_dump()))

    return agents
