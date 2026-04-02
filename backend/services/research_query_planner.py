"""리서치 섹션별 검색 쿼리 플래너."""
from dataclasses import dataclass

from models.schemas import ResearchBrief


@dataclass(slots=True)
class SectionSearchPlan:
    section: str
    source_type: str
    query: str
    display: int = 5
    start: int = 1
    sort: str = "sim"


SECTION_SOURCE_STRATEGY: dict[str, list[str]] = {
    "market_overview": ["news", "doc", "webkr"],
    "competitive_landscape": ["news", "webkr", "blog"],
    "target_analysis": ["blog", "cafearticle", "news"],
    "trends": ["news", "blog", "webkr"],
    "implications": ["doc", "news"],
}


def plan_research_queries(
    brief: ResearchBrief,
    llm_keywords: dict[str, list[str]] | None = None,
) -> dict[str, list[SectionSearchPlan]]:
    category = brief.category.strip()
    target = brief.target_customer.strip()
    objective = brief.objective.strip()
    usage = brief.usage_plan.strip()

    section_queries: dict[str, list[str]] = {
        "market_overview": [
            f"{category} 시장 한국",
            f"{category} 시장 규모 국내",
            f"{category} 산업 동향 한국",
        ],
        "competitive_landscape": [
            f"{category} 브랜드 경쟁 한국",
            f"{category} 대체재 서비스 국내",
            f"{category} 주요 업체 시장 점유 한국",
        ],
        "target_analysis": [
            f"{target} {category} 니즈",
            f"{target} {category} 후기",
            f"{target} {category} 행동 패턴",
        ],
        "trends": [
            f"{category} 트렌드 MZ 한국",
            f"{category} 트렌드 2030 국내",
            f"{category} 소비 트렌드 한국",
        ],
        "implications": [
            f"{category} 문제점 기회 한국",
            f"{objective} 차별화 포인트 {category}",
            f"{usage} 실행 인사이트 {category}",
        ],
    }
    if llm_keywords:
        for section, queries in llm_keywords.items():
            filtered = [query.strip() for query in queries if query and query.strip()]
            if filtered and section in section_queries:
                section_queries[section] = filtered

    plans: dict[str, list[SectionSearchPlan]] = {}
    for section, sources in SECTION_SOURCE_STRATEGY.items():
        queries = section_queries[section]
        section_plans: list[SectionSearchPlan] = []
        for index, source_type in enumerate(sources):
            query = queries[min(index, len(queries) - 1)]
            sort = "date" if source_type == "news" else "sim"
            section_plans.append(
                SectionSearchPlan(
                    section=section,
                    source_type=source_type,
                    query=query,
                    sort=sort,
                )
            )
        plans[section] = section_plans
    return plans
