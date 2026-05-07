# Architecture

빅데이터마케팅랩의 모듈 경계, 데이터 흐름, 배포 토폴로지를 기술한다.

## 모노레포 경계

```
bigmarlab/
├── frontend/   # Next.js — UI 전담 (LLM/DB 직접 호출 금지)
└── backend/    # FastAPI — LLM·데이터 전담 (UI 로직 인지 금지)
```

- **frontend** 책임: 사용자 입력, 화면 렌더링, sessionStorage 기반 Phase 상태 전달, SSE/NDJSON 수신.
- **backend** 책임: LLM 호출, RAG 검색, DB 영속화, 인증, 외부 API(Naver/OpenAI 검색).
- 통신: HTTP/JSON + SSE + NDJSON. 프론트는 `frontend/src/lib/api.ts`를 통해서만 호출.

## 백엔드 계층 구조

```
routers/  →  services/  →  prompts/ + rag/  →  OpenAI / DB
```

- **routers/**: HTTP 엔드포인트, 요청 검증, 인증 체크.
- **services/**: 비즈니스 로직, 트랜잭션, 외부 API 오케스트레이션.
- **prompts/**: 프롬프트 템플릿 (서비스에 인라인 금지).
- **rag/**: 임베딩, 메모리 빌더, 패널 선택, 검색 등 RAG 파이프라인.

## RAG 파이프라인 — Phase 3 에이전트 선정

```
brief + report + topic
   │
   ▼
persona_builder.py
   ├─ panel_query.py 프롬프트로 LLM 합성 쿼리 생성
   └─ embedder.py 로 합성 쿼리 → 1536차원 임베딩
   │
   ▼
panel_selector.py
   ├─ panels.avg_embedding (사전 계산된 메모리 평균 벡터)과 코사인 유사도 비교
   ├─ 클러스터 다양성(0.7) + 주제 관련성(0.3) 복합 스코어
   └─ N명 선택
   │
   ▼
routers/agents.py 가 SSE로 스트리밍
```

핵심 함수:

- `panel_selector.score_panels_by_query()` — `avg_embedding` 기반 1차 스코어링. **메모리 벌크 로드 없음**.
- `load_panel_memories_bulk` — 선정 단계에서 호출하지 않음. Phase 4에서 선정된 N명만 개별 로드. (자세한 이유: [adr/0003](./adr/0003-avg-embedding-first-pass-scoring.md))

## RAG 파이프라인 — Phase 4 회의 시뮬레이션

```
회의 시작
   │
   ▼
meeting_service.py
   ├─ 선정된 RAG 에이전트의 persona 1회 DB 조회 → 메모리 캐싱 (in-memory)
   │
   ▼ (매 발언 턴)
   ├─ retrieval 쿼리 구성 (LLM 발언 생성 컨텍스트와 분리):
   │     이전 라운드 요약 + 현재 모더레이터 질문 + 직전 최대 3명 발언 (본인 제외)
   │     → "영감 연쇄" 구조 (다른 참여자 발언이 내 메모리를 트리거)
   │
   ├─ retriever.py: 캐시된 메모리에서 코사인 유사도 검색 (DB 재조회 없음)
   │
   ├─ rag_utterance.py 프롬프트: 1인칭 서사형 프로필(scratch traits/events/styles) +
   │                              검색된 기억을 주입 → LLM 발언 생성
   │     LLM 프롬프트는 전체 대화 히스토리 + 턴 지시문을 사용 (retrieval 쿼리와 분리)
   │
   └─ 라운드 전환 시 모더레이터 followup 텍스트를 round_summaries에 누적
         → 다음 라운드 retrieval에 이전 논점 맥락 전달
```

### 분리 원칙

- **retrieval 쿼리** ≠ **LLM 발언 생성 컨텍스트**.
- retrieval은 다른 참여자 발언을 포함해 "영감 연쇄"를 유도.
- LLM 프롬프트는 자신이 보고 있는 전체 대화 히스토리를 그대로 본다.

## 외부 의존성

| 서비스 | 용도 | 위치 |
|---|---|---|
| OpenAI `gpt-4o` | 모든 LLM 호출 | `services/openai_client.py` |
| OpenAI `text-embedding-3-small` | 1536차원 임베딩 | `rag/embedder.py` |
| Naver 검색 API | 시장조사 보강 | `services/naver_search_service.py` |
| OpenAI Web Search | 시장조사 1차 소스 | `services/openai_web_search_service.py` |

## 인증 아키텍처

- JWT 액세스 토큰 + httpOnly 쿠키 리프레시 토큰.
- bcrypt 패스워드 해싱.
- 리프레시 토큰은 SHA-256 해시로 DB(`refresh_tokens`)에 저장하여 무효화 가능.

## 배포 토폴로지

```
GitHub (main push)
   │
   ▼
GitHub Actions + Workload Identity Federation (OIDC, 서비스 계정 키 불필요)
   │
   ├─ Cloud Run frontend (port 3000)
   └─ Cloud Run backend  (port 8080)
              │
              ▼
       Cloud SQL PostgreSQL
       (asia-northeast3:bigmarlab-db)
              │
              └─ Cloud SQL Proxy (개발 시 로컬 :5432)
```

### 환경변수 (런타임 주입)

- `CORS_ORIGINS`, `DATABASE_URL`, `JWT_SECRET_KEY`, `OPENAI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `ADMIN_EMAILS`.

### GitHub Secrets

- `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `BACKEND_URL`, `FRONTEND_URL`.

## 성능 주의사항

- **`load_panel_memories_bulk` 전체 호출 금지**: 500명 × 5,373건 메모리 × 30KB JSONB ≈ 160MB 전송 + json.loads 5,373회로 타임아웃. 항상 `avg_embedding` 1차 스코어링 → 선정 N명만 개별 로드.
- **`embedding_cache.json` 동시 접근 금지**: `seed_panels` 실행 중에는 다른 프로세스가 같은 캐시 파일을 읽으면 JSON 파싱 에러. 동시 실행 시 캐시 우회 또는 스크립트 종료 후 실행.

## 실험실(Lab) 라우트 — Twin-2K-500 1:1 메신저

본 서비스의 5-Phase 흐름과 분리된 별도 진입점. 인증 없이 게스트 접근.

```
/  (랜딩, 공개)
   │
   ├─ "메인 서비스" CTA → /login → /dashboard → Phase 1~5 (인증 필요)
   │
   └─ "실험실 체험" CTA → /lab (공개)
                          │
                          └─ /lab/chat/{twinId}  (1:1 메신저, SSE)
```

### Lab 백엔드 흐름

```
GET /api/lab/twins
   └─ Panel.source='twin2k500' 50명 → LabTwin[] 응답

POST /api/lab/chat (SSE, 인증 없음, IP rate limit)
   │
   ├─ rate limit 체크 (인메모리 일일 카운터, IP 단위 30회)
   │
   ├─ lab_service.py
   │   ├─ load_persona_from_db(twin_id, source='twin2k500')
   │   ├─ retriever.retrieve(persona, focal_point=직전 user msg + 직전 twin msg)
   │   ├─ prompts/twin_utterance.py 프롬프트 합성 (영어 메모리 → 한국어 응답 지시)
   │   └─ meeting_service._stream_llm_turn(...) 재사용 → SSE delta 스트림
   │
   └─ usage_tracker.log(action='lab_chat', user_id=None, ...)
```

### 게스트 Rate Limit

- IP 단위 인메모리 카운터, 일일 30회 메시지 한도.
- 시범 단계 가정 — Cloud Run 다중 인스턴스 환경에서는 Redis 도입 필요.
- 초과 시 HTTP `429 Too Many Requests`.

### 데이터 격리

- `panels.source` / `panel_memories.source` 컬럼으로 본 서비스(`fgi500`)와 Lab(`twin2k500`) 분리.
- 모든 Lab 쿼리는 `source='twin2k500'` 필터 필수. 라우터 내 헬퍼 함수로 강제.

## 관련 ADR

- [0001 — Frontend/Backend 모노레포 분리](./adr/0001-monorepo-frontend-backend-separation.md)
- [0002 — RAG 패널 연령 필터 제거](./adr/0002-rag-panel-no-age-filter.md)
- [0003 — `avg_embedding` 1차 스코어링 도입](./adr/0003-avg-embedding-first-pass-scoring.md)
- [0004 — Phase 3 RAG/LLM 모드 분기](./adr/0004-phase3-rag-llm-mode-split.md)
- [0005 — Lab + Twin-2K-500 통합](./adr/0005-lab-twin-2k-500-integration.md)
