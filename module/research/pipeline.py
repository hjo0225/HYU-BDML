"""
Fast Research Agent Pipeline
=============================
Step 0~3 파이프라인 로직.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from openai import AsyncOpenAI
from tavily import TavilyClient

from .models import InputA, InputB, ResearchOutput, SourceInfo
from .prompts import STEP0_SYSTEM, STEP1_SYSTEM, STEP3_SYSTEM

# ── 설정값 ──────────────────────────────────────────────────
LLM_MODEL = "gpt-4o"
MAX_SEARCH_QUERIES = 5
MAX_PAGES_TO_READ = 8
TAVILY_MAX_RESULTS = 5
JINA_CONTENT_LIMIT = 3000

RAW_BASE = Path("raw")


# ── 유틸 ────────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    """프로젝트명의 특수문자/공백을 밑줄로 치환."""
    return re.sub(r"[^\w가-힣-]", "_", name).strip("_")


def _project_dir(project_name: str) -> Path:
    return RAW_BASE / _sanitize_name(project_name) / "research"


def _init_clients() -> tuple[AsyncOpenAI, TavilyClient]:
    openai_key = os.getenv("OPENAI_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not openai_key or openai_key.startswith("sk-your"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    if not tavily_key or tavily_key.startswith("tvly-your"):
        raise RuntimeError("TAVILY_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    return AsyncOpenAI(api_key=openai_key), TavilyClient(api_key=tavily_key)


async def _call_llm(
    client: AsyncOpenAI,
    system: str,
    user_msg: str,
    temperature: float = 0.3,
) -> dict:
    """LLM 호출 공통 함수. JSON 응답을 dict로 반환."""
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


# ── Step 0: 입력 보강 (A → B) ──────────────────────────────

async def step0_enrich(client: AsyncOpenAI, input_a: InputA) -> InputB:
    """A → B 변환."""
    user_msg = (
        "아래 사용자 입력을 보강해주세요.\n\n"
        f"project_name: {input_a.project_name}\n"
        f"topic: {input_a.topic}\n"
        f"purpose: {input_a.purpose}\n"
        f"target_audience: {input_a.target_audience or '(미입력)'}\n"
        f"constraints: {input_a.constraints or '(미입력)'}\n"
        f"known_info: {input_a.known_info or '(미입력)'}\n"
        f"gaps: {json.dumps(input_a.gaps, ensure_ascii=False) if input_a.gaps else '(미입력)'}"
    )
    result = await _call_llm(client, STEP0_SYSTEM, user_msg)
    return InputB(**result)


async def step0_revise(client: AsyncOpenAI, current_b: InputB, feedback: str) -> InputB:
    """사용자 피드백을 반영하여 B를 수정."""
    user_msg = (
        f"현재 조사 계획(B):\n{json.dumps(current_b.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        f'사용자 수정 요청:\n"{feedback}"\n\n'
        "수정사항을 반영한 B를 JSON으로 출력하세요."
    )
    result = await _call_llm(client, STEP0_SYSTEM, user_msg)
    return InputB(**result)


def save_input_b(project_name: str, input_b: InputB) -> Path:
    """승인된 B를 raw/{project_name}/research/input_b.json에 저장."""
    pdir = _project_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / "input_b.json"
    path.write_text(
        json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


# ── Step 1: 쿼리 분해 ──────────────────────────────────────

async def step1_make_queries(client: AsyncOpenAI, input_b: InputB) -> list[str]:
    """B → 검색 쿼리 3~5개."""
    user_msg = (
        "아래 조사 계획에 맞는 검색 쿼리를 생성해주세요.\n\n"
        f"{json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2)}"
    )
    result = await _call_llm(client, STEP1_SYSTEM, user_msg)
    queries = result.get("queries", [])
    if not queries:
        for v in result.values():
            if isinstance(v, list):
                queries = v
                break
    return queries[:MAX_SEARCH_QUERIES]


# ── Step 2: 병렬 검색 + 페이지 읽기 ────────────────────────

async def _search_tavily(tavily: TavilyClient, query: str) -> list[dict]:
    """Tavily 단일 쿼리 검색 (sync API → executor)."""
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: tavily.search(
                query=query,
                search_depth="basic",
                max_results=TAVILY_MAX_RESULTS,
                include_raw_content=False,
            ),
        )
        return results.get("results", [])
    except Exception as e:
        print(f"  [WARN] 검색 실패 [{query}]: {e}")
        return []


async def _read_jina(url: str) -> Optional[str]:
    """Jina Reader로 페이지 본문 추출."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(jina_url, headers={"Accept": "text/markdown"})
            if resp.status_code == 200:
                return resp.text[:JINA_CONTENT_LIMIT]
    except Exception as e:
        print(f"  [WARN] 페이지 읽기 실패 [{url[:60]}]: {e}")
    return None


async def step2_search_and_read(
    tavily: TavilyClient,
    queries: list[str],
    project_name: str,
) -> list[SourceInfo]:
    """병렬 검색 + 페이지 읽기. 결과를 raw/에 저장."""

    # 2-1. 병렬 검색
    search_tasks = [_search_tavily(tavily, q) for q in queries]
    all_results = await asyncio.gather(*search_tasks)

    # 2-2. 중복 URL 제거
    seen: set[str] = set()
    unique: list[dict] = []
    for results in all_results:
        for r in results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

    # 검색 원본 저장
    pdir = _project_dir(project_name)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "search_results.json").write_text(
        json.dumps(unique, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 2-3. 상위 N개 페이지 본문 추출 (병렬)
    top = unique[:MAX_PAGES_TO_READ]
    read_tasks = [_read_jina(r["url"]) for r in top]
    contents = await asyncio.gather(*read_tasks)

    # 페이지 본문 개별 저장
    sources_dir = pdir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    sources: list[SourceInfo] = []
    for idx, (r, content) in enumerate(zip(top, contents), 1):
        if content:
            md_path = sources_dir / f"source_{idx:03d}.md"
            md_path.write_text(content, encoding="utf-8")

        sources.append(
            SourceInfo(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("content", "")[:300],
                content=content,
            )
        )

    return sources


# ── Step 3: 통합 정리 ──────────────────────────────────────

async def step3_synthesize(
    client: AsyncOpenAI,
    input_b: InputB,
    sources: list[SourceInfo],
) -> ResearchOutput:
    """수집 결과 → 조사 프레임 매핑 → 최종 출력."""

    src_text = ""
    for i, s in enumerate(sources, 1):
        src_text += f"\n--- 출처 {i} ---\n"
        src_text += f"URL: {s.url}\n제목: {s.title}\n"
        if s.content:
            src_text += f"본문:\n{s.content}\n"
        else:
            src_text += f"스니펫: {s.snippet}\n"

    user_msg = (
        "아래 조사 계획과 수집된 소스를 기반으로 통합 정리해주세요.\n\n"
        f"## 조사 계획\n{json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        f"## 수집된 소스\n{src_text}"
    )

    result = await _call_llm(client, STEP3_SYSTEM, user_msg, temperature=0.2)

    return ResearchOutput(
        topic=input_b.topic,
        purpose=input_b.purpose,
        research_frame=result.get("research_frame", {}),
        gaps_remaining=result.get("gaps_remaining", []),
        sources=sources,
        summary_report=result.get("summary_report", ""),
    )


# ── 전체 파이프라인 (Step 1~3) ──────────────────────────────

async def run_pipeline(project_name: str, input_b: InputB) -> ResearchOutput:
    """승인된 B를 받아 Step 1~3을 실행하고 ResearchOutput을 반환."""
    openai_client, tavily_client = _init_clients()

    # Step 1
    queries = await step1_make_queries(openai_client, input_b)

    # Step 2
    sources = await step2_search_and_read(tavily_client, queries, project_name)

    # Step 3
    output = await step3_synthesize(openai_client, input_b, sources)

    return output


# ── 단독 Step 0 (start 엔드포인트용) ────────────────────────

async def run_step0(input_a: InputA) -> InputB:
    """Step 0만 실행: A → B 변환."""
    openai_client, _ = _init_clients()
    return await step0_enrich(openai_client, input_a)


async def run_step0_revise(current_b: InputB, feedback: str) -> InputB:
    """사용자 피드백으로 B를 수정."""
    openai_client, _ = _init_clients()
    return await step0_revise(openai_client, current_b, feedback)
