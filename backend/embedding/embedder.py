"""OpenAI text-embedding-3-small 임베딩 모듈.

캐시를 먼저 확인하고, 없으면 OpenAI API 호출.
"""
from __future__ import annotations

import os
import time

import openai

from .cache import get_cached, set_cached

_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
_CACHE_PATH = os.getenv("EMBEDDING_CACHE_PATH", "")


def _cache_path() -> str:
    return _CACHE_PATH or ""


def embed(text: str, use_cache: bool = True) -> list[float]:
    """단일 텍스트 임베딩.

    Args:
        text: 임베딩할 텍스트.
        use_cache: True 면 캐시 우선 사용.

    Returns:
        1536차원 float 리스트.
    """
    if not text.strip():
        return [0.0] * 1536

    cache_path = _cache_path()
    if use_cache and cache_path:
        cached = get_cached(text, cache_path)
        if cached is not None:
            return cached

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.embeddings.create(input=text, model=_MODEL)
    embedding = response.data[0].embedding

    if use_cache and cache_path:
        set_cached(text, embedding, cache_path)

    return embedding


def batch_embed(texts: list[str], use_cache: bool = True, delay: float = 0.5) -> list[list[float]]:
    """여러 텍스트 배치 임베딩.

    Args:
        texts: 임베딩할 텍스트 리스트.
        use_cache: 캐시 사용 여부.
        delay: API 호출 간 지연 (초). Rate Limit 방어.

    Returns:
        텍스트 순서에 대응하는 임베딩 리스트.
    """
    results = []
    for i, text in enumerate(texts):
        if i > 0 and delay > 0:
            time.sleep(delay)
        results.append(embed(text, use_cache=use_cache))
    return results


def average_embedding(embeddings: list[list[float]]) -> list[float]:
    """임베딩 리스트의 평균 벡터 산출."""
    if not embeddings:
        return [0.0] * 1536
    dim = len(embeddings[0])
    avg = [0.0] * dim
    for emb in embeddings:
        for j, v in enumerate(emb):
            avg[j] += v
    n = len(embeddings)
    return [v / n for v in avg]
