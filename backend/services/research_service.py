"""시장조사 서비스 — 키워드 추출 → 병렬 검색 → 종합 보고서"""
import asyncio
import json
import re
from typing import AsyncGenerator
from pydantic import BaseModel
from agents import Agent, Runner, WebSearchTool, ModelSettings
from models.schemas import ResearchBrief
from prompts.research import (
    REFINER_PROMPT,
    KEYWORD_EXTRACTOR_PROMPT,
    SEARCHER_PROMPT,
    REPORT_SYNTHESIZER_PROMPT,
)

# Agents SDK 환경 로드
import services.openai_client  # noqa: F401

# 진행 단계 정의
RESEARCH_STEPS = [
    "연구 정보 고도화 중...",
    "검색 키워드 추출 중...",
    "시장 규모 검색 중...",
    "경쟁 환경 검색 중...",
    "타깃 고객 검색 중...",
    "트렌드 검색 중...",
    "시사점 검색 중...",
    "보고서 종합 중...",
]

# 한국 내 검색
_web_search = WebSearchTool(
    user_location={"type": "approximate", "country": "KR"},
    search_context_size="high",
)


# ── 1. 고도화 에이전트 (웹검색 없음) ──
class RefinedOutput(BaseModel):
    refined_background: str
    refined_objective: str
    refined_usage_plan: str


refiner_agent = Agent(
    name="연구 정보 고도화",
    instructions=REFINER_PROMPT,
    model="gpt-4o",
    output_type=RefinedOutput,
)


# ── 2. 키워드 추출 에이전트 ──
class SearchKeywords(BaseModel):
    market_overview: str
    competitive_landscape: str
    target_analysis: str
    trends: str
    implications: str


keyword_agent = Agent(
    name="키워드 추출",
    instructions=KEYWORD_EXTRACTOR_PROMPT,
    model="gpt-4o",
    output_type=SearchKeywords,
    model_settings=ModelSettings(temperature=0.3),
)


# ── 3. 검색 에이전트 (키워드별 웹검색) ──
searcher_agent = Agent(
    name="웹 검색 리서처",
    instructions=SEARCHER_PROMPT,
    model="gpt-4o",
    tools=[_web_search],
)


# ── 4. 종합 보고서 에이전트 ──
class ReportOutput(BaseModel):
    market_overview: str
    competitive_landscape: str
    target_analysis: str
    trends: str
    implications: str
    sources: str


synthesizer_agent = Agent(
    name="보고서 종합",
    instructions=REPORT_SYNTHESIZER_PROMPT,
    model="gpt-4o",
    output_type=ReportOutput,
)


def _clean_inline_citations(text: str) -> str:
    """본문에 섞인 인라인 출처 링크/마커 제거"""
    text = re.sub(r'\s*\(\[([^\]]*)\]\([^\)]+\)\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\(https?://[^\)]+\)', r'\1', text)
    text = re.sub(r'\s*\(https?://[^\)]+\)', '', text)
    text = re.sub(r'\s*\([a-zA-Z0-9.-]+\.(com|co|org|net|io|kr)[^\)]*\)', '', text)
    text = re.sub(r'turn\d+search\d+', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'  +', ' ', text).strip()
    return text


def _clean_sources(text: str) -> str:
    """출처 필드 정리"""
    def _repl_wrapped(m):
        title = m.group(1)
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{title} ({url})"
    text = re.sub(r'\(\[([^\]]*)\]\((https?://[^\)]+)\)\)', _repl_wrapped, text)
    def _repl(m):
        title = m.group(1)
        url = re.sub(r'\?utm_source=[^&)\s]+', '', m.group(2))
        return f"{title} ({url})"
    text = re.sub(r'\[([^\]]*)\]\((https?://[^\)]+)\)', _repl, text)
    text = re.sub(r'\?utm_source=[^&)\s]+', '', text)
    return text.strip()


def _clean_report(report: ReportOutput) -> dict:
    """보고서 본문 출처 제거 + 출처 정리"""
    return {
        "market_overview": _clean_inline_citations(report.market_overview),
        "competitive_landscape": _clean_inline_citations(report.competitive_landscape),
        "target_analysis": _clean_inline_citations(report.target_analysis),
        "trends": _clean_inline_citations(report.trends),
        "implications": _clean_inline_citations(report.implications),
        "sources": _clean_sources(report.sources),
    }


async def run_research(brief: ResearchBrief) -> AsyncGenerator[str, None]:
    """시장조사 수행 — 키워드 추출 → 병렬 검색 → 종합"""

    def _status(step: int):
        return f"data: {json.dumps({'type': 'status', 'step': step, 'total': len(RESEARCH_STEPS), 'message': RESEARCH_STEPS[step - 1]}, ensure_ascii=False)}\n\n"

    user_message = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}"
    )

    # ── 단계 1: 연구 정보 고도화 ──
    yield _status(1)
    refined_result = await Runner.run(refiner_agent, user_message)
    refined: RefinedOutput = refined_result.final_output

    # ── 단계 2: 검색 키워드 추출 ──
    yield _status(2)
    kw_result = await Runner.run(keyword_agent, user_message)
    keywords: SearchKeywords = kw_result.final_output

    # ── 단계 3~7: 키워드별 병렬 웹검색 ──
    search_fields = [
        ("market_overview", keywords.market_overview),
        ("competitive_landscape", keywords.competitive_landscape),
        ("target_analysis", keywords.target_analysis),
        ("trends", keywords.trends),
        ("implications", keywords.implications),
    ]

    async def _search(field: str, query: str) -> tuple[str, str]:
        result = await Runner.run(searcher_agent, query)
        return field, result.final_output

    # 5개 키워드 병렬 검색
    tasks = [_search(field, query) for field, query in search_fields]
    search_results = {}
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        field, text = await coro
        search_results[field] = text
        yield _status(3 + i)

    # ── 단계 8: 검색 결과 종합 → 보고서 ──
    yield _status(8)

    synthesis_input = "\n\n".join(
        f"[{field}]\n{text}" for field, text in search_results.items()
    )
    report_result = await Runner.run(synthesizer_agent, synthesis_input)
    report: ReportOutput = report_result.final_output

    # 결과 조합
    data = {
        "refined": refined.model_dump(),
        "report": _clean_report(report),
    }
    yield f"data: {json.dumps({'type': 'result', 'data': data}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
