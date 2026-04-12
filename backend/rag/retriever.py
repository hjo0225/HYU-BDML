"""
B-3: Retriever (회상 RAG)
한 페르소나의 메모리 중 focal_point와 관련 있는 N개를 반환.
원본 genagents의 retrieve 함수를 numpy 위에서 재현.
"""

import numpy as np
from .embedder import embed


def cos_sim(a, b) -> float:
    a, b = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def normalize_minmax(values: list[float]) -> list[float]:
    """min-max 정규화. 모든 값이 같으면 모두 0.5 (원본 동작)."""
    if not values:
        return []
    mn, mx = min(values), max(values)
    if mx == mn:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def retrieve(
    persona: dict,
    focal_point: str,
    n_count: int = 25,
    hp: tuple = (0, 1, 0.5),
    stochastic: bool = False,
    stochastic_temperature: float = 0.5,
) -> list[dict]:
    """
    한 페르소나의 메모리 중 focal_point와 관련된 n_count개 반환.

    입력:
    - persona: 페르소나 JSON 로드된 dict (memories에 embedding 필수)
    - focal_point: query 문자열 (대화 맥락)
    - n_count: 반환할 메모리 수 (메모리 총수보다 크면 전수 반환)
    - hp: (recency_w, relevance_w, importance_w) 가중치
    - stochastic: True면 top-2k에서 softmax sampling
    - stochastic_temperature: stochastic sampling 온도

    출력: list of dict. 각 dict는 메모리 원본 + score, score_breakdown 추가

    예외:
    - persona["memories"]에 embedding 없는 메모리가 있으면 ValueError
    """
    memories = persona.get("memories", [])

    if not memories:
        return []

    # embedding 유효성 검사
    for m in memories:
        if "embedding" not in m:
            raise ValueError(
                f"category='{m.get('category')}' 메모리에 embedding이 없습니다. "
                "add_embeddings.py를 먼저 실행하세요."
            )

    # 메모리 1개 엣지 케이스
    if len(memories) == 1:
        m = dict(memories[0])
        query_vec = embed(focal_point)
        rel = cos_sim(query_vec, m["embedding"])
        imp = m["importance"] / 100.0
        final = hp[0] * 0.0 + hp[1] * rel + hp[2] * imp
        m["score"] = final
        m["score_breakdown"] = {
            "relevance": rel,
            "importance_norm": imp,
            "recency": 0.0,
            "final": final,
        }
        return [m]

    # query 임베딩
    query_vec = embed(focal_point)

    # 각 메모리 점수 계산 (raw)
    relevances = [cos_sim(query_vec, m["embedding"]) for m in memories]
    importances = [m["importance"] / 100.0 for m in memories]
    recencies = [0.0] * len(memories)

    # min-max 정규화
    relevances_norm = normalize_minmax(relevances)
    importances_norm = normalize_minmax(importances)
    recencies_norm = normalize_minmax(recencies)

    recency_w, relevance_w, importance_w = hp

    # 최종 점수 계산
    finals = [
        recency_w * recencies_norm[i]
        + relevance_w * relevances_norm[i]
        + importance_w * importances_norm[i]
        for i in range(len(memories))
    ]

    # 메모리 복사 + score 추가
    scored = []
    for i, m in enumerate(memories):
        mc = dict(m)
        mc["score"] = finals[i]
        mc["score_breakdown"] = {
            "relevance": relevances_norm[i],
            "importance_norm": importances_norm[i],
            "recency": recencies_norm[i],
            "final": finals[i],
        }
        scored.append(mc)

    n_count = min(n_count, len(scored))

    if not stochastic:
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n_count]

    # stochastic: top-2k 후보에서 softmax sampling
    scored.sort(key=lambda x: x["score"], reverse=True)
    k = min(2 * n_count, len(scored))
    top_2k = scored[:k]

    scores_arr = np.array([m["score"] for m in top_2k])
    exp_scores = np.exp(scores_arr / stochastic_temperature)
    probs = exp_scores / np.sum(exp_scores)

    selected_indices = np.random.choice(k, size=n_count, replace=False, p=probs)
    return [top_2k[i] for i in selected_indices]
