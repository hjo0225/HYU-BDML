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


def _parse_age_range(text: str) -> tuple[int, int] | None:
    """타깃 고객 텍스트에서 연령 범위 추출"""
    import re
    m = re.search(r'(\d+)-(\d+)대', text)
    if m:
        return int(m.group(1)), int(m.group(2)) + 9
    m = re.search(r'(\d+)대', text)
    if m:
        start = int(m.group(1))
        return start, start + 9
    m = re.search(r'(\d+)-(\d+)세', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def check_agent_fitness(
    agents: list[AgentSchema],
    brief: ResearchBrief,
    report: MarketReport,
) -> dict:
    """에이전트 구성 적합성 검증 결과를 반환한다."""
    customer_agents = [a for a in agents if a.type == "customer"]
    expert_agents = [a for a in agents if a.type == "expert"]
    persona_agents = [a for a in agents if a.persona_profile]

    strengths: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    score = 100

    # 소비자/전문가 구성 비율
    if len(customer_agents) >= 3 and len(expert_agents) >= 2:
        strengths.append(f"소비자 {len(customer_agents)}명 + 전문가 {len(expert_agents)}명으로 균형 잡힌 구성입니다.")
    else:
        if len(customer_agents) < 3:
            warnings.append(f"소비자 페르소나가 {len(customer_agents)}명으로 부족합니다.")
            suggestions.append("소비자 페르소나를 3명 이상으로 구성하면 다양한 고객 관점을 확보할 수 있습니다.")
            score -= 15
        if len(expert_agents) < 2:
            warnings.append(f"전문가 페르소나가 {len(expert_agents)}명으로 부족합니다.")
            suggestions.append(f"{brief.category} 분야의 서로 다른 전문가를 2명 이상 포함하세요.")
            score -= 10

    # 타깃 고객 연령 일치도
    age_range = _parse_age_range(brief.target_customer)
    if age_range and persona_agents:
        min_age, max_age = age_range
        matched = sum(
            1 for a in customer_agents
            if a.persona_profile and min_age <= a.persona_profile.age <= max_age
        )
        if matched == len(customer_agents):
            strengths.append(f"소비자 전원이 타깃 연령대({min_age}-{max_age}세)에 부합합니다.")
        elif matched >= 1:
            warnings.append(f"소비자 {len(customer_agents)}명 중 {matched}명만 타깃 연령대에 부합합니다.")
            suggestions.append("타깃 고객층의 실제 연령대에 맞는 페르소나로 조정하세요.")
            score -= 10
        else:
            warnings.append("소비자 페르소나 중 타깃 연령대에 해당하는 에이전트가 없습니다.")
            suggestions.append(f"타깃 고객({brief.target_customer})에 맞는 연령대로 수정하세요.")
            score -= 20

    # 전문가 분야 다양성
    if len(expert_agents) >= 2:
        occupations = [a.persona_profile.occupation for a in expert_agents if a.persona_profile]
        if len(set(occupations)) == len(occupations):
            strengths.append("전문가들이 서로 다른 분야를 커버하고 있습니다.")
        else:
            warnings.append("전문가들의 전문 분야가 유사합니다.")
            suggestions.append("서로 다른 관점을 제공할 수 있는 전문 분야로 분산하세요.")
            score -= 10

    # 소비자 페르소나 성격 차별화
    if len(customer_agents) >= 2:
        personalities = [
            a.persona_profile.personality for a in customer_agents if a.persona_profile
        ]
        if personalities:
            has_critical = any(
                kw in p for p in personalities
                for kw in ["회의적", "보수적", "신중", "비판적", "까다로운"]
            )
            if has_critical:
                strengths.append("회의적/비판적 성향의 소비자가 포함되어 균형 잡힌 논의가 가능합니다.")
            else:
                suggestions.append("회의적이거나 보수적인 성향의 소비자를 포함하면 비판적 관점을 확보할 수 있습니다.")
                score -= 5

    if report.target_analysis.strip():
        strengths.append("시장조사 보고서의 타깃 분석을 바탕으로 에이전트 구성을 해석할 수 있습니다.")
    else:
        warnings.append("시장조사 보고서의 타깃 분석 정보가 약해 세부 적합성 판단이 어렵습니다.")
        score -= 10

    if not strengths:
        strengths.append("기본적인 에이전트 구성은 완료되어 추가 개선의 출발점으로 사용할 수 있습니다.")

    score = max(0, min(100, score))
    summary = (
        f"{len(agents)}명의 에이전트 구성을 기준으로 타깃 고객 일치도, "
        f"소비자/전문가 비율, 페르소나 차별화를 종합 평가했습니다."
    )

    return {
        "score": score,
        "summary": summary,
        "strengths": strengths,
        "warnings": warnings,
        "suggestions": suggestions,
    }


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
