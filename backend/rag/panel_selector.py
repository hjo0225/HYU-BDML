"""
panel_selector.py
DB에서 전체 패널을 조회하여 클러스터 다양성 + 주제 관련성 기반 N명 선정.
연령 필터링 없이 전체 패널 풀에서 주제 임베딩 유사도로 적합한 패널을 선정한다.
"""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import Panel
from .retriever import cos_sim

DIM_COLS = [
    "dim_night_owl", "dim_gamer", "dim_social_diner", "dim_drinker",
    "dim_shopper", "dim_health", "dim_entertainment",
    "dim_weekend_oriented",
]


async def load_panels(session: AsyncSession) -> list[dict]:
    """DB에서 전체 패널 목록 조회 → dict 리스트 반환."""
    result = await session.execute(select(Panel))
    panels = result.scalars().all()
    return [_panel_to_dict(p) for p in panels]


def _panel_to_dict(p: Panel) -> dict:
    """ORM Panel → dict 변환."""
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
    }


def score_panels_by_topic(
    panels: list[dict],
    topic_embedding: list[float],
    panel_memories: dict[str, list[dict]],
) -> dict[str, float]:
    """
    각 패널의 메모리와 topic_embedding 간 평균 코사인 유사도를 계산한다.
    메모리가 없는 패널은 0.0.
    """
    scores: dict[str, float] = {}
    for p in panels:
        pid = p["panel_id"]
        mems = panel_memories.get(pid, [])
        if not mems:
            scores[pid] = 0.0
            continue
        sims = []
        for m in mems:
            emb = m.get("embedding")
            if emb:
                sims.append(cos_sim(topic_embedding, emb))
        scores[pid] = float(np.mean(sims)) if sims else 0.0
    return scores


def select_representative_panels(
    panels: list[dict],
    n: int = 5,
    topic_embedding: list[float] | None = None,
    panel_memories: dict[str, list[dict]] | None = None,
    topic_weight: float = 0.3,
) -> list[str]:
    """
    클러스터 다양성 기반으로 n명 선정. 완전 결정론적.
    topic_embedding이 주어지면 주제 관련성을 반영해 패널을 선택한다.
    (1-topic_weight)*cluster_centrality + topic_weight*topic_relevance
    """
    # 클러스터 목록
    clusters = sorted(set(p["cluster"] for p in panels))
    n_clusters = len(clusters)
    if n_clusters == 0:
        return []

    # 주제 관련성 스코어 (있으면)
    topic_scores: dict[str, float] = {}
    if topic_embedding and panel_memories:
        topic_scores = score_panels_by_topic(panels, topic_embedding, panel_memories)

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
            # 거리를 0~1로 정규화 (작을수록 좋으므로 1-norm)
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
