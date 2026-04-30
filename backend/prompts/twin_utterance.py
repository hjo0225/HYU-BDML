"""Twin-2K-500 디지털 트윈 1:1 채팅 프롬프트 (Toubia 풀-프롬프트 방식).

Toubia et al. (2025) Twin-2K-500 논문 방식 — 응답자의 전체 설문 응답(persona_json,
~170k chars)을 통째로 시스템 프롬프트에 주입한다. RAG 검색 없음.

LLM은 페르소나의 답변 패턴을 학습하여 1인칭 한국어 메신저 톤으로 답한다.
"""

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
"""


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
