# 빅데이터마케팅랩 (BigDataMarketingLab)

AI 에이전트 기반 정성조사(FGI) 시뮬레이션 웹앱. 사용자가 연구 정보를 입력하면 AI가 시장조사 → RAG 기반 패널 구성 → FGI 회의 시뮬레이션 → 회의록 생성까지 자동 수행.

## 아키텍처: Frontend / Backend 분리

모노레포 구조로 `frontend/`와 `backend/`를 완전히 분리한다.

```
bigmarlab/
├── frontend/                         # Next.js — UI 전담
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # 프로젝트 목록 (대시보드)
│   │   │   ├── login/page.tsx
│   │   │   ├── register/page.tsx
│   │   │   └── (phases)/
│   │   │       ├── research-input/page.tsx   # Phase 1
│   │   │       ├── market-research/page.tsx  # Phase 2
│   │   │       ├── agent-setup/page.tsx      # Phase 3 (주제→모드→에이전트 위저드)
│   │   │       ├── meeting/page.tsx          # Phase 4 (자동 시작 SSE)
│   │   │       └── minutes/page.tsx          # Phase 5
│   │   ├── components/
│   │   │   ├── auth/AuthGuard.tsx
│   │   │   └── layout/
│   │   │       ├── AppShell.tsx
│   │   │       ├── Sidebar.tsx
│   │   │       ├── Stepper.tsx
│   │   │       └── TopNav.tsx
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx        # 사용자 세션 (JWT + httpOnly 쿠키)
│   │   │   └── ProjectContext.tsx     # Phase 간 상태
│   │   ├── lib/
│   │   │   ├── api.ts                # backend 호출 유틸리티 (SSE/NDJSON 포함)
│   │   │   ├── types.ts              # 타입 (backend schemas 동기화)
│   │   │   └── persona.ts            # 페르소나 헬퍼
│   │   └── styles/globals.css
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   └── tailwind.config.ts
│
├── backend/                          # FastAPI — LLM·데이터 전담
│   ├── main.py                       # FastAPI 앱 + CORS + lifespan(init_db)
│   ├── database.py                   # SQLAlchemy ORM 모델 + async 세션
│   ├── Dockerfile
│   ├── routers/
│   │   ├── auth.py                   # 회원가입/로그인/토큰 갱신/로그아웃
│   │   ├── projects.py               # CRUD 프로젝트 저장
│   │   ├── research.py               # POST /api/research, /api/research/refine
│   │   ├── agents.py                 # POST /api/agents, /agents/stream, /agents/stream/v2 (모드 분기)
│   │   ├── meeting.py                # POST /api/meeting (SSE)
│   │   ├── minutes.py                # POST /api/minutes
│   │   └── usage.py                  # 토큰 사용량 조회 (admin)
│   ├── services/
│   │   ├── openai_client.py
│   │   ├── research_service.py       # 시장조사 + Naver/OpenAI 검색
│   │   ├── research_query_planner.py # 쿼리 분해
│   │   ├── research_source_ranker.py # 소스 랭킹
│   │   ├── research_synthesizer.py   # 보고서 합성
│   │   ├── agent_service.py          # LLM 가상 에이전트 추천 (llm 모드)
│   │   ├── persona_builder.py        # DB 기반 패널→AgentSchema 변환 (rag 모드, topic 지원)
│   │   ├── meeting_service.py        # LangGraph 상태머신 FGI 엔진 (RAG/LLM 분기)
│   │   ├── minutes_service.py
│   │   ├── auth_service.py           # JWT + bcrypt
│   │   ├── project_service.py        # 프로젝트 제목 자동 생성
│   │   ├── naver_search_service.py
│   │   ├── openai_web_search_service.py
│   │   └── usage_tracker.py          # 토큰 로깅 (in-memory + DB)
│   ├── prompts/
│   │   ├── research.py
│   │   ├── agent_recommend.py
│   │   ├── moderator.py              # 사회자 + 발언 선택 + 포화도 판단
│   │   ├── rag_utterance.py          # RAG 기반 발언 생성 프롬프트
│   │   ├── panel_query.py            # 리서치 컨텍스트 → 이상적 참여자 프로필 합성
│   │   └── minutes.py
│   ├── rag/                          # RAG 파이프라인 (패널 기반)
│   │   ├── __init__.py
│   │   ├── codebook_data.json        # 인구통계 코드북
│   │   ├── embedder.py               # OpenAI text-embedding-3-small (1536차원)
│   │   ├── memory_builder.py         # 14개 카테고리 자전적 기억 생성
│   │   ├── scratch_builder.py        # CSV→인구통계 dict 변환
│   │   ├── panel_selector.py         # 클러스터 다양성 + 주제 관련성 기반 패널 선택
│   │   └── retriever.py              # 코사인 유사도 RAG 검색
│   ├── scripts/
│   │   ├── seed_panels.py            # CSV→DB 패널 데이터 적재 (avg_embedding 포함)
│   │   └── compute_avg_embeddings.py # 기존 패널 avg_embedding 1회성 계산
│   ├── models/
│   │   └── schemas.py                # Pydantic v2 스키마
│   ├── requirements.txt
│   └── .env
│
├── .github/workflows/
│   └── deploy.yml                    # GitHub Actions → Cloud Run 배포
├── CLAUDE.md
└── README.md
```

## 기술 스택

### Frontend (`frontend/`)

- Next.js 14.2 (App Router) + TypeScript 5
- Tailwind CSS 3.4 + Pretendard 폰트
- React Context + sessionStorage (상태관리)
- fetch → backend FastAPI 호출 (SSE/NDJSON 스트리밍 지원)

### Backend (`backend/`)

- FastAPI 0.115+ (Python 3.12)
- OpenAI API (`gpt-4o`) — `openai` + `openai-agents` 패키지
- LangGraph + LangChain — 회의 상태머신
- SQLAlchemy 2.0+ (async) + Cloud SQL PostgreSQL / SQLite (aiosqlite)
- Alembic — DB 마이그레이션
- JWT (python-jose) + bcrypt — 인증
- SSE: `StreamingResponse` (starlette)
- Pydantic v2 (스키마 검증)
- pandas, numpy — 패널 데이터 처리

## DB 스키마 (Cloud SQL / SQLite)

- **User** — 사용자 (id UUID, email, hashed_pw, name, role, is_active)
- **RefreshToken** — JWT 리프레시 토큰 (token_hash SHA-256, expires_at, is_revoked)
- **Project** — 연구 세션 (brief/refined/market_report/agents/meeting_topic/meeting_messages/minutes 각 JSONB/Text)
- **ProjectEdit** — 수정 이력 감사 로그 (field, old_value, new_value)
- **ActivityLog** — 토큰 사용량 추적 (action, model, input_tokens, output_tokens, cost_usd)
- **Panel** — FGI 패널 500명 (인구통계 + 8개 행동 차원 + scratch JSONB + avg_embedding 1536차원)
- **PanelMemory** — 패널별 14개 카테고리 자전적 기억 + 1536차원 임베딩 (~7,000건)

## 패널 데이터 파이프라인

### 원본 → DB 적재 (1회성, `scripts/seed_panels.py`)

CSV 설문 원본(510컬럼 × 500명)을 가공하여 Cloud SQL에 적재한다. **적재 완료 후 로컬 CSV는 삭제됨 (백업은 별도 보관).** DB에 원본은 저장하지 않는다.

```
CSV 510컬럼 (설문 원본, 로컬에만 존재)
│
├─ scratch_builder.py → 핵심 인구통계 추출
│   출력: {"age":50, "gender":"여성", "occupation":"사무직", "region":"서울",
│          "strong_traits":["쇼핑 활동"], "recent_life_events":["이직"], ...}
│   → panels 테이블의 scratch(JSONB) 컬럼에 저장
│
└─ memory_builder.py → 14개 주제로 자연어 압축
    ps_A (가전 45컬럼)    → "집에 보유한 가전: TV, 에어컨, 로봇청소기"
    ps_B (식생활 12컬럼)  → "배달앱 이용, 혼밥 즐김, 커피전문점 자주 방문"
    ps_D (건강 50컬럼)    → "비흡연, 오메가3 복용, 뇌건강 관심"
    pay_* (결제 데이터)    → "월평균 180만원, 편의점 32%, 심야 34%"
    lbs_* (위치 데이터)    → "활동반경 400km, 카페 3449회"
    app_* (앱 데이터)      → "소셜 1110시간, 자주쓰는 앱: YouTube, 토스"
    ... 등 14개 카테고리
    │
    └─ embedder.py → 각 메모리 텍스트를 1536차원 벡터로 변환 (OpenAI text-embedding-3-small)
       → panel_memories 테이블에 저장 (text + importance + embedding)
```

적재 명령: `cd backend && python -m scripts.seed_panels`

- Cloud SQL Proxy 실행 필요 (`cloud-sql-proxy bdml-492404:asia-northeast3:bigmarlab-db --port=5432`)
- `backend/.env`에 DATABASE_URL, OPENAI_API_KEY 필요
- 확인 없이 한 사람씩 즉시 저장, 중단 후 재실행 시 이어서 적재
- 전체 500명 약 10~20분, OpenAI 임베딩 비용 ~$0.02

### Phase 플로우 (사용자 경험 순서)

```
Phase 1: 연구 정보 입력 → Phase 2: 시장조사
→ Phase 3: 주제 · 에이전트 (3-step 위저드)
    Step 1: 회의 주제 입력 (textarea)
    Step 2: 모드 선택 — RAG 실제 패널 / LLM 가상 에이전트
    Step 3: 에이전트 생성 결과 + 편집
→ Phase 4: 회의 시뮬레이션 (주제 Phase 3에서 설정됨, 진입 시 자동 시작)
→ Phase 5: 회의록 · 내보내기
```

- Phase 3 에이전트 생성 엔드포인트: `POST /api/agents/stream/v2` (AgentStreamRequest: brief, refined, report, **topic**, **mode**)
  - `mode="rag"`: `persona_builder.build_personas_stream(target_customer, n_agents, topic)` → 주제 임베딩으로 패널 관련성 반영
  - `mode="llm"`: `agent_service.recommend_agents(req)` → LLM 가상 에이전트 생성 (SSE 래핑)
- Phase 4는 `project.meetingTopic`에서 주제를 받아 자동 시작 (topic input UI 없음)

### 런타임 데이터 흐름 (RAG 파이프라인)

Phase 3 에이전트 선정 (RAG 모드):

1. `persona_builder.py` — brief + report + topic → LLM 합성 쿼리(`prompts/panel_query.py`) → 임베딩 생성
2. `panel_selector.py` — 500명 `panels.avg_embedding`(사전 계산된 메모리 평균 벡터)과 합성 쿼리 임베딩을 코사인 유사도로 비교 → 클러스터 다양성(0.7) + 주제 관련성(0.3) 복합 스코어로 N명 선택
   - `score_panels_by_query()`: avg_embedding 기반 (메모리 벌크 로드 없음)
   - `load_panel_memories_bulk`는 선정 단계에서 호출하지 않음 (Phase 4에서 선정된 N명만 개별 로드)
3. `routers/agents.py` — `AgentStreamRequest`의 brief/report에서 텍스트 추출 → `build_personas_stream`에 전달

Phase 4 회의 시뮬레이션:

3. `meeting_service.py` — 회의 시작 시 RAG 에이전트의 persona를 **1회 DB 조회 → 메모리 캐싱**
4. 매 발언 턴: retrieval 쿼리와 LLM 발언 생성 컨텍스트를 **분리**
   - **retrieval 쿼리** (메모리 검색용): 이전 라운드 요약 + 현재 모더레이터 질문 + 직전 최대 3명 발언 (본인 제외) → 다른 참여자 발언이 내 메모리를 트리거하는 "영감 연쇄" 구조
   - **LLM 프롬프트** (발언 생성용): 전체 대화 히스토리 + 턴 지시문 (기존과 동일)
   - 라운드 전환 시 모더레이터 followup 텍스트를 `round_summaries`에 누적 → 다음 라운드 retrieval에 이전 논점 맥락 전달
5. `retriever.py` — 캐시된 메모리에서 retrieval 쿼리와 코사인 유사도로 관련 기억 검색 (in-memory, DB 재조회 없음)
6. `rag_utterance.py` 프롬프트 — 1인칭 서사형 프로필(scratch의 traits/events/styles 활용) + 검색된 기억을 주입, 수다 톤으로 발언 생성

## API 엔드포인트

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
| POST   | `/api/agents/stream`    | RAG 에이전트 선택              | O     | SSE      |
| POST   | `/api/agents/stream/v2` | 주제 인식 에이전트 (모드 분기) | O     | SSE      |
| POST   | `/api/meeting`          | 회의 시뮬레이션                | O     | SSE      |
| POST   | `/api/minutes`          | 회의록 생성                    | O     | -        |
| GET    | `/api/usage`            | 토큰 사용량                    | O     | -        |
| GET    | `/api/usage/history`    | 활동 로그                      | Admin | -        |
| GET    | `/api/usage/stats`      | 사용 통계                      | Admin | -        |
| GET    | `/api/health`           | 헬스체크                       | -     | -        |

## 통신 규칙

- Frontend `lib/api.ts`를 통해 backend 호출
- 개발: `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` 직접 호출 (프록시 우회)
- 운영: Cloud Run 백엔드 URL을 빌드 시 주입
- SSE 엔드포인트: `fetch + ReadableStream.getReader()`로 수신
- NDJSON 스트리밍: 시장조사 (Phase 2)
- 요청/응답 JSON (SSE/NDJSON 제외)
- Backend Pydantic ↔ Frontend TypeScript 타입 동기화

## 배포

- GCP Cloud Run (frontend: 3000, backend: 8080, 분리 배포)
- Cloud SQL PostgreSQL (asia-northeast3:bigmarlab-db)
- GitHub Actions + Workload Identity Federation (OIDC 기반, 서비스 계정 키 불필요)
- 환경변수: CORS_ORIGINS, DATABASE_URL, JWT_SECRET_KEY, OPENAI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, ADMIN_EMAILS 등 런타임 주입
- Secrets: GCP_PROJECT_ID, GCP_WORKLOAD_IDENTITY_PROVIDER, BACKEND_URL, FRONTEND_URL

## 개발 명령어

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (별도 터미널)
cd frontend && npm install && npm run dev

# 패널 데이터 적재 (최초 1회)
cd backend && python -m scripts.seed_panels

# http://localhost:3000 접속
```

## 코드 컨벤션

### Frontend

- 한국어 주석, 함수형 컴포넌트 + hooks
- `'use client'` 명시, API 호출은 `lib/api.ts` 경유

### Backend

- 한국어 주석/docstring
- 라우터 → 서비스 → OpenAI 호출 (계층 분리)
- 프롬프트는 `prompts/`에 별도 파일
- request/response는 Pydantic 스키마

## 주의사항

- Phase 4: AI 자동 진행만 (사용자 개입 X), 오른쪽 패널은 회의 아젠다만 표시 (회의 정보·발언 횟수·메모리 활성화 UI 제거됨), 채팅 메시지에 메모리 배지 없음
- 내보내기: Markdown + 클립보드 복사만
- sessionStorage로 Phase 간 데이터 전달 (ProjectContext)
- **패널 데이터 적재 완료 상태**: Cloud SQL에 500명 패널 + 5,373개 메모리(1536차원 임베딩) 적재 완료. `seed_panels.py`는 재적재용으로 유지하되 CSV 원본(별도 백업 보관)이 필요함
- **RAG 패널 선정**: 연령 필터링 없이 전체 500명 풀에서 클러스터 다양성 + 주제 관련성만으로 선정. 패널 연령 분포가 30~40대에 편중되어 있어 연령 필터 시 20대 대상 서비스에서 패널 부족 문제 발생하므로 의도적으로 제거함.
- **이전 프로젝트 하위호환**: agent-setup 진입 시 에이전트는 있지만 meetingTopic이 없으면 topic 단계부터 시작. 기존 에이전트 데이터 삭제 불필요.
- **RAG 패널 선정 성능 주의**: 연령 필터 제거 후 500명 전원의 메모리(5,373건 × 30KB JSONB)를 `load_panel_memories_bulk`로 한 번에 로드하면 ~160MB 전송 + json.loads 5,373회로 타임아웃 발생. **절대 전체 패널 메모리를 벌크 로드하지 말 것.** panels.avg_embedding(패널당 평균 임베딩 1개)으로 1차 스코어링하고, 선정된 N명의 메모리만 개별 로드해야 함.
- **embedding_cache.json 동시 접근 금지**: seed_panels 등 임베딩 생성 스크립트가 돌고 있을 때 다른 프로세스가 같은 캐시 파일을 읽으면 JSON 파싱 에러 발생. 동시 실행 시 캐시를 우회(OpenAI 직접 호출)하거나 스크립트 종료 후 실행할 것.
