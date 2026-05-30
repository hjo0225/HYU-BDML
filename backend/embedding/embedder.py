"""OpenAI text-embedding-3-small 임베딩 모듈.

캐시를 먼저 확인하고, 없으면 OpenAI API 호출.
OPENAI_API_KEY 미설정 시 결정적 합성 임베딩으로 자동 폴백 — mock 단계에서
API 비용을 피하면서도 KMeans·다양성 점수 등 다운스트림 계산이 동작한다.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import time

import openai

from .cache import get_cached, set_cached

_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
_CACHE_PATH = os.getenv("EMBEDDING_CACHE_PATH", "")
_DIM = 1536


def _cache_path() -> str:
    return _CACHE_PATH or ""


def _synthetic_embed(text: str) -> list[float]:
    """결정적 합성 임베딩 — 텍스트 sha256 을 seed 로 정규분포 샘플 + L2 정규화.

    OpenAI 임베딩과 동일 차원(1536). 의미상 인접성은 보존되지 않지만
    텍스트가 같으면 항상 같은 벡터라 KMeans 재현성·테스트 결정성 보장.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = random.Random(seed)
    vec = [rng.gauss(0.0, 1.0) for _ in range(_DIM)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _has_api_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key and not key.startswith("dummy") and not key.startswith("test"))


def embed(text: str, use_cache: bool = True, synthetic: bool | None = None) -> list[float]:
    """단일 텍스트 임베딩.

    Args:
        text: 임베딩할 텍스트.
        use_cache: True 면 캐시 우선 사용.
        synthetic: True=강제 합성, False=강제 실 API, None=API 키 유무 자동 판단.

    Returns:
        1536차원 float 리스트.
    """
    if not text.strip():
        return [0.0] * _DIM

    use_synth = synthetic if synthetic is not None else not _has_api_key()
    if use_synth:
        return _synthetic_embed(text)

    cache_path = _cache_path()
    if use_cache and cache_path:
        cached = get_cached(text, cache_path)
        if cached is not None:
            return cached

    # 호출 stall 방어 — 타임아웃 미설정 시 SDK 기본 600초. (2026-05-30)
    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        timeout=float(os.getenv("OPENAI_TIMEOUT", "60")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    )
    response = client.embeddings.create(input=text, model=_MODEL)
    embedding = response.data[0].embedding

    if use_cache and cache_path:
        set_cached(text, embedding, cache_path)

    return embedding


def batch_embed(texts: list[str], use_cache: bool = True, delay: float = 0.5,
                synthetic: bool | None = None) -> list[list[float]]:
    """여러 텍스트 배치 임베딩.

    Args:
        texts: 임베딩할 텍스트 리스트.
        use_cache: 캐시 사용 여부.
        delay: 실 API 호출 간 지연 (초). 합성 모드에서는 지연 무시.
        synthetic: True=강제 합성, False=강제 실 API, None=자동 판단.

    Returns:
        텍스트 순서에 대응하는 임베딩 리스트.
    """
    use_synth = synthetic if synthetic is not None else not _has_api_key()
    results = []
    for i, text in enumerate(texts):
        if i > 0 and delay > 0 and not use_synth:
            time.sleep(delay)
        results.append(embed(text, use_cache=use_cache, synthetic=use_synth))
    return results


def average_embedding(embeddings: list[list[float]]) -> list[float]:
    """임베딩 리스트의 평균 벡터 산출."""
    if not embeddings:
        return [0.0] * _DIM
    dim = len(embeddings[0])
    avg = [0.0] * dim
    for emb in embeddings:
        for j, v in enumerate(emb):
            avg[j] += v
    n = len(embeddings)
    return [v / n for v in avg]
