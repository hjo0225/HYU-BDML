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

응답:

```ts
type LabTwin = {
  twin_id: string;
  name: string;          // 익명화된 표시 이름
  emoji: string;
  age: number;
  gender: string;
  occupation: string;
  region: string;
  intro: string;         // 1~2문장 짧은 소개 (한국어)
};
type LabTwinsResponse = { twins: LabTwin[] };
```

- 시범 단계: `Panel.source='twin2k500'`인 50명만 반환.

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
- `{ type: "delta", delta: "..." }`
- `{ type: "end", content: "<full response>" }`
- `{ type: "error", reason: "rate_limit" | "twin_not_found" | "internal" }`

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
