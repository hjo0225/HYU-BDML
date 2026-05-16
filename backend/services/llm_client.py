"""LLM Chat Completion 헬퍼 — V1·V4 평가 + 향후 1:1 대화·FGI 공유.

OpenAI gpt-4o 동기 SDK 를 asyncio.to_thread 로 감싸 비동기 컨텍스트에서도
event loop 를 막지 않는다. 합성/mock 모드는 OPENAI_API_KEY 미설정 시 자동
폴백 — 결정적이라 테스트 안정.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Optional

import openai

_DEFAULT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")


def _has_api_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key and not key.startswith("dummy") and not key.startswith("test"))


def _mock_answer(system: str, user: str) -> str:
    """결정적 mock — system+user 의 sha256 으로 길이 고정 텍스트 생성.

    실제 의미는 없지만 동일 입력에 대해 항상 같은 답을 돌려주므로 V1 cosine
    비교가 결정적으로 동작한다. 한국어 더미 문장 풀에서 회전.
    """
    pool = [
        "저는 이 질문에 대해 신중하게 생각해 보았습니다.",
        "제 평소 가치관과 일치하는 방향으로 답하겠습니다.",
        "가족과 안정을 우선시하는 편이라 다음과 같이 답할 것 같습니다.",
        "단기적인 이익보다 장기적인 만족을 추구합니다.",
        "주변 사람들의 의견을 듣고 합리적으로 판단하려고 합니다.",
    ]
    digest = hashlib.sha256((system + "||" + user).encode("utf-8")).digest()
    start = digest[0] % len(pool)
    n = 2 + (digest[1] % 3)  # 2~4 문장
    sentences = [pool[(start + i) % len(pool)] for i in range(n)]
    return " ".join(sentences) + f" (응답 길이 시드={digest[:4].hex()})"


async def chat_completion(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 400,
    mock: Optional[bool] = None,
) -> str:
    """단일 chat completion.

    Args:
        system: 시스템 프롬프트 (페르소나).
        user: 사용자 질문.
        model: OpenAI 모델 (기본 CHAT_MODEL env 또는 gpt-4o).
        temperature, max_tokens: 표준 인자.
        mock: True=강제 mock, False=강제 실 API, None=API 키 유무 자동.

    Returns:
        에이전트 답변 텍스트.
    """
    use_mock = mock if mock is not None else not _has_api_key()
    if use_mock:
        return _mock_answer(system, user)

    def _call() -> str:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        res = client.chat.completions.create(
            model=model or _DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (res.choices[0].message.content or "").strip()

    return await asyncio.to_thread(_call)
