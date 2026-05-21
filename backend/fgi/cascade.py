"""follow-up cascade — 토큰 1차 필터 → LLM 4차원 rubric 2차 (plan 0008 v2 · §03~06).

1차(무료): 직전 발화 토큰<N(기본 25) 또는 hedging 마커 → 모호 확정.
2차(LLM): 1차 통과한 발화만 4차원 rubric 채점, total<2 → 모호 + 빠진 차원별 후속질문.
키 없으면 결정적 휴리스틱 폴백.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from fgi import config
from fgi.prompts.cascade import (
    DYNAMIC_FOLLOWUP_SYSTEM,
    DYNAMIC_FOLLOWUP_USER,
    FOLLOWUP_BY_DIMENSION,
    INACTIVE_PROMPTS,
    RUBRIC_SYSTEM,
    RUBRIC_USER,
)
from services.llm_client import chat_completion

_HEDGING = re.compile(r"잘\s*모르겠|사람마다\s*다|케바케|케이스\s*바이|좋은\s*것\s*같|그냥\s*(좋|싫)|글쎄", re.I)


def _pick(variants: list[str], idx: int) -> str:
    """변형 리스트에서 idx 로 순환 선택 — 동일 질문 반복 방지."""
    return variants[idx % len(variants)] if variants else ""


def _followup_for(dimension: str, idx: int) -> str:
    return _pick(FOLLOWUP_BY_DIMENSION.get(dimension, FOLLOWUP_BY_DIMENSION["example"]), idx)


@dataclass
class CascadeResult:
    need_followup: bool
    stage: str                 # 'token_filter' | 'llm_rubric' | 'pass'
    reason: str
    follow_up: str | None = None  # 트리거 시 사회자가 던질 후속 질문


def _approx_tokens(text: str) -> int:
    """한국어 근사 토큰 — 문자 수 기반(공백 제외) (§04: 30자≈20~30토큰)."""
    return len(re.sub(r"\s", "", text))


def token_filter(utterance: str, *, variant: int = 0) -> CascadeResult | None:
    """1차. 모호 확정 시 CascadeResult, 보류 시 None(→2차)."""
    if _approx_tokens(utterance) < config.TOKEN_THRESHOLD_N:
        return CascadeResult(True, "token_filter", f"발화 너무 짧음(<{config.TOKEN_THRESHOLD_N})",
                             _followup_for("example", variant))
    m = _HEDGING.search(utterance)
    if m:
        return CascadeResult(True, "token_filter", f"hedging '{m.group()}'",
                             _followup_for("reasoning", variant))
    return None


def _mock_rubric(question: str, utterance: str) -> dict:
    scores = {
        "example": 1 if re.search(r"지난|예전|친구|그때|한번|적이", utterance) else 0,
        "specifics": 1 if re.search(r"\d|번|시간|자주|개월|원|%", utterance) else 0,
        "reasoning": 1 if re.search(r"왜냐|때문|라서|어서|니까", utterance) else 0,
        "relevance": 1,
    }
    total = sum(scores.values())
    missing = next((k for k, v in scores.items() if v == 0), "example")
    return {"scores": scores, "total": total, "vague": total < config.SPECIFICITY_CUTOFF,
            "missing_dimension": missing, "follow_up_hint": ""}


async def judge_specificity(question: str, utterance: str, *, mock: bool | None = None) -> dict:
    try:
        raw = (await chat_completion(
            system=RUBRIC_SYSTEM, user=RUBRIC_USER.format(question=question, utterance=utterance),
            model=config.CHAT_MODEL, temperature=0.0, max_tokens=160, mock=mock,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        # mock 모드는 chat_completion 이 페르소나 더미를 주므로 JSON 파싱 실패 → 휴리스틱
        data = json.loads(raw)
        if "total" not in data:
            raise ValueError
        return data
    except Exception:  # noqa: BLE001
        return _mock_rubric(question, utterance)


def _usable_hint(hint: str) -> bool:
    """rubric 이 제안한 follow_up_hint 가 바로 던질 만한 질문 형태인지."""
    h = (hint or "").strip()
    return len(h) >= 6 and (h.endswith("?") or h[-1] in "요까죠")


async def needs_followup(question: str, utterance: str, *, mock: bool | None = None,
                         variant: int = 0) -> CascadeResult:
    """cascade 결합 — 1차 통과 시에만 2차 LLM. variant 로 후속 질문 변형을 순환한다."""
    first = token_filter(utterance, variant=variant)
    if first is not None:
        return first
    rubric = await judge_specificity(question, utterance, mock=mock)
    if rubric.get("vague"):
        miss = rubric.get("missing_dimension", "example")
        # judge 가 맥락형 질문을 제안했으면 우선 사용, 아니면 차원별 변형 템플릿.
        hint = str(rubric.get("follow_up_hint", "")).strip()
        fu = hint if _usable_hint(hint) else _followup_for(miss, variant)
        return CascadeResult(True, "llm_rubric", f"구체성 부족(total={rubric.get('total')}, 빠진 차원={miss})", fu)
    return CascadeResult(False, "pass", f"구체성 충분(total={rubric.get('total')})", None)


def inactive_agents(history: list[dict], agent_ids: list[str]) -> list[str]:
    """§05-a — 최활발 발화자의 INACTIVE_RATIO 미만으로 발언한 에이전트 id 목록."""
    counts = {aid: 0 for aid in agent_ids}
    for t in history:
        if t.get("agent_id") in counts:
            counts[t["agent_id"]] += 1
    if not counts:
        return []
    mx = max(counts.values())
    if mx == 0:
        return []
    threshold = mx * config.INACTIVE_RATIO
    return [aid for aid, c in counts.items() if c < threshold]


async def dynamic_round_followup(
    goal_question: str, subtopic: str, transcript: str, *, mock: bool | None = None,
) -> str:
    """라운드 종료 시 LLM 이 대화 전체를 보고 부족한 지점 1개를 짚는 후속 질문. 없으면 빈 문자열."""
    try:
        raw = (await chat_completion(
            system=DYNAMIC_FOLLOWUP_SYSTEM,
            user=DYNAMIC_FOLLOWUP_USER.format(subtopic=subtopic, goal_question=goal_question, transcript=transcript),
            model=config.CHAT_MODEL, temperature=0.4, max_tokens=120, mock=mock,
        )).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return str(json.loads(raw).get("follow_up", "")).strip()
    except Exception:  # noqa: BLE001 — 키 없음/파싱 실패 시 후속 생략
        return ""


def inactive_prompt(name: str, idx: int = 0) -> str:
    """비활동 참가자 호명 — idx 로 변형을 순환해 같은 멘트 반복을 피한다."""
    return _pick(INACTIVE_PROMPTS, idx).format(name=name)
