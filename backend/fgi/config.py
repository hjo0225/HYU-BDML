"""FGI 엔진 하이퍼파라미터 (plan 0008 v2 · item 4).

사용자 제공 스펙의 §08 튜닝 값. env 로 override 가능 — 파일럿에서 조정.
"""
from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# follow-up cascade
TOKEN_THRESHOLD_N = _i("FGI_TOKEN_THRESHOLD", 25)         # 1차 필터: 직전 발화 토큰<N → 모호
SPECIFICITY_CUTOFF = _i("FGI_SPECIFICITY_CUTOFF", 2)      # 2차 LLM rubric: 총점<cutoff → 모호
FOLLOWUP_LIMIT_PER_ROUND = _i("FGI_FOLLOWUP_LIMIT", 5)    # Round 당 follow-up 한도
INACTIVE_RATIO = _f("FGI_INACTIVE_RATIO", 1 / 3)         # 비활동: 최활발자 발화수의 1/3 미만

# engagement score 가중치 (합=1.0)
W_RELEVANCE = _f("FGI_W_RELEVANCE", 0.4)
W_RECENCY = _f("FGI_W_RECENCY", 0.3)
W_REACTION = _f("FGI_W_REACTION", 0.2)
W_RANDOM = _f("FGI_W_RANDOM", 0.1)

# Round / 세션 제어
MAX_UTTER_PER_ROUND = _i("FGI_MAX_UTTER_PER_ROUND", 15)   # Round 내 총 발화 상한 (§11)
BASE_TURNS_PER_ROUND = _i("FGI_BASE_TURNS", 0)            # 0=참여자 수만큼 (동적 선정)
DEFAULT_MAX_ROUNDS = _i("FGI_DEFAULT_ROUNDS", 5)
NOVELTY_THRESHOLD = _f("FGI_NOVELTY_THRESHOLD", 0.3)      # §11 발화 포화도: novelty<임계 → Round 종료
SESSION_MAX_MIN = _f("FGI_SESSION_MAX_MIN", 60)          # §12 세션 최대 시간(분)

# Round 내부 Phase 구조 (v0.2 스펙: A 질문 → B 순서답변 → C 티키타카 → D 개입)
TIKITAKA_THRESHOLD = _f("FGI_TIKITAKA_THRESHOLD", 0.7)    # τ(현재 미사용): 과거 Phase C 발화권 컷오프. v0.3.4 부터 점수는 순서 결정에만 쓰고 하드 게이트는 폐지(보수적 점수에 토론이 죽는 문제). 호환 위해 키 유지.
MAX_TIKITAKA_UTTER = _i("FGI_MAX_TIKITAKA", 15)           # Phase C 발화 총상한 (모든 쟁점 세그먼트 합)
MAX_C_PER_AGENT = _i("FGI_MAX_C_PER_AGENT", 2)           # 한 쟁점 세그먼트 내 에이전트당 발화 상한 (독점 방지, 호환용)
PROBE_MAX_UTTER = _i("FGI_PROBE_MAX_UTTER", 4)           # 쟁점 하나당 토론 발화 상한
PHASE_D_MAX_PULLINS = _i("FGI_PHASE_D_MAX", 3)           # Phase D 강제 호명 상한 (자연스러움 보정)
# Phase C 발화자 선정 규칙 (plan 0026):
# - 직전 N턴 동안 발화한 사람은 후보에서 제외 (예: 본인이 말했으면 다음 2턴까지는 발화 못함)
# - 라운드(Phase C 전체) 누적 발화 ROUND_C_MAX_PER_AGENT 미만만 후보 — 한 사람 독점 방지 안전장치
# - 정렬 키는 관심도(interest) 내림차순 — 발화 균등성은 직전 lock 으로만 보장
# ROUND_C_MAX_PER_AGENT 는 5 로 풀어서 사실상 직전 lock(2턴) 만 작동하게 한다(사용자 피드백):
# "한번 발화하고 2명 말한 다음턴엔 다시 관심도 계산에 참여해서 발화권한 얻을 수 있어야"
PHASE_C_RECENT_LOCK = _i("FGI_PHASE_C_RECENT_LOCK", 2)
ROUND_C_MAX_PER_AGENT = _i("FGI_ROUND_C_MAX_PER_AGENT", 5)

# engagement: LLM 반응/자기보고 앙상블 (§13). 끄면 임베딩 프록시만 사용.
USE_LLM_ENGAGEMENT = os.getenv("FGI_LLM_ENGAGEMENT", "1") not in ("0", "false", "False")
SELF_REPORT_WEIGHT = _f("FGI_SELF_REPORT_WEIGHT", 0.3)   # 임베딩식 vs LLM 자기보고 앙상블 비중
# Round 전환: 사회자 LLM 판단 사용 (§11)
USE_MODERATOR_JUDGE = os.getenv("FGI_MODERATOR_JUDGE", "1") not in ("0", "false", "False")

# 사용자(기업 관계자) 실시간 개입
INTERVENTION_TIMEOUT = _f("FGI_INTERVENTION_TIMEOUT", 1800)  # 개입 여부 결정 대기(초) — 30분. routers/fgi.py 가 동일 값을 명시 전달해 env 영향 차단(2026-05-29).
INTERVENTION_MAX_PER_ROUND = _i("FGI_INTERVENTION_MAX", 2)

# 발화·모더레이터 모델. nano(2026-05-29 하향)가 발화 동질화·지시 미준수(끝에 '[answer]' 누출,
# '저도' 시작, 앞사람 답 베끼기)를 일으켜 데모 품질용으로 gpt-4.1-mini 로 복귀(2026-05-31).
# 4.1-mini: $0.40/1M in · $1.60/1M out (nano 의 4배지만 세션당 ~$0.17 로 데모엔 미미).
# engagement(아래 ENGAGEMENT_MODEL)는 점수 산출이라 nano 유지 — 자주 호출돼 비용·레이턴시 민감.
# 비용 다시 줄여야 하면 env FGI_CHAT_MODEL 로 nano 복원 가능.
CHAT_MODEL = os.getenv("FGI_CHAT_MODEL", "gpt-4.1-mini")
# engagement(관심도 추정) 전용 모델 — 발화·모더레이터 모델과 분리해서 OpenAI 최저가 모델 사용.
# plan 0025 v2: 발화 중에도 LLM 추정을 자주 호출하므로 비용·레이턴시 ↓ 가 중요.
# gpt-4.1-nano: $0.10/1M input · $0.40/1M output (4.1-mini 의 ¼ 가격).
ENGAGEMENT_MODEL = os.getenv("FGI_ENGAGEMENT_MODEL", "gpt-4.1-nano")

# 발화 토큰 SSE 송출 속도 — 토큰(델타) 사이 인위적 sleep(ms).
# 0=즉시(LLM 도착 속도 그대로), >0=느리게. 데모 가독성용. plan 0024 follow-up.
STREAM_TOKEN_DELAY_MS = _i("FGI_STREAM_TOKEN_DELAY_MS", 35)
