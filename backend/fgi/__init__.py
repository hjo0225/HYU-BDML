"""정식 FGI(다자 회의) 엔진 패키지 — plan 0008.

라운드 루프(moderator → agent×N → 사용자 개입 → round_end → … → session_end)를
SSE 로 흘려보내고 fgi_turns 에 영속화한다. 발화는 services.llm_client 를 공유
(키 없으면 mock 자동 폴백). spike/ 의 패턴을 참고해 재작성했으며 직접 import 하지 않는다.
"""
