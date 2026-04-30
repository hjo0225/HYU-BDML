# ADR-0004: Phase 3 에이전트 생성 — RAG/LLM 모드 분기

## Status

Accepted (2026-04-12)

## Context

초기에는 Phase 3 에이전트가 두 가지 방식 중 하나로 고정되어 있었다:

- 옵션 A — 실제 패널 500명 풀에서 RAG로 선정 (`/api/agents/stream`).
- 옵션 B — LLM이 brief/report만 보고 가상 에이전트를 생성 (`/api/agents`).

문제:

- 패널 풀이 부족한 도메인(전문직, 특정 산업 종사자)은 RAG가 낮은 품질의 매칭을 반환.
- 반대로 일반 소비재 같은 케이스는 RAG가 훨씬 풍부한 응답을 만듦.
- 사용자에게 두 엔드포인트를 별도로 노출하는 것은 UX가 어색하고, Phase 3 위저드의 단계 구성이 일관성 없어졌다.

또한 Phase 3에 회의 주제(`topic`) 입력이 추가되어, RAG 선정 시 주제 임베딩으로 패널 관련성을 반영할 수 있게 되었다.

## Decision

Phase 3을 **3-step 위저드**로 재구성한다:

1. **Step 1 — 회의 주제 입력** (textarea). `project.meetingTopic` 저장.
2. **Step 2 — 모드 선택**: `rag` (실제 패널) 또는 `llm` (가상 에이전트).
3. **Step 3 — 에이전트 생성 + 편집**.

신규 엔드포인트 **`POST /api/agents/stream/v2`** (SSE) 하나로 두 모드를 처리한다:

```ts
type AgentStreamRequest = {
  brief: string;
  refined: string;
  report: string;
  topic: string;
  mode: "rag" | "llm";
};
```

- `mode="rag"`: `persona_builder.build_personas_stream(target_customer, n_agents, topic)` — 주제 임베딩으로 패널 관련성 반영.
- `mode="llm"`: `agent_service.recommend_agents(req)` — SSE 래핑된 LLM 가상 에이전트 생성.

기존 `/api/agents`, `/api/agents/stream`은 하위호환을 위해 유지하지만 신규 호출은 `v2`로 통일.

## Consequences

**긍정적**

- 사용자가 도메인 특성에 따라 모드를 선택할 수 있음.
- 회의 주제가 RAG 선정 품질을 직접 개선 (주제 임베딩 기반 관련성).
- 프론트엔드 위저드 흐름이 단일 엔드포인트로 단순화.
- `meetingTopic`이 Phase 3에서 결정되므로 Phase 4 진입 시 별도 입력 UI 불필요.

**부정적**

- 기존 프로젝트는 `meetingTopic`이 없으므로 하위호환 처리 필요 (Step 1부터 시작).
- 두 모드의 산출물 형태가 일치해야 하므로 `AgentSchema`를 양쪽에서 통일해야 함.

## 관련

- `backend/routers/agents.py`
- `backend/services/persona_builder.py`
- `backend/services/agent_service.py`
- [PRD.md — Phase 3](../PRD.md#phase-3--주제--에이전트-3-step-위저드)
- [api-spec.md](../api-spec.md#post-apiagentsstreamv2)
