"""engagement score 공식 — 발화자 선정의 정량 근거.

본 스파이크에서 검증할 핵심 가설:
  "(relevance × 0.5) + (recency × 0.3) + (extraversion × 0.2) 의 가중합이
   archive 의 round-robin 보다 라운드마다 다양한 발화자를 선정하면서도
   주제 관련성을 유지한다."

각 항은 0~1 정규화돼 있어 가중합도 0~1 사이에 떨어진다. 가중치는
ADR-0005 의 hyperparameter 후보로 기록.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpeakerSelection:
    agent_id: str
    score: float
    breakdown: dict[str, float]   # {"relevance": ..., "recency": ..., "extraversion": ..., "total": ...}


def turns_since_last_spoke(agent_id: str, history: list[dict]) -> int:
    """history 끝에서부터 거꾸로 세어 agent_id 가 마지막으로 발언한 후 몇 turn 이 지났는지.

    한 번도 발언한 적 없으면 매우 큰 값(=무한대 대용) 반환.
    """
    for i, turn in enumerate(reversed(history)):
        if turn.get("speaker_id") == agent_id:
            return i
    return 9999


def recency_priority(turns_since: int, plateau: float = 3.0) -> float:
    """오래 안 발언한 사람일수록 높은 점수.

    turns_since=0(직전 발언) → 0.0, plateau 이상 → 1.0 로 선형 증가.
    """
    return min(turns_since / plateau, 1.0)


def cosine(a: list[float], b: list[float]) -> float:
    """OpenAI 임베딩(1536d) 코사인 유사도. -1~1 → 0~1 로 시프트."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    cs = dot / (na * nb)
    return (cs + 1.0) / 2.0   # [-1,1] → [0,1]


# 검증할 가중치 후보 (ADR-0005 에서 결과로 비교)
DEFAULT_WEIGHTS = {"relevance": 0.5, "recency": 0.3, "extraversion": 0.2}


def select_next_speaker(
    candidates: list[dict],
    moderator_emb: list[float],
    history: list[dict],
    weights: dict[str, float] | None = None,
) -> SpeakerSelection:
    """가중합 최댓값을 가진 candidate 선정.

    candidates: [{ "agent_id", "summary_emb", "extraversion" }, ...]
    """
    w = weights or DEFAULT_WEIGHTS
    best: SpeakerSelection | None = None

    for c in candidates:
        relevance = cosine(c["summary_emb"], moderator_emb)
        recency = recency_priority(turns_since_last_spoke(c["agent_id"], history))
        extraversion = c["extraversion"]
        total = (
            w["relevance"] * relevance
            + w["recency"] * recency
            + w["extraversion"] * extraversion
        )
        sel = SpeakerSelection(
            agent_id=c["agent_id"],
            score=total,
            breakdown={
                "relevance": relevance,
                "recency": recency,
                "extraversion": extraversion,
                "total": total,
            },
        )
        if best is None or sel.score > best.score:
            best = sel

    assert best is not None
    return best
