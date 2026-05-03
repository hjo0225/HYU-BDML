"""Lab — 답변 인용/근거 서비스 (A+B 하이브리드).

A: LLM이 답변 끝 마커로 자가 인용한 카테고리 리스트
B: 답변 텍스트를 임베딩해서 트윈의 PanelMemory 청크와 코사인 유사도 top-k

verify_llm_citations()는 두 결과를 합쳐:
  - LLM 자가 인용 카테고리 중 임베딩 매칭에서 등장한 것은 신뢰 (via='both')
  - LLM이 빠뜨린 임베딩 top-k 카테고리도 보조 인용으로 추가 (via='embedding')
  - LLM이 말했지만 임베딩 매칭에 없는 카테고리는 drop (할루시네이션 차단)

source='twin2k500' 필터는 항상 적용 (CLAUDE.md SSOT).
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import select

from database import AsyncSessionLocal, PanelMemory
from models.schemas import LabConfidence, MemoryCitation
from rag.embedder import embed


# 코사인 매칭 후보 수 (LLM 자가인용 검증 + 보조 인용 동시 풀)
_TOP_K_PROBE = 6
# 사용자에게 노출할 최대 인용 수
_MAX_CITATIONS = 3
# 임베딩 매칭 최소 유사도 — 이보다 낮으면 인용으로 노출하지 않음
_MIN_SCORE = 0.18
# 인용 본문 트리밍 길이 (사용자에게 펼침 시 보일 영문 원문)
_SNIPPET_MAX_CHARS = 360


def _cosine(a: list[float], b: list[float]) -> float:
    """두 1536차원 벡터의 코사인 유사도. 둘 다 길이 같다고 가정."""
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _trim(text: str, n: int = _SNIPPET_MAX_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


async def _load_memories(twin_id: str) -> list[PanelMemory]:
    """source='twin2k500'인 트윈의 메모리 전체 로드 (50명 × ~32 청크라 부담 작음)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PanelMemory).where(
                PanelMemory.panel_id == twin_id,
                PanelMemory.source == "twin2k500",
            )
        )
        return list(result.scalars().all())


async def find_supporting_memories(
    twin_id: str,
    answer_text: str,
    k: int = _MAX_CITATIONS,
) -> list[MemoryCitation]:
    """답변을 임베딩하여 트윈 메모리와 코사인 유사도 top-k 반환.

    매칭이 임계값 미만이거나 메모리가 없으면 빈 리스트.
    """
    answer_text = (answer_text or "").strip()
    if not answer_text:
        return []

    rows = await _load_memories(twin_id)
    if not rows:
        return []

    try:
        query_vec = embed(answer_text)
    except Exception:
        # 임베딩 실패는 인용을 막지 않음 — 빈 리스트로 후퇴
        return []

    scored: list[tuple[float, PanelMemory]] = []
    for row in rows:
        emb = row.embedding
        # JSONB가 dict로 들어오는 케이스는 없지만 안전하게 list만 처리
        if not isinstance(emb, list):
            continue
        score = _cosine(query_vec, emb)
        scored.append((score, row))

    scored.sort(key=lambda t: t[0], reverse=True)

    out: list[MemoryCitation] = []
    seen_categories: set[str] = set()
    for score, row in scored:
        if score < _MIN_SCORE:
            break
        if row.category in seen_categories:
            continue
        seen_categories.add(row.category)
        out.append(
            MemoryCitation(
                category=row.category,
                snippet_en=_trim(row.text),
                snippet_ko=None,
                score=round(float(score), 4),
                via="embedding",
            )
        )
        if len(out) >= k:
            break
    return out


async def _scored_top_k(twin_id: str, answer_text: str, k: int) -> list[tuple[float, PanelMemory]]:
    """내부용 — 임베딩 매칭 결과를 (score, row)로 반환."""
    rows = await _load_memories(twin_id)
    if not rows:
        return []
    try:
        query_vec = embed(answer_text)
    except Exception:
        return []
    scored: list[tuple[float, PanelMemory]] = []
    for row in rows:
        emb = row.embedding
        if not isinstance(emb, list):
            continue
        scored.append((_cosine(query_vec, emb), row))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:k]


async def verify_llm_citations(
    twin_id: str,
    llm_cited_categories: Iterable[str],
    answer_text: str,
    confidence: LabConfidence,
) -> tuple[list[MemoryCitation], LabConfidence]:
    """LLM 자가 인용 + 임베딩 검증 결합.

    - LLM이 말한 카테고리 중 임베딩 top-k에 등장하는 것 → via='both' 로 노출
    - LLM이 빠뜨린 임베딩 top-k 카테고리 → via='embedding' 으로 보조 노출
    - LLM이 말했지만 매칭이 없으면 drop (할루시네이션 차단)
    - confidence는 LLM이 'unknown'이라고 했어도 매칭이 강하면 'inferred'로 승격할 수 있음

    반환: (검증된 인용 리스트, 보정된 confidence)
    """
    answer_text = (answer_text or "").strip()
    llm_cats = [c for c in (llm_cited_categories or []) if c]

    if not answer_text:
        return [], "unknown"

    scored = await _scored_top_k(twin_id, answer_text, _TOP_K_PROBE)
    if not scored:
        return [], confidence

    # category → (best_score, best_row)
    best_by_category: dict[str, tuple[float, PanelMemory]] = {}
    for score, row in scored:
        if row.category in best_by_category:
            if score > best_by_category[row.category][0]:
                best_by_category[row.category] = (score, row)
        else:
            best_by_category[row.category] = (score, row)

    citations: list[MemoryCitation] = []
    used_categories: set[str] = set()

    # 1) LLM 자가 인용 카테고리 중 매칭이 있는 것 우선
    for cat in llm_cats:
        if cat in used_categories:
            continue
        match = best_by_category.get(cat)
        if not match:
            continue
        score, row = match
        if score < _MIN_SCORE:
            continue
        citations.append(
            MemoryCitation(
                category=row.category,
                snippet_en=_trim(row.text),
                snippet_ko=None,
                score=round(float(score), 4),
                via="both",
            )
        )
        used_categories.add(cat)
        if len(citations) >= _MAX_CITATIONS:
            break

    # 2) 보조: 임베딩 top 매칭이지만 LLM이 빠뜨린 카테고리
    if len(citations) < _MAX_CITATIONS:
        for score, row in scored:
            if row.category in used_categories:
                continue
            if score < _MIN_SCORE:
                break
            citations.append(
                MemoryCitation(
                    category=row.category,
                    snippet_en=_trim(row.text),
                    snippet_ko=None,
                    score=round(float(score), 4),
                    via="embedding",
                )
            )
            used_categories.add(row.category)
            if len(citations) >= _MAX_CITATIONS:
                break

    # confidence 보정 — 매칭 강도와 LLM 신호 결합
    top_score = scored[0][0] if scored else 0.0
    adjusted = confidence
    if confidence == "unknown" and top_score >= 0.45:
        # LLM이 모른다고 했지만 강한 매칭이 있으면 inferred로 승격
        adjusted = "inferred"
    elif confidence == "direct" and top_score < _MIN_SCORE:
        # LLM이 direct라 했지만 매칭 약함 → guess로 강등
        adjusted = "guess"

    return citations, adjusted
