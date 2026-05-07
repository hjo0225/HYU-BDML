"""에이전트 추천과 페르소나 후처리를 담당하는 서비스."""
import re
from pydantic import BaseModel
from agents import Agent, Runner
from models.schemas import (
    AgentRequest,
    AgentSchema,
    PersonaProfile,
)
from prompts.agent_recommend import AGENT_RECOMMEND_PROMPT, CUSTOMER_REGEN_PROMPT

# 시스템 환경변수에서 OpenAI 키를 읽어 SDK/Agents SDK가 동일한 키를 사용하게 한다.
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


# 모델 응답을 안정적으로 검증하기 위한 구조화 출력 타입
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


# 전체 참여자 구성을 한 번에 제안하는 메인 에이전트
recommender_agent = Agent(
    name="에이전트 설계자",
    instructions=AGENT_RECOMMEND_PROMPT,
    model="gpt-4o-mini",
    output_type=AgentListOutput,
)

# 나이 제약을 벗어난 소비자 페르소나만 다시 뽑기 위한 보정 에이전트
_single_regen_agent = Agent(
    name="소비자 에이전트 재생성",
    instructions=CUSTOMER_REGEN_PROMPT,
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


def _parse_age_range(target_customer: str) -> tuple[int, int] | None:
    """타깃 고객 문자열에서 2030, 20대 등 연령대 범위를 추출한다."""
    if not target_customer:
        return None
    
    # "2030", "20-30대"처럼 두 개 연령대가 한 번에 언급된 경우를 먼저 처리한다.
    multi_match = re.search(r'([1-9][0-9])(?:대)?\s*(?:~|-|부터|과|와|,|\s)\s*([1-9][0-9])(?:대)?', target_customer)
    if multi_match:
        try:
            start = int(multi_match.group(1)[:2])
            end = int(multi_match.group(2)[:2])
            # "2030"처럼 붙어 있어도 정규식상 20, 30으로 나뉘어 들어온다.
            if end < start and len(multi_match.group(2)) == 2:
                pass
            return tuple(sorted([start, end + 9]))
        except ValueError:
            pass

    # "2030대"처럼 접미사와 함께 붙은 표기도 별도로 처리한다.
    century_match = re.search(r'([1-9]0)([1-9]0)(?:대)?', target_customer)
    if century_match:
        try:
            start = int(century_match.group(1))
            end = int(century_match.group(2))
            return tuple(sorted([start, end + 9]))
        except ValueError:
            pass
            
    # 단일 연령대만 있으면 해당 10년 구간 전체를 허용 범위로 본다.
    single_match = re.search(r'([1-9][0-9])(?:대)', target_customer)
    if single_match:
        try:
            age = int(single_match.group(1))
            return (age, age + 9)
        except ValueError:
            pass
            
    return None


async def _regenerate_customer_agent(
    original: AgentOutput,
    age_range: tuple[int, int],
    req: AgentRequest,
) -> AgentOutput:
    """연령 제약을 위반한 소비자 페르소나만 다시 생성한다."""
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

    # 타깃 고객 문자열에서 읽어낸 연령대를 프롬프트 제약으로 다시 전달한다.
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
        f"- 시장 개요: {req.report.market_overview.summary}\n"
        f"- 경쟁 환경: {req.report.competitive_landscape.summary}\n"
        f"- 타깃 고객 분석: {req.report.target_analysis.summary}\n"
        f"- 트렌드: {req.report.trends.summary}\n"
        f"- 시사점: {req.report.implications.summary}\n"
        f"{age_constraint}"
    )

    result = await Runner.run(recommender_agent, user_message)
    _log_runner_usage(result, "agents/recommend")
    output: AgentListOutput = result.final_output

    agents: list[AgentSchema] = []
    for agent in output.agents:
        # 모델이 제약을 놓친 경우 해당 소비자만 재생성해 전체 결과를 보정한다.
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
