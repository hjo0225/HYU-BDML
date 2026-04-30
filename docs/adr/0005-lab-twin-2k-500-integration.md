# ADR-0005: 실험실(Lab) — Twin-2K-500 1:1 메신저 통합

## Status

Accepted (2026-04-30)

## Context

본 서비스의 5-Phase FGI 시뮬레이션 외에, **연구·시연용 실험실(Lab)** 페이지를 두어 Twin-2K-500 데이터셋(Toubia et al. 2025, *Marketing Science*) 기반 **디지털 트윈 페르소나와 1:1로 대화**하는 기능을 제공하고자 했다.

설계상 결정해야 할 항목:

1. Twin 데이터를 기존 `panels` 테이블에 **통합** vs **별도 테이블** 분리.
2. Lab 접근 정책 — **인증 필요** vs **게스트 오픈**.
3. Twin 적재 범위 — **시범 N명** vs **전체 ~2,058명**.
4. Twin은 영어 응답자 — 채팅 언어를 **영어 유지** vs **한국어 변환**.
5. 채팅 영속화 — DB 저장 vs sessionStorage.
6. `panels.cluster` (NOT NULL) 처리 — Twin은 FGI K-means 클러스터(0~24)와 무관하므로 **sentinel(`-1`)** vs **Twin 전용 클러스터 공간**.

## Decision

### 1. 데이터 모델: `panels.source` 컬럼 추가로 통합

- `Panel`, `PanelMemory` 테이블에 `source VARCHAR(20)` 추가 (기존 500명은 `'fgi500'`, Twin은 `'twin2k500'`).
- 이유: 기존 RAG 인프라(`retriever.retrieve`, `_stream_rag_turn`, `embedder`)를 그대로 재사용하기 위함. 별도 테이블이면 거의 같은 코드를 두 벌 유지해야 함.
- 운영 분리는 라우터 레벨에서 `Panel.source` 필터로 처리한다.

### 2. 접근 정책: 게스트 오픈 + IP 단위 rate limit

- AuthGuard 미적용. 비로그인 사용자도 `/lab` 직접 접근 가능.
- 이유: 실서비스가 아니라 시연·연구용이며, 로그인 진입장벽을 두면 체험률이 극단적으로 떨어진다.
- 토큰 비용 폭주 방지: **IP 단위 일일 30회 메시지 한도** (인메모리 카운터). Redis 미도입.
- `usage_tracker`는 `action='lab_chat'`, `user_id=None` 허용으로 게스트 사용량 집계.

### 3. 적재 범위: 시범 50명

- Hugging Face `LLM-Digital-Twin/Twin-2K-500`에서 50명 샘플링.
- 이유: 임베딩 비용·시간 최소화하면서 카드 그리드 UX 확인. 운영 시 확장 가능.

### 4. 발화 방식: Toubia 풀-프롬프트 (RAG 미사용)

- Toubia et al. (2025) 논문 방식 그대로 — `panels.persona_full`(persona_json 원본 ~170k chars, ~42k tokens)을 매 턴 시스템 프롬프트에 통째로 주입.
- RAG(임베딩 검색·메모리 단편 추출) 미사용. 풀 페르소나로 LLM이 응답자의 답변 패턴 전체를 본다.
- 한국어 응답: 시스템 프롬프트 끝에 "위 영어 응답 데이터를 기반으로 자연스러운 한국어 1인칭으로 답하라" 지시.
- 이유:
  - 논문 재현성 — Twin-2K-500은 풀-프롬프트로 평가된 데이터셋. RAG 단편화는 측정된 적 없음.
  - 응답 일관성 — 페르소나 전체를 보면 가치관·정치성향·라이프스타일 모순이 줄어든다.
  - 검색 misses 없음 — 사용자 질문이 어떤 카테고리든 LLM이 직접 페르소나에서 찾는다.
- 비용: gpt-4o-mini 기준 ~$0.0075/턴 (입력 42k × $0.15/1M). gpt-4o로 전환 시 ~$0.21/턴.
- 모델은 `LAB_LLM_MODEL` 환경변수로 조정 (기본 `gpt-4o-mini`).
- panel_memories 테이블은 twin2k500용으로도 채워져 있지만(향후 하이브리드 모드 가능성) 현재 채팅에서는 사용하지 않음.

### 5. 영속화: sessionStorage만

- 채팅 히스토리는 클라이언트 `sessionStorage[lab-chat-${twinId}]`에만 저장.
- 이유: 게스트 모드라 사용자 식별이 불가능하고, DB 적재는 비용·법적 부담만 늘림.
- 새로고침 복원만 지원.

### 6. 클러스터 공간: Twin 전용 K-means (오프셋 100, K=5)

- Twin 패널의 `cluster` 값은 **100~104** 범위로 할당. (FGI는 0~24, 완전 분리.)
- `seed_twin.py`가 50명 적재 후 `avg_embedding`에 K-means(K=5)를 돌려 `cluster = 100 + label`로 업데이트.
- 이유: `panels.cluster`가 NOT NULL이고, sentinel(`-1`)은 의미 없는 값이라 추후 다양성 샘플링이나 분석을 막는다. 정상 클러스터를 두면 Lab에서도 "다양한 5명 트윈 묶음 보기" 같은 기능을 같은 `panel_selector` 코드로 만들 수 있다.
- `K`는 환경변수 `SEED_TWIN_K`로 조정 가능 (기본 5). 적재 인원 수 < K이면 recluster 스킵.

## Consequences

**긍정적**

- 기존 RAG 코드 재사용률이 높아 신규 코드 분량 최소화 (router + service + 적재 스크립트 + 프론트 페이지).
- 체험 진입장벽 0 — 랜딩에서 한 번 클릭으로 트윈과 대화 가능.
- 영어 임베딩 유지로 검색 의미 손실 없음.
- 운영 영역(Phase 1~5)과 실험 영역(Lab)이 코드 경로상 명확히 분리됨 (`routers/lab.py` 단독).

**부정적**

- `panels.source` 필터를 모든 Lab 쿼리에 적용해야 하며, 빠뜨리면 Twin 데이터가 본 서비스에 노출될 위험. → 라우터에서 필터 누락 방지를 위한 헬퍼 함수 도입 권장.
- IP rate limit은 인메모리이므로 멀티 인스턴스 환경(Cloud Run 다중 컨테이너)에서 정확하지 않음. 시범 단계 가정.
- 채팅 미영속화로 인해 사용자가 새 탭/디바이스 이동 시 히스토리 손실. 시범 단계에서 허용.
- Twin 영어 메모리 → 한국어 응답 변환 시 LLM이 의미를 미세하게 왜곡할 가능성. 시범 단계에서 허용.

## 관련

- `backend/routers/lab.py`
- `backend/services/lab_service.py`
- `backend/scripts/seed_twin.py`
- `backend/prompts/twin_utterance.py`
- [PRD.md — 실험실](../PRD.md#실험실-lab--twin-2k-500-11-메신저)
- [ARCHITECTURE.md — Lab 흐름](../ARCHITECTURE.md)
- [DATA_MODEL.md — source 컬럼](../DATA_MODEL.md)
