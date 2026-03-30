"""에이전트 추천 프롬프트"""
AGENT_RECOMMEND_PROMPT = """
연구 정보와 시장조사를 기반으로 FGI 시뮬레이션에 적합한 AI 에이전트 5명을 설계하세요.

유형: customer(가상 고객), expert(도메인 전문가)
차별화 규칙:
- 고객끼리 연령/성격/가치관/소비성향 다르게
- 하나는 반드시 회의적/보수적
- 전문가는 분석적 관점

JSON 배열로만 응답:
[{"id":"agent-1", "type":"customer", "name":"이름 (나이)", "emoji":"이모지", "description":"2-3줄", "tags":["태그1","태그2","태그3"], "system_prompt":"상세 페르소나 (말투, 성격, 관심사, 가치관, 경험. 150자+)", "color":"#hex"}]

에이전트 color는 순서대로: #2E6DB4, #E67E22, #9B59B6, #27AE60, #C0392B
""".strip()
