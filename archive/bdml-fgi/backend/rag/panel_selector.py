"""
panel_selector.py
DB에서 전체 패널을 조회하여 클러스터 다양성 + 주제 관련성 기반 N명 선정.
panels.avg_embedding(사전 계산된 평균 벡터)으로 스코어링하여 메모리 벌크 로드 없이 선정.
"""

from __future__ import annotations

import json

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Panel
from .retriever import cos_sim

DIM_COLS = [
    "dim_night_owl", "dim_gamer", "dim_social_diner", "dim_drinker",
    "dim_shopper", "dim_health", "dim_entertainment",
    "dim_weekend_oriented",
]


async def load_panels(session: AsyncSession) -> list[dict]:
    """DB에서 전체 패널 목록 조회 → dict 리스트 반환. avg_embedding 포함."""
    result = await session.execute(select(Panel))
    panels = result.scalars().all()
    return [_panel_to_dict(p) for p in panels]


def _panel_to_dict(p: Panel) -> dict:
    """ORM Panel → dict 변환."""
    avg_emb = p.avg_embedding
    if isinstance(avg_emb, str):
        avg_emb = json.loads(avg_emb)
    return {
        "panel_id": p.panel_id,
        "cluster": p.cluster,
        "age": p.age,
        "gender": p.gender,
        "occupation": p.occupation,
        "region": p.region,
        "dim_night_owl": p.dim_night_owl,
        "dim_gamer": p.dim_gamer,
        "dim_social_diner": p.dim_social_diner,
        "dim_drinker": p.dim_drinker,
        "dim_shopper": p.dim_shopper,
        "dim_health": p.dim_health,
        "dim_entertainment": p.dim_entertainment,
        "dim_weekend_oriented": p.dim_weekend_oriented,
        "avg_embedding": avg_emb,
    }


def score_panels_by_query(
    panels: list[dict],
    query_embedding: list[float],
) -> dict[str, float]:
    """각 패널의 avg_embedding과 query_embedding 간 코사인 유사도를 계산한다."""
    scores: dict[str, float] = {}
    for p in panels:
        pid = p["panel_id"]
        avg_emb = p.get("avg_embedding")
        if avg_emb and len(avg_emb) > 100:
            scores[pid] = cos_sim(query_embedding, avg_emb)
        else:
            scores[pid] = 0.0
    return scores


def select_representative_panels(
    panels: list[dict],
    n: int = 5,
    query_embedding: list[float] | None = None,
    topic_weight: float = 0.3,
) -> list[str]:
    """
    클러스터 다양성 기반으로 n명 선정.
    query_embedding이 주어지면 panels의 avg_embedding과 비교하여 주제 관련성을 반영.
    (1-topic_weight)*cluster_centrality + topic_weight*topic_relevance
    """
    clusters = sorted(set(p["cluster"] for p in panels))
    n_clusters = len(clusters)
    if n_clusters == 0:
        return []

    # 주제 관련성 스코어 (avg_embedding 기반)
    topic_scores: dict[str, float] = {}
    if query_embedding:
        topic_scores = score_panels_by_query(panels, query_embedding)

    # n개 클러스터를 균등 간격으로 선택
    step = n_clusters / n
    selected_clusters = [clusters[int(i * step)] for i in range(min(n, n_clusters))]

    # 전체 패널의 차원 통계 (정규화용)
    all_dims = np.array([[p.get(c, 0) or 0 for c in DIM_COLS] for p in panels])
    col_min = all_dims.min(axis=0)
    col_max = all_dims.max(axis=0)
    col_range = np.where(col_max - col_min == 0, 1, col_max - col_min)

    panel_ids: list[str] = []
    for cluster_id in selected_clusters:
        cluster_panels = [p for p in panels if p["cluster"] == cluster_id]
        if not cluster_panels:
            cluster_panels = panels

        dims = np.array([[p.get(c, 0) or 0 for c in DIM_COLS] for p in cluster_panels])
        normalized = (dims - col_min) / col_range
        center = normalized.mean(axis=0)
        dists = np.linalg.norm(normalized - center, axis=1)

        if topic_scores:
            max_dist = dists.max() if dists.max() > 0 else 1.0
            centrality = 1.0 - (dists / max_dist)
            relevance = np.array([
                topic_scores.get(p["panel_id"], 0.0) for p in cluster_panels
            ])
            combined = (1 - topic_weight) * centrality + topic_weight * relevance
            best_idx = int(np.argmax(combined))
        else:
            best_idx = int(np.argmin(dists))

        panel_ids.append(cluster_panels[best_idx]["panel_id"])

    return panel_ids
