# API Specification

Backend FastAPI 엔드포인트 명세. Frontend는 `frontend/src/lib/api.ts`를 통해서만 호출한다.

## 인증

- JWT(액세스 토큰) + httpOnly 쿠키(리프레시 토큰) 조합.
- 액세스 토큰 만료 시 `POST /api/auth/refresh`로 갱신.
- 보호 엔드포인트 호출 시 `Authorization: Bearer <token>` 헤더 사용.
- 어드민 권한 엔드포인트는 `User.role == "admin"` 필요.

## 엔드포인트 목록

| Method | Endpoint                | 설명                           | Auth  | 스트리밍 |
| ------ | ----------------------- | ------------------------------ | ----- | -------- |
| POST   | `/api/auth/register`    | 회원가입                       | -     | -        |
| POST   | `/api/auth/login`       | 로그인                         | -     | -        |
| POST   | `/api/auth/refresh`     | 토큰 갱신                      | -     | -        |
| POST   | `/api/auth/logout`      | 로그아웃                       | O     | -        |
| GET    | `/api/auth/me`          | 현재 사용자                    | O     | -        |
| GET    | `/api/projects`         | 프로젝트 목록                  | O     | -        |
| POST   | `/api/projects`         | 프로젝트 생성                  | O     | -        |
| GET    | `/api/projects/{id}`    | 프로젝트 조회                  | O     | -        |
| PATCH  | `/api/projects/{id}`    | 프로젝트 업데이트              | O     | -        |
| DELETE | `/api/projects/{id}`    | 프로젝트 삭제                  | O     | -        |
| POST   | `/api/research/refine`  | 브리프 정제                    | O     | -        |
| POST   | `/api/research`         | 시장조사                       | O     | NDJSON   |
| POST   | `/api/agents`           | 에이전트 추천 (LLM)            | O     | -        |
| POST   | `/api/agents/stream`    | RAG 에이전트 선택 (legacy)     | O     | SSE      |
| POST   | `/api/agents/stream/v2` | 주제 인식 에이전트 (모드 분기) | O     | SSE      |
| POST   | `/api/meeting`          | 회의 시뮬레이션                | O     | SSE      |
| POST   | `/api/minutes`          | 회의록 생성                    | O     | -        |
| GET    | `/api/usage`            | 토큰 사용량                    | O     | -        |
| GET    | `/api/usage/history`    | 활동 로그                      | Admin | -        |
| GET    | `/api/usage/stats`      | 사용 통계                      | Admin | -        |
| GET    | `/api/lab/twins`        | Lab Twin 페르소나 목록         | -     | -        |
| GET    | `/api/lab/twins/{id}`   | Lab Twin 단일 상세 + persona_full | -  | -        |
| POST   | `/api/lab/chat`         | Lab 1:1 메신저 채팅            | -     | SSE      |
| GET    | `/api/health`           | 헬스체크                       | -     | -        |

## 주요 페이로드

### `POST /api/agents/stream/v2`

```ts
type AgentStreamRequest = {
  brief: string;
  refined: string;
  report: string;
  topic: string;        // 회의 주제 (Phase 3 Step 1)
  mode: "rag" | "llm";  // Phase 3 Step 2
};
```

- `mode="rag"`: `persona_builder.build_personas_stream(target_customer, n_agents, topic)` 호출. 주제 임베딩으로 패널 관련성 반영.
- `mode="llm"`: `agent_service.recommend_agents(req)` 호출. SSE 래핑된 LLM 가상 에이전트 생성.

### `POST /api/meeting`

- 입력: `project.meetingTopic`, 선정된 에이전트 목록.
- SSE 이벤트: 발언 스트리밍, 라운드 전환, 종료 신호.

### `GET /api/lab/twins`

Lab 실험실용 Twin-2K-500 페르소나 목록. **인증 불필요** (게스트 오픈).

응답: `LabTwin`은 인구통계·Big5·자기인식·태그 등 카드/모달용 필드 + ADR-0006의 사전 계산 충실도(`faithfulness`) + 카테고리별 한국어 probe 질문 캐시(`probe_questions`)를 포함한다. 전체 필드는 `models/schemas.py`의 `LabTwin` / `frontend/src/lib/types.ts`의 `LabTwin` 참조.

```ts
type LabFaithfulness = {
  overall: number;                     // 0~1
  by_category: Record<string, number>; // 예: { "values_environment": 0.8, ... }
  n_eval: number;
  evaluated_at?: string | null;        // ISO8601 UTC
};
type LabProbeQuestion = {
  category: string;        // 예: "social_trust"
  question: string;        // 한국어 메신저 질문
};
type LabTwin = {
  twin_id: string;
  name: string;
  /* ... 인구통계, Big5, 자기인식, 태그 ... */
  faithfulness?: LabFaithfulness | null;  // ADR-0006: 사전 계산된 데이터 충실도
  probe_questions: LabProbeQuestion[];     // 채팅 사이드바용 카테고리별 한국어 질문
};
type LabTwinsResponse = { twins: LabTwin[] };
```

- 시범 단계: `Panel.source='twin2k500'`인 50명만 반환.
- `faithfulness`는 `eval_lab_faithfulness` 스크립트 결과가 `Panel.scratch.faithfulness`에 저장된 트윈만 채워진다.
- `probe_questions`는 `seed_lab_probe_questions.py`가 채워둔 `Panel.scratch.probe_questions` (카테고리당 1문항) 캐시를 의미 그룹 순으로 정렬해 반환. 시드되지 않은 트윈은 `[]`.

### `GET /api/lab/twins/{twin_id}`

Lab 채팅 페이지 우측 "에이전트 입력값" 패널이 호출. **인증 불필요**. `LabTwin` 모든 필드 + `persona_full`(Toubia 풀-프롬프트로 시스템 프롬프트에 그대로 주입되는 `persona_json` 텍스트, 영문 ~170k chars)을 함께 반환한다.

```ts
type LabTwinDetail = LabTwin & {
  persona_full: string | null;  // panels.persona_full 원본 (없으면 null)
};
```

- 트윈이 없거나 `source='twin2k500'`이 아니면 `404 { detail: { reason: "twin_not_found" } }`.
- 클라이언트는 `persona_full`을 `JSON.parse`한 뒤 최상위 키를 섹션 헤더로 풀어 사람이 읽기 좋게 가시화한다(`PersonaInputPanel`).

### `POST /api/lab/chat`

Lab 1:1 메신저. **인증 불필요** + **IP 단위 일일 30회 rate limit**. SSE 스트리밍.

요청:

```ts
type LabChatRequest = {
  twin_id: string;
  history: { role: "me" | "twin"; content: string }[];
  message: string;
};
```

SSE 이벤트:

- `{ type: "start", twin_id, name }`
- `{ type: "delta", delta: "..." }` — 본문 토큰 스트리밍. **`[[CITE: ... | CONF: ...]]` 자가인용 마커는 서버에서 제거된 뒤 클라이언트로 전달된다** (delta에는 절대 포함되지 않음).
- `{ type: "end", content, citations, confidence }` — ADR-0006: A+B 하이브리드 인용·신뢰도 첨부.
- `{ type: "error", reason: "rate_limit" | "twin_not_found" | "persona_missing" | "internal" }`

`end` 페이로드 상세:

```ts
type MemoryCitation = {
  category: string;          // 예: "values_environment"
  snippet_en: string;        // 영어 원문(트리밍 ~360자)
  snippet_ko: string | null; // 향후 확장 — 현재 null
  score: number;             // 코사인 유사도 0~1
  via: "llm_self_cite" | "embedding" | "both";
};
type LabChatEnd = {
  type: "end";
  content: string;                          // 자가인용 마커가 제거된 본문
  citations: MemoryCitation[];              // 최대 3개
  confidence: "direct" | "inferred" | "guess" | "unknown";
};
```

내부 동작: 시스템 프롬프트가 답변 끝에 `[[CITE: cat1, cat2 | CONF: <level>]]` 마커를 출력하도록 지시. 백엔드가 이 마커를 본문에서 분리한 뒤 답변 임베딩 vs `PanelMemory.embedding` 코사인 top-K로 검증. 매칭 없는 자가인용은 drop된다.

Rate limit 초과 시 HTTP `429 Too Many Requests` + `{ type: "error", reason: "rate_limit", remaining_seconds: <int> }`.

## 스트리밍 규약

### SSE (Server-Sent Events)

- 사용처: `/api/agents/stream`, `/api/agents/stream/v2`, `/api/meeting`.
- 구현: starlette `StreamingResponse` + `text/event-stream`.
- 클라이언트 수신: `fetch + ReadableStream.getReader()`로 디코딩.
- 이벤트 형식: `data: <JSON>\n\n`.

### NDJSON

- 사용처: `/api/research`.
- 라인 단위 JSON. 진행률·중간 결과를 점진적으로 푸시.

## 통신 규칙

- Frontend는 `frontend/src/lib/api.ts`를 통해서만 backend를 호출한다 (직접 fetch 금지).
- 개발 환경: `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`을 빌드 시 주입하여 직접 호출 (Next.js 프록시 우회).
- 운영 환경: Cloud Run 백엔드 URL을 빌드 시 주입.
- 요청/응답은 JSON (SSE/NDJSON 제외).
- Backend Pydantic 스키마(`backend/models/schemas.py`)와 Frontend `frontend/src/lib/types.ts`는 **항상 동기화**한다 — 변경 시 양쪽을 같은 PR에서 갱신.

## CORS

- `backend/main.py`에서 `CORS_ORIGINS` 환경변수 기반 허용 목록 설정.
- 운영: Cloud Run frontend 도메인만 허용.
