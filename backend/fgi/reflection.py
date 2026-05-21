"""세션 휘발 Reflection 메모리 (plan 0008 v2 · §04).

Round 종료 시 에이전트별 기억을 갱신한다. 기억은 **FGI 세션 동안만** in-memory 로 유지되고
(세션 종료 시 clear), 각 에이전트는 **자기 발화 vs 타 에이전트 발화**를 구분해 기억한다.
DB 영속(agent_memories source='fgi')은 비범위(후속).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _AgentMem:
    own: list[str] = field(default_factory=list)     # 자신의 발화
    others: list[str] = field(default_factory=list)  # 타인의 발화(요지)


# session_id → {agent_id → _AgentMem}
_STORE: dict[str, dict[str, _AgentMem]] = {}


def record(session_id: str, *, speaker_id: str | None, speaker_name: str, content: str, agent_ids: list[str]) -> None:
    """한 발화를 발화자 본인은 own, 나머지 참여자는 others 에 기록."""
    room = _STORE.setdefault(session_id, {aid: _AgentMem() for aid in agent_ids})
    for aid in agent_ids:
        mem = room.setdefault(aid, _AgentMem())
        if aid == speaker_id:
            mem.own.append(content)
        else:
            mem.others.append(f"{speaker_name}: {content}")


def context_for(session_id: str, agent_id: str, *, k: int = 3) -> str:
    """에이전트 발화 직전 주입할 세션 기억 (자기/타인 구분, 최근 k개)."""
    room = _STORE.get(session_id, {})
    mem = room.get(agent_id)
    if not mem or (not mem.own and not mem.others):
        return ""
    parts = []
    if mem.own:
        parts.append("[내가 이번 회의에서 한 말]\n" + "\n".join(f"- {x}" for x in mem.own[-k:]))
    if mem.others:
        parts.append("[다른 참여자들이 한 말]\n" + "\n".join(f"- {x}" for x in mem.others[-k:]))
    return "\n".join(parts)


def clear(session_id: str) -> None:
    _STORE.pop(session_id, None)
