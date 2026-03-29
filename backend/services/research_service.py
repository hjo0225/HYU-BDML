"""시장조사 서비스 — OpenAI 스트리밍 호출"""
import json
from typing import AsyncGenerator
from models.schemas import ResearchBrief
from services.openai_client import get_client
from prompts.research import RESEARCH_SYSTEM_PROMPT

# 진행 단계 정의
RESEARCH_STEPS = [
    "연구 정보 분석 중...",
    "시장 개요 조사 중...",
    "경쟁 환경 분석 중...",
    "타깃 고객 분석 중...",
    "트렌드 및 시사점 도출 중...",
]


async def run_research(brief: ResearchBrief) -> AsyncGenerator[str, None]:
    """시장조사 수행 — SSE 이벤트를 yield"""
    client = get_client()

    # 사용자 메시지 구성
    user_message = (
        f"연구 배경: {brief.background}\n"
        f"연구 목적: {brief.objective}\n"
        f"활용방안: {brief.usage_plan}\n"
        f"카테고리: {brief.category}\n"
        f"타깃 고객: {brief.target_customer}"
    )

    # 스트리밍 호출
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        stream=True,
    )

    collected = ""
    step_index = 0
    # 단계별 진행 알림을 위한 토큰 임계값
    step_thresholds = [1, 100, 300, 600, 900]

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            collected += delta.content

            # 토큰 수에 따라 진행 단계 업데이트
            token_count = len(collected)
            if step_index < len(step_thresholds) and token_count >= step_thresholds[step_index]:
                yield f"data: {json.dumps({'type': 'status', 'step': step_index + 1, 'total': len(RESEARCH_STEPS), 'message': RESEARCH_STEPS[step_index]}, ensure_ascii=False)}\n\n"
                step_index += 1

            # 청크 전송
            yield f"data: {json.dumps({'type': 'chunk', 'content': delta.content}, ensure_ascii=False)}\n\n"

    # 완료 — JSON 파싱
    try:
        # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
        json_str = collected.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        result = json.loads(json_str)
        yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
    except (json.JSONDecodeError, IndexError):
        # 파싱 실패 시 원문 그대로 전달
        yield f"data: {json.dumps({'type': 'error', 'message': '결과 파싱 실패. 원문을 확인하세요.', 'raw': collected}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
