"""V3 페르소나 독립성 — 페어와이즈 유클리드 거리 평균.

EVAL_SPEC.md §3 정합. 임계 ≥3.0 high / 1.5~3.0 moderate / <1.5 mode collapse 의심.
프로젝트 단위 지표 — 개별 agent snapshot 의 identity_stats.distinct 에
같은 값을 stamp.
"""
from __future__ import annotations

import math
from typing import Any

from embedding.embedder import average_embedding, embed


def _euclidean(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _pca_2d(vectors: list[list[float]]) -> list[tuple[float, float]]:
    """sklearn PCA 가 있으면 2D 투영, 없으면 첫 두 차원 폴백.

    UI 산점도용. 합성 임베딩에서도 의미는 없지만 시각화는 작동한다.
    """
    if len(vectors) < 2:
        return [(0.0, 0.0)] * len(vectors)
    try:
        import numpy as np  # type: ignore
        from sklearn.decomposition import PCA  # type: ignore
        X = np.array(vectors, dtype=float)
        pca = PCA(n_components=2)
        coords = pca.fit_transform(X)
        return [(float(x), float(y)) for x, y in coords]
    except ImportError:
        return [(v[0] if len(v) > 0 else 0.0, v[1] if len(v) > 1 else 0.0) for v in vectors]


def compute_v3(
    *,
    agent_persona_vectors: dict[str, list[float]],
) -> dict[str, Any]:
    """V3 distinct score + 2D 좌표.

    Args:
        agent_persona_vectors: {agent_id: avg_embedding_of_answers}.

    Returns:
        {distinct: float, n_agents: int, scatter: [{agent_id, x, y}]}
    """
    ids = list(agent_persona_vectors.keys())
    vecs = [agent_persona_vectors[i] for i in ids]
    n = len(ids)

    if n < 2:
        return {"distinct": 0.0, "n_agents": n, "scatter": [{"agent_id": i, "x": 0.0, "y": 0.0} for i in ids]}

    total = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += _euclidean(vecs[i], vecs[j])
            pairs += 1
    distinct = total / pairs if pairs else 0.0

    coords = _pca_2d(vecs)
    scatter = [{"agent_id": ids[k], "x": round(coords[k][0], 4), "y": round(coords[k][1], 4)} for k in range(n)]

    return {
        "distinct": round(distinct, 4),
        "n_agents": n,
        "scatter": scatter,
    }


def build_persona_vector(
    *,
    answers: list[str],
    synthetic_embeddings: bool | None = None,
) -> list[float]:
    """단일 agent 의 답변 N개 임베딩 평균 = 페르소나 벡터."""
    if not answers:
        return [0.0] * 1536
    embs = [embed(a, synthetic=synthetic_embeddings) for a in answers if a]
    return average_embedding(embs) if embs else [0.0] * 1536
