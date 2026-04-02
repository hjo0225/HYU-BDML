"""출처 유형별 가중치와 근거 랭킹."""
from datetime import date
from urllib.parse import urlparse

from models.schemas import EvidenceItem
from services.naver_search_service import SearchResultItem


SOURCE_TYPE_WEIGHTS: dict[str, float] = {
    "doc": 1.0,
    "news": 0.9,
    "webkr": 0.75,
    "blog": 0.55,
    "cafearticle": 0.4,
}

SECTION_FOCUS_TERMS: dict[str, list[str]] = {
    "market_overview": ["시장 규모", "성장률", "매출", "점유율", "규모", "전망"],
    "competitive_landscape": ["브랜드", "경쟁", "업체", "플레이어", "대체재", "점유율"],
    "target_analysis": ["고객", "소비자", "니즈", "행동", "불편", "후기", "선호"],
    "trends": ["트렌드", "변화", "확산", "전환", "신기술", "문화", "패턴"],
    "implications": ["기회", "전략", "차별화", "제안", "시사점", "실행", "우선순위"],
}


def score_result(item: SearchResultItem, section_terms: list[str], support_bonus: float = 0.0) -> float:
    base_weight = SOURCE_TYPE_WEIGHTS.get(item.source_type, 0.3)
    haystack = f"{item.title} {item.snippet}".lower()
    matched = sum(1 for term in section_terms if term and term.lower() in haystack)
    term_bonus = min(0.25, matched * 0.06)
    freshness_bonus = _freshness_bonus(item)
    engine_bonus = 0.04 if item.source_engine == "openai_web" else 0.0
    return round(min(1.0, base_weight + term_bonus + freshness_bonus + support_bonus + engine_bonus), 3)


def convert_to_evidence(item: SearchResultItem, relevance_score: float) -> EvidenceItem:
    return EvidenceItem(
        source_type=item.source_type,  # type: ignore[arg-type]
        source_engine=item.source_engine,  # type: ignore[arg-type]
        title=item.title,
        url=item.url,
        publisher=item.publisher,
        published_at=item.published_at,
        snippet=item.snippet,
        relevance_score=relevance_score,
    )


def dedupe_and_rank(
    items: list[SearchResultItem],
    section_terms: list[str],
    section: str | None = None,
    limit: int = 6,
) -> list[EvidenceItem]:
    ranked: list[EvidenceItem] = []
    seen_urls: set[str] = set()
    support_map = _build_support_map(items)
    focus_terms = SECTION_FOCUS_TERMS.get(section or "", [])

    for item in sorted(
        items,
        key=lambda current: score_result(
            current,
            section_terms + focus_terms,
            support_map.get(_canonical_key(current), 0.0),
        ),
        reverse=True,
    ):
        if not item.url or item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        support_bonus = support_map.get(_canonical_key(item), 0.0)
        ranked.append(
            convert_to_evidence(item, score_result(item, section_terms + focus_terms, support_bonus))
        )
        if len(ranked) >= limit:
            break
    return ranked


def confidence_from_evidence(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "low"

    avg_score = sum(item.relevance_score for item in evidence) / len(evidence)
    source_diversity = len({item.source_type for item in evidence})
    high_authority = sum(1 for item in evidence if item.source_type in {"doc", "news"})

    if avg_score >= 0.8 and source_diversity >= 2 and high_authority >= 2:
        return "high"
    if avg_score >= 0.6 and high_authority >= 1:
        return "medium"
    return "low"


def _build_support_map(items: list[SearchResultItem]) -> dict[str, float]:
    grouped: dict[str, set[str]] = {}
    for item in items:
        key = _canonical_key(item)
        grouped.setdefault(key, set()).add(item.source_engine)
    return {
        key: 0.1 if len(engines) >= 2 else 0.0
        for key, engines in grouped.items()
    }


def _canonical_key(item: SearchResultItem) -> str:
    title = " ".join(item.title.lower().split())
    host = urlparse(item.url).netloc.lower().replace("www.", "")
    return f"{host}|{title}"


def _freshness_bonus(item: SearchResultItem) -> float:
    if item.source_type != "news" or not item.published_at:
        return 0.0
    try:
        published = date.fromisoformat(item.published_at)
    except ValueError:
        return 0.0
    days_old = max(0, (date.today() - published).days)
    if days_old <= 30:
        return 0.08
    if days_old <= 90:
        return 0.04
    return 0.0
