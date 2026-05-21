"""FGI 기억 DB 영속 (plan 0008 v2 · §04 후속분).

세션 종료 시 참여 에이전트별로 이번 회의에서의 발언 요지를 agent_memories(source='fgi')로
1건씩 INSERT 한다. 세션 휘발 Reflection 과 별개로, 다음 회의/대화에서 retrieval 가능하도록 누적.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database import AgentMemory
from fgi import engagement, reflection


async def persist_fgi_memories(
    db: AsyncSession, *, session_id: str, topic: str, agent_ids: list[str], mock: bool | None = None,
) -> int:
    """참여 에이전트별 FGI 발언 요지를 임베딩과 함께 적재. 적재 건수 반환."""
    room = reflection._STORE.get(session_id, {})
    n = 0
    for aid in agent_ids:
        mem = room.get(aid)
        if not mem or not mem.own:
            continue
        text = f"[FGI: {topic}] " + " / ".join(mem.own[-5:])
        text = text[:1500]
        emb = await engagement.embed_text(text, mock=mock)
        db.add(AgentMemory(
            agent_id=aid, source="fgi", category="fgi_session", text=text,
            importance=50, embedding=emb, meta_json={"session_id": session_id, "topic": topic},
        ))
        n += 1
    await db.commit()
    return n
