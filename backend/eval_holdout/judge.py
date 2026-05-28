"""LLM judge — gpt-4.1-mini 가 (질문, 인간응답, AI응답) → 일치 여부 판정 (plan 0023).

PoC: 같은 회사 모델로 자기 채점 편향이 있으나 비용·간결성 우선. 후속에서
Claude 3.5 Sonnet 으로 교체해 독립성 확보.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from eval_holdout.parser import QAPair
from services.llm_client import chat_completion

JUDGE_MODEL = "gpt-4.1-mini"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 300

Verdict = Literal["match", "partial", "no_match"]

_SYSTEM = """\
당신은 두 응답이 같은 '입장·태도·내용'을 표현하는지 판정하는 심사자입니다.
주제가 같다는 것만으로 일치라고 부르면 안 됩니다. 입장·선호·답이 같아야 일치입니다.

판정 규칙:
- "match": 두 응답이 같은 입장·태도·결론을 표현. 표현이 달라도 의미가 같으면 match.
- "partial": 한쪽은 명확하고 한쪽은 모호하거나 부분적으로만 같음. 또는 일부 차원만 일치.
- "no_match": 입장·태도·결론이 다름 또는 한쪽이 회피·동문서답.

반드시 다음 JSON 형식으로만 응답하세요. 다른 텍스트 금지.
{"verdict": "match" | "partial" | "no_match", "confidence": 0.0~1.0, "rationale": "한 문장 한국어 근거"}
"""

_USER_TEMPLATE = """\
[질문 카테고리] {section_label}{domain_tag}
[질문 유형] {qtype}
[질문] {question}

[인간 응답 (원본)]
{human_answer}

[AI 응답 (재예측)]
{agent_answer}

위 두 응답이 같은 입장인지 JSON 으로 판정.
"""


def _strip_code_fence(text: str) -> str:
    """LLM 이 ```json``` 펜스로 감싸 보내는 경우 제거."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_verdict(raw: str) -> dict:
    """judge 응답 JSON 파싱. 실패 시 conservative fallback."""
    t = _strip_code_fence(raw)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        # 본문에 JSON 만 추출 시도
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if not m:
            return {
                "verdict": "no_match",
                "confidence": 0.0,
                "rationale": "judge 출력 파싱 실패",
            }
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {
                "verdict": "no_match",
                "confidence": 0.0,
                "rationale": "judge 출력 파싱 실패",
            }
    verdict = obj.get("verdict", "no_match")
    if verdict not in ("match", "partial", "no_match"):
        verdict = "no_match"
    try:
        conf = float(obj.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    rationale = str(obj.get("rationale", "")).strip()[:300] or "근거 없음"
    return {"verdict": verdict, "confidence": conf, "rationale": rationale}


async def evaluate_pair(
    pair: QAPair,
    agent_answer: str,
    *,
    mock: bool | None = None,
) -> dict:
    """(질문, 인간응답, AI응답) → {verdict, confidence, rationale}."""
    user = _USER_TEMPLATE.format(
        section_label=pair.section_label,
        domain_tag=" / 포토이즘 도메인" if pair.domain else "",
        qtype=pair.qtype,
        question=pair.question,
        human_answer=pair.answer,
        agent_answer=agent_answer or "(응답 없음)",
    )
    raw = await chat_completion(
        system=_SYSTEM,
        user=user,
        model=JUDGE_MODEL,
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        mock=mock,
    )
    return _parse_verdict(raw)


# 점수화 — match=1.0, partial=0.5, no_match=0.0
_VERDICT_SCORE = {"match": 1.0, "partial": 0.5, "no_match": 0.0}


def verdict_to_score(verdict: str) -> float:
    return _VERDICT_SCORE.get(verdict, 0.0)
