"""홀드아웃 80:20 split + 에이전트 응답 수집 (plan 0023).

PoC(옵션 C): persona_full_prompt 를 손대지 않고 같은 질문을 재예측시킨다.
모델이 외운 그대로 뱉는 것도 "복제 충실도" 의 일부로 인정하는 단순 비교.
"""
from __future__ import annotations

import asyncio
import random
from typing import Iterable

from database import Agent
from eval_holdout.parser import QAPair
from fgi.prompts.utterance import build_v1_1_persona_intro
from services.agent_service import demographics as _agent_demographics
from services.llm_client import chat_completion

# 응답 생성 모델 — 발화·1:1 대화와 동일 (gpt-4.1-mini, llm_client 기본)
GEN_TEMPERATURE = 0.7
GEN_MAX_TOKENS = 400

# 결정적 split
DEFAULT_SEED = 42
DEFAULT_HOLDOUT_RATIO = 0.2


def split_holdout(
    pairs: list[QAPair],
    *,
    ratio: float = DEFAULT_HOLDOUT_RATIO,
    seed: int = DEFAULT_SEED,
    per_lens_holdout: int | None = None,
) -> tuple[list[QAPair], list[QAPair]]:
    """결정적 split — (in_sample, holdout) 반환.

    Lens 비례 유지를 위해 lens 별로 셔플 후 자른다 (stratified).

    Args:
        ratio: lens 별 holdout 비율. per_lens_holdout 가 주어지면 무시.
        seed: 셔플 시드.
        per_lens_holdout: 지정 시 lens 별로 정확히 N개 holdout. lens 페어가
            N 미만이면 전체를 holdout 으로 (in_sample 0). lens 간 표본 균등화용.
    """
    rng = random.Random(seed)
    by_lens: dict[str, list[QAPair]] = {}
    for p in pairs:
        by_lens.setdefault(p.lens, []).append(p)

    in_sample: list[QAPair] = []
    holdout: list[QAPair] = []
    for lens in sorted(by_lens.keys()):
        bucket = list(by_lens[lens])
        rng.shuffle(bucket)
        if per_lens_holdout is not None:
            k = min(per_lens_holdout, len(bucket))
        else:
            k = max(1, round(len(bucket) * ratio))
        holdout.extend(bucket[:k])
        in_sample.extend(bucket[k:])
    return in_sample, holdout


def _format_question_prompt(pair: QAPair) -> str:
    """홀드아웃 질문 → agent 에게 던질 user 프롬프트.

    원본 응답이 옵션 번호("1 - A: …") 또는 Likert 점수("3 - 아마 사실 아님")인 경우가
    많아 agent 가 자유 텍스트로 답하면 비교가 어려울 수 있다. 그래서 응답 형식을
    가볍게 강제: "한 줄로 자기 입장을 말한 뒤, 어떤 선택지에 가까운지 한 단어로 표시".
    """
    lines = [
        f"[{pair.section_label} — {'포토이즘 도메인 ' if pair.domain else ''}질문]",
        f"질문: {pair.question}",
        "",
        f"위 질문에 1~3문장으로 자기 입장을 답하세요. (질문 유형: {pair.qtype})",
    ]
    return "\n".join(lines)


async def collect_agent_answer(
    agent: Agent,
    pair: QAPair,
    *,
    mock: bool | None = None,
) -> str:
    """agent 에게 1건의 홀드아웃 질문을 던지고 응답 수집.

    system = V1.1(anti-RLHF) + persona_full_prompt (FGI/1:1 대화와 동일 조립).
    """
    age_range, gender = _agent_demographics(agent)
    v1_1_intro = build_v1_1_persona_intro(age_range, gender)
    persona = agent.persona_full_prompt or "당신은 소비자 페르소나입니다."
    system = v1_1_intro + "\n\n" + persona
    user = _format_question_prompt(pair)
    return await chat_completion(
        system=system,
        user=user,
        temperature=GEN_TEMPERATURE,
        max_tokens=GEN_MAX_TOKENS,
        mock=mock,
    )


async def collect_all_answers(
    agent: Agent,
    pairs: Iterable[QAPair],
    *,
    concurrency: int = 4,
    mock: bool | None = None,
) -> list[tuple[QAPair, str]]:
    """홀드아웃 페어 전체에 대해 agent 응답 수집. concurrency 제한 동시 호출."""
    sem = asyncio.Semaphore(concurrency)
    pairs = list(pairs)

    async def _one(pair: QAPair) -> tuple[QAPair, str]:
        async with sem:
            ans = await collect_agent_answer(agent, pair, mock=mock)
            return pair, ans

    return await asyncio.gather(*(_one(p) for p in pairs))
