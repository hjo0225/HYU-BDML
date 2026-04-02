"""리서치 근거를 섹션별 보고서로 합성."""
import json

from openai import AsyncOpenAI

from models.schemas import EvidenceItem, MarketReport, ReportSection, ResearchBrief
from prompts.research import SEARCHER_PROMPT
from services.research_source_ranker import confidence_from_evidence


SECTION_LABELS = {
    "market_overview": "시장 개요",
    "competitive_landscape": "경쟁 환경",
    "target_analysis": "타깃 분석",
    "trends": "트렌드",
    "implications": "시사점",
}

SECTION_WRITING_RULES = {
    "market_overview": (
        "이 섹션은 숫자 중심으로 작성한다. "
        "1문단은 시장 규모, 성장률, 한국 시장의 구조를 설명한다. "
        "2문단은 왜 이 시장이 지금 중요한지와 핵심 변화 요인을 설명한다. "
        "브랜드 사례나 타깃 감정 묘사는 최소화한다."
    ),
    "competitive_landscape": (
        "이 섹션은 플레이어 중심으로 작성한다. "
        "1문단은 주요 경쟁자와 경쟁 구도를 설명한다. "
        "2문단은 차별화 포인트, 대체재, 경쟁상 리스크를 설명한다. "
        "시장 전체 일반론이나 소비자 묘사는 최소화한다."
    ),
    "target_analysis": (
        "이 섹션은 사람 중심으로 작성한다. "
        "1문단은 타깃 고객의 행동 패턴과 구매 맥락을 설명한다. "
        "2문단은 니즈, pain point, 선택 기준을 구체적으로 설명한다. "
        "기업 나열이나 시장 규모 숫자 반복은 최소화한다."
    ),
    "trends": (
        "이 섹션은 변화 중심으로 작성한다. "
        "1문단은 최근 트렌드와 소비 변화 방향을 설명한다. "
        "2문단은 기술 변화나 문화 변화가 시장에 미치는 영향을 설명한다. "
        "개별 브랜드 설명보다는 변화의 방향과 신호를 우선한다."
    ),
    "implications": (
        "이 섹션은 행동 제안 중심으로 작성한다. "
        "반드시 앞선 시장 개요, 경쟁 환경, 타깃 분석, 트렌드의 내용을 종합해 작성한다. "
        "1문단은 시장에서 확인된 문제점과 기회를 요약한다. "
        "2문단은 차별화 포인트와 실제 실행 시사점을 제안한다. "
        "근거 없는 일반론, 당연한 결론, 추상적 조언을 금지한다. "
        "새 사실을 길게 추가하지 말고, 앞선 근거를 바탕으로 무엇을 해야 하는지에 집중한다."
    ),
}


async def synthesize_section(
    client: AsyncOpenAI,
    brief: ResearchBrief,
    section: str,
    evidence: list[EvidenceItem],
    related_sections: dict[str, ReportSection] | None = None,
    research_context: str = "",
) -> ReportSection:
    related_sections = related_sections or {}
    fallback = _fallback_section(evidence)

    if not evidence:
        return fallback

    instructions = (
        SEARCHER_PROMPT.replace("{research_context}", research_context or brief.objective)
        + "\n\n"
        + (
            "당신은 위 규칙을 따르되, 최종 출력은 반드시 JSON만 작성한다.\n"
            f"섹션 작성 규칙: {SECTION_WRITING_RULES.get(section, '')}\n"
            "근거보기는 별도로 제공되므로, summary 본문에서는 출처 제목·URL·도메인을 나열하지 말고 근거 내용을 읽어 자연스러운 설명문으로 재구성한다.\n"
            "여러 근거가 공통으로 말하는 사실을 하나의 논리로 엮어 설명하고, 근거 제목을 그대로 베끼지 않는다.\n"
            "본문은 '주장 -> 이유/맥락'의 흐름으로 읽히게 작성하고, 문장마다 실제 evidence에 있는 정보만 사용한다.\n"
            "summary는 반드시 2문단이어야 하며, 문단 사이에는 줄바꿈 두 개를 넣는다.\n"
            "각 문단은 2~4문장으로 충분히 구체적으로 쓴다.\n"
            "다른 섹션과 겹치는 설명을 반복하지 말고, 이 섹션의 중심축에 맞는 내용만 우선적으로 남긴다.\n"
            "JSON 스키마:\n"
            "{"
            "\"summary\": \"2문단 요약\", "
            "\"key_claims\": [\"주장1\", \"주장2\", \"주장3\"], "
            "\"evidence\": [근거 객체 원본], "
            "\"confidence\": \"high|medium|low\""
            "}\n"
            "반드시 제공된 근거만 사용하고, evidence에는 선택한 근거 객체를 그대로 넣는다."
        )
    )
    prompt = (
        f"[작성 대상 섹션]\n{SECTION_LABELS.get(section, section)}\n\n"
        f"[카테고리]\n{brief.category}\n\n"
        f"[타깃 고객]\n{brief.target_customer}\n\n"
        f"[연구 목적]\n{brief.objective}\n\n"
        f"[관련 섹션]\n{_related_sections_text(related_sections)}\n\n"
        f"[근거 목록]\n{json.dumps([item.model_dump() for item in evidence], ensure_ascii=False)}"
    )

    response = await client.responses.create(
        model="gpt-4.1-mini",
        instructions=instructions,
        input=prompt,
        temperature=0.3,
    )
    content = getattr(response, "output_text", "") or ""

    try:
        parsed = json.loads(_extract_json_object(content))
        parsed_evidence = [
            item for item in parsed.get("evidence", [item.model_dump() for item in evidence[:4]])
            if isinstance(item, dict) and str(item.get("url", "")).strip().startswith(("http://", "https://"))
        ]
        section_data = ReportSection.model_validate(
            {
                "summary": _ensure_two_paragraphs(parsed.get("summary", fallback.summary), section, evidence),
                "key_claims": parsed.get("key_claims", fallback.key_claims),
                "evidence": parsed_evidence or [item.model_dump() for item in evidence[:4]],
                "confidence": parsed.get("confidence", confidence_from_evidence(evidence)),
            }
        )
        if not section_data.summary.strip():
            return fallback
        return section_data
    except Exception:
        return fallback


def build_report(
    market_overview: ReportSection,
    competitive_landscape: ReportSection,
    target_analysis: ReportSection,
    trends: ReportSection,
    implications: ReportSection,
) -> MarketReport:
    return MarketReport(
        market_overview=market_overview,
        competitive_landscape=competitive_landscape,
        target_analysis=target_analysis,
        trends=trends,
        implications=implications,
    )


def _fallback_section(evidence: list[EvidenceItem]) -> ReportSection:
    selected = evidence[:4]
    claims = [item.title for item in selected[:3]]
    first_paragraph = _compose_fallback_paragraph(selected[:2])
    second_paragraph = _compose_fallback_paragraph(selected[2:4])
    summary = "\n\n".join(part for part in [first_paragraph, second_paragraph] if part).strip()
    if not summary:
        summary = "수집된 근거가 제한적이어서 요약 신뢰도가 낮습니다."
    return ReportSection(
        summary=summary,
        key_claims=claims,
        evidence=selected,
        confidence=confidence_from_evidence(evidence),
    )


def _related_sections_text(related_sections: dict[str, ReportSection]) -> str:
    if not related_sections:
        return "없음"
    return "\n".join(
        f"- {SECTION_LABELS.get(key, key)}: {value.summary}"
        for key, value in related_sections.items()
    )


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON object not found")
    return text[start : end + 1]


def _ensure_two_paragraphs(summary: str, section: str, evidence: list[EvidenceItem]) -> str:
    text = (summary or "").strip()
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if len(parts) >= 2:
        return "\n\n".join(parts[:2])

    fallback = _fallback_section(evidence).summary
    fallback_parts = [part.strip() for part in fallback.split("\n\n") if part.strip()]
    if not parts:
        return fallback
    if section == "implications" and fallback_parts:
        second = fallback_parts[-1]
    else:
        second = fallback_parts[1] if len(fallback_parts) > 1 else fallback_parts[0]
    return f"{parts[0]}\n\n{second}".strip()


def _compose_fallback_paragraph(items: list[EvidenceItem]) -> str:
    if not items:
        return ""
    snippets = [item.snippet.strip() for item in items if item.snippet.strip()]
    titles = [item.title.strip() for item in items if item.title.strip()]

    if snippets:
        lead = snippets[0]
        if len(snippets) > 1:
            return f"{lead} 또한 {snippets[1]}"
        return lead
    if titles:
        lead = titles[0]
        if len(titles) > 1:
            return f"{lead} 이와 함께 {titles[1]} 흐름이 함께 관찰된다."
        return lead
    return ""
