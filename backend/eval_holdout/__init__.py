"""Holdout 유사도 평가 (plan 0023, PoC).

pid_xxx.txt 원본 인간 응답에서 Q&A 페어를 추출 → 80:20 split → 홀드아웃 질문을
에이전트에 재예측시키고 LLM judge 로 일치 여부를 채점한다. 사전계산해 JSON
파일 캐시(`backend/data/holdout_eval/{agent_id}.json`)에 저장한다.
"""
