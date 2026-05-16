"""follow-up cascade — 발언이 얕거나 일반론에 빠졌을 때 follow-up 트리거.

2단 캐스케이드로 비용을 아낀다:
  1차 token filter (무료, 정규식·길이): 명백히 얕은 발언은 즉시 통과
  2차 LLM rubric (~1~3 cent/call): 1차 통과한 발언만 rubric 평가

본 스파이크에서 검증할 핵심 가설:
  "1차 필터로 cascade 호출의 50% 이상을 사전 제거하면서도, 2차에서
   판정 정확도(육안 확인 기준) 가 유지된다."
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


# 일반론·hedging 마커 (1차 필터에서 즉시 follow-up 필요로 판정)
HEDGING_PATTERNS = [
    r"잘\s*모르겠",
    r"사람마다\s*다",
    r"케이스\s*바이\s*케이스",
    r"좋은\s*것\s*같",
    r"나쁘지\s*않",
    r"음[…\.]+",
    r"글쎄[…\.]+",
]

_HEDGING_RE = re.compile("|".join(HEDGING_PATTERNS), re.IGNORECASE)


@dataclass
class CascadeResult:
    need_followup: bool
    stage: str               # "token_filter" or "llm_rubric"
    score: int | None        # llm_rubric 단계에서만 채워짐 (1~5)
    reason: str


def token_filter(utterance: str, min_tokens: int = 25) -> CascadeResult | None:
    """발화 길이와 hedging 마커로 사전 판정.

    Returns:
      CascadeResult — 명백히 얕은 경우 (need_followup=True)
      None         — 판정 보류, LLM rubric 단계로 진행
    """
    # 길이 너무 짧으면 즉시 follow-up
    approx_tokens = len(utterance.split())
    if approx_tokens < min_tokens:
        return CascadeResult(
            need_followup=True,
            stage="token_filter",
            score=None,
            reason=f"발화 길이 부족 ({approx_tokens}<{min_tokens} 토큰 근사)",
        )

    # hedging 마커 발견 시 즉시 follow-up
    m = _HEDGING_RE.search(utterance)
    if m:
        return CascadeResult(
            need_followup=True,
            stage="token_filter",
            score=None,
            reason=f"hedging 마커 '{m.group()}'",
        )

    # 1차에서는 판정 불가 → 2차로
    return None
