"""회의록 생성 서비스 — OpenAI 호출"""
from models.schemas import MinutesRequest
from services.openai_client import get_async_client
from prompts.minutes import MINUTES_PROMPT


async def generate_minutes(req: MinutesRequest) -> str:
    """회의 대화 로그를 분석하여 Markdown 회의록 생성"""
    client = get_async_client()

    # 대화 로그 구성
    conversation_log = "\n".join(
        f"[{msg.agent_name}]: {msg.content}" for msg in req.messages
    )

    # 에이전트 정보 구성
    agent_info = "\n".join(
        f"- {a.emoji} {a.name} ({a.type}): {a.description}" for a in req.agents
    )

    user_message = (
        f"[연구 정보]\n"
        f"- 배경: {req.brief.background}\n"
        f"- 목적: {req.brief.objective}\n"
        f"- 활용방안: {req.brief.usage_plan}\n\n"
        f"[참여 에이전트]\n{agent_info}\n\n"
        f"[회의 대화 로그]\n{conversation_log}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": MINUTES_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.5,
        max_tokens=4000,
    )

    return response.choices[0].message.content or ""
