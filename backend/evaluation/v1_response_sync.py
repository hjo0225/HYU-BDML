"""V1 응답 동기화율 — agent 답변 vs 원문 답변 cosine similarity.

EVAL_SPEC.md §1 정합. 임계 ≥0.80 success / 0.60~0.80 warning / <0.60 error.
"""
from __future__ import annotations

import math
from typing import Any

from embedding.embedder import embed
from .stimuli import Question, v1_questions


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 1536-dim 벡터의 코사인 유사도. -1~1."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    return dot / denom if denom else 0.0


def compute_v1(
    *,
    agent_answers: dict[str, str],
    scratch: dict[str, Any],
    questions: list[Question] | None = None,
    synthetic_embeddings: bool | None = None,
) -> dict[str, Any]:
    """V1 sync score 계산.

    Args:
        agent_answers: {qid: agent_answer_text}. runner 가 LLM 호출로 채워줌.
        scratch: agent.scratch dict (원문 답변 소스).
        questions: 평가 자극. 기본 v1_questions().
        synthetic_embeddings: embed 함수에 그대로 전달.

    Returns:
        {sync: float, n_eval: int, by_question: [{qid, agent, original, cosine}], skipped: [qid]}
    """
    qs = questions if questions is not None else v1_questions()
    by_q: list[dict[str, Any]] = []
    skipped: list[str] = []

    for q in qs:
        if not q.scratch_key:
            skipped.append(q.qid)
            continue
        original = scratch.get(q.scratch_key) if isinstance(scratch, dict) else None
        agent_ans = agent_answers.get(q.qid)
        if not original or not agent_ans:
            skipped.append(q.qid)
            continue
        emb_agent = embed(agent_ans, synthetic=synthetic_embeddings)
        emb_orig = embed(original, synthetic=synthetic_embeddings)
        sim = cosine_similarity(emb_agent, emb_orig)
        by_q.append({
            "qid": q.qid,
            "agent": agent_ans,
            "original": original,
            "cosine": round(sim, 4),
        })

    sync = sum(b["cosine"] for b in by_q) / len(by_q) if by_q else 0.0
    return {
        "sync": round(sync, 4),
        "n_eval": len(by_q),
        "by_question": by_q,
        "skipped": skipped,
    }
