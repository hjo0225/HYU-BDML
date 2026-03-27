"""
Fast Research Agent Pipeline
============================
인터뷰 질문지 설계 / 보고서 작성을 위한 배경 조사 에이전트.

실행: python pipeline.py

구조:
  Step 0. 입력 보강 (A → B) + 사용자 확인
  Step 1. 쿼리 분해 (B → 검색 쿼리 3~5개)
  Step 2. 병렬 검색 + 페이지 읽기 (Tavily + Jina Reader)
  Step 3. 통합 정리 → JSON + 요약 리포트
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from tavily import TavilyClient
import httpx

# ── .env 로드 ──
load_dotenv()


# ============================================================
# 1. 데이터 모델
# ============================================================

class InputA(BaseModel):
    """사용자 최소 입력."""
    topic: str = Field(..., description="조사 주제")
    purpose: str = Field(..., description="용도: interview_prep | report_context")
    target_audience: Optional[str] = Field(None, description="인터뷰 대상 / 타겟 세그먼트")
    constraints: Optional[str] = Field(None, description="범위 제한")
    known_info: Optional[str] = Field(None, description="이미 아는 정보")
    gaps: Optional[list[str]] = Field(None, description="알고 싶은 빈 칸")


class InputB(BaseModel):
    """LLM이 보강한 구조화된 입력."""
    topic: str
    purpose: str
    context: dict = Field(default_factory=dict)
    research_frame: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)


class SourceInfo(BaseModel):
    """수집된 출처."""
    url: str
    title: str
    snippet: str
    content: Optional[str] = None
    reliability: str = "unverified"


class ResearchOutput(BaseModel):
    """최종 출력."""
    topic: str
    purpose: str
    research_frame: dict = Field(default_factory=dict)
    gaps_remaining: list[str] = Field(default_factory=list)
    sources: list[SourceInfo] = Field(default_factory=list)
    summary_report: str = ""


# ============================================================
# 2. 설정 및 클라이언트 초기화
# ============================================================

def init_clients() -> tuple[OpenAI, TavilyClient]:
    """API 키를 검증하고 클라이언트를 초기화한다."""

    openai_key = os.getenv("OPENAI_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not openai_key or openai_key.startswith("sk-your"):
        print("❌ OPENAI_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 API 키를 입력해주세요.")
        sys.exit(1)

    if not tavily_key or tavily_key.startswith("tvly-your"):
        print("❌ TAVILY_API_KEY가 설정되지 않았습니다.")
        print("   https://tavily.com 에서 무료 키를 발급받으세요.")
        sys.exit(1)

    return OpenAI(api_key=openai_key), TavilyClient(api_key=tavily_key)


# 설정값
LLM_MODEL = "gpt-4o"
MAX_SEARCH_QUERIES = 5
MAX_PAGES_TO_READ = 8
TAVILY_MAX_RESULTS = 5
JINA_CONTENT_LIMIT = 3000  # 토큰 절약을 위한 본문 길이 제한 (자)


# ============================================================
# 3. 프롬프트
# ============================================================

STEP0_SYSTEM = """당신은 리서치 플래닝 전문가입니다.
사용자의 최소 입력(A)을 받아서, Fast Research를 위한 구조화된 입력(B)으로 보강합니다.

## 규칙
1. purpose에 따라 research_frame을 자동 선택:
   - interview_prep → consumer_segments, purchase_behavior, pain_points, trends, competitors
   - report_context → market_size, growth_rate, competitors, trends, regulation

2. 사용자가 known_info를 제공했으면, 그 내용과 중복되는 항목은 gaps에서 제외합니다.
3. 사용자가 gaps를 제공했으면, 그걸 최우선 조사 대상으로 포함합니다.
4. gaps가 비어있으면, topic + purpose로부터 "반드시 알아야 하는데 아직 모르는 것"을 3~5개 추론합니다.
5. constraints를 구조화합니다 (region, time_range, focus 등).

## 출력
반드시 아래 JSON만 출력하세요. 다른 텍스트 없이.
{
  "topic": "...",
  "purpose": "...",
  "context": {
    "project_name": "...",
    "target_audience": "...",
    "product_category": "...",
    "known_info": "...",
    "gaps": ["...", "..."]
  },
  "research_frame": ["...", "..."],
  "constraints": {
    "region": "...",
    "time_range": "...",
    "focus": "..."
  }
}"""

STEP1_SYSTEM = """당신은 검색 쿼리 생성 전문가입니다.
보강된 리서치 입력(B)을 받아서 최적의 검색 쿼리 3~5개를 생성합니다.

## 규칙
1. 각 쿼리는 research_frame의 항목 하나 이상을 커버합니다.
2. known_info에 이미 있는 내용은 검색하지 않습니다.
3. gaps에 명시된 항목을 최우선으로 검색합니다.
4. 쿼리는 짧고 구체적으로 (한국어 1~8단어).
5. 연도/시기가 중요하면 포함합니다.
6. constraints의 region, focus를 반영합니다.

## 출력
반드시 아래 JSON만 출력하세요.
{"queries": ["쿼리1", "쿼리2", "쿼리3"]}"""

STEP3_SYSTEM = """당신은 리서치 통합 전문가입니다.
여러 출처에서 수집된 정보를 조사 프레임에 맞춰 통합 정리합니다.

## 규칙
1. research_frame의 각 항목별로 findings를 정리합니다.
2. 같은 수치가 여러 출처에서 나오면 출처별로 병기합니다.
3. 신뢰도 표기: high(공식 통계/보고서) | medium(뉴스/업계 리포트) | low(블로그/비공식).
4. 정보가 부족한 항목은 gaps_remaining에 명시합니다.
5. 과장하거나 추론으로 빈 칸을 채우지 않습니다.
6. summary_report는 마크다운 형식으로, 핵심 발견 + 인터뷰/보고서 설계 시 고려사항 + 미확인 항목을 포함합니다.

## 출력
반드시 아래 JSON만 출력하세요.
{
  "research_frame": {
    "항목명": {
      "findings": "조사 결과 요약",
      "confidence": "high | medium | low",
      "sources": ["url1", "url2"]
    }
  },
  "gaps_remaining": ["채우지 못한 정보1"],
  "summary_report": "## 조사 요약\\n\\n..."
}"""


# ============================================================
# 4. Step 0: 입력 보강 (A → B) + 사용자 확인 루프
# ============================================================

def _call_llm(client: OpenAI, system: str, user_msg: str, temperature: float = 0.3) -> dict:
    """LLM 호출 공통 함수. JSON 응답을 dict로 반환."""
    response = client.chat.completions.create(
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


def step0_enrich(client: OpenAI, input_a: InputA) -> InputB:
    """A → B 변환."""
    user_msg = f"""아래 사용자 입력을 보강해주세요.

topic: {input_a.topic}
purpose: {input_a.purpose}
target_audience: {input_a.target_audience or '(미입력)'}
constraints: {input_a.constraints or '(미입력)'}
known_info: {input_a.known_info or '(미입력)'}
gaps: {json.dumps(input_a.gaps, ensure_ascii=False) if input_a.gaps else '(미입력)'}"""

    result = _call_llm(client, STEP0_SYSTEM, user_msg)
    return InputB(**result)


def display_b(b: InputB) -> None:
    """B를 사용자에게 보여준다."""
    print("\n" + "=" * 60)
    print("📋  조사 계획 (확인해주세요)")
    print("=" * 60)
    print(f"  주제:  {b.topic}")
    print(f"  목적:  {b.purpose}")

    ctx = b.context
    if ctx.get("target_audience"):
        print(f"  타겟:  {ctx['target_audience']}")
    if ctx.get("known_info"):
        print(f"  이미 아는 것: {ctx['known_info']}")

    gaps = ctx.get("gaps", [])
    if gaps:
        print(f"  알고 싶은 것:")
        for g in gaps:
            print(f"    - {g}")

    print(f"\n  [조사 항목]  {', '.join(b.research_frame)}")

    if b.constraints:
        parts = [f"{k}={v}" for k, v in b.constraints.items() if v]
        print(f"  [제약 조건]  {', '.join(parts)}")

    print("=" * 60)
    print("  ✏️  수정할 내용을 입력하거나, '승인'을 입력하세요.")


def step0_with_review(client: OpenAI, input_a: InputA) -> InputB:
    """Step 0 전체: 보강 → 확인 → (수정 루프) → 승인."""
    input_b = step0_enrich(client, input_a)

    while True:
        display_b(input_b)
        feedback = input("\n> ").strip()

        if feedback.lower() in ["승인", "확인", "ok", "yes", "y", ""]:
            print("\n✅ 승인됨.\n")
            return input_b

        # 수정 반영
        update_msg = f"""현재 조사 계획(B):
{json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2)}

사용자 수정 요청:
"{feedback}"

수정사항을 반영한 B를 JSON으로 출력하세요."""

        result = _call_llm(client, STEP0_SYSTEM, update_msg)
        input_b = InputB(**result)


# ============================================================
# 5. Step 1: 쿼리 분해
# ============================================================

def step1_make_queries(client: OpenAI, input_b: InputB) -> list[str]:
    """B → 검색 쿼리 3~5개."""
    user_msg = f"""아래 조사 계획에 맞는 검색 쿼리를 생성해주세요.

{json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2)}"""

    result = _call_llm(client, STEP1_SYSTEM, user_msg)

    # {"queries": [...]} 형태
    queries = result.get("queries", [])
    if not queries:
        # fallback: 첫 번째 리스트 값 사용
        for v in result.values():
            if isinstance(v, list):
                queries = v
                break

    return queries[:MAX_SEARCH_QUERIES]


# ============================================================
# 6. Step 2: 병렬 검색 + 페이지 읽기
# ============================================================

async def _search_tavily(tavily: TavilyClient, query: str) -> list[dict]:
    """Tavily 단일 쿼리 검색. (sync API를 async에서 호출)"""
    try:
        # tavily-python은 sync이므로 executor에서 실행
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
        print(f"  ⚠️  검색 실패 [{query}]: {e}")
        return []


async def _read_jina(url: str) -> Optional[str]:
    """Jina Reader로 페이지 본문 추출."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(jina_url, headers={"Accept": "text/markdown"})
            if resp.status_code == 200:
                return resp.text[:JINA_CONTENT_LIMIT]
    except Exception as e:
        print(f"  ⚠️  페이지 읽기 실패 [{url[:60]}]: {e}")
    return None


async def step2_search_and_read(
    tavily: TavilyClient, queries: list[str]
) -> list[SourceInfo]:
    """병렬 검색 + 페이지 읽기."""

    # 2-1. 병렬 검색
    search_tasks = [_search_tavily(tavily, q) for q in queries]
    all_results = await asyncio.gather(*search_tasks)

    # 2-2. 중복 URL 제거
    seen = set()
    unique = []
    for results in all_results:
        for r in results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

    print(f"  검색 결과: {len(unique)}개 URL 수집")

    # 2-3. 상위 N개 페이지 본문 추출 (병렬)
    top = unique[:MAX_PAGES_TO_READ]
    read_tasks = [_read_jina(r["url"]) for r in top]
    contents = await asyncio.gather(*read_tasks)

    read_count = sum(1 for c in contents if c)
    print(f"  페이지 읽기: {read_count}개 성공")

    # 2-4. SourceInfo 변환
    sources = []
    for r, content in zip(top, contents):
        sources.append(SourceInfo(
            url=r.get("url", ""),
            title=r.get("title", ""),
            snippet=r.get("content", "")[:300],
            content=content,
        ))

    return sources


# ============================================================
# 7. Step 3: 통합 정리
# ============================================================

def step3_synthesize(
    client: OpenAI, input_b: InputB, sources: list[SourceInfo]
) -> ResearchOutput:
    """수집 결과 → 조사 프레임 매핑 → 최종 출력."""

    # 소스 텍스트 포맷
    src_text = ""
    for i, s in enumerate(sources, 1):
        src_text += f"\n--- 출처 {i} ---\n"
        src_text += f"URL: {s.url}\n제목: {s.title}\n"
        if s.content:
            src_text += f"본문:\n{s.content}\n"
        else:
            src_text += f"스니펫: {s.snippet}\n"

    user_msg = f"""아래 조사 계획과 수집된 소스를 기반으로 통합 정리해주세요.

## 조사 계획
{json.dumps(input_b.model_dump(), ensure_ascii=False, indent=2)}

## 수집된 소스
{src_text}"""

    result = _call_llm(client, STEP3_SYSTEM, user_msg, temperature=0.2)

    return ResearchOutput(
        topic=input_b.topic,
        purpose=input_b.purpose,
        research_frame=result.get("research_frame", {}),
        gaps_remaining=result.get("gaps_remaining", []),
        sources=sources,
        summary_report=result.get("summary_report", ""),
    )


# ============================================================
# 8. 출력 저장
# ============================================================

def save_outputs(output: ResearchOutput) -> tuple[Path, Path]:
    """결과를 output/ 디렉토리에 저장."""
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = out_dir / f"research_{timestamp}.json"
    json_data = output.model_dump()
    # content 필드는 JSON에서 제외 (너무 길어서)
    for s in json_data.get("sources", []):
        s.pop("content", None)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 마크다운 리포트
    md_path = out_dir / f"report_{timestamp}.md"
    md_path.write_text(output.summary_report, encoding="utf-8")

    return json_path, md_path


# ============================================================
# 9. 사용자 입력 수집
# ============================================================

def collect_user_input() -> InputA:
    """CLI에서 사용자 입력을 수집한다."""
    print("\n" + "=" * 60)
    print("🔍  Fast Research Agent")
    print("=" * 60)

    topic = input("\n조사 주제를 입력하세요:\n> ").strip()
    if not topic:
        print("주제는 필수입니다.")
        sys.exit(1)

    print("\n용도를 선택하세요:")
    print("  1) interview_prep  — 인터뷰 질문지 설계를 위한 배경 조사")
    print("  2) report_context  — 보고서 작성을 위한 맥락 조사")
    purpose_choice = input("> ").strip()
    purpose = "report_context" if purpose_choice == "2" else "interview_prep"

    print("\n[선택] 인터뷰 대상 / 타겟 세그먼트 (엔터로 건너뛰기):")
    target = input("> ").strip() or None

    print("\n[선택] 범위 제한 (예: '프리미엄 제품 중심') (엔터로 건너뛰기):")
    constraints = input("> ").strip() or None

    print("\n[선택] 이미 알고 있는 정보 (엔터로 건너뛰기):")
    known = input("> ").strip() or None

    print("\n[선택] 특별히 알고 싶은 것 (쉼표로 구분, 엔터로 건너뛰기):")
    gaps_raw = input("> ").strip()
    gaps = [g.strip() for g in gaps_raw.split(",") if g.strip()] if gaps_raw else None

    return InputA(
        topic=topic,
        purpose=purpose,
        target_audience=target,
        constraints=constraints,
        known_info=known,
        gaps=gaps,
    )


# ============================================================
# 10. 메인
# ============================================================

async def run_pipeline(input_a: InputA) -> ResearchOutput:
    """파이프라인 전체 실행."""

    openai_client, tavily_client = init_clients()

    # Step 0
    print("\n── Step 0: 입력 보강 중...")
    input_b = step0_with_review(openai_client, input_a)

    # Step 1
    print("── Step 1: 검색 쿼리 생성 중...")
    queries = step1_make_queries(openai_client, input_b)
    input_b.search_queries = queries
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
    print()

    # Step 2
    print("── Step 2: 병렬 검색 + 페이지 읽기 중...")
    sources = await step2_search_and_read(tavily_client, queries)
    print()

    # Step 3
    print("── Step 3: 통합 정리 중...")
    output = step3_synthesize(openai_client, input_b, sources)

    if output.gaps_remaining:
        print(f"  ⚠️  미확인 항목: {', '.join(output.gaps_remaining)}")
    print()

    return output


def main():
    # 입력 수집
    input_a = collect_user_input()

    # 파이프라인 실행
    output = asyncio.run(run_pipeline(input_a))

    # 결과 저장
    json_path, md_path = save_outputs(output)

    # 완료 메시지
    print("=" * 60)
    print("✅  Fast Research 완료!")
    print(f"  📊 JSON: {json_path}")
    print(f"  📝 리포트: {md_path}")
    print("=" * 60)

    # 리포트 미리보기
    print("\n── 요약 리포트 ──\n")
    print(output.summary_report)


if __name__ == "__main__":
    main()
