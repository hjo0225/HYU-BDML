"""인사이트 보고서 생성 — FGI transcript → 구조화 JSON (plan 0008 v2 · §14).

세션 종료 시 호출. meta + key_insights + agent_perspectives + round_analysis + action_items.
LLM 으로 인사이트/관점/액션 + 라운드별 분석 요약을 추출한다. round_analysis 의 title 은
플랜의 소주제(정확), summary 는 LLM 분석(없으면 간결 폴백), meta 는 엔진이 모은 값.
키 없으면 결정적 mock 폴백. (블러/과금 없음 — 데모는 전체 공개)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from database import FGITurn
from fgi.prompts.report import REPORT_SYSTEM, REPORT_USER
from services.llm_client import chat_completion

_REPORT_MODEL = "gpt-4o-mini"


def _speaker(turn: FGITurn, name_by_agent: dict[str, str]) -> str:
    if turn.role == "moderator":
        return "모더레이터"
    if turn.role == "user":
        return "기업 관계자(개입)"
    return name_by_agent.get(turn.agent_id or "", "참여자")


def _format_transcript(turns: list[FGITurn], name_by_agent: dict[str, str]) -> str:
    return "\n".join(f"[R{t.round}] {_speaker(t, name_by_agent)}: {t.content}" for t in turns)


def _first_quote(turns: list[FGITurn], agent_id: str) -> str:
    for t in turns:
        if t.role == "agent" and t.agent_id == agent_id and len(t.content) > 8:
            return t.content[:120]
    return ""


def _fallback_round_summary(rs: dict) -> str:
    """LLM 라운드 요약이 없을 때 폴백 — 발언 원문 덤프 대신 간결한 한 줄.

    엔진이 모은 rs['summary']는 '- 이름: 발언' 줄 모음(원문 덤프)이라, 분석 요약이
    없을 경우엔 참여 인원만 추려 간결히 표시한다(데모/키 없음/LLM 실패 시).
    """
    raw = (rs.get("summary") or "").strip()
    n = raw.count("\n- ") + (1 if raw.startswith("- ") else 0)
    sub = rs.get("subtopic", "")
    if n:
        return f"{n}명의 참여자가 '{sub}'에 대해 의견을 나눴습니다."
    return f"'{sub}'에 대한 논의가 진행되었습니다."


def _mock_report(turns: list[FGITurn], name_by_agent: dict[str, str]) -> dict:
    names = list(dict.fromkeys(name_by_agent.values()))
    return {
        "key_insights": [
            {"title": "참여자별 우선순위가 엇갈림", "description": "비용·경험·편의 사이 트레이드오프가 반복 언급됨.", "sources": names[:2]},
            {"title": "감정적 요인이 결정적 트리거", "description": "정량 불만보다 '나를 이해 못 한다'는 감정이 이탈을 좌우.", "sources": names[1:3]},
            {"title": "재방문 동기에 일부 공감대 형성", "description": "핵심 개선 시 재방문 의향이 상승.", "sources": names[:1]},
        ],
        "agent_perspectives": [
            {"name": name_by_agent.get(aid, "참여자"), "stance": "의견 제시",
             "key_quote": _first_quote(turns, aid) or "주제에 대한 경험을 공유함"}
            for aid in dict.fromkeys(t.agent_id for t in turns if t.role == "agent" and t.agent_id)
        ],
        "action_items": [
            {"title": "핵심 불만 요인 우선 개선", "description": "가장 많이 지적된 마찰을 먼저 해소.", "expected_effect": "재방문률 상승"},
            {"title": "리텐션 프로그램 시범 운영", "description": "재방문 동기를 높이는 혜택 설계.", "expected_effect": "이탈 방지"},
            {"title": "후속 정량 조사", "description": "이번 가설을 설문으로 검증.", "expected_effect": "의사결정 신뢰도 ↑"},
        ],
    }


async def build_report(
    *,
    topic: str,
    turns: list[FGITurn],
    name_by_agent: dict[str, str],
    round_summaries: list[dict],
    n_agents: int,
    n_rounds: int,
    duration_min: int | None,
    mock: bool | None = None,
) -> dict:
    """구조화 인사이트 보고서 dict. meta·round title 은 엔진/플랜 값, 인사이트·라운드 요약은 LLM(실패 시 mock)."""
    transcript = _format_transcript(turns, name_by_agent)
    names = ", ".join(dict.fromkeys(name_by_agent.values()))
    # 라운드 구성(번호→소주제) 을 LLM 에 함께 줘서 라운드별 분석 요약을 정렬되게 생성.
    round_plan = "\n".join(
        f"라운드 {rs['round']}: {rs.get('subtopic', '')}" for rs in round_summaries
    ) or "(라운드 정보 없음)"
    llm_part: dict
    llm_round_summary: dict[int, str] = {}      # {round: 분석 요약}
    try:
        raw = (await chat_completion(
            system=REPORT_SYSTEM,
            user=REPORT_USER.format(
                topic=topic, agent_names=names, transcript=transcript, round_plan=round_plan,
            ),
            model=_REPORT_MODEL, temperature=0.4, max_tokens=1800, mock=mock,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        if not data.get("key_insights"):
            raise ValueError
        llm_part = {
            "key_insights": data.get("key_insights", []),
            "agent_perspectives": data.get("agent_perspectives", []),
            "action_items": data.get("action_items", []),
        }
        for ra in data.get("round_analysis", []) or []:
            try:
                s = (ra.get("summary") or "").strip()
                if s:
                    llm_round_summary[int(ra["round"])] = s
            except (KeyError, TypeError, ValueError):
                continue
    except Exception:  # noqa: BLE001
        llm_part = _mock_report(turns, name_by_agent)

    return {
        "topic": topic,
        "meta": {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "n_agents": n_agents,
            "n_rounds": n_rounds,
            "duration_min": duration_min,
        },
        # title 은 플랜의 소주제(정확), summary 는 LLM 분석 요약(없으면 간결 폴백).
        "round_analysis": [
            {
                "round": rs["round"],
                "title": rs.get("subtopic", f"Round {rs['round']}"),
                "summary": llm_round_summary.get(rs["round"]) or _fallback_round_summary(rs),
            }
            for rs in round_summaries
        ],
        **llm_part,
    }
