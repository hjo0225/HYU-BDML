"""
B-1: Embedder
텍스트 → 1536차원 벡터 변환 + 로컬 파일 캐시
"""

import json
import os
from pathlib import Path

# backend/rag/ 기준으로 캐시 경로를 고정한다.
CACHE_PATH = Path(__file__).parent / "embedding_cache.json"
MODEL = "text-embedding-3-small"


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def embed(text: str) -> list[float]:
    """
    텍스트를 1536차원 벡터로 변환.

    입력: 비어있지 않은 문자열
    출력: 길이 1536의 float list
    예외: text가 비어있거나 str이 아니면 ValueError
    """
    if not isinstance(text, str):
        raise ValueError(f"text must be str, got {type(text)}")

    normalized = text.replace("\n", " ").strip()

    if not normalized:
        raise ValueError("text must not be empty or whitespace-only")

    cache = _load_cache()
    if normalized in cache:
        return cache[normalized]

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    response = client.embeddings.create(input=normalized, model=MODEL)
    vector = response.data[0].embedding

    cache[normalized] = vector
    _save_cache(cache)

    return vector
