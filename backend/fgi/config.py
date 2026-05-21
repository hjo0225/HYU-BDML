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
TIKITAKA_THRESHOLD = _f("FGI_TIKITAKA_THRESHOLD", 0.7)    # τ: Phase C 발화권 관심도(0~1) 컷오프
MAX_TIKITAKA_UTTER = _i("FGI_MAX_TIKITAKA", 15)           # Phase C 발화 총상한 (모든 쟁점 세그먼트 합)
MAX_C_PER_AGENT = _i("FGI_MAX_C_PER_AGENT", 2)           # 한 쟁점 세그먼트 내 에이전트당 발화 상한 (독점 방지)
PROBE_MAX_UTTER = _i("FGI_PROBE_MAX_UTTER", 4)           # 쟁점 하나당 토론 발화 상한
PHASE_D_MAX_PULLINS = _i("FGI_PHASE_D_MAX", 3)           # Phase D 강제 호명 상한 (자연스러움 보정)

# engagement: LLM 반응/자기보고 앙상블 (§13). 끄면 임베딩 프록시만 사용.
USE_LLM_ENGAGEMENT = os.getenv("FGI_LLM_ENGAGEMENT", "1") not in ("0", "false", "False")
SELF_REPORT_WEIGHT = _f("FGI_SELF_REPORT_WEIGHT", 0.3)   # 임베딩식 vs LLM 자기보고 앙상블 비중
# Round 전환: 사회자 LLM 판단 사용 (§11)
USE_MODERATOR_JUDGE = os.getenv("FGI_MODERATOR_JUDGE", "1") not in ("0", "false", "False")

# 사용자(기업 관계자) 실시간 개입
INTERVENTION_TIMEOUT = _f("FGI_INTERVENTION_TIMEOUT", 600)  # 개입 여부 결정 대기(초) — 사용자가 정할 때까지 대기, 안전 상한
INTERVENTION_MAX_PER_ROUND = _i("FGI_INTERVENTION_MAX", 2)

CHAT_MODEL = os.getenv("FGI_CHAT_MODEL", "gpt-4o-mini")
