"""회의 시뮬레이션 서비스.

회의 주제를 정제하고, 발언자 선택과 발언 생성을 반복하면서 SSE로 실시간 스트리밍한다.
"""
import asyncio
import json
import operator
import re
from typing import TypedDict, Annotated, AsyncGenerator

from openai import AsyncOpenAI
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from models.schemas import AgentSchema, MeetingDesign, MeetingMessage
from prompts.moderator import (
    CLOSING_PROMPT,
    FOLLOWUP_AND_SATURATION_PROMPT,
    INSIGHT_CHECK_PROMPT,
    MEETING_DESIGN_PROMPT,
    MODERATOR_PROMPT,
    PARTICIPANT_RULES_PROMPT,
    SPEAKER_SELECTION_PROMPT,
    TOPIC_REFINE_PROMPT,
)
from prompts.rag_utterance import UTTERANCE_PROMPT
from rag.retriever import retrieve
from services.persona_builder import load_persona_from_db, _CATEGORY_LABELS
from database import AsyncSessionLocal

# 시스템 환경변수에서 OpenAI 키를 읽어 LangChain/OpenAI 호출이 동일한 환경변수를 사용하게 한다.
import services.openai_client  # noqa: F401
from services.naver_search_service import SearchResultItem
from services.openai_web_search_service import OpenAIWebSearchService
from services.usage_tracker import tracker


def _log_langchain_usage(response, label: str):
    """LangChain AIMessage에서 토큰 사용량 추출·기록"""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        tracker.log(
            service=label,
            model="gpt-4o-mini",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


# 발언 생성용 모델과 판정용 모델을 분리해 비용과 응답 품질을 조절한다.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)            # 발언용
llm_structured = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)  # 판정용
_meeting_search = OpenAIWebSearchService(AsyncOpenAI())

MAX_MEETING_SEARCHES = 2
MEETING_SEARCH_SECTION = "meeting_topic"
MEETING_SEARCH_PLANNER_PROMPT = """당신은 FGI 모더레이터 보조 리서처입니다.
현재 회의 주제와 직전 논의 흐름을 보고, 회의 진행에 꼭 필요한 경우에만 아주 좁은 범위의 추가 검색을 제안하세요.

규칙:
1. 회의 주제와 직접 연결된 사실 확인이나 빈칸 보완일 때만 should_search=true
2. 새 주제를 열거나 경쟁사 전수조사처럼 범위를 넓히지 말 것
3. 검색어는 한국 웹검색용 짧은 문구 1개만 제안할 것
4. search_count가 max_searches 이상이면 반드시 should_search=false
5. 반드시 JSON으로만 응답할 것

응답 형식:
{"should_search": true, "query": "검색어", "reason": "한 줄 이유"}
""".strip()


# LangGraph에서 노드 간에 공유하는 상태
class MeetingState(TypedDict):
    topic: str
    context: str
    agents: list[dict]                          # AgentSchema.model_dump() 리스트
    history: Annotated[list[dict], operator.add] # 누적 발언 로그
    current_round: int
    max_rounds: int                             # 한 회의에서 허용하는 최대 라운드 수
    spoke_this_round: list[str]                 # 현재 라운드에서 이미 발언한 agent_id 목록
    next_speaker_id: str
    saturation_count: int                       # 연속으로 새 인사이트가 없다고 판단된 횟수
    should_end: bool
    pending_messages: Annotated[list[dict], operator.add]  # 메시지 단위 API에서 꺼내 갈 버퍼
    search_count: int


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
    _log_langchain_usage(response, "meeting/moderator_opening")
    opening = _clean_meeting_text(response.content, "모더레이터")

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

    # 한 라운드 안에서 모두 발언했으면 모더레이터 팔로업으로 넘어간다.
    if not remaining:
        return {"next_speaker_id": "__round_done__"}

    # 한 명만 남았으면 모델 호출 없이 바로 선택한다.
    if len(remaining) == 1:
        return {"next_speaker_id": remaining[0]}

    # 두 명 이상 남았을 때만 현재 대화 맥락을 보고 다음 발언자를 고른다.
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
        SystemMessage(content=SPEAKER_SELECTION_PROMPT),
        HumanMessage(content=(
            f"현재까지 대화:\n{history_text}\n\n"
            f"남은 참여자:\n{candidates}"
        )),
    ])
    _log_langchain_usage(response, "meeting/select_speaker")

    try:
        parsed = json.loads(response.content)
        chosen_id = parsed["agent_id"]
        if chosen_id in remaining:
            return {"next_speaker_id": chosen_id}
    except (json.JSONDecodeError, KeyError):
        pass

    # 구조화 응답이 깨지면 첫 후보를 선택해 회의를 계속 진행한다.
    return {"next_speaker_id": remaining[0]}


async def agent_speak(state: MeetingState) -> dict:
    """에이전트 발언 노드"""
    speaker_id = state["next_speaker_id"]
    agent_data = next(a for a in state["agents"] if a["id"] == speaker_id)

    # 자신의 이전 발언을 눈에 띄게 표시해 중복 발화를 줄인다.
    history_lines = []
    for h in state["history"]:
        prefix = "★ 나의 이전 발언 ★ " if h["speaker"] == agent_data["name"] else ""
        history_lines.append(f"[{prefix}{h['speaker']}]: {h['content']}")
    history_text = "\n".join(history_lines)

    # 첫 라운드는 아이스브레이킹, 이후 라운드는 심화 답변 중심으로 유도한다.
    current_round = state["current_round"]
    has_spoken_before = any(h["speaker"] == agent_data["name"] for h in state["history"])
    turn_instruction = (
        f"{current_round}번째 라운드입니다. "
        f"{_build_turn_instruction(current_round, has_spoken_before)}\n"
        "이전 자신의 발언을 반복하지 말고, 다른 참여자 의견을 참고해 내용을 구체화하세요."
    )

    # 실제 발언 본문 생성
    response = await llm.ainvoke([
        SystemMessage(content=agent_data["system_prompt"] + "\n\n" + PARTICIPANT_RULES_PROMPT),
        HumanMessage(content=f"현재까지 대화:\n{history_text}\n\n{turn_instruction}"),
    ])
    _log_langchain_usage(response, f"meeting/agent/{agent_data['name']}")
    content = _clean_meeting_text(response.content, agent_data["name"])

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

    # 팔로업 생성과 포화 판정을 한 번의 구조화 호출로 처리한다.
    response = await llm_structured.ainvoke([
        SystemMessage(content=FOLLOWUP_AND_SATURATION_PROMPT.format(moderator_prompt=MODERATOR_PROMPT)),
        HumanMessage(content=(
            f"현재 라운드: {current_round}\n"
            f"전체 대화:\n{history_text}\n\n"
            f"팔로업과 포화 판정을 수행하세요."
        )),
    ])
    _log_langchain_usage(response, "meeting/moderator_followup")

    # 구조화 응답 파싱
    try:
        parsed = json.loads(response.content)
        followup_text = _clean_meeting_text(parsed["followup"], "모더레이터")
        has_new = parsed["has_new_insight"]
    except (json.JSONDecodeError, KeyError):
        followup_text = _clean_meeting_text(response.content, "모더레이터")
        has_new = True  # 판단이 불명확하면 회의를 더 이어가는 쪽이 안전하다.

    # 새 인사이트가 없으면 카운터를 누적하고, 있으면 다시 0으로 초기화한다.
    new_saturation = 0 if has_new else state["saturation_count"] + 1

    # 최대 라운드 도달 또는 인사이트 고갈(최소 3라운드 후) 시 종료한다.
    min_rounds_done = current_round >= state["max_rounds"]
    saturation_exceeded = new_saturation >= 3 and current_round >= 3
    should_end = min_rounds_done or saturation_exceeded

    # 종료하는 턴이면 팔로업 대신 마무리 멘트를 만든다.
    if should_end:
        closing_response = await llm.ainvoke([
            SystemMessage(content=CLOSING_PROMPT.format(moderator_prompt=MODERATOR_PROMPT)),
            HumanMessage(content=f"전체 대화:\n{history_text}\n\n마무리하세요."),
        ])
        _log_langchain_usage(closing_response, "meeting/moderator_closing")
        followup_text = _clean_meeting_text(closing_response.content, "모더레이터")

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


# import 이후 재사용할 수 있도록 그래프를 한 번만 컴파일한다.
_meeting_graph = build_meeting_graph()


# ── RAG 헬퍼 ──
def _format_profile(scratch: dict) -> str:
    """scratch dict를 1인칭 서사형 프로필 텍스트로 변환."""
    parts: list[str] = []

    # 기본 인구통계
    age = scratch.get("age", "")
    gender = scratch.get("gender", "")
    region = scratch.get("region", "")
    occupation = scratch.get("occupation", "")
    if age and gender:
        parts.append(f"{region} 사는 {age}세 {gender}".strip())
    if occupation:
        parts.append(f"직업은 {occupation}")

    # 가구·결혼
    marital = scratch.get("marital_status", "")
    if marital:
        parts.append(marital)
    children = scratch.get("children_in_household", [])
    if children:
        parts.append(f"자녀: {', '.join(children)}")

    # 성격·라이프스타일
    strong = scratch.get("strong_traits", [])
    if strong:
        parts.append(f"활발한 편: {', '.join(strong)}")
    weak = scratch.get("weak_traits", [])
    if weak:
        parts.append(f"별로 안 하는 편: {', '.join(weak)}")

    # 소비·패션·투자 스타일
    styles = []
    for key, label in [("consumption_style", "소비"), ("fashion_style", "패션"), ("investment_style", "투자")]:
        v = scratch.get(key)
        if v:
            styles.append(f"{label}은 {v}")
    if styles:
        parts.append(", ".join(styles))

    # 최근 생애사건
    events = scratch.get("recent_life_events", [])
    if events:
        parts.append(f"최근에 {', '.join(events)} 경험")

    return ". ".join(parts) if parts else "프로필 정보 없음"


def _format_memories(memories: list[dict]) -> str:
    lines = [f"- {m['text']}" for m in memories if m.get("text")]
    return "\n".join(lines) if lines else "관련 기억 없음"


async def generate_meeting_design(
    topic: str,
    research_context: str,
    agent_summaries: str,
) -> dict:
    """FGI 회의 설계안 생성 (meeting_design 이벤트용)."""
    response = await llm_structured.ainvoke([
        SystemMessage(content=MEETING_DESIGN_PROMPT),
        HumanMessage(content=(
            f"회의 주제: {topic}\n\n"
            f"참여 패널:\n{agent_summaries}\n\n"
            f"연구 맥락:\n{research_context[:1200]}"
        )),
    ])
    _log_langchain_usage(response, "meeting/design")
    try:
        return json.loads(response.content)
    except (json.JSONDecodeError, KeyError):
        return {
            "session_objective": f"{topic}에 대한 소비자 인식과 경험 탐색",
            "discussion_questions": [],
            "key_themes": [],
            "moderator_notes": "",
        }


# ── SSE 헬퍼 ──
def _sse(data: dict) -> str:
    """SSE 포맷 문자열 생성"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _clean_meeting_text(text: str, speaker_name: str | None = None) -> str:
    """모델 출력의 불필요한 화자 라벨과 과도한 표기를 정리한다."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    prefixes = [r"모더레이터", r"진행자"]
    if speaker_name:
        prefixes.append(re.escape(speaker_name))
    prefix_pattern = r"^\s*(?:\[?(?:" + "|".join(prefixes) + r")\]?\s*[:：\-]\s*)"
    cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?m)^\s*[A-Z]\s*$", "", cleaned)
    cleaned = cleaned.replace("~", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_turn_instruction(current_round: int, has_spoken_before: bool) -> str:
    """라운드별 발화 지시. 라운드가 진행될수록 심화되지만 결론 강제는 하지 않는다."""
    if not has_spoken_before:
        return (
            "바로 의견부터 말하세요. 인사나 자기소개 없이 시작할 것.\n"
            "- 주제에 대한 내 생각을 먼저 말하고, 이유나 경험을 덧붙일 것\n"
            "- 번호, 제목, 꼬리표를 붙이지 말 것"
        )

    if current_round == 2:
        return (
            "다른 참여자 발언 중 인상적인 부분을 짚고, 내 경험에서 다른 각도를 제시하세요.\n"
            "- 무조건 동의하지 말고, 다르게 느낀 점이 있으면 편하게 말할 것\n"
            "- 번호, 제목, 꼬리표를 붙이지 말 것"
        )

    return (
        "아직 나오지 않은 새로운 관점이나 구체적인 경험을 꺼내세요.\n"
        "- 앞에서 나온 의견을 요약하거나 정리하지 말 것\n"
        "- '최종 입장', '결론' 같은 표현을 쓰지 말 것\n"
        "- 내 생활에서 떠오르는 새로운 에피소드를 말할 것"
    )


async def _stream_llm_turn(
    system_prompt: str,
    human_prompt: str,
    meta: dict,
    usage_label: str = "meeting/stream",
) -> AsyncGenerator[str, None]:
    """한 번의 발언 생성 과정을 start -> delta* -> end 이벤트로 변환한다."""
    yield _sse({"type": "start", **meta})

    full_text = ""
    input_tokens = 0
    output_tokens = 0
    async for chunk in llm.astream([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]):
        delta = chunk.content
        if delta:
            full_text += delta
            yield _sse({"type": "delta", "delta": delta})
        # 마지막 청크에 usage 정보가 붙는 경우가 있어 매번 확인한다.
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

    # usage 메타데이터가 없을 때는 대략적인 길이 기반으로 기록한다.
    if not input_tokens and not output_tokens:
        input_tokens = len(system_prompt + human_prompt) // 3  # 대략 추정
        output_tokens = len(full_text) // 3
    tracker.log(service=usage_label, model="gpt-4o-mini", input_tokens=input_tokens, output_tokens=output_tokens)

    full_text = _clean_meeting_text(full_text, meta.get("agent_name"))
    yield _sse({"type": "end", "content": full_text, "retrieved_memory_count": 0, **meta})
    meta["_full_text"] = full_text


async def _stream_rag_turn(
    panel_id: str,
    agent_data: dict,
    human_prompt: str,
    meta: dict,
    persona_cache: dict[str, dict],
    retrieval_query: str | None = None,
    n_retrieve: int = 25,
    usage_label: str = "meeting/stream/rag",
) -> AsyncGenerator[str, None]:
    """RAG 에이전트 발언: DB 캐시에서 persona 조회 → 메모리 검색 → 스트리밍 발화.

    retrieval_query: 메모리 검색용 쿼리 (모더레이터 질문 + 직전 발언).
                     None이면 human_prompt를 그대로 사용 (폴백).
    human_prompt: LLM 발언 생성에 전달되는 전체 대화 컨텍스트.
    """
    focal = retrieval_query or human_prompt
    retrieved_count = 0
    activated_categories: list[str] = []
    persona = persona_cache.get(panel_id)

    if persona:
        scratch = persona.get("scratch", {})
        profile_text = _format_profile(scratch)
        memories = persona.get("memories", [])

        if memories:
            try:
                retrieved = await asyncio.to_thread(retrieve, persona, focal, n_retrieve)
                retrieved_count = len(retrieved)
                memories_text = _format_memories(retrieved)
                # 상위 5개 메모리의 카테고리만 추출 (검색 점수순, 중복 제거)
                activated_categories = list(dict.fromkeys(
                    _CATEGORY_LABELS.get(m.get("category", ""), m.get("category", ""))
                    for m in retrieved[:5] if m.get("category")
                ))
            except Exception:
                memories_text = _format_memories(memories[:10])
                retrieved_count = min(10, len(memories))
        else:
            memories_text = "관련 기억 없음"

        system_prompt = UTTERANCE_PROMPT.format(
            profile=profile_text,
            memories=memories_text,
        )
    else:
        # persona 없으면 기존 system_prompt로 폴백
        system_prompt = agent_data.get("system_prompt", "") + "\n\n" + PARTICIPANT_RULES_PROMPT

    yield _sse({"type": "start", **meta})

    full_text = ""
    input_tokens = 0
    output_tokens = 0
    async for chunk in llm.astream([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]):
        delta = chunk.content
        if delta:
            full_text += delta
            yield _sse({"type": "delta", "delta": delta})
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

    if not input_tokens and not output_tokens:
        input_tokens = len(system_prompt + human_prompt) // 3
        output_tokens = len(full_text) // 3
    tracker.log(service=usage_label, model="gpt-4o-mini",
                input_tokens=input_tokens, output_tokens=output_tokens)

    full_text = _clean_meeting_text(full_text, meta.get("agent_name"))
    yield _sse({
        "type": "end",
        "content": full_text,
        "retrieved_memory_count": retrieved_count,
        "activated_categories": activated_categories,
        **meta,
    })
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


def _format_search_context(query: str, items: list[SearchResultItem]) -> str:
    if not items:
        return ""

    lines = [f"[추가 검색 참고] 쿼리: {query}"]
    for idx, item in enumerate(items[:3], start=1):
        publisher = item.publisher or "출처 미상"
        date = item.published_at or "날짜 미상"
        snippet = (item.snippet or item.title or "").strip()
        lines.append(
            f"{idx}. {item.title} | {publisher} | {date} | {snippet}"
        )
    lines.append("위 검색 결과는 회의 주제와 직접 연결된 보조 근거입니다. 발언에 필요할 때만 신중히 반영하세요.")
    return "\n".join(lines)


async def _plan_meeting_search(state: MeetingState) -> str | None:
    """최근 대화가 막혔을 때만 보조 검색어를 제안한다."""
    if state["search_count"] >= MAX_MEETING_SEARCHES or state["current_round"] < 2:
        return None

    recent_history = state["history"][-8:]
    history_text = "\n".join(
        f"[{h['speaker']}]: {h['content']}" for h in recent_history
    )

    response = await llm_structured.ainvoke([
        SystemMessage(content=MEETING_SEARCH_PLANNER_PROMPT),
        HumanMessage(content=(
            f"회의 주제: {state['topic']}\n"
            f"연구 맥락:\n{state['context'][:800]}\n\n"
            f"최근 대화:\n{history_text}\n\n"
            f"현재 search_count={state['search_count']}, max_searches={MAX_MEETING_SEARCHES}"
        )),
    ])
    _log_langchain_usage(response, "meeting/search_planner")

    try:
        parsed = json.loads(response.content)
        if parsed.get("should_search") and parsed.get("query"):
            return str(parsed["query"]).strip()
    except (json.JSONDecodeError, TypeError, KeyError):
        return None
    return None


async def _maybe_run_meeting_search(state: MeetingState) -> tuple[str, int]:
    """검색이 필요하다고 판단된 경우에만 검색 컨텍스트를 추가한다."""
    query = await _plan_meeting_search(state)
    if not query:
        return "", state["search_count"]

    try:
        items = await _meeting_search.search(section=MEETING_SEARCH_SECTION, query=query)
    except Exception:
        return "", state["search_count"]

    context = _format_search_context(query, items)
    if not context:
        return "", state["search_count"]
    return context, state["search_count"] + 1


# ── 외부 인터페이스 (메시지 단위) ──
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
        "search_count": 0,
    }

    async for event in _meeting_graph.astream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            for msg_dict in update.get("pending_messages", []):
                yield MeetingMessage(**msg_dict)
                await asyncio.sleep(0.3)


# ── 외부 인터페이스 (토큰 스트리밍) ──

async def _check_new_insight(state: MeetingState) -> dict:
    """새로운 인사이트 유무만 빠르게 판정해 종료 여부를 결정한다."""
    history_text = "\n".join(
        f"[{h['speaker']}]: {h['content']}" for h in state["history"]
    )
    current_round = state["current_round"]

    response = await llm_structured.ainvoke([
        SystemMessage(content=INSIGHT_CHECK_PROMPT),
        HumanMessage(content=(
            f"현재 라운드: {current_round}\n"
            f"전체 대화:\n{history_text}\n\n"
            f"새 인사이트 판정을 수행하세요."
        )),
    ])
    _log_langchain_usage(response, "meeting/check_insight")

    has_new = True
    try:
        parsed = json.loads(response.content)
        if "has_new_insight" in parsed:
            has_new = parsed["has_new_insight"]
    except Exception:
        pass

    new_saturation = 0 if has_new else state["saturation_count"] + 1
    # 최소 라운드(질문 수)를 보장: max_rounds 미달이면 saturation으로 종료하지 않음
    min_rounds_done = current_round >= state["max_rounds"]
    saturation_exceeded = new_saturation >= 3 and current_round >= 3  # 최소 3라운드 후 판정
    should_end = min_rounds_done or saturation_exceeded

    return {
        "saturation_count": new_saturation,
        "should_end": should_end,
        "current_round": current_round + 1,
    }


async def run_meeting_stream(
    agents: list[AgentSchema],
    topic: str,
    context: str,
    max_rounds: int = 5,
    panel_ids: dict[str, str] | None = None,
) -> AsyncGenerator[str, None]:
    """FGI 회의 시뮬레이션 — SSE 문자열을 토큰 단위로 yield.
    LangGraph 그래프를 수동 step으로 실행하며 발언 노드만 토큰 스트리밍."""

    # 시작 전에 주제를 짧고 선명한 질문으로 정리해 이후 발언 품질을 맞춘다.
    topic_refine_resp = await llm_structured.ainvoke([
        SystemMessage(content=TOPIC_REFINE_PROMPT),
        HumanMessage(content=f"원본 주제: {topic}\n연구 맥락: {context[:300]}"),
    ])
    _log_langchain_usage(topic_refine_resp, "meeting/topic_refine")
    try:
        refined_topic = json.loads(topic_refine_resp.content)["refined_topic"]
    except (json.JSONDecodeError, KeyError):
        refined_topic = topic

    yield _sse({"type": "topic_refined", "topic": refined_topic})
    await asyncio.sleep(0)
    topic = refined_topic  # 이후 모든 모델 호출은 정제된 주제를 기준으로 진행한다.

    # 회의 설계안 생성 (meeting_design 이벤트)
    _panel_ids: dict[str, str] = panel_ids or {}

    # RAG 에이전트의 persona를 DB에서 한 번만 조회해 캐싱한다.
    persona_cache: dict[str, dict] = {}
    if _panel_ids:
        async with AsyncSessionLocal() as session:
            for pid in set(_panel_ids.values()):
                persona = await load_persona_from_db(session, pid)
                if persona:
                    persona_cache[pid] = persona

    agent_summaries = "\n".join(
        "- {name} ({demo})".format(
            name=a.name,
            demo="{ag} {g} {occ} {reg}".format(
                ag=a.demographics.age_group if a.demographics else "",
                g=a.demographics.gender if a.demographics else "",
                occ=a.demographics.occupation if a.demographics else "",
                reg=a.demographics.region if a.demographics else "",
            ).strip() or a.description,
        )
        for a in agents
    )
    design_dict = await generate_meeting_design(topic, context, agent_summaries)
    yield _sse({"type": "meeting_design", "design": design_dict})
    await asyncio.sleep(0)

    # 토론 질문 목록 추출 → 질문 수가 라운드 수를 결정
    discussion_questions: list[str] = []
    for q in design_dict.get("discussion_questions", []):
        discussion_questions.append(q.get("question", ""))
    # 질문이 없으면 기본 max_rounds 사용, 있으면 질문 수로 결정
    effective_max_rounds = len(discussion_questions) if discussion_questions else max_rounds

    state: MeetingState = {
        "topic": topic,
        "context": context,
        "agents": [a.model_dump() for a in agents],
        "history": [],
        "current_round": 0,
        "max_rounds": effective_max_rounds,
        "spoke_this_round": [],
        "next_speaker_id": "",
        "saturation_count": 0,
        "should_end": False,
        "pending_messages": [],
        "search_count": 0,
    }

    agent_map = {a.id: a.model_dump() for a in agents}
    participant_names = ", ".join(a.name for a in agents)

    # 1. 모더레이터 오프닝
    meta = {**_MODERATOR_META}
    async for chunk in _stream_llm_turn(
        MODERATOR_PROMPT,
        f"회의 주제: {topic}\n연구 맥락: {context}\n참여자: {participant_names}\n\n회의를 시작하세요.",
        meta,
        usage_label="meeting/stream/moderator_opening",
    ):
        yield chunk
        await asyncio.sleep(0)
    opening = meta["_full_text"]
    state["history"] = [{"speaker": "모더레이터", "content": opening}]
    state["current_round"] = 1
    state["spoke_this_round"] = []
    state["saturation_count"] = 0

    # 라운드 요약 누적 (이전 라운드 맥락을 다음 라운드 retrieval에 전달)
    round_summaries: list[str] = []
    # 현재 라운드의 모더레이터 질문 (라운드 시작 시 갱신)
    current_moderator_question = opening

    # 2. 라운드 루프
    while not state["should_end"]:
        # 같은 라운드 안에서 참여자가 한 번씩 발언할 때까지 반복한다.
        while True:
            # 발언자 선택은 짧은 판정이므로 스트리밍 없이 처리한다.
            selection = await select_next_speaker(state)
            state["next_speaker_id"] = selection["next_speaker_id"]

            if state["next_speaker_id"] == "__round_done__":
                break

            # 실제 발언 본문은 토큰 단위로 스트리밍한다.
            speaker_id = state["next_speaker_id"]
            agent_data = agent_map[speaker_id]

            history_lines = []
            for h in state["history"]:
                prefix = "★ 나의 이전 발언 ★ " if h["speaker"] == agent_data["name"] else ""
                history_lines.append(f"[{prefix}{h['speaker']}]: {h['content']}")
            history_text = "\n".join(history_lines)

            current_round = state["current_round"]
            has_spoken_before = any(h["speaker"] == agent_data["name"] for h in state["history"])
            turn_instruction = (
                f"{current_round}번째 라운드입니다. "
                f"{_build_turn_instruction(current_round, has_spoken_before)}\n"
                "이전 자신의 발언을 반복하지 말고, 다른 참여자 의견을 참고해 내용을 구체화하세요."
            )

            meta = _agent_meta(agent_data)
            panel_id = _panel_ids.get(speaker_id)

            if panel_id:
                # 메모리 검색용 쿼리: 이전 라운드 요약 + 모더레이터 질문 + 직전 발언들
                recent_utterances = [
                    h["content"] for h in state["history"]
                    if h["speaker"] != "모더레이터" and h["speaker"] != agent_data["name"]
                ][-3:]  # 직전 최대 3명의 발언
                retrieval_parts = []
                if round_summaries:
                    retrieval_parts.append("이전 논의: " + " ".join(round_summaries))
                retrieval_parts.append("현재 질문: " + current_moderator_question)
                if recent_utterances:
                    retrieval_parts.append("다른 참여자 발언:\n" + "\n".join(recent_utterances))
                retrieval_query = "\n\n".join(retrieval_parts)

                async for chunk in _stream_rag_turn(
                    panel_id,
                    agent_data,
                    f"현재까지 대화:\n{history_text}\n\n{turn_instruction}",
                    meta,
                    persona_cache=persona_cache,
                    retrieval_query=retrieval_query,
                    usage_label=f"meeting/stream/agent/{agent_data['name']}",
                ):
                    yield chunk
                    await asyncio.sleep(0)
            else:
                async for chunk in _stream_llm_turn(
                    agent_data["system_prompt"] + "\n\n" + PARTICIPANT_RULES_PROMPT,
                    f"현재까지 대화:\n{history_text}\n\n{turn_instruction}",
                    meta,
                    usage_label=f"meeting/stream/agent/{agent_data['name']}",
                ):
                    yield chunk
                    await asyncio.sleep(0)

            content = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": agent_data["name"], "content": content}]
            state["spoke_this_round"] = state["spoke_this_round"] + [speaker_id]

        # 라운드 종료 뒤 인사이트 고갈 여부를 점검하고 필요하면 보조 검색을 수행한다.
        yield ": keepalive\n\n"
        await asyncio.sleep(0)
        followup_result = await _check_new_insight(state)
        has_ended = followup_result["should_end"]
        search_context, next_search_count = await _maybe_run_meeting_search(state)

        # 다음 라운드에서 사용할 질문 인덱스 (0-based, current_round는 1-based)
        next_q_idx = state["current_round"]  # 현재 라운드가 끝났으니 다음 질문 인덱스

        if has_ended or next_q_idx >= len(discussion_questions):
            # 종료 조건 충족 또는 모든 질문 소진 → 마무리
            history_text = "\n".join(
                f"[{h['speaker']}]: {h['content']}" for h in state["history"]
            )
            meta = {**_MODERATOR_META}
            async for chunk in _stream_llm_turn(
                CLOSING_PROMPT.format(moderator_prompt=MODERATOR_PROMPT),
                (
                    f"전체 대화:\n{history_text}\n\n"
                    f"{search_context}\n\n"
                    "마무리하세요."
                ),
                meta,
                usage_label="meeting/stream/moderator_closing",
            ):
                yield chunk
                await asyncio.sleep(0)
            closing = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": "모더레이터", "content": closing}]
            state["should_end"] = True
        else:
            # 다음 질문으로 전환: 이번 라운드 요약 + 다음 질문 제시
            next_question = discussion_questions[next_q_idx]
            history_text = "\n".join(
                f"[{h['speaker']}]: {h['content']}" for h in state["history"]
            )
            meta = {**_MODERATOR_META}
            async for chunk in _stream_llm_turn(
                MODERATOR_PROMPT,
                (
                    f"현재 라운드: {state['current_round']}\n"
                    f"전체 대화:\n{history_text}\n\n"
                    f"{search_context}\n\n"
                    f"이번 라운드의 핵심 논점을 1~2문장으로 짧게 정리한 뒤, "
                    f"다음 질문으로 자연스럽게 넘어가세요:\n\"{next_question}\""
                ),
                meta,
                usage_label="meeting/stream/moderator_followup",
            ):
                yield chunk
                await asyncio.sleep(0)
            followup_text = meta["_full_text"]
            state["history"] = state["history"] + [{"speaker": "모더레이터", "content": followup_text}]
            round_summaries.append(f"[라운드 {state['current_round']}] {followup_text}")
            current_moderator_question = followup_text

        # 다음 루프를 위해 상태를 갱신한다.
        state["saturation_count"] = followup_result["saturation_count"]
        state["should_end"] = followup_result["should_end"]
        state["current_round"] = followup_result["current_round"]
        state["spoke_this_round"] = []
        state["search_count"] = next_search_count

    yield _sse({"type": "done"})
