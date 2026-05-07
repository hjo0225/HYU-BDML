# API Specification — Ditto

Backend FastAPI 엔드포인트 명세. Frontend 는 `frontend/src/lib/api.ts` 를 통해서만 호출한다.

## 인증

- JWT (액세스 토큰) + httpOnly 쿠키 (리프레시 토큰).
- 액세스 토큰 만료 시 `POST /api/auth/refresh`.
- 보호 엔드포인트는 `Authorization: Bearer <token>`.
- 어드민 권한 엔드포인트는 `User.role == "admin"` 필요.

## 엔드포인트 목록

| Method | Endpoint | 설명 | Auth | 스트리밍 | Phase |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | 회원가입 | - | - | 2 |
| POST | `/api/auth/login` | 로그인 | - | - | 2 |
| POST | `/api/auth/refresh` | 토큰 갱신 | - | - | 2 |
| POST | `/api/auth/logout` | 로그아웃 | O | - | 2 |
| GET | `/api/auth/me` | 현재 사용자 | O | - | 2 |
| GET | `/api/projects` | ResearchProject 목록 | O | - | 2 |
| POST | `/api/projects` | ResearchProject 생성 | O | - | 2 |
| GET | `/api/projects/{id}` | ResearchProject 조회 | O | - | 2 |
| PATCH | `/api/projects/{id}` | ResearchProject 업데이트 | O | - | 2 |
| DELETE | `/api/projects/{id}` | ResearchProject 삭제 | O | - | 2 |
| POST | `/api/projects/{id}/agents/seed-twin` | Twin-2K-500 30명 적재 트리거 | O | NDJSON | 2 |
| GET | `/api/projects/{id}/agents` | 에이전트 목록 | O | - | 2 |
| GET | `/api/agents/{id}` | 에이전트 상세 + persona_full_prompt | O | - | 2 |
| PATCH | `/api/agents/{id}` | display_name/intro/scratch 편집 | O | - | 3 |
| POST | `/api/agents/{id}/conversations` | 대화 세션 시작 | O | - | 3 |
| POST | `/api/conversations/{id}/messages` | 1:1 대화 메시지 송신 | O | SSE | 3 |
| GET | `/api/conversations/{id}` | 대화 상세 (turns 포함) | O | - | 3 |
| POST | `/api/projects/{id}/fgi-sessions` | FGI 세션 시작 | O | - | 4 |
| POST | `/api/fgi-sessions/{id}/run` | FGI 진행 | O | SSE | 4 |
| POST | `/api/fgi-sessions/{id}/intervene` | 사용자 발언 개입 | O | - | 4 |
| GET | `/api/fgi-sessions/{id}` | FGI 세션 상세 + turns + minutes | O | - | 4 |
| POST | `/api/agents/{id}/evaluate` | 평가 트리거 (V1/V4 또는 V1~V5 전체) | O | NDJSON | 3, 4, 5 |
| GET | `/api/agents/{id}/evaluations` | 평가 스냅샷 시계열 | O | - | 3 |
| GET | `/api/agents/{id}/evaluations/latest` | 최신 평가 결과 (대시보드) | O | - | 3 |
| GET | `/api/usage` | 토큰 사용량 (본인) | O | - | 2 |
| GET | `/api/usage/history` | 활동 로그 | Admin | - | 2 |
| GET | `/api/usage/stats` | 사용 통계 | Admin | - | 2 |
| GET | `/api/health` | 헬스체크 | - | - | 2 |
| POST | `/api/projects/{id}/surveys` | Survey 생성 | O | - | 6 |
| GET | `/api/surveys/{id}` | Survey 조회 | O | - | 6 |
| POST | `/api/surveys/{id}/publish` | 배포 링크 발급 | O | - | 6 |
| POST | `/api/public/surveys/{token}/responses` | 응답자 응답 제출 | - | - | 6 |
| POST | `/api/surveys/{id}/build-agents` | 응답 → 에이전트 생성 | O | NDJSON | 6 |

## 주요 페이로드

### `POST /api/projects/{id}/agents/seed-twin`

Twin-2K-500 한국어 30명을 적재하여 해당 프로젝트의 에이전트로 등록. NDJSON 진행률 스트림.

```ts
type SeedTwinRequest = {
  limit?: number;        // 기본 30
  cluster_k?: number;    // 다양성 K-means K (기본 5)
};
type SeedTwinNDJSON =
  | { type: "progress"; current: number; total: number; agent_id?: string }
  | { type: "agent_created"; agent: Agent }
  | { type: "done"; total_created: number }
  | { type: "error"; reason: string };
```

### `POST /api/conversations/{id}/messages`

1:1 대화 메시지 송신 + SSE 응답.

요청:

```ts
type SendMessageRequest = { content: string };
```

SSE 이벤트:

- `{ type: "start", conversation_id, agent_id }`
- `{ type: "delta", delta: "..." }` — 본문 토큰 스트리밍. **`[[CITE: ... | CONF: ...]]` 자가인용 마커는 서버에서 제거된 뒤 클라이언트로 전달된다.**
- `{ type: "end", turn_id, content, citations, confidence }`
- `{ type: "error", reason: string }`

`end` 페이로드:

```ts
type MemoryCitation = {
  category: string;          // 예: "l1_economic"
  snippet: string;           // 한국어 메모리 원문 트리밍
  score: number;             // 코사인 유사도 0~1
  via: "llm_self_cite" | "embedding" | "both";
};
type ConversationTurnEnd = {
  type: "end";
  turn_id: string;
  content: string;                  // 자가인용 마커 제거된 본문
  citations: MemoryCitation[];      // 최대 3개
  confidence: "direct" | "inferred" | "guess" | "unknown";
};
```

### `POST /api/fgi-sessions/{id}/run`

FGI 진행 SSE. 모더레이터·에이전트·사용자 개입 구간이 섞인 스트림.

SSE 이벤트:

- `{ type: "round_start", round: 1 }`
- `{ type: "moderator", content: "...", round }`
- `{ type: "agent_delta", agent_id, delta: "..." }` — 에이전트 발화 토큰 스트림
- `{ type: "agent_end", agent_id, turn_id, content, citations, confidence }`
- `{ type: "user_turn_required", round, deadline_seconds: 60 }` — 사용자 개입 가능 구간 (선택)
- `{ type: "round_end", round, summary }`
- `{ type: "session_end", minutes_md, summary }`
- `{ type: "error", reason }`

### `POST /api/fgi-sessions/{id}/intervene`

`user_turn_required` 이벤트 구간에서 사용자 발언 삽입.

```ts
type InterveneRequest = { content: string };
type InterveneResponse = { ok: true; turn_id: string };
```

### `POST /api/agents/{id}/evaluate`

평가 트리거. NDJSON 진행률.

요청:

```ts
type EvaluateRequest = {
  metrics: ("v1" | "v2" | "v3" | "v4" | "v5")[];
  cf_set_version?: string;        // V5 자극 세트 버전 (기본 latest)
  judge_model?: string;           // V4 Judge 모델 (기본 gpt-4o)
  stability_model_2?: string;     // V2 두 번째 모델 (기본 claude-3-5-sonnet-20240620)
};
type EvaluateNDJSON =
  | { type: "metric_start"; metric: string }
  | { type: "metric_progress"; metric: string; current: number; total: number }
  | { type: "metric_done"; metric: string; result: number | object }
  | { type: "snapshot_saved"; snapshot_id: string }
  | { type: "error"; metric?: string; reason: string };
```

### `GET /api/agents/{id}/evaluations/latest`

대시보드용 최신 평가 응답.

```ts
type EvaluationSnapshot = {
  id: string;
  agent_id: string;
  version: number;
  identity_stats: {
    sync: number;            // V1, 0~1
    stability: number;       // V2, 0~1
    distinct: number;        // V3, 0~∞ (페르소나 평균 거리)
  };
  logic_stats: {
    humanity: number;        // V4, 1~5
    reasoning_delta: number; // V5, 0~∞
  };
  verdict: "verified_s3" | "partial" | "failed";
  evaluated_at: string;      // ISO8601
};
```

### `POST /api/projects/{id}/fgi-sessions`

FGI 세션 생성.

```ts
type CreateFGIRequest = {
  topic: string;             // 회의 주제
  agent_ids: string[];       // 참여 에이전트 (최대 6명)
  max_rounds?: number;       // 기본 6
  allow_user_intervention?: boolean;  // 기본 true
};
type FGISession = {
  id: string;
  project_id: string;
  topic: string;
  agent_ids: string[];
  status: "running" | "completed" | "cancelled";
  minutes_md: string | null;
  started_at: string;
  ended_at: string | null;
};
```

## 스트리밍 규약

### SSE (Server-Sent Events)

- 사용처: `/api/conversations/{id}/messages`, `/api/fgi-sessions/{id}/run`.
- 구현: starlette `StreamingResponse` + `text/event-stream`.
- 클라이언트 수신: `fetch + ReadableStream.getReader()` 로 디코딩.
- 이벤트 형식: `data: <JSON>\n\n`.

### NDJSON

- 사용처: `/api/projects/{id}/agents/seed-twin`, `/api/agents/{id}/evaluate`, `/api/surveys/{id}/build-agents`.
- 라인 단위 JSON. 진행률·중간 결과를 점진적으로 푸시.

## 통신 규칙

- Frontend 는 `frontend/src/lib/api.ts` 를 통해서만 backend 를 호출한다 (직접 fetch 금지).
- 개발 환경: `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` 빌드 시 주입.
- 운영 환경: Cloud Run 백엔드 URL 을 빌드 시 주입.
- Backend Pydantic 스키마 (`backend/models/schemas.py`) 와 Frontend `frontend/src/lib/types.ts` 는 **항상 동기화** — 변경 시 양쪽을 같은 PR 에서 갱신.

## CORS

- `backend/main.py` 에서 `CORS_ORIGINS` 환경변수 기반 허용 목록 설정.
- 운영: Cloud Run frontend 도메인만 허용.

## Rate Limiting (Phase 6)

- 인증된 사용자: 워크스페이스 단위 일일 토큰 한도 (DB `activity_logs` 기반 집계).
- 공개 Survey 응답 엔드포인트(`/api/public/surveys/...`): 응답자 토큰 단위 IP rate limit.
