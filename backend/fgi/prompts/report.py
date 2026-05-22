"""인사이트 보고서 프롬프트 — FGI transcript → 구조화 JSON (plan 0008 v2 · §14).
"""

REPORT_SYSTEM = "당신은 소비자 리서치 FGI 결과를 경영진용 인사이트 보고서로 정리하는 수석 애널리스트입니다."

REPORT_USER = """\
다음은 '{topic}' 주제로 진행된 FGI 전체 발언록입니다. 참여자: {agent_names}

[라운드 구성]
{round_plan}

[발언록]
{transcript}

이 발언록을 분석하여 아래 JSON 스키마로만 출력하세요(코드펜스·설명 없이 JSON 객체 하나).
실제 발언에 근거하고 추측을 최소화하세요.

{{
  "key_insights": [
    {{"title": "한 줄 핵심 발견", "description": "근거 요지", "sources": ["참여자명", ...]}}
  ],                                  // 3~5개
  "agent_perspectives": [
    {{"name": "참여자명", "stance": "이 주제에서의 입장(한 단어~짧은 구)", "key_quote": "대표 발언 인용"}}
  ],                                  // 참여자 전원
  "round_analysis": [
    {{"round": 1, "summary": "해당 라운드 토론의 분석 요약(2~3문장). 발언을 단순 나열하지 말고, 무엇이 드러났는지·참여자 간 공통점과 차이·시사점을 애널리스트 관점으로 종합. 필요하면 참여자명을 근거로 인용."}}
  ],                                  // [라운드 구성]의 각 round 당 정확히 1개, round 번호 일치
  "action_items": [
    {{"title": "실행 제안", "description": "구체 내용", "expected_effect": "예상 효과"}}
  ]                                   // 3~5개
}}
"""
