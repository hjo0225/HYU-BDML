"""에이전트 추천 서비스 — OpenAI 호출"""
import json
from models.schemas import AgentRequest, AgentSchema
from services.openai_client import get_client
from prompts.agent_recommend import AGENT_RECOMMEND_PROMPT


async def recommend_agents(req: AgentRequest) -> list[AgentSchema]:
    """연구 정보 + 시장조사를 기반으로 에이전트 5명 추천"""
    client = get_client()

    # 사용자 메시지 구성
    user_message = (
        f"[연구 정보]\n"
        f"- 배경: {req.brief.background}\n"
        f"- 목적: {req.brief.objective}\n"
        f"- 활용방안: {req.brief.usage_plan}\n"
        f"- 카테고리: {req.brief.category}\n"
        f"- 타깃 고객: {req.brief.target_customer}\n\n"
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

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": AGENT_RECOMMEND_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.8,
    )

    raw = response.choices[0].message.content or ""

    # JSON 파싱 (```json ... ``` 래핑 처리)
    json_str = raw.strip()
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    agents_data = json.loads(json_str)
    return [AgentSchema(**agent) for agent in agents_data]
