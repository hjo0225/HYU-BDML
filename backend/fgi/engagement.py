"""engagement score 동적 발화자 선정 (plan 0008 v2 · item 4 · §13).

score = 0.4·topic_relevance + 0.3·recency + 0.2·reaction + 0.1·random
  - topic_relevance: 에이전트 avg_embedding ↔ 현재 소주제 임베딩 코사인
  - recency: 마지막 발화 이후 경과 턴 (오래 침묵할수록 ↑)
  - reaction: 에이전트 avg_embedding ↔ 직전 발화자 avg_embedding 코사인 (유사할수록 반응 의지 ↑)
  - random: 자연스러운 비결정성

추가 임베딩 호출은 소주제당 1회뿐 — 에이전트/발화자 임베딩은 기적재 avg_embedding 재사용.
키 없으면 결정적 합성 임베딩 폴백.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from dataclasses import dataclass

from fgi import config
from services.llm_client import chat_completion


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.5
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.5
    return (dot / (na * nb) + 1.0) / 2.0  # [-1,1] → [0,1]


def _synth_embedding(text: str, dim: int = 1536) -> list[float]:
    """결정적 합성 임베딩 — 키 없을 때 폴백."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [((h[i % len(h)] / 255.0) - 0.5) for i in range(dim)]
    n = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / n for v in vals]


async def embed_text(text: str, *, mock: bool | None = None) -> list[float]:
    """소주제 임베딩 — OpenAI text-embedding-3-small, 키 없으면 합성."""
    key = os.getenv("OPENAI_API_KEY", "")
    use_mock = mock if mock is not None else not (key and not key.startswith(("dummy", "test")))
    if use_mock:
        return _synth_embedding(text)
    try:
        import asyncio
        import openai

        def _call() -> list[float]:
            client = openai.OpenAI(api_key=key)
            r = client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
            return r.data[0].embedding

        return await asyncio.to_thread(_call)
    except Exception:  # noqa: BLE001
        return _synth_embedding(text)


_ENG_SYSTEM = "당신은 FGI 진행을 돕는 분석기입니다. 각 참여자의 발언 의향을 추정합니다."


async def llm_engagement(
    agents_meta: list[dict],          # [{agent_id, name, summary}]
    subtopic: str,
    last_utterance: str,
    *,
    mock: bool | None = None,
) -> dict[str, dict[str, float]]:
    """1회 LLM 호출로 참여자별 self-report 관심도(interest)와 직전 발화 반응 가능성(reaction)을
    0~1 로 일괄 추정 (§13 LLM 추정 + self-report 앙상블). 실패/키없음 시 빈 dict → 임베딩 프록시 사용."""
    # LLM(특히 mini)이 긴 UUID 키를 정확히 되돌려주지 못해 일부 참여자가 누락→0.5 폴백되는
    # 문제를 피하려고, 프롬프트에는 짧은 라벨(p1..pN)을 쓰고 응답을 다시 agent_id 로 매핑한다.
    labels = {f"p{i + 1}": a for i, a in enumerate(agents_meta)}
    roster = "\n".join(
        f"- {lbl}: {a['name']} — {a.get('summary', '')[:80]}" for lbl, a in labels.items()
    )
    user = (
        f"현재 소주제: {subtopic}\n직전 발언: \"{last_utterance or '(없음)'}\"\n참여자:\n{roster}\n\n"
        "각 참여자가 ① 지금 발언하고 싶어할 관심도(interest) ② 직전 발언에 동의·반박으로 반응할 가능성"
        "(reaction)을 각각 0~1 로 추정하세요. 참여자 전원(p1~p"
        f"{len(labels)})을 빠짐없이 포함하고, 서로 다른 값으로 구분되게 매기세요. JSON 만 출력: "
        '{"p1": {"interest": 0.0, "reaction": 0.0}, ...}'
    )
    try:
        raw = (await chat_completion(system=_ENG_SYSTEM, user=user, model=config.ENGAGEMENT_MODEL,
                                     temperature=0.3, max_tokens=600, mock=mock)).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
        ordered_vals = [v for v in data.values() if isinstance(v, dict)]
        out: dict[str, dict[str, float]] = {}
        for i, (lbl, a) in enumerate(labels.items()):
            # 모델이 라벨(p1)·UUID·이름 중 무엇으로 키를 돌려주든 매칭. 그래도 못 찾으면
            # 응답 순서(roster 순)대로 i 번째 값을 폴백 사용 — 균일 0.5 로 죽지 않게.
            d = None
            for key in (lbl, a["agent_id"], a.get("name")):
                if key and isinstance(data.get(key), dict):
                    d = data[key]
                    break
            if d is None and i < len(ordered_vals):
                d = ordered_vals[i]
            d = d or {}
            out[a["agent_id"]] = {
                "interest": max(0.0, min(1.0, float(d.get("interest", 0.5)))),
                "reaction": max(0.0, min(1.0, float(d.get("reaction", 0.5)))),
            }
        return out
    except Exception:  # noqa: BLE001
        return {}


async def novelty(recent_text: str, prior_text: str, *, mock: bool | None = None) -> float:
    """직전 발화들의 새로운 정보량 (§11). prior 와 유사할수록 novelty↓. prior 없으면 1.0."""
    if not prior_text.strip():
        return 1.0
    e1, e2 = await embed_text(recent_text, mock=mock), await embed_text(prior_text, mock=mock)
    # cosine 은 [0,1] 시프트된 값 → 1-cos 으로 신규성. 0.5(무상관)=novelty 0.5
    return max(0.0, min(1.0, 1.0 - cosine(e1, e2)))


@dataclass
class Selection:
    agent_id: str
    score: float
    breakdown: dict[str, float]


def _turns_since(agent_id: str, history: list[dict], plateau: float = 3.0) -> float:
    for i, t in enumerate(reversed(history)):
        if t.get("agent_id") == agent_id:
            return min(i / plateau, 1.0)
    return 1.0  # 한 번도 발언 안 함 → 최대 우선


def select_next_speaker(
    agents: list[dict],            # [{agent_id, embedding}]
    subtopic_emb: list[float],
    history: list[dict],           # [{agent_id, ...}] 시간순
    last_speaker_emb: list[float] | None,
    *,
    llm_scores: dict[str, dict[str, float]] | None = None,  # {id:{interest,reaction}} (LLM)
    rng: random.Random | None = None,
) -> Selection:
    r = rng or random
    ls = llm_scores or {}
    best: Selection | None = None
    for a in agents:
        aid = a["agent_id"]
        emb = a.get("embedding")
        relevance = cosine(emb, subtopic_emb)
        recency = _turns_since(aid, history)
        # reaction: LLM 추정 우선, 없으면 임베딩 프록시
        if aid in ls:
            reaction = ls[aid]["reaction"]
        else:
            reaction = cosine(emb, last_speaker_emb) if last_speaker_emb else 0.5
        rand = r.random()
        base = (
            config.W_RELEVANCE * relevance + config.W_RECENCY * recency
            + config.W_REACTION * reaction + config.W_RANDOM * rand
        )
        # self-report 관심도 앙상블 (§13 병행)
        if aid in ls:
            total = (1 - config.SELF_REPORT_WEIGHT) * base + config.SELF_REPORT_WEIGHT * ls[aid]["interest"]
        else:
            total = base
        if best is None or total > best.score:
            best = Selection(
                agent_id=aid, score=total,
                breakdown={"relevance": round(relevance, 3), "recency": round(recency, 3),
                           "reaction": round(reaction, 3), "random": round(rand, 3),
                           "interest": round(ls.get(aid, {}).get("interest", -1), 3), "total": round(total, 3)},
            )
    assert best is not None
    return best
