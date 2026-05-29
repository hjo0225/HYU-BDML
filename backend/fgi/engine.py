"""FGI 라운드 엔진 v2 (plan 0008 v2 · item 4).

흐름(사용자 제공 스펙):
  1) 사회자가 주제를 N Round(소주제+목표질문)로 분해한 토론 플랜 생성
  2) 매 턴 engagement score 동적 발화자 선정 (round-robin 아님)
  3) 발화마다 follow-up cascade (토큰 1차 → LLM rubric 2차) · 비활동 참가자 pull-in
  4) Round 종료 시 Reflection (세션 휘발, 자기/타인 구분)
  5) Round 사이 사용자 개입 창(30초, Round당 최대 2회)
  6) 세션 종료 → 구조화 인사이트 보고서

SSE 이벤트: round_start / moderator_delta / moderator_end / agent_delta / agent_end /
engagement / user_turn_required / round_end / session_end / error
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, FGISession, FGITurn
from fgi import cascade, config, engagement, memory, reflection, report
from fgi.prompts import moderator as mod_prompts
from fgi.prompts.utterance import (
    AGENT_REPLY,
    AGENT_TURN,
    FGI_GOAL_PREAMBLE,
    PASS_INSTRUCTION,
    STANCE_INSTRUCTION,
    build_v1_1_persona_intro,
)
from services.agent_service import demographics as _agent_demographics
from services.llm_client import chat_completion, stream_chat


# ── 사용자 개입 조정 (run 코루틴 ↔ intervene 엔드포인트) ─────────────────────
class _Waiter:
    def __init__(self, round_no: int, order: int):
        self.round = round_no
        self.order = order
        self.queue: asyncio.Queue[str] = asyncio.Queue()


_WAITERS: dict[str, _Waiter] = {}

# '개입 안 함' 신호 — 사용자가 명시적으로 건너뛸 때 큐에 넣는 센티넬 (v0.3.2).
_SKIP_SENTINEL = "__SKIP_INTERVENTION__"

# 수동 제어 플래그 (§11 수동 전환 · §12 수동 종료) — control 엔드포인트가 set, run 루프가 소비.
_CONTROLS: dict[str, dict[str, bool]] = {}


def get_waiter(session_id: str) -> _Waiter | None:
    return _WAITERS.get(session_id)


def skip_intervention(session_id: str) -> bool:
    """사용자가 '개입 안 함'을 선택 → 대기 중이면 즉시 다음 라운드로 진행. 대기 중이면 True."""
    waiter = _WAITERS.get(session_id)
    if waiter is None:
        return False
    waiter.queue.put_nowait(_SKIP_SENTINEL)
    return True


def set_control(session_id: str, action: str) -> bool:
    """action='next_round'|'end_session' 플래그 설정. 진행 중 세션이면 True."""
    if action not in ("next_round", "end_session"):
        return False
    _CONTROLS.setdefault(session_id, {})[action] = True
    return True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_quotes(text: str) -> str:
    """발화 전체를 감싼 따옴표 제거 — 모델이 본문을 따옴표로 감싸 출력하는 누출 보정."""
    t = text.strip()
    while len(t) >= 2 and t[0] in "\"'“”‘’" and t[-1] in "\"'“”‘’":
        t = t[1:-1].strip()
    return t


def _strip_speaker_prefix(text: str, name: str) -> str:
    """발화 앞에 붙은 발화자 본인 이름 라벨 제거 — '최수아:', '[최수아]', '최수아 -' 등의 누출 보정.

    프롬프트로 본문만 출력하라고 지시해도 모델이 대본처럼 '이름: 내용'을 붙이는 경우가 있어,
    채팅 버블 라벨과 본문에 이름이 중복 노출되는 것을 막는다. 본인 이름일 때만 제거한다.
    """
    t = text.strip()
    if not name:
        return t
    nm = re.escape(name.strip())
    # '[최수아]' / '최수아' 뒤에 : ：, ) ] > - – — 또는 공백+구분자가 오는 라벨 형태만 제거.
    m = re.match(rf"^\s*\[?{nm}\]?\s*[:：)\]>\-–—]\s*", t)
    return t[m.end():].strip() if m else t


def _is_pass(text: str) -> bool:
    """에이전트가 '새로 더할 게 없다'며 패스했는지 — 발언으로 치지 않는다 (v0.3.2)."""
    t = text.strip().strip("[]()*").strip().lower()
    return t in ("", "pass", "패스", "[pass]") or t.startswith("[pass]") or len(t) < 2


def _word_chunks(text: str):
    """이미 계산된 텍스트(템플릿/외부 LLM 결과)를 어절 단위로 잘라 streaming 흉내를 낸다.
    공백을 유지해 합치면 원문이 되도록 한다. 모더레이터 SSE(precomputed 경로)용."""
    for tok in text.split(" "):
        yield tok + " "


def _engagement_payload(round_no, phase, scores, agents, *, next_agent_id=None,
                        probe_index=None, probe_total=None, excluded_ids=None):
    """발화자 선정 점수를 라이브 SSE 이벤트 dict 로 만든다 (plan 0022 / 0026).

    scores 는 engagement.llm_engagement 결과({id:{interest,reaction}}). interest(0~1)만
    노출한다. excluded_ids 는 "이번 발화자 후보에서 빠진" agent id 목록(plan 0026 cooling
    표시용) — Phase B 에서 이미 1차 답변 끝낸 사람, Phase C 에서 직전 N턴 lock 이거나
    라운드 누적 발화 상한 도달한 사람. 프론트는 이 목록의 카드를 dim 처리한다.
    scores 가 비면(키 없음·LLM engagement off·파싱 실패) None 을 반환해 이벤트를 생략한다.
    """
    if not scores:
        return None
    payload = {
        "type": "engagement",
        "round": round_no,
        "phase": phase,
        "scores": {a.id: round(float(scores.get(a.id, {}).get("interest", 0.5)), 3) for a in agents},
    }
    if next_agent_id:
        payload["next_agent_id"] = next_agent_id
    if probe_index is not None:
        payload["probe_index"] = probe_index
    if probe_total is not None:
        payload["probe_total"] = probe_total
    if excluded_ids:
        payload["excluded"] = list(excluded_ids)
    return payload


async def _save_turn(db, *, session_id, round_no, order, role, content, agent_id=None, meta=None) -> FGITurn:
    turn = FGITurn(
        id=str(uuid.uuid4()), session_id=session_id, round=round_no, order_in_round=order,
        role=role, agent_id=agent_id, content=content, meta_json=meta,
    )
    db.add(turn)
    await db.commit()
    return turn


async def _generate_plan(topic: str, n_rounds: int, mock: bool | None) -> list[dict]:
    """주제를 N Round(소주제+목표질문)로 분해. 실패 시 일반 플랜."""
    try:
        raw = (await chat_completion(
            system=mod_prompts.MODERATOR_SYSTEM,
            user=mod_prompts.ROUND_PLAN_USER.format(topic=topic, n_rounds=n_rounds),
            model=config.CHAT_MODEL, temperature=0.4, max_tokens=600, mock=mock,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(raw)
        plan = [p for p in plan if p.get("subtopic") and p.get("goal_question")]
        if plan:
            return plan[:n_rounds]
    except Exception:  # noqa: BLE001
        pass
    # 폴백 — 일반 토론 흐름
    generic = [
        {"subtopic": "현황과 경험", "goal_question": f"'{topic}'와 관련해 평소 경험은 어떠셨나요?"},
        {"subtopic": "원인과 감정", "goal_question": "그렇게 느끼게 된 결정적 계기는 무엇이었나요?"},
        {"subtopic": "비교와 대안", "goal_question": "다른 선택지와 비교하면 어떤 점이 달랐나요?"},
        {"subtopic": "개선과 기대", "goal_question": "어떤 점이 바뀌면 생각이 달라질까요?"},
        {"subtopic": "가격·의향", "goal_question": "비용 측면에서 수용 가능한 선은 어디인가요?"},
    ]
    return generic[:n_rounds] if n_rounds <= len(generic) else generic + generic[: n_rounds - len(generic)]


def _others_recent(history: list[dict], self_id: str, k: int = 4) -> str:
    lines = [f"- {t['name']}: {t['content']}" for t in history[-k - 1:] if t.get("agent_id") != self_id and t["role"] != "moderator"]
    return "\n".join(lines[-k:]) or "(아직 다른 참여자 발언 없음)"


async def _stream_agent(db, *, session, agent, agent_ids, round_no, order, moderator_msg, history, mock,
                        stance=None, allow_pass=False, reply_to=None):
    """에이전트 1발화 — 토큰 스트리밍 yield + 저장 + 기억 기록. 마지막에 ('end', turn, content).

    stance('critical'|'positive')가 주어지면 라운드 진영 지시를 앞에 덧붙인다(v0.3, 자유토론 전용).
    allow_pass=True 면 '새로 더할 게 없으면 [PASS]' 지침을 주고, 응답이 패스면 토큰을 흘리지 않고
    ('pass', None, None) 만 내보낸 뒤 종료(발언으로 저장하지 않음, v0.3.2).
    reply_to=(이름, 발언)이 주어지면 그 화자에게 직접 답글을 다는 AGENT_REPLY 를 쓴다(v0.4 교차 대화).
    """
    refl = reflection.context_for(session.id, agent.id)
    others = _others_recent(history, agent.id)
    if reply_to is not None:
        target_name, target_content = reply_to
        user = AGENT_REPLY.format(moderator_message=moderator_msg, target_name=target_name, target_content=target_content)
    else:
        user = AGENT_TURN.format(moderator_message=moderator_msg, others_summary=others)
    if allow_pass:
        user = PASS_INSTRUCTION + "\n\n" + user
    if stance and stance in STANCE_INSTRUCTION:
        user = STANCE_INSTRUCTION[stance] + "\n\n" + user
    if refl:
        user = refl + "\n\n" + user
    # Toubia v1.1(anti-RLHF·1인칭 평서체) + FGI 참여 지침 + 페르소나 본문 순서로 결합.
    # v1.1 머리말이 최상단에 와야 'AI 어시스턴트' 자기 인식을 먼저 끊을 수 있다.
    age_range, gender = _agent_demographics(agent)
    v1_1_intro = build_v1_1_persona_intro(age_range, gender)
    persona = agent.persona_full_prompt or "당신은 소비자 페르소나입니다."
    system_prompt = v1_1_intro + "\n\n" + FGI_GOAL_PREAMBLE + "\n\n" + persona
    parts: list[str] = []
    # allow_pass(Phase C 찬반토론) 일 때도 SSE 가 끊기지 않게 하기 위해 '머리 버퍼링' 전략 사용.
    # 머리 ~8자만 silent 누적해 '[PASS]' 마커인지 결정 → 정상 발언이면 그동안 모은 버퍼를 한 번에
    # flush 한 뒤 이후 토큰은 그대로 흘려보낸다. PASS 마커로 보이면 끝까지 silent (마지막에 확정 후
    # ('pass', …) 만 송출). 이전 구현은 전체를 silent 로 모았다가 끝에 한 덩어리로 dump 했었다.
    pass_buf = ""
    pass_flushed = False
    DECIDE_LEN = 8  # '[pass]' = 6자. 여유 두고 8자 모이면 분기.
    # plan 0025 v2 의 발화 중 listener_update(토큰 임계 송출) 는 plan 0026 에서 폐기.
    # 이유: inline await llm_engagement 가 토큰 스트림에 200~500ms 정체를 끼워넣어
    # 발화 텍스트와 막대 변동이 한 발화 안에서 뒤섞이는 UX 문제 + 개입 SSE race 의심.
    # 이제 발화 중에는 토큰만 흐르고, engagement 는 다음 발화 cycle 시작 시점에 1회 송출.
    async for delta in stream_chat(
        system=system_prompt,
        messages=[{"role": "user", "content": user}],
        model=config.CHAT_MODEL, temperature=0.9, max_tokens=240, mock=mock,
    ):
        parts.append(delta)
        if not allow_pass or pass_flushed:
            yield ("delta", delta, None)
            continue
        pass_buf += delta
        head = pass_buf.strip().lower()
        if len(head) >= DECIDE_LEN:
            # '[pass' / 'pass' / '패스' 로 시작하면 패스 가능성 — 끝까지 silent 유지.
            looks_pass = head.startswith("[pass") or head == "pass" or head.startswith("패스")
            if not looks_pass:
                yield ("delta", pass_buf, None)
                pass_flushed = True
    name = agent.display_name or "참여자"
    # 따옴표 누출 + 본인 이름 라벨('최수아:') 누출을 본문에서 제거 — 버블 라벨과 중복 노출 방지.
    content = _strip_speaker_prefix(_strip_quotes("".join(parts)), name)
    if allow_pass and _is_pass(content):
        yield ("pass", None, None)   # 새로 더할 게 없음 → 발언하지 않음
        return
    if allow_pass and not pass_flushed:
        # 결정 임계 미달(짧은 정상 발언) — 모은 본문을 한 번에 노출. 진짜 streaming 은 아니지만
        # PASS 아닌 게 확정된 시점이라 어쩔 수 없이 한 덩어리.
        yield ("delta", content, None)
    turn = await _save_turn(db, session_id=session.id, round_no=round_no, order=order,
                            role="agent", content=content, agent_id=agent.id, meta={"display_name": name})
    history.append({"round": round_no, "order": order, "role": "agent", "agent_id": agent.id, "name": name, "content": content})
    reflection.record(session.id, speaker_id=agent.id, speaker_name=name, content=content, agent_ids=agent_ids)
    yield ("end", turn, content)


async def run_fgi(
    db: AsyncSession,
    *,
    session: FGISession,
    agents: list[Agent],
    max_rounds: int = 5,
    allow_user_intervention: bool = True,
    intervention_timeout: float | None = None,
    plan: list[dict] | None = None,
    mock: bool | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    timeout = config.INTERVENTION_TIMEOUT if intervention_timeout is None else intervention_timeout
    agent_ids = [a.id for a in agents]
    by_id = {a.id: a for a in agents}
    name_by = {a.id: (a.display_name or "참여자") for a in agents}
    # 세션 기억 방 초기화 (record 가 agent_ids 를 알도록)
    reflection._STORE.setdefault(session.id, {aid: reflection._AgentMem() for aid in agent_ids})

    agents_meta = [{"agent_id": a.id, "name": name_by[a.id], "summary": (a.intro_ko or "")} for a in agents]
    started_dt = session.started_at if (session.started_at and session.started_at.tzinfo) else (
        session.started_at.replace(tzinfo=timezone.utc) if session.started_at else _now())

    def _session_over() -> bool:
        if _CONTROLS.get(session.id, {}).get("end_session"):
            return True
        return (_now() - started_dt).total_seconds() / 60 > config.SESSION_MAX_MIN

    # 확정된 라운드 플랜(AI 제안)이 있으면 그대로 사용, 없으면 엔진이 자체 생성.
    # probes: Phase C(자유토론) 수렴 시 의견을 갈라 재점화할 쟁점.
    confirmed = [
        {
            "subtopic": (p.get("subtopic") or "").strip(),
            "goal_question": (p.get("goal_question") or "").strip(),
            "probes": [str(x).strip() for x in (p.get("probes") or []) if str(x).strip()],
        }
        for p in (plan or [])
        if (p.get("goal_question") or "").strip()
    ]
    plan = confirmed if confirmed else await _generate_plan(session.topic, max_rounds, mock)
    history: list[dict] = []
    round_summaries: list[dict] = []
    ended_early = False

    # 에이전트 1발화 → 이벤트 스트림 + 마지막 content 를 _holder 에 저장하는 재사용 헬퍼.
    _holder = {"content": ""}

    async def _agent_says(agent: Agent, moderator_msg: str, order_no: int, round_no: int,
                          stance: str | None = None, allow_pass: bool = False,
                          reply_to: tuple[str, str] | None = None):
        spoke = False
        async for kind, a, b in _stream_agent(
            db, session=session, agent_ids=agent_ids, agent=agent, round_no=round_no,
            order=order_no, moderator_msg=moderator_msg, history=history, mock=mock,
            stance=stance, allow_pass=allow_pass, reply_to=reply_to,
        ):
            if kind == "delta":
                yield {"type": "agent_delta", "agent_id": agent.id, "delta": a}
                if config.STREAM_TOKEN_DELAY_MS > 0:
                    await asyncio.sleep(config.STREAM_TOKEN_DELAY_MS / 1000)
            elif kind == "end":
                spoke = True
                _holder["content"] = b
                yield {"type": "agent_end", "agent_id": agent.id, "turn_id": a.id,
                       "content": b, "citations": [], "confidence": "unknown"}
            # kind == "pass": 발언하지 않음 (이벤트 없음)
        _holder["passed"] = not spoke

    async def _mod_record(text: str, order_no: int, round_no: int, meta: dict | None = None) -> None:
        await _save_turn(db, session_id=session.id, round_no=round_no, order=order_no, role="moderator", content=text, meta=meta)
        history.append({"round": round_no, "order": order_no, "role": "moderator", "agent_id": None, "name": "모더레이터", "content": text})

    # 모더레이터 발언도 에이전트와 동일하게 토큰 SSE 로 흘린다(moderator_delta* → moderator_end).
    # 최종 텍스트는 _mod_holder["text"] 에 담아 호출부가 후속 발화 프롬프트로 재사용한다.
    _mod_holder = {"text": ""}

    async def _mod_emit(order_no: int, round_no: int, *, user: str | None = None,
                        precomputed: str | None = None, system: str | None = None,
                        phase: str | None = None, follow_up: bool = False, probe: bool = False,
                        meta: dict | None = None, temperature: float = 0.6, max_tokens: int = 200,
                        fallback: str | None = None):
        parts: list[str] = []
        if precomputed is not None:
            # 템플릿/외부 LLM 결과 — 어절 단위로 흘려 streaming 흉내.
            for chunk in _word_chunks(precomputed):
                parts.append(chunk)
                yield {"type": "moderator_delta", "round": round_no, "delta": chunk}
                if config.STREAM_TOKEN_DELAY_MS > 0:
                    await asyncio.sleep(config.STREAM_TOKEN_DELAY_MS / 1000)
            text = precomputed.strip()
        else:
            try:
                async for delta in stream_chat(
                    system=system or mod_prompts.MODERATOR_SYSTEM,
                    messages=[{"role": "user", "content": user or ""}],
                    model=config.CHAT_MODEL, temperature=temperature, max_tokens=max_tokens, mock=mock,
                ):
                    parts.append(delta)
                    yield {"type": "moderator_delta", "round": round_no, "delta": delta}
                    if config.STREAM_TOKEN_DELAY_MS > 0:
                        await asyncio.sleep(config.STREAM_TOKEN_DELAY_MS / 1000)
            except Exception:  # noqa: BLE001 — 키 없음/네트워크 오류 시 fallback 으로
                pass
            text = _strip_quotes("".join(parts)).strip()
            if not text and fallback:
                # 스트림이 시작도 못 함 → fallback 을 한 번에 보내 빈 버블 방지.
                text = fallback.strip()
                yield {"type": "moderator_delta", "round": round_no, "delta": text}
        if not text:
            text = "..."
        await _mod_record(text, order_no, round_no, meta=meta)
        reflection.record(session.id, speaker_id=None, speaker_name="모더레이터", content=text, agent_ids=agent_ids)
        _mod_holder["text"] = text
        end_ev: dict[str, Any] = {"type": "moderator_end", "round": round_no, "content": text}
        if phase:
            end_ev["phase"] = phase
        if follow_up:
            end_ev["follow_up"] = True
        if probe:
            end_ev["probe"] = True
        yield end_ev

    # 한 Round = Phase A(질문) → B(순서답변) → C(티키타카) → D(개입) → 종료 follow-up (v0.2 §03).
    for r, step in enumerate(plan, 1):
        if _session_over():
            ended_early = True
            break
        subtopic = step["subtopic"]
        goal_q = step["goal_question"]
        yield {"type": "round_start", "round": r, "subtopic": subtopic, "goal_question": goal_q}
        order = 0

        # (제거됨) 진영 부여 stance_by — 라운드마다 비판/긍정 진영을 강제하던 찬반 메커니즘.
        # 사용자 요청으로 폐기: 참여자가 자기 경험을 말하는 대신 "~의견에 동의/반박"을 반복하게 만들어서.

        # ── Phase A — 모더레이터가 Round 질문 제시 (토큰 SSE) ────────────────
        async for ev in _mod_emit(
            order, r, phase="A", max_tokens=200,
            user=mod_prompts.SUBTOPIC_OPENING.format(round_no=r, subtopic=subtopic, goal_question=goal_q),
        ):
            yield ev
        mod_msg = _mod_holder["text"]
        order += 1

        # ── Phase B — 관심도 순 1차 답변 (plan 0026): 매 발화 전 LLM 재호출 → 관심도 1위 발화 → remaining 에서 제거 ──
        # 한 사람 1회씩 모두 답할 때까지 반복. 직전 발화는 lock 없음 (Phase B 는 1회 보장 = 자동 제외).
        last_text = ""
        phase_b_remaining = set(a.id for a in agents)
        while phase_b_remaining:
            if _session_over():
                ended_early = True
                break
            scores = await engagement.llm_engagement(agents_meta, subtopic, last_text, mock=mock) if config.USE_LLM_ENGAGEMENT else {}

            def _interest_b(a) -> float:
                return scores.get(a.id, {}).get("interest", 0.5)

            cands_b = sorted([a for a in agents if a.id in phase_b_remaining],
                             key=lambda a: -_interest_b(a))
            if not cands_b:
                break
            # 발화자 선정 시점 engagement SSE (phase="B"). 이미 1차 답변 끝낸 사람은
            # phase_b_remaining 에 없으므로 excluded 로 전달 → 프론트 카드 dim.
            eng_ev = _engagement_payload(
                r, "B", scores, agents, next_agent_id=cands_b[0].id,
                excluded_ids=[a.id for a in agents if a.id not in phase_b_remaining],
            )
            if eng_ev:
                yield eng_ev
            agent = cands_b[0]
            async for ev in _agent_says(agent, mod_msg, order, r):
                yield ev
            last_text = _holder["content"]
            phase_b_remaining.discard(agent.id)
            order += 1

        # ── Phase C — 쟁점 주도 토론 (plan 0026 재설계) ───────────────────────
        # cycle = 한 발화. 매 cycle 마다 LLM engagement 재호출 → 관심도 1위가 발화.
        # 발화 후 recent_speakers 에 추가 → 다음 PHASE_C_RECENT_LOCK 턴 동안 후보 제외.
        # 라운드 누적 발화는 ROUND_C_MAX_PER_AGENT 미만만 후보 (한 사람 독점 방지).
        probes_list: list[str] = list(step.get("probes") or [])
        segments: list[str | None] = probes_list if probes_list else [None]
        spoke_in_c: set[str] = set()
        c_total = 0
        # 라운드 누적 발화 카운터 (plan 0026) — Phase C 전체에서 한 사람 최대 ROUND_C_MAX_PER_AGENT 회.
        round_c_count: dict[str, int] = {a.id: 0 for a in agents}

        for seg_idx, seg_q in enumerate(segments):
            if ended_early or _session_over() or c_total >= config.MAX_TIKITAKA_UTTER:
                break
            ctrl = _CONTROLS.get(session.id, {})
            if ctrl.get("next_round"):
                ctrl["next_round"] = False
                break
            if seg_q is not None:
                recent_turns = [t for t in history if t["round"] == r and t["role"] == "agent"][-3:]
                recent = "\n".join(f"- {t['name']}: {t['content']}" for t in recent_turns) or "(아직 이번 라운드 발언 없음)"
                async for ev in _mod_emit(
                    order, r, phase="C", probe=True, temperature=0.6, max_tokens=160, fallback=seg_q,
                    user=mod_prompts.PROBE_INTRO.format(subtopic=subtopic, recent=recent, probe=seg_q),
                    meta={"kind": "phase_c_probe", "probe_source": seg_q},
                ):
                    yield ev
                probe_msg = _mod_holder["text"]
                order += 1
                active_q = probe_msg
            else:
                active_q = mod_msg

            seg_count: dict[str, int] = {a.id: 0 for a in agents}
            recent_speakers: list[str] = []  # segment 내 직전 N턴 발화 lock 추적
            last_text = active_q
            seg_utter = 0
            while seg_utter < config.PROBE_MAX_UTTER and c_total < config.MAX_TIKITAKA_UTTER and not ended_early:
                if _session_over():
                    ended_early = True
                    break
                if _CONTROLS.get(session.id, {}).get("next_round"):
                    _CONTROLS[session.id]["next_round"] = False
                    break
                scores = await engagement.llm_engagement(agents_meta, subtopic, last_text, mock=mock) if config.USE_LLM_ENGAGEMENT else {}

                def _interest(a) -> float:
                    return scores.get(a.id, {}).get("interest", 0.5)

                # 후보 필터 (plan 0026):
                # - 직전 PHASE_C_RECENT_LOCK 턴(default 2) 발화자 제외 → "내가 말했으면 다른 2명 말할 때까지 발화 못함"
                # - 라운드 누적 발화 ROUND_C_MAX_PER_AGENT 미만 → "찬반토론 라운드 최대 2회"
                # - 세그먼트 호환: MAX_C_PER_AGENT(default 2) 미만 (보통 recent_lock 이 더 엄격)
                forbidden = set(recent_speakers[-config.PHASE_C_RECENT_LOCK:])
                cands = [
                    a for a in agents
                    if a.id not in forbidden
                    and seg_count[a.id] < config.MAX_C_PER_AGENT
                    and round_c_count[a.id] < config.ROUND_C_MAX_PER_AGENT
                ]
                # 관심도 내림차순 (1순위 키). 발화 균등성은 위 필터로만 보장.
                cands.sort(key=lambda a: -_interest(a))
                if not cands:
                    break  # 전원 lock 또는 라운드 상한 도달 → 다음 세그먼트로

                # Phase C 에서 후보가 아닌 사람(직전 lock 또는 라운드 누적 상한 도달)은
                # excluded 로 전달 → 프론트 카드 dim. seg_count 도달도 포함.
                excluded = [
                    a.id for a in agents
                    if a.id in forbidden
                    or seg_count[a.id] >= config.MAX_C_PER_AGENT
                    or round_c_count[a.id] >= config.ROUND_C_MAX_PER_AGENT
                ]
                eng_ev = _engagement_payload(r, "C", scores, agents, next_agent_id=cands[0].id,
                                             probe_index=seg_idx + 1, probe_total=len(segments),
                                             excluded_ids=excluded)
                if eng_ev:
                    yield eng_ev

                # cycle = 한 사람 발화 (관심도 1위)
                agent = cands[0]
                # (제거됨) 찬반 메커니즘 — stance(진영) + reply_to(직전 화자에 직접 동의/반박) 미사용.
                # 사용자 요청: 토론처럼 동의/반박을 반복하지 말고 각자 사회자 질문에 자기 경험으로 답하게 한다.
                async for ev in _agent_says(agent, active_q, order, r, allow_pass=True):
                    yield ev
                if _holder.get("passed"):
                    # 패스 — 같은 사람이 다음 cycle 첫 후보로 다시 뽑히지 않게 lock 에 넣음
                    recent_speakers.append(agent.id)
                    continue
                last_text = _holder["content"]
                recent_speakers.append(agent.id)
                spoke_in_c.add(agent.id)
                seg_count[agent.id] += 1
                round_c_count[agent.id] += 1
                order += 1
                seg_utter += 1
                c_total += 1

        # ── Phase D — Phase C 동안 침묵한 에이전트 강제 호명 (Follow-up 1) ──
        if not ended_early:
            silent = [a for a in agents if a.id not in spoke_in_c]
            for di, agent in enumerate(silent[: config.PHASE_D_MAX_PULLINS]):
                if _session_over():
                    ended_early = True
                    break
                q = cascade.inactive_prompt(name_by[agent.id], idx=di)
                async for ev in _mod_emit(order, r, precomputed=q, phase="D", follow_up=True,
                                          meta={"kind": "phase_d_pull"}):
                    yield ev
                q = _mod_holder["text"]
                order += 1
                async for ev in _agent_says(agent, q, order, r):  # 질문에 답하는 세션 — 진영 없음
                    yield ev
                order += 1

        # ── Round 종료 — 동적 follow-up 1회 (v0.3): 순서답변+티키타카를 보고 부족한 지점을 LLM 이 1개 질문 ──
        if not ended_early:
            round_lines = "\n".join(
                f"- {t['name']}: {t['content']}" for t in history if t["round"] == r and t["role"] == "agent"
            )
            fq = await cascade.dynamic_round_followup(goal_q, subtopic, round_lines, mock=mock)
            if fq:
                async for ev in _mod_emit(order, r, precomputed=fq, follow_up=True,
                                          meta={"kind": "follow_up_dynamic"}):
                    yield ev
                fq = _mod_holder["text"]
                order += 1
                # 관심도 높은 2명이 응답 (라운드당 1회 한정).
                fscores = await engagement.llm_engagement(agents_meta, fq, fq, mock=mock) if config.USE_LLM_ENGAGEMENT else {}
                responders = sorted(agents, key=lambda a: fscores.get(a.id, {}).get("interest", 0.5), reverse=True)[:2]
                eng_ev = _engagement_payload(r, "followup", fscores, agents,
                                             next_agent_id=responders[0].id if responders else None)
                if eng_ev:
                    yield eng_ev
                for ag in responders:
                    if _session_over():
                        break
                    async for ev in _agent_says(ag, fq, order, r):  # 질문에 답하는 세션 — 진영 없음
                        yield ev
                    order += 1

        summary = "\n".join(f"- {t['name']}: {t['content']}" for t in history if t["round"] == r and t["role"] == "agent")
        round_summaries.append({"round": r, "subtopic": subtopic, "summary": summary})
        yield {"type": "round_end", "round": r, "summary": summary}

        if ended_early:
            break

        # 사용자 개입 창 (30초, Round당 최대 2회) — 개입 시 전원 응답 (§10)
        if allow_user_intervention and r < len(plan):
            interventions = 0
            while interventions < config.INTERVENTION_MAX_PER_ROUND:
                waiter = _Waiter(round_no=r, order=order)
                _WAITERS[session.id] = waiter
                yield {"type": "user_turn_required", "round": r, "deadline_seconds": int(timeout),
                       "remaining": config.INTERVENTION_MAX_PER_ROUND - interventions}
                # 디버그(2026-05-29): "안 정해도 자동 진행" 버그가 timeout/외부 sentinel 중 어느 쪽인지 추적.
                print(f"[FGI] 개입 대기 진입 — session={session.id[:8]} round={r} "
                      f"timeout={timeout}s slot={interventions + 1}/{config.INTERVENTION_MAX_PER_ROUND}", flush=True)
                try:
                    user_msg = await asyncio.wait_for(waiter.queue.get(), timeout)
                except asyncio.TimeoutError:
                    print(f"[FGI] 개입 대기 timeout — session={session.id[:8]} round={r} ({timeout}s 경과)", flush=True)
                    _WAITERS.pop(session.id, None)
                    break
                finally:
                    _WAITERS.pop(session.id, None)
                # 어떤 신호로 풀렸는지 stdout 확인.
                _signal = "skip" if user_msg == _SKIP_SENTINEL else "intervene"
                print(f"[FGI] 개입 대기 풀림 — session={session.id[:8]} round={r} signal={_signal}", flush=True)
                if user_msg == _SKIP_SENTINEL:
                    break  # 사용자가 '개입 안 함' 선택 → 다음 라운드로
                await db.commit()
                interventions += 1
                order += 1
                history.append({"round": r, "order": waiter.order, "role": "user", "agent_id": None, "name": "기업 관계자", "content": user_msg})
                reflection.record(session.id, speaker_id=None, speaker_name="기업 관계자", content=user_msg, agent_ids=agent_ids)
                # 개입 질문에 참여자 전원이 우선 응답 (engagement 점수 순)
                scores = await engagement.llm_engagement(agents_meta, user_msg, user_msg, mock=mock) if config.USE_LLM_ENGAGEMENT else {}
                ordered = sorted(agents, key=lambda ag: scores.get(ag.id, {}).get("interest", 0.5), reverse=True)
                eng_ev = _engagement_payload(r, "intervention", scores, agents,
                                             next_agent_id=ordered[0].id if ordered else None)
                if eng_ev:
                    yield eng_ev
                for resp_agent in ordered:
                    async for kind, a, b in _stream_agent(db, session=session, agent_ids=agent_ids, agent=resp_agent, round_no=r, order=order,
                                                          moderator_msg=user_msg, history=history, mock=mock):
                        if kind == "delta":
                            yield {"type": "agent_delta", "agent_id": resp_agent.id, "delta": a}
                            if config.STREAM_TOKEN_DELAY_MS > 0:
                                await asyncio.sleep(config.STREAM_TOKEN_DELAY_MS / 1000)
                        elif kind == "end":
                            yield {"type": "agent_end", "agent_id": resp_agent.id, "turn_id": a.id,
                                   "content": b, "citations": [], "confidence": "unknown"}
                    order += 1

    # 세션 종료 → 기억 영속 + 구조화 보고서
    n_done_rounds = len(round_summaries)
    await memory.persist_fgi_memories(db, session_id=session.id, topic=session.topic, agent_ids=agent_ids, mock=mock)
    duration_min = max(1, round((_now() - started_dt).total_seconds() / 60))

    all_turns = (await db.execute(
        select(FGITurn).where(FGITurn.session_id == session.id)
        .order_by(FGITurn.round, FGITurn.order_in_round, FGITurn.created_at)
    )).scalars().all()
    # plan 0029 — agents_persona(이름→한 줄 페르소나 요약)를 넘기면 인사이트별 검증 채팅이
    # 자동 생성된다. intro_ko 우선, 없으면 persona_full_prompt 앞 200자.
    agents_persona = {
        name_by[a.id]: (a.intro_ko or (a.persona_full_prompt or "")[:200] or "")
        for a in agents
    }
    rep = await report.build_report(
        topic=session.topic, turns=list(all_turns), name_by_agent=name_by,
        round_summaries=round_summaries, n_agents=len(agents), n_rounds=n_done_rounds,
        duration_min=duration_min, agents_persona=agents_persona, mock=mock,
    )

    session.minutes_md = json.dumps(rep, ensure_ascii=False)
    session.status = "completed"
    session.ended_at = _now()
    db.add(session)
    await db.commit()
    reflection.clear(session.id)
    _CONTROLS.pop(session.id, None)

    yield {"type": "session_end", "report": rep, "minutes_md": session.minutes_md, "ended_early": ended_early}
