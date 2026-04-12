# 빅마랩 (BigDataMarketingLab)

AI 에이전트 기반 정성조사(FGI) 시뮬레이션 웹앱. 사용자가 연구 정보를 입력하면 AI가 시장조사 → RAG 기반 패널 구성 → FGI 회의 시뮬레이션 → 회의록 생성까지 자동 수행.

## 디자인 레퍼런스

**docs/design-reference.html** 파일이 디자인 원본이다. 모든 UI 구현 시 이 파일의 스타일을 따를 것.
단, 색상은 아래 한양대 팔레트로 교체:

- 원본 `#3182F6` → `#1B4B8C` (primary)
- 원본 `#1a6fe8` → `#0D2B5E` (primary hover)
- 원본 `#EBF3FE` → `#E8F0FA` (primary bg)
- 원본 `#B8D4F9` → `#A3C4E8` (primary border)
- 원본 `#DBEAFE` → `#C8DAF0` (light border)

참고할 핵심 클래스: .card, .fl, .fr, .btn-primary, .btn-ghost, .info-box, .report-block, .hypo-item, .pcard-edit, .stat-box, .action-bar, .export-row, .expbtn

## 아키텍처: Frontend / Backend 분리

모노레포 구조로 `frontend/`와 `backend/`를 완전히 분리한다.

```
bigmarlab/
├── docs/
│   ├── design-reference.html
│   └── RAG/                          # RAG 파이프라인 연구 자료
├── frontend/                         # Next.js — UI 전담
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # 랜딩/대시보드
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
│   │   │   ├── AuthContext.tsx        # 사용자 세션
│   │   │   └── ProjectContext.tsx     # Phase 간 상태
│   │   ├── lib/
│   │   │   ├── api.ts                # backend 호출 유틸리티
│   │   │   ├── types.ts              # 타입 (backend schemas 동기화)
│   │   │   └── persona.ts            # 페르소나 헬퍼
│   │   └── styles/globals.css
│   ├── next.config.js
│   ├── package.json
│   └── tailwind.config.ts
│
├── backend/                          # FastAPI — LLM·데이터 전담
│   ├── main.py                       # FastAPI 앱 + CORS + lifespan(init_db)
│   ├── database.py                   # SQLAlchemy ORM (Cloud SQL / SQLite)
│   ├── routers/
│   │   ├── research.py               # POST /api/research, /api/research/refine
│   │   ├── agents.py                 # POST /api/agents, /agents/stream, /agents/stream/v2 (모드 분기)
│   │   ├── meeting.py                # POST /api/meeting (SSE)
│   │   ├── minutes.py                # POST /api/minutes
│   │   ├── auth.py                   # 회원가입/로그인/토큰 갱신
│   │   ├── projects.py               # CRUD 프로젝트 저장
│   │   └── usage.py                  # 토큰 사용량 조회
│   ├── services/
│   │   ├── openai_client.py
│   │   ├── research_service.py       # 시장조사 + Naver/OpenAI 검색
│   │   ├── research_query_planner.py
│   │   ├── research_source_ranker.py
│   │   ├── research_synthesizer.py
│   │   ├── agent_service.py          # LLM 가상 에이전트 추천 (llm 모드)
│   │   ├── persona_builder.py        # DB 기반 패널→AgentSchema 변환 (rag 모드, topic 지원)
│   │   ├── meeting_service.py        # LangGraph 상태머신 FGI 엔진
│   │   ├── minutes_service.py
│   │   ├── auth_service.py           # JWT + bcrypt
│   │   ├── project_service.py        # 프로젝트 제목 생성
│   │   ├── naver_search_service.py
│   │   ├── openai_web_search_service.py
│   │   └── usage_tracker.py          # 토큰 로깅
│   ├── prompts/
│   │   ├── research.py
│   │   ├── agent_recommend.py
│   │   ├── moderator.py              # 사회자 + 발언 선택 + 포화도 판단
│   │   ├── rag_utterance.py          # RAG 기반 발언 생성 프롬프트
│   │   └── minutes.py
│   ├── rag/                          # RAG 파이프라인 (패널 기반)
│   │   ├── __init__.py
│   │   ├── codebook_data.json        # 인구통계 코드북
│   │   ├── embedder.py               # OpenAI text-embedding-3-small
│   │   ├── memory_builder.py         # 14개 카테고리 자전적 기억 생성
│   │   ├── scratch_builder.py        # CSV→인구통계 dict 변환
│   │   ├── panel_selector.py         # 클러스터 다양성 + 주제 관련성 기반 패널 선택
│   │   └── retriever.py              # 코사인 유사도 RAG 검색
│   ├── scripts/
│   │   └── seed_panels.py            # CSV→DB 패널 데이터 적재
│   ├── models/
│   │   └── schemas.py                # Pydantic 스키마
│   ├── requirements.txt
│   └── .env
│
├── CLAUDE.md
└── README.md
```

## 기술 스택

### Frontend (`frontend/`)

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS + Pretendard 폰트
- React Context + sessionStorage (상태관리)
- fetch → backend FastAPI 호출

### Backend (`backend/`)

- FastAPI (Python 3.11+)
- OpenAI API (`gpt-4o`, `gpt-4o-mini`) — `openai` 패키지
- LangGraph + LangChain — 회의 상태머신
- SQLAlchemy (async) + Cloud SQL PostgreSQL / SQLite
- Alembic — DB 마이그레이션
- JWT (python-jose) + bcrypt — 인증
- SSE: `StreamingResponse` (starlette)
- Pydantic v2 (스키마 검증)
- pandas, numpy — 패널 데이터 처리

## DB 스키마 (Cloud SQL / SQLite)

- **User** — 사용자 (email, hashed_pw, role)
- **RefreshToken** — JWT 리프레시 토큰
- **Project** — 연구 세션 (phase_data JSONB × 5단계)
- **ProjectEdit** — 수정 이력 감사 로그
- **ActivityLog** — 토큰 사용량 추적
- **Panel** — FGI 패널 500명 (인구통계 + 8개 행동 차원 + scratch JSONB)
- **PanelMemory** — 패널별 14개 카테고리 자전적 기억 + 1536차원 임베딩 (~7,000건)

## 패널 데이터 파이프라인

### 원본 → DB 적재 (1회성, `scripts/seed_panels.py`)

로컬의 CSV 설문 원본(510컬럼 × 500명)을 가공하여 Cloud SQL에 적재한다.
CSV 원본(`backend/raw/`)은 개인정보이므로 git에 포함하지 않으며, DB에도 원본은 저장하지 않는다.

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
- 10명 단위로 계속 여부 확인, 중단 후 재실행 시 이어서 적재
- 전체 500명 약 10~20분, OpenAI 임베딩 비용 ~$0.02

### Phase 플로우 (사용자 경험 순서)

```
Phase 1: 연구 정보 입력 → Phase 2: 시장조사
→ Phase 3: 주제 · 에이전트 (3-step 위저드)
    Step 1: 회의 주제 입력 (textarea)
    Step 2: 모드 선택 — 📊 RAG 실제 패널 / 🤖 LLM 가상 에이전트
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
1. `panel_selector.py` — DB에서 전체 패널 조회 → 연령 필터 → 클러스터 다양성 + 주제 관련성 복합 스코어로 N명 선택
   - `score_panels_by_topic()`: 각 패널 메모리와 topic 임베딩 간 평균 코사인 유사도
   - 복합 스코어: `(1-w)*cluster_centrality + w*topic_relevance` (w=0.3)
2. `persona_builder.py` — `load_panel_memories_bulk()` 벌크 조회 → Panel + PanelMemory → AgentSchema 변환

Phase 4 회의 시뮬레이션:
3. `meeting_service.py` — 회의 시작 시 RAG 에이전트의 persona를 **1회 DB 조회 → 메모리 캐싱**
4. 매 발언 턴: `retriever.py` — 캐시된 메모리에서 대화 맥락과 코사인 유사도로 관련 기억 검색 (in-memory, DB 재조회 없음)
5. `rag_utterance.py` 프롬프트 — 인구통계 + 검색된 기억을 주입하여 자연스러운 발언 생성

## 통신 규칙

- Frontend `lib/api.ts`를 통해 backend 호출
- 개발: Next.js `rewrites`로 `/api/*` → `http://localhost:8000/api/*` 프록시
- SSE 엔드포인트: `fetch + ReadableStream.getReader()`로 수신
- NDJSON 스트리밍: 시장조사 (Phase 2)
- 요청/응답 JSON (SSE/NDJSON 제외)
- Backend Pydantic ↔ Frontend TypeScript 타입 동기화

## 배포

- GCP Cloud Run (frontend/backend 분리 배포)
- Cloud SQL PostgreSQL (asia-northeast3:bigmarlab-db)
- GitHub Actions + Workload Identity Federation
- 환경변수: CORS_ORIGINS, DATABASE_URL, JWT_SECRET_KEY 등 런타임 주입

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

- Phase 4: AI 자동 진행만 (사용자 개입 X)
- 내보내기: Markdown + 클립보드 복사만
- sessionStorage로 Phase 간 데이터 전달 (ProjectContext)
- `backend/raw/`, `backend/personas/`, `backend/rag/embedding_cache.json`은 .gitignore

## 프로젝트 정보

- 프로젝트명: Interactive Multiagent
- Notion 경로: Projects/BML_Multiagent

## Notion 문서화

- 문서화 요청 시 Notion에 아래 표준 구조로 정리
- Overview: 프로젝트 목적, 대상 사용자, 핵심 기능, 기술스택
- DB Schema: 테이블명, 컬럼, 타입, PK/FK, 인덱스, 관계도
- API Spec: 엔드포인트, HTTP 메서드, 경로 파라미터, 요청/응답 스키마, 인증
- Frontend Structure: 라우팅 구조, 주요 컴포넌트 트리, 상태관리
- README: 설치법, 실행법, 환경변수, 디렉토리 구조
- Changelog: 날짜별 주요 변경사항
- Tech Stack & Config: 프레임워크, 라이브러리, 배포 환경
