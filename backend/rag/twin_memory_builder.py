"""Twin-2K-500 `persona_summary` → 카테고리별 자연어 메모리 변환.

`persona_summary`는 영어 정형 텍스트로 다음 구조를 가진다:
- demographics 블록
- "The person's <X> score(s) are the following:" 헤더로 시작하는 다수의 심리척도 블록
- 정성응답 3개 (aspire / ought / actual)
- ultimatum/trust/dictator 게임의 정성 사고 흐름

영어 원본을 그대로 임베딩한다 — 발화 시 LLM이 한국어로 변환.
"""
from __future__ import annotations

import re


# section_name : (정규식, 카테고리, 중요도)
# 정규식은 헤더 라인부터 다음 헤더 또는 EOF까지 캡처한다.
def _section(start_pat: str) -> re.Pattern:
    """헤더 패턴부터 다음 'The person\'s ...are the following' 헤더 직전 또는 EOF까지."""
    return re.compile(
        rf"({start_pat}.*?)(?=\nThe person'?s\s|\nThe person also answered|\nThe person was asked|\Z)",
        re.DOTALL | re.IGNORECASE,
    )


# 메모리 카테고리 매핑 — persona_summary의 헤더 패턴 → (RAG 카테고리, importance)
# 헤더 후 본문을 그대로 카테고리 메모리로 사용한다.
_SECTION_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (_section(r"The person'?s demographics"),                                  "demographics",       70),
    (_section(r"The person'?s Big 5 scores"),                                  "personality_big5",   65),
    (_section(r"The person'?s need for cognition"),                            "cognition_general",  55),
    (_section(r"The person'?s agentic ?/ ?communal"),                          "values_agency",      55),
    (_section(r"The person'?s minimalism"),                                    "values_minimalism",  45),
    (_section(r"The person'?s basic empathy"),                                 "emotion_empathy",    50),
    (_section(r"The person'?s G\.R\.E\.E\.N"),                                 "values_environment", 45),
    (_section(r"The person'?s CRT score"),                                     "cognition_reflection", 50),
    (_section(r"The person'?s fluid and crystallized"),                        "cognition_intelligence", 55),
    (_section(r"The person'?s syllogism"),                                     "cognition_logic",    45),
    (_section(r"The person'?s ultimatum game"),                                "social_ultimatum",   55),
    (_section(r"The person'?s mental accounting"),                             "finance_mental",     45),
    (_section(r"The person'?s social desirability"),                           "social_desirability", 40),
    (_section(r"The person'?s Beck anxiety"),                                  "emotion_anxiety",    50),
    (_section(r"The person'?s individualism vs collectivism"),                 "values_individualism", 55),
    (_section(r"The person'?s financial literacy"),                            "finance_literacy",   50),
    (_section(r"The person'?s numeracy"),                                      "cognition_numeracy", 45),
    (_section(r"The person'?s discount rate and present bias"),                "finance_time_pref",  50),
    (_section(r"The person'?s risk aversion"),                                 "decision_risk",      55),
    (_section(r"The person'?s loss aversion"),                                 "decision_loss",      55),
    (_section(r"The person'?s trust game"),                                    "social_trust",       60),
    (_section(r"The person'?s regulatory focus"),                              "values_regulatory",  45),
    (_section(r"The person'?s tightwad"),                                      "finance_tightwad",   50),
    (_section(r"The person'?s Beck depression"),                               "emotion_depression", 50),
    (_section(r"The person'?s need for uniqueness"),                           "values_uniqueness",  40),
    (_section(r"The person'?s self-monitoring"),                               "self_monitoring",    40),
    (_section(r"The person'?s self-concept clarity"),                          "self_clarity",       45),
    (_section(r"The person'?s need for closure"),                              "cognition_closure",  40),
    (_section(r"The person'?s maximization"),                                  "decision_maximization", 45),
    (_section(r"The person'?s dictator game"),                                 "social_dictator",    55),
]


# 정성응답 3개 — 각각 별도 메모리. 가장 중요도 높음 (자기 정체성 직접 진술).
_QUAL_PATTERNS: list[tuple[str, re.Pattern, int]] = [
    (
        "self_aspire",
        re.compile(
            r'type of person you\s+aspire to be.*?They answered:\s*"([^"]+)"',
            re.DOTALL,
        ),
        80,
    ),
    (
        "self_ought",
        re.compile(
            r'type of person you\s+ought to be.*?They answered:\s*"([^"]+)"',
            re.DOTALL,
        ),
        75,
    ),
    (
        "self_actual",
        re.compile(
            r'type of person you\s+actually are.*?They answered:\s*"([^"]+)"',
            re.DOTALL,
        ),
        85,
    ),
]


def _clean_text(text: str) -> str:
    """공백 정규화 (멀티스페이스 → 단일, 양끝 trim)."""
    return re.sub(r"[ \t]+", " ", text).strip()


def build_memories(persona_summary: str) -> list[tuple[str, str, int]]:
    """`persona_summary` → list of (category, text, importance).

    빈 텍스트나 매칭 실패 카테고리는 자동으로 스킵.
    """
    out: list[tuple[str, str, int]] = []
    seen: set[str] = set()

    # 1) 심리척도/인구통계 섹션
    for pat, category, importance in _SECTION_PATTERNS:
        m = pat.search(persona_summary)
        if not m:
            continue
        body = _clean_text(m.group(1))
        # 너무 짧은 섹션(헤더만 잡힌 경우) 제외
        if len(body) < 30:
            continue
        # 같은 카테고리 중복 방지
        if category in seen:
            continue
        seen.add(category)
        out.append((category, body, importance))

    # 2) 정성응답 — self_aspire / self_ought / self_actual
    for category, pat, importance in _QUAL_PATTERNS:
        m = pat.search(persona_summary)
        if not m:
            continue
        answer = _clean_text(m.group(1))
        if len(answer) < 10:
            continue
        out.append((
            category,
            f"When asked about themselves ({category.replace('self_', '')}), they said: \"{answer}\"",
            importance,
        ))

    return out
