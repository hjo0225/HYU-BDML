# ADR-0003: `panels.avg_embedding` 1차 스코어링 도입

## Status

Accepted (2026-04-18)

## Context

[ADR-0002](./0002-rag-panel-no-age-filter.md)로 연령 필터를 제거한 뒤, Phase 3 에이전트 선정 단계에서 500명 전원의 메모리를 비교해야 했다. 초기 구현은 `load_panel_memories_bulk`로 전체 메모리를 한 번에 로드했으나:

- 메모리 5,373건 × 평균 30KB JSONB ≈ **160MB 전송**.
- `json.loads` 5,373회로 CPU 병목.
- Cloud Run 백엔드에서 **타임아웃 발생**.

각 패널의 메모리들을 평균낸 단일 벡터로 1차 스코어링한 뒤, 선정된 N명만 개별 메모리를 로드하면 된다는 관찰에 도달.

## Decision

`panels` 테이블에 **`avg_embedding vector(1536)`** 컬럼을 추가한다. 이 컬럼은 해당 패널의 모든 `panel_memories.embedding`을 평균낸 벡터다.

- `seed_panels.py` 적재 시 함께 계산.
- 기존 적재본은 `compute_avg_embeddings.py`로 1회성 백필.
- `panel_selector.score_panels_by_query()`는 `avg_embedding`만 비교 (메모리 벌크 로드 없음).
- Phase 4 회의 시뮬레이션에서 선정된 N명만 `meeting_service`가 개별 메모리를 캐싱.

**불변 규칙: `load_panel_memories_bulk`로 전체 500명 메모리를 한 번에 로드하지 않는다.**

## Consequences

**긍정적**

- Phase 3 응답 속도가 타임아웃 직전 수준에서 수 초 내로 단축.
- DB 전송량 ~160MB → 패널당 6KB(1536 × 4byte) × 500 ≈ 3MB로 축소.
- Phase 4는 N명(보통 5~8명)만 개별 로드하므로 부담 없음.

**부정적**

- 메모리 평균 벡터는 개별 메모리보다 의미 해상도가 낮아, 1차 스코어링이 "주제와 가장 가까운 1개 메모리를 가진 패널"을 놓칠 수 있음. 클러스터 다양성 가중치(0.7)가 이를 일부 완화.
- 새 메모리 추가 시 `avg_embedding`을 재계산해야 함 — 현재는 적재 시점에만 계산하고 이후 갱신은 백필 스크립트로 처리.

## 관련

- `backend/rag/panel_selector.py:score_panels_by_query`
- `backend/scripts/compute_avg_embeddings.py`
- [ARCHITECTURE.md — 성능 주의사항](../ARCHITECTURE.md#성능-주의사항)
