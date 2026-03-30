"""회의 시뮬레이션 서비스 — LangGraph 기반 멀티 에이전트 FGI 엔진"""
import asyncio
import json
import operator
from typing import TypedDict, Annotated, AsyncGenerator

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from models.schemas import AgentSchema, MeetingMessage
from prompts.moderator import MODERATOR_PROMPT

# Agents SDK 환경 로드 (.env에서 OPENAI_API_KEY)
import services.openai_client  # noqa: F401


# ── LLM 인스턴스 ──
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)            # 발언용
llm_structured = ChatOpenAI(model="gpt-4o", temperature=0.3)  # 판정용


# ── 그래프 상태 정의 ──
class MeetingState(TypedDict):
    topic: str
    context: str
    agents: list[dict]                          # AgentSchema.model_dump() 리스트
    history: Annotated[list[dict], operator.add] # [{"speaker": str, "content": str}]
    current_round: int
    max_rounds: int                             # 기본 5
    spoke_this_round: list[str]                 # 현재 라운드에서 발언한 agent_id 목록
    next_speaker_id: str
    saturation_count: int                       # 연속 "새 인사이트 없음" 횟수
    should_end: bool
    pending_messages: Annotated[list[dict], operator.add]  # SSE 출력 버퍼


# ── 참여자 발언 규칙 ──
_PARTICIPANT_RULES = """
회의 발언 규칙:
- 반드시 2-4문장으로 답변할 것
- 인사나 자기소개는 첫 발언에서만 간단히. 이후 라운드에서는 절대 반복하지 말 것
- 이전 자신의 발언을 기억하고 반복하지 말 것. 새로운 관점이나 심화된 의견을 제시할 것
- 다른 참여자의 의견에 동의/반박/보충하며 자연스러운 대화를 이어갈 것
- 자신만의 페르소나(경험, 성격, 가치관)에 기반해 일관되게 답변할 것
- 모더레이터의 질문에 직접 답하되, 구체적 경험이나 사례를 포함할 것
""".strip()


# ── 노드 함수 ──
async def moderator_opening(state: MeetingState) -> dict:
    """모더레이터 오프닝 발언 노드"""
    participant_names = ", ".join(a["name"] for a in state["agents"])

    response = await llm.ainvoke([
        SystemMessage(content=MODERATOR_PROMPT),
        HumanMessage(content=(
            f"회의 주제: {state['topic']}\n"
            f"연구 맥락: {state['context']}\n"
            f"참여자: {participant_names}\n\n"
            f"회의를 시작하세요."
        )),
    ])
    opening = response.content

    msg = MeetingMessage(
        role="moderator",
        agent_name="모더레이터",
        agent_emoji="🎙️",
        content=opening,
    )

    return {
        "history": [{"speaker": "모더레이터", "content": opening}],
        "pending_messages": [msg.model_dump()],
        "current_round": 1,
        "spoke_this_round": [],
        "saturation_count": 0,
    }


async def select_next_speaker(state: MeetingState) -> dict:
    """다음 발언자 선택 노드"""
    all_ids = [a["id"] for a in state["agents"]]
    remaining = [aid for aid in all_ids if aid not in state["spoke_this_round"]]

    # 모두 발언 완료
    if not remaining:
        return {"next_speaker_id": "__round_done__"}

    # 1명 남음 — 선택 불필요
    if len(remaining) == 1:
        return {"next_speaker_id": remaining[0]}

    # 2명 이상 — LLM에게 선택 위임
    history_text = "\n".join(
        f"[{h['speaker']}]: {h['content']}" for h in state["history"]
    )
    remaining_agents = [
        a for a in state["agents"] if a["id"] in remaining
    ]
    candidates = "\n".join(
        f"- {a['name']} (id: {a['id']})" for a in remaining_agents
    )

    response = await llm_structured.ainvoke([
        SystemMessage(content=(
            "당신은 FGI 모더레이터입니다. 대화 맥락을 분석하여 다음 발언자를 선택하세요.\n"
            "선택 기준: 직전 발언에 반론/보충 가능한 사람, 아직 충분히 의견을 표현하지 못한 사람, "
            "다른 관점을 가진 사람.\n"
            '반드시 JSON으로만 응답: {"agent_id": "선택한 id"}'
        )),
        HumanMessage(content=(
            f"현재까지 대화:\n{history_text}\n\n"
            f"남은 참여자:\n{candidates}"
        )),
    ])

    try:
        parsed = json.loads(response.content)
        chosen_id = parsed["agent_id"]
        if chosen_id in remaining:
            return {"next_speaker_id": chosen_id}
    except (json.JSONDecodeError, KeyError):
        pass

    # 파싱 실패 또는 유효하지 않은 id → fallback
    return {"next_speaker_id": remaining[0]}


async def agent_speak(state: MeetingState) -> dict:
    """에이전트 발언 노드"""
    speaker_id = state["next_speaker_id"]
    agent_data = next(a for a in state["agents"] if a["id"] == speaker_id)

    # 대화 이력 구성 — 자신의 발언에 ★ 표시
    history_lines = []
    for h in state["history"]:
        prefix = "★ 나의 이전 발언 ★ " if h["speaker"] == agent_data["name"] else ""
        history_lines.append(f"[{prefix}{h['speaker']}]: {h['content']}")
    history_text = "\n".join(history_lines)

    # 라운드별 지시
    current_round = state["current_round"]
    if current_round == 1 and speaker_id not in state["spoke_this_round"]:
        turn_instruction = "첫 번째 라운드입니다. 간단히 인사하고 주제에 대한 첫 의견을 말하세요."
    else:
        turn_instruction = (
            f"{current_round}번째 라운드입니다. 인사하지 마세요. "
            f"이전 자신의 발언과 다른 참여자 의견을 참고하여 심화된 의견을 제시하세요."
        )

    # LLM 호출
    response = await llm.ainvoke([
        SystemMessage(content=agent_data["system_prompt"] + "\n\n" + _PARTICIPANT_RULES),
        HumanMessage(content=f"현재까지 대화:\n{history_text}\n\n{turn_instruction}"),
    ])
    content = response.content

    msg = MeetingMessage(
        role="agent",
        agent_id=agent_data["id"],
        agent_name=agent_data["name"],
        agent_emoji=agent_data["emoji"],
        content=content,
        color=agent_data["color"],
    )

    return {
        "history": [{"speaker": agent_data["name"], "content": content}],
        "pending_messages": [msg.model_dump()],
        "spoke_this_round": state["spoke_this_round"] + [speaker_id],
    }


async def moderator_followup(state: MeetingState) -> dict:
    """모더레이터 팔로업 + 포화 판정 노드"""
    history_text = "\n".join(
        f"[{h['speaker']}]: {h['content']}" for h in state["history"]
    )
    current_round = state["current_round"]

    # 팔로업 + 포화 판정을 하나의 LLM 호출로
    response = await llm_structured.ainvoke([
        SystemMessage(content=(
            MODERATOR_PROMPT + "\n\n"
            "추가 지시:\n"
            "1. 이번 라운드의 핵심 논점을 정리하고 팔로업 질문을 던지세요.\n"
            "2. 이번 라운드에서 이전에 없던 새로운 인사이트가 나왔는지 판정하세요.\n"
            "   새로운 관점, 구체적 사례, 기존과 다른 의견이 하나라도 있으면 '새 인사이트 있음'.\n"
            "반드시 JSON으로만 응답:\n"
            '{"followup": "팔로업 발언", "has_new_insight": true/false, "insight_summary": "요약"}'
        )),
        HumanMessage(content=(
            f"현재 라운드: {current_round}\n"
            f"전체 대화:\n{history_text}\n\n"
            f"팔로업과 포화 판정을 수행하세요."
        )),
    ])

    # JSON 파싱
    try:
        parsed = json.loads(response.content)
        followup_text = parsed["followup"]
        has_new = parsed["has_new_insight"]
    except (json.JSONDecodeError, KeyError):
        followup_text = response.content
        has_new = True  # 파싱 실패 시 안전하게 계속

    # 포화 카운터 업데이트
    new_saturation = 0 if has_new else state["saturation_count"] + 1

    # 종료 조건 판정
    should_end = new_saturation >= 2 or current_round >= state["max_rounds"]

    # 종료 시 마무리 멘트로 교체
    if should_end:
        closing_response = await llm.ainvoke([
            SystemMessage(content=(
                MODERATOR_PROMPT + "\n\n"
                "마지막 라운드입니다. 핵심 논점을 정리하고 마무리하세요."
            )),
            HumanMessage(content=f"전체 대화:\n{history_text}\n\n마무리하세요."),
        ])
        followup_text = closing_response.content

    msg = MeetingMessage(
        role="moderator",
        agent_name="모더레이터",
        agent_emoji="🎙️",
        content=followup_text,
    )

    return {
        "history": [{"speaker": "모더레이터", "content": followup_text}],
        "pending_messages": [msg.model_dump()],
        "saturation_count": new_saturation,
        "should_end": should_end,
        "current_round": current_round + 1,
        "spoke_this_round": [],
    }


# ── 엣지 조건 함수 ──
def route_after_speaker_selection(state: MeetingState) -> str:
    """발언자 선택 결과에 따라 분기"""
    if state["next_speaker_id"] == "__round_done__":
        return "moderator_followup"
    return "agent_speak"


def route_after_followup(state: MeetingState) -> str:
    """팔로업 후 종료 여부 분기"""
    if state["should_end"]:
        return END
    return "select_next_speaker"


# ── 그래프 조립 ──
def build_meeting_graph():
    """LangGraph 회의 시뮬레이션 그래프 구성"""
    graph = StateGraph(MeetingState)

    # 노드 등록
    graph.add_node("moderator_opening", moderator_opening)
    graph.add_node("select_next_speaker", select_next_speaker)
    graph.add_node("agent_speak", agent_speak)
    graph.add_node("moderator_followup", moderator_followup)

    # 엣지 연결
    graph.set_entry_point("moderator_opening")
    graph.add_edge("moderator_opening", "select_next_speaker")
    graph.add_conditional_edges("select_next_speaker", route_after_speaker_selection, {
        "agent_speak": "agent_speak",
        "moderator_followup": "moderator_followup",
    })
    graph.add_edge("agent_speak", "select_next_speaker")
    graph.add_conditional_edges("moderator_followup", route_after_followup, {
        "select_next_speaker": "select_next_speaker",
        END: END,
    })

    return graph.compile()


# 싱글턴 그래프 인스턴스
_meeting_graph = build_meeting_graph()


# ── SSE 헬퍼 ──
def _sse(data: dict) -> str:
    """SSE 포맷 문자열 생성"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_llm_turn(
    system_prompt: str,
    human_prompt: str,
    meta: dict,
) -> AsyncGenerator[str, None]:
    """LLM 호출을 토큰 스트리밍하며 start→delta*→end SSE 이벤트를 yield.
    완성된 전체 텍스트를 meta["_full_text"]에 저장."""
    yield _sse({"type": "start", **meta})

    full_text = ""
    async for chunk in llm.astream([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]):
        delta = chunk.content
        if delta:
            full_text += delta
            yield _sse({"type": "delta", "delta": delta})

    yield _sse({"type": "end", "content": full_text, **meta})
    meta["_full_text"] = full_text


# ── 메타 생성 헬퍼 ──
_MODERATOR_META = {
    "role": "moderator",
    "agent_id": None,
    "agent_name": "모더레이터",
    "agent_emoji": "🎙️",
    "color": None,
}


def _agent_meta(agent_data: dict) -> dict:
    return {
        "role": "agent",
        "agent_id": agent_data["id"],
        "agent_name": agent_data["name"],
        "agent_emoji": agent_data["emoji"],
        "color": agent_data["color"],
    }


# ── 외부 인터페이스 (메시지 단위 — 라우터 호환) ──
async def run_meeting(
    agents: list[AgentSchema],
    topic: str,
    context: str,
) -> AsyncGenerator[MeetingMessage, None]:
    """FGI 회의 시뮬레이션 — MeetingMessage를 비동기로 yield"""

    initial_state: MeetingState = {
        "topic": topic,
        "context": context,
        "agents": [a.model_dump() for a in agents],
        "history": [],
        "current_round": 0,
        "max_rounds": 5,
        "spoke_this_round": [],
        "next_speaker_id": "",
        "saturation_count": 0,
        "should_end": False,
        "pending_messages": [],
    }

    async for event in _meeting_graph.astream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            for msg_dict in update.get("pending_messages", []):
                yield MeetingMessage(**msg_dict)
                await asyncio.sleep(0.3)


# ── 외부 인터페이스 (토큰 스트리밍) ──
async def run_meeting_stream(
    agents: list[AgentSchema],
    topic: str,
    context: str,
) -> AsyncGenerator[str, None]:
    """FGI 회의 시뮬레이션 — SSE 문자열을 토큰 단위로 yield.
    LangGraph 그래프를 수동 step으로 실행하며 발언 노드만 토큰 스트리밍."""

    state: MeetingState = {
        "topic": topic,
        "context": context,
        "agents": [a.model_dump() for a in agents],
        "history": [],
        "current_round": 0,
        "max_rounds": 5,
        "spoke_this_round": [],
        "next_speaker_id": "",
        "saturation_count": 0,
        "should_end": False,
        "pending_messages": [],
    }

    agent_map = {a.id: a.model_dump() for a in agents}
    participant_names = ", ".join(a.name for a in agents)

    # ── 1. 모더레이터 오프닝 (토큰 스트리밍) ──
    meta = {**_MODERATOR_META}
    async for chunk in _stream_llm_turn(
        MODERATOR_PROMPT,
        f"회의 주제: {topic}\n연구 맥락: {context}\n참여자: {participant_names}\n\n회의를 시작하세요.",
        meta,
    ):
        yield chunk
    opening = meta["_full_text"]
    state["history"] = [{"speaker": "모더레이터", "content": opening}]
    state["current_round"] = 1
    state["spoke_this_round"] = []
    state["saturation_count"] = 0

    # ── 2. 라운드 루프 ──
    while not state["should_end"]:
        # 발언자 선택 → 발언 반복
        while True:
            # select_next_speaker (LLM 판정, 스트리밍 불필요)
            selection = await select_next_speaker(state)
            state["next_speaker_id"] = selection["next_speaker_id"]

            if state["next_speaker_id"] == "__round_done__":
                break

            # agent_speak (토큰 스트리밍)
            speaker_id = state["next_speaker_id"]
            agent_data = agent_map[speaker_id]

            history_lines = []
            for h in state["history"]:
                prefix = "★ 나의 이전 발언 ★ " if h["speaker"] == agent_data["name"] else ""
                history_lines.append(f"[{prefix}{h['speaker']}]: {h['content']}")
            history_text = "\n".join(history_lines)

            current_round = state["current_round"]
            if current_round == 1 and speaker_id not in state["spoke_this_round"]:
                turn_instruction = "첫 번째 라운드입니다. 간단히 인사하고 주제에 대한 첫 의견을 말하세요."
            else:
                turn_instruction = (
                    f"{current_round}번째 라운드입니다. 인사하지 마세요. "
                    f"이전 자신의 발언과 다른 참여자 의견을 참고하여 심화된 의견을 제시하세요."
                )

            meta = _agent_meta(agent_data)
            async for chunk in _stream_llm_turn(
                agent_data["system_prompt"] + "\n\n" + _PARTICIPANT_RULES,
                f"현재까지 대화:\n{history_text}\n\n{turn_instruction}",
                meta,
            ):
                yield chunk

            content = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": agent_data["name"], "content": content}]
            state["spoke_this_round"] = state["spoke_this_round"] + [speaker_id]

        # moderator_followup (판정은 ainvoke, 마무리/팔로업은 스트리밍)
        followup_result = await moderator_followup(state)
        # 판정 결과 반영
        has_ended = followup_result["should_end"]

        if has_ended:
            # 마무리 멘트를 토큰 스트리밍으로 재생성
            history_text = "\n".join(
                f"[{h['speaker']}]: {h['content']}" for h in state["history"]
            )
            meta = {**_MODERATOR_META}
            async for chunk in _stream_llm_turn(
                MODERATOR_PROMPT + "\n\n마지막 라운드입니다. 핵심 논점을 정리하고 마무리하세요.",
                f"전체 대화:\n{history_text}\n\n마무리하세요.",
                meta,
            ):
                yield chunk
            closing = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": "모더레이터", "content": closing}]
        else:
            # 팔로업을 토큰 스트리밍으로 재생성
            history_text = "\n".join(
                f"[{h['speaker']}]: {h['content']}" for h in state["history"]
            )
            meta = {**_MODERATOR_META}
            async for chunk in _stream_llm_turn(
                MODERATOR_PROMPT,
                f"현재 라운드: {state['current_round']}\n전체 대화:\n{history_text}\n\n"
                f"이번 라운드의 핵심 논점을 정리하고 팔로업 질문을 던지세요.",
                meta,
            ):
                yield chunk
            followup_text = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": "모더레이터", "content": followup_text}]

        # 상태 업데이트
        state["saturation_count"] = followup_result["saturation_count"]
        state["should_end"] = followup_result["should_end"]
        state["current_round"] = followup_result["current_round"]
        state["spoke_this_round"] = []

    yield _sse({"type": "done"})
