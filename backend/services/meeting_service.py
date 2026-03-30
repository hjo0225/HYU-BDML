"""회의 시뮬레이션 서비스 — 멀티 에이전트 FGI 엔진"""
import asyncio
from typing import AsyncGenerator
from models.schemas import AgentSchema, MeetingMessage
from services.openai_client import get_async_client
from prompts.moderator import MODERATOR_PROMPT


async def call_openai(system: str, user: str, max_tokens: int) -> str:
    """비동기 OpenAI 호출"""
    client = get_async_client()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.85,
    )
    return response.choices[0].message.content or ""


async def run_meeting(
    agents: list[AgentSchema],
    topic: str,
    context: str,
) -> AsyncGenerator[MeetingMessage, None]:
    """FGI 회의 시뮬레이션 — MeetingMessage를 비동기로 yield"""
    history: list[tuple[str, str]] = []

    # 라운드 수 결정: 에이전트 수에 따라 조절
    rounds = 4 if len(agents) <= 3 else (3 if len(agents) <= 5 else 2)

    # ── 1. 모더레이터 오프닝 ──
    participant_names = ", ".join(a.name for a in agents)
    opening = await call_openai(
        system=MODERATOR_PROMPT,
        user=(
            f"회의 주제: {topic}\n"
            f"연구 맥락: {context}\n"
            f"참여자: {participant_names}\n\n"
            f"회의를 시작하세요."
        ),
        max_tokens=300,
    )
    history.append(("모더레이터", opening))
    yield MeetingMessage(
        role="moderator",
        agent_name="모더레이터",
        agent_emoji="🎙️",
        content=opening,
    )

    # ── 2. 라운드 반복 ──
    for r in range(rounds):
        # 각 에이전트 발언
        for agent in agents:
            history_text = "\n".join(f"[{name}]: {content}" for name, content in history)
            response = await call_openai(
                system=agent.system_prompt + "\n\n발언은 2-4문장. 자신만의 관점 유지.",
                user=f"현재까지 대화:\n{history_text}\n\n당신의 차례입니다.",
                max_tokens=250,
            )
            history.append((agent.name, response))
            yield MeetingMessage(
                role="agent",
                agent_id=agent.id,
                agent_name=agent.name,
                agent_emoji=agent.emoji,
                content=response,
                color=agent.color,
            )
            await asyncio.sleep(0.5)  # 자연스러운 진행감

        # 모더레이터 팔로업
        is_last = r == rounds - 1
        history_text = "\n".join(f"[{name}]: {content}" for name, content in history)

        moderator_system = MODERATOR_PROMPT
        if is_last:
            moderator_system += "\n\n마지막 라운드입니다. 핵심 논점을 정리하고 마무리하세요."

        followup = await call_openai(
            system=moderator_system,
            user=(
                f"현재까지 대화:\n{history_text}\n\n"
                f"{'마무리하세요.' if is_last else '팔로업 또는 새 질문을 던지세요.'}"
            ),
            max_tokens=300,
        )
        history.append(("모더레이터", followup))
        yield MeetingMessage(
            role="moderator",
            agent_name="모더레이터",
            agent_emoji="🎙️",
            content=followup,
        )
