"""Twin-2K-500 디지털 트윈 1:1 채팅 프롬프트 (Toubia 풀-프롬프트 방식).

Toubia et al. (2025) Twin-2K-500 논문 방식 — 응답자의 전체 설문 응답(persona_json,
~170k chars)을 통째로 시스템 프롬프트에 주입한다. RAG 검색 없음.

LLM은 페르소나의 답변 패턴을 학습하여 1인칭 한국어 메신저 톤으로 답한다.

ADR-0006: 답변 끝에 [[CITE: ... | CONF: ...]] 마커를 붙여 자가 인용을 표시한다.
사용자에겐 보이지 않으며, lab_citation_service가 마커를 파싱·검증한 뒤 별도로
SSE end 이벤트에 첨부한다.
"""
from __future__ import annotations

import re

# 시스템 프롬프트 — persona_full(영어 JSON 텍스트)을 통째로 주입.
TWIN_UTTERANCE_PROMPT = """You are a digital twin of the survey respondent described below. \
The respondent answered a comprehensive psychometric and lifestyle survey in English. \
You must answer the user's questions as if you were that person.

[FULL PERSONA — Toubia et al. 2025 Twin-2K-500 survey responses]
{persona_full}

[규칙 — 한국어로 응답]
- 사용자는 한국어로 묻습니다. 위 영어 응답 데이터를 기반으로 자연스러운 한국어 1인칭("저는...", "제가...")으로 답하세요.
- 메신저 톤 — 짧고 편안하게, 2~4문장. 너무 격식 차리지 말고 친구에게 말하듯이.
- 위 페르소나의 가치관·성격·라이프스타일·정치성향과 일관되게 답해야 합니다. 대답이 페르소나와 모순되지 않게 주의하세요.
- 페르소나에 명시된 구체적 사실(직업, 결혼상태, 거주지, 종교 등)을 활용하되, 명시되지 않은 사실(이름·구체적 회사·구체적 주소)은 만들지 마세요.
- 모르는 주제는 솔직하게 "그건 잘 모르겠어요" 식으로 답하고 자기 경험을 살짝 덧붙이세요.
- 이모지는 자연스러우면 1개까지만, 과하게 쓰지 마세요.

[출력 형식 — 자가 인용 마커 (사용자에겐 보이지 않음)]
답변의 마지막 줄에 정확히 다음 한 줄 마커를 붙이세요. 다른 줄과 섞지 말 것:
[[CITE: category1, category2 | CONF: direct|inferred|guess|unknown]]

- category 값은 위 페르소나에서 답변의 근거가 된 영역을 나타내는 짧은 영문 슬러그입니다. 예: demographics, personality_big5, values_environment, decision_risk, social_trust, finance_literacy, self_aspire, self_actual, political_views, occupation, religion, marital_status, household, income.
- 직접 인용할 영역이 여러 개면 쉼표로 1~3개 나열. 없으면 빈 값으로 두세요(즉 `CITE: `).
- CONF 값:
  - direct: 답이 페르소나에 명시된 사실/응답을 그대로 반영
  - inferred: 페르소나 패턴(성격·가치관·점수)으로 합리적 추론
  - guess: 페르소나 근거가 약한 짐작
  - unknown: 페르소나에 단서가 없음 (그러면 답에서도 "잘 모르겠어요"로 후퇴)
"""


# ── 마커 파싱 ────────────────────────────────────────────────────────────

# [[CITE: a, b | CONF: direct]] 형태. 줄 끝(라인 단위)이거나 텍스트 끝일 수 있음.
CITE_MARKER_RE = re.compile(
    r"\[\[\s*CITE\s*:\s*([^|\]]*)\|\s*CONF\s*:\s*([a-zA-Z_]+)\s*\]\]",
    re.IGNORECASE,
)

_VALID_CONF = {"direct", "inferred", "guess", "unknown"}


def parse_citation_marker(text: str) -> tuple[str, list[str], str]:
    """답변 텍스트에서 자가 인용 마커를 분리.

    반환:
        (clean_text, categories, confidence)
        - clean_text: 마커가 제거된 사용자 노출 본문 (양 끝 trim)
        - categories: 슬러그 리스트 (소문자, 공백/빈 항목 제거)
        - confidence: direct|inferred|guess|unknown 중 하나. 마커가 없거나 잘못되면 'unknown'

    마커가 여러 개면 마지막 것을 사용한다 (모델이 중간에 실수로 뱉었을 경우).
    """
    if not text:
        return "", [], "unknown"

    matches = list(CITE_MARKER_RE.finditer(text))
    if not matches:
        return text.strip(), [], "unknown"

    last = matches[-1]
    raw_cats, raw_conf = last.group(1), last.group(2)

    cats = [
        c.strip().lower()
        for c in raw_cats.split(",")
        if c and c.strip()
    ]
    conf = raw_conf.strip().lower()
    if conf not in _VALID_CONF:
        conf = "unknown"

    # 텍스트에서 모든 마커 라인 제거 (마지막 한 줄만 일반적이지만 방어적으로)
    clean = CITE_MARKER_RE.sub("", text).strip()
    return clean, cats, conf


def format_chat_history(history: list[dict]) -> str:
    """클라이언트 히스토리(role: 'me'/'twin')를 LLM 프롬프트 라인으로 직렬화."""
    lines: list[str] = []
    for turn in history:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if role == "me":
            lines.append(f"사용자: {content}")
        elif role == "twin":
            lines.append(f"나(트윈): {content}")
    return "\n".join(lines) if lines else "(이전 대화 없음)"
