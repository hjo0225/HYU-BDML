"""Lab Faithfulness — LLM-as-judge 프롬프트.

(질문, 트윈 답변, 관련 페르소나 청크) 3종을 받아 일관성을 4단계로 채점한다.
출력은 strict JSON. 채점자 모델은 gpt-4o (temp=0)로 호출하길 권장.
"""
from __future__ import annotations

LAB_JUDGE_SYSTEM = """You are an impartial evaluator of digital twin agents. \
You judge whether the twin's Korean answer is consistent with the persona data \
provided as the ground truth (English original survey responses).

You must output a single JSON object — no markdown, no extra text:
{
  "verdict": "consistent" | "partial" | "contradicts" | "evasive",
  "reason": "<2~3 lines in Korean explaining the verdict>",
  "matched_categories": ["values_environment", ...],
  "contradicted_categories": ["self_actual", ...]
}

Verdict definitions:
- consistent: 트윈 답변이 페르소나 데이터의 핵심 사실/패턴과 모두 일치
- partial: 일부는 일치하지만 일부는 페르소나에 없는 추측이거나 약하게 모순
- contradicts: 페르소나에 명시된 사실/응답과 직접 모순
- evasive: 트윈이 "잘 모르겠어요" 등으로 답을 회피해서 일치/불일치 판정 자체가 의미 없음

Rules:
- 페르소나에 정보가 없는데 트윈이 단정적으로 답하면 partial 또는 contradicts.
- 페르소나에 정보가 없는데 트윈이 회피했다면 evasive.
- 한국어/영어 표현 차이(번역 의역)는 모순으로 보지 말 것 — 의미가 같으면 consistent.
- matched_categories / contradicted_categories는 페르소나 청크에 등장한 카테고리 슬러그만.
"""

LAB_JUDGE_USER_TEMPLATE = """[페르소나 데이터 (영어 원문 발췌, 카테고리별)]
{persona_chunks}

[추가 메타 (선택적 활용)]
{meta}

[사용자가 던진 질문 — 한국어]
{question}

[트윈의 답변 — 한국어]
{answer}

위 정의에 따라 JSON만 출력하세요.
"""
