# 빅데이터마케팅랩 (BigDataMarketingLab)

AI 에이전트 기반 정성조사(FGI) 시뮬레이션 웹앱. 사용자가 연구 정보를 입력하면 AI가 시장조사 → RAG 기반 패널 구성 → FGI 회의 시뮬레이션 → 회의록 생성까지 자동 수행.

## Tech Stack

### Frontend (`frontend/`)

- Next.js 14.2 (App Router) + TypeScript 5
- Tailwind CSS 3.4 + IBM Plex Sans KR 폰트 (Google Fonts)
- React Context + sessionStorage (상태관리)
- fetch → backend FastAPI 호출 (SSE/NDJSON 스트리밍 지원)

### Backend (`backend/`)

- FastAPI 0.115+ (Python 3.12)
- OpenAI API (`gpt-4o`) — `openai` + `openai-agents` 패키지
- LangGraph + LangChain — 회의 상태머신
- SQLAlchemy 2.0+ (async) + Cloud SQL PostgreSQL / SQLite (aiosqlite)
- Alembic — DB 마이그레이션
- JWT (python-jose) + bcrypt — 인증
- Pydantic v2, pandas, numpy

## Directory Map

모노레포 구조 — `frontend/`(UI 전담)와 `backend/`(LLM·데이터 전담)를 완전히 분리한다.

```
bigmarlab/
├── frontend/                         # Next.js — UI 전담
│   └── src/
│       ├── app/                      # App Router
│       │   ├── page.tsx              # 랜딩 (공개, 인증 시 /dashboard 리다이렉트)
│       │   ├── login/, register/     # 인증
│       │   ├── dashboard/            # 프로젝트 목록 (인증 필요)
│       │   ├── (phases)/             # research-input, market-research, agent-setup, meeting, minutes (인증 필요)
│       │   └── lab/                  # 실험실 (공개) — page.tsx 목록 + chat/[twinId]/page.tsx 메신저
│       ├── components/               # AuthGuard, layout (AppShell, Sidebar, Stepper, TopNav)
│       ├── contexts/                 # AuthContext (JWT 세션), ProjectContext (Phase 간 상태)
│       ├── lib/                      # api.ts (SSE/NDJSON), types.ts (backend 동기화), persona.ts
│       └── styles/globals.css
│
├── backend/                          # FastAPI — LLM·데이터 전담
│   ├── main.py                       # FastAPI 앱 + CORS + lifespan(init_db)
│   ├── database.py                   # SQLAlchemy ORM + async 세션
│   ├── routers/                      # auth, projects, research, agents, meeting, minutes, usage, lab
│   ├── services/                     # research_*, agent_service, persona_builder, meeting_service, minutes_service, auth_service, project_service, *_search_service, usage_tracker, lab_service
│   ├── prompts/                      # research, agent_recommend, moderator, rag_utterance, panel_query, minutes, twin_utterance
│   ├── rag/                          # embedder, memory_builder, scratch_builder, panel_selector, retriever, codebook_data.json, twin_scratch_builder, twin_memory_builder
│   ├── scripts/                      # seed_panels, compute_avg_embeddings, seed_twin (1회성)
│   └── models/schemas.py             # Pydantic v2 스키마 (Project, Agent, Meeting, Lab*)
│
├── docs/                             # 명세서 (Single Source of Truth — 아래 참조)
├── scripts/playwright-audit/         # 1회성 UI 감사 (audit.mjs + screenshots/)
├── .github/workflows/deploy.yml      # GitHub Actions → Cloud Run 배포
├── CLAUDE.md
└── README.md
```

## Reference Documents (Progressive Disclosure)

필요한 시점에만 다음 문서를 읽으세요. 자동 로드하지 마세요. **`docs/` 안 파일들이 단일 진실 공급원(SSOT)입니다.**

### Product Requirements — `@docs/PRD.md`

**Read when:** 새 Phase 추가, 사용자 흐름 변경, 수용 기준(acceptance criteria) 확인 시

### API Specification — `@docs/api-spec.md`

**Read when:** API 엔드포인트 추가/수정, 요청·응답 스키마 변경, SSE/NDJSON 페이로드 변경 시

### Architecture — `@docs/ARCHITECTURE.md`

**Read when:** frontend ↔ backend 경계 변경, 새 외부 의존성(OpenAI, Naver 등) 추가, RAG 파이프라인의 데이터 흐름 변경, 배포 토폴로지 변경 시

### Data Model — `@docs/DATA_MODEL.md`

**Read when:** Cloud SQL 스키마, Alembic 마이그레이션, 패널/메모리 임베딩 처리 로직, 패널 적재 스크립트 작업 시

### Decision Log — `@docs/adr/`

**Read when:** "왜 이렇게 설계됐는지" 알아야 할 때 (예: 연령 필터 제거 사유, `avg_embedding` 도입, RAG/LLM 모드 분기). 새 아키텍처 결정 시 새 ADR을 추가하고, 이전 결정은 "Superseded by ADR-XXXX"로 표시합니다.

## 디자인 시스템 (BDML 로고 기반)

### 로고

- 파일: `frontend/public/logo.png` (원본: `docs/RAG/image.png`)
- 구성: "BDML" 타이포 + 데이터 차트 그래픽 + "Big Data Marketing Lab" 서브텍스트
- 사용 위치: 로그인/회원가입 카드 헤더, 대시보드 헤더, TopNav, Sidebar

### 컬러 팔레트

로고의 두 가지 핵심 컬러를 기반으로 전체 UI 컬러 시스템을 구성한다.

| 역할 | 변수 | 값 | 용도 |
|---|---|---|---|
| **Navy (기본)** | `--accent` | `#0d2748` | 버튼, 링크, 완료 상태, 텍스트 |
| Navy hover | `--accent-hover` | `#091c38` | 버튼 hover |
| Navy light | `--accent-light` | `#e8eef6` | 선택/활성 배경 |
| **Cyan (포인트)** | `--cyan` | `#38b6e8` | 활성 인디케이터, 진행 상태, 하이라이트 |
| Cyan hover | `--cyan-hover` | `#2a9fd0` | Cyan 요소 hover |
| Cyan light | `--cyan-light` | `#e5f4fb` | 태그/배지 배경 |
| Text primary | `--text-primary` | `#0d2748` | 본문 텍스트 (= Navy) |
| Text secondary | `--text-secondary` | `#3d5a80` | 보조 텍스트 |
| Text muted | `--text-muted` | `#8aa0ba` | 비활성 텍스트 |

### 컬러 사용 규칙

- **Navy (`--accent`)**: 주요 CTA 버튼 배경, 완료된 Phase 표시, 텍스트 링크
- **Cyan (`--cyan`)**: 현재 활성 Phase 표시, 진행률 인디케이터, 강조 배지
- **Auth 페이지 그라데이션**: `linear-gradient(135deg, #091c38 0%, #0d2748 50%, #1a6b8a 100%)` — Navy → Teal 전환
- 새 컬러 추가 시 Navy/Cyan 계열 내에서 확장할 것
- `tailwind.config.ts`에 CSS 변수 기반 컬러 토큰 정의. `cyan`, `cyan-light` 등 Tailwind 클래스로 사용 가능.

## 개발 명령어

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (별도 터미널)
cd frontend && npm install && npm run dev

# 패널 데이터 적재 (최초 1회, Cloud SQL Proxy 실행 필요)
cd backend && python -m scripts.seed_panels

# http://localhost:3000 접속
```

## 코드 컨벤션

### Frontend

- 한국어 주석, 함수형 컴포넌트 + hooks
- `'use client'` 명시, API 호출은 `lib/api.ts` 경유
- Backend Pydantic ↔ Frontend `lib/types.ts` 항상 동기화

### Backend

- 한국어 주석/docstring
- 라우터 → 서비스 → OpenAI 호출 (계층 분리)
- 프롬프트는 `prompts/`에 별도 파일
- request/response는 Pydantic 스키마 (`models/schemas.py`)

## Workflow Rules

- **명세 우선 갱신:** 코드 변경이 명세서와 어긋나면, 반드시 `docs/` 안 해당 문서를 먼저 갱신한 뒤 코드를 수정합니다.
- **API 시그니처 변경 시:** `docs/api-spec.md`와 `frontend/src/lib/types.ts`(Pydantic ↔ TypeScript)를 같은 PR에서 갱신합니다. SSE/NDJSON 페이로드도 동일.
- **아키텍처 결정 변경 시:** 기존 ADR을 수정하지 말고, 새 ADR을 `docs/adr/`에 추가하고 이전 것을 "Superseded by ADR-XXXX"로 표시합니다.
- **frontend ↔ backend 통신:** 모든 API 호출은 `frontend/src/lib/api.ts` 경유. 직접 fetch 금지.
- **DB 스키마 변경:** Alembic 마이그레이션 작성 + `docs/DATA_MODEL.md` 갱신. Cloud SQL(PostgreSQL)과 로컬 SQLite(aiosqlite) 양쪽 호환을 항상 확인.
- **프롬프트 변경:** `backend/prompts/` 안 별도 파일에서만 수정. 서비스 코드에 인라인 금지.
- **모노레포 경계:** frontend는 LLM/DB 직접 호출 금지, backend는 UI 로직(렌더링·sessionStorage) 인지 금지.

## IMPORTANT

- 명세서 없이 추측으로 코드를 작성하지 않습니다. 불명확하면 사용자에게 질문합니다.
- `docs/` 안 파일들이 **단일 진실 공급원(Single Source of Truth)**입니다.
- **Phase 4 시뮬레이션:** AI 자동 진행만 (사용자 개입 X). 오른쪽 패널은 회의 아젠다만 표시 (회의 정보·발언 횟수·메모리 활성화 UI 제거됨), 채팅 메시지에 메모리 배지 없음.
- **내보내기:** Markdown + 클립보드 복사만.
- **Phase 간 데이터 전달:** sessionStorage(`ProjectContext`).
- **패널 데이터 적재 완료 상태:** Cloud SQL에 500명 패널 + 5,373개 메모리(1536차원 임베딩) 적재 완료. `seed_panels.py`는 재적재용으로 유지하되 CSV 원본(별도 백업 보관) 필요. **DB 덤프·CSV 원본·`embedding_cache.json`은 절대 git 커밋 금지.**
- **RAG 패널 선정 — 연령 필터 없음:** 전체 500명 풀에서 클러스터 다양성 + 주제 관련성만으로 선정. 자세한 사유는 [ADR-0002](./docs/adr/0002-rag-panel-no-age-filter.md).
- **RAG 패널 선정 — 성능 주의:** 절대 `load_panel_memories_bulk`로 전체 500명 메모리(5,373건 × 30KB JSONB ≈ 160MB)를 한 번에 로드하지 말 것 — 타임아웃 발생. `panels.avg_embedding`(패널당 평균 임베딩 1개)으로 1차 스코어링하고, 선정된 N명의 메모리만 개별 로드. 자세한 사유는 [ADR-0003](./docs/adr/0003-avg-embedding-first-pass-scoring.md).
- **`embedding_cache.json` 동시 접근 금지:** `seed_panels` 등 임베딩 생성 스크립트가 도는 중에는 같은 캐시 파일을 다른 프로세스가 읽으면 JSON 파싱 에러 발생. 동시 실행 시 캐시 우회(OpenAI 직접 호출)하거나 스크립트 종료 후 실행.
- **이전 프로젝트 하위호환:** `agent-setup` 진입 시 에이전트는 있지만 `meetingTopic`이 없으면 topic 단계부터 시작. 기존 에이전트 데이터 삭제 불필요.
- **랜딩 / 라우팅:** `/`는 공개 랜딩(서비스 소개). 인증 사용자는 `/`에서 `/dashboard`로 자동 리다이렉트. 기존 프로젝트 목록은 `/dashboard`에 위치. `/login` 후 디폴트 진입은 `/dashboard`.
- **실험실(Lab) — 공개 게스트:** `/lab/*`은 AuthGuard 미적용. 인증 없이 누구나 접근. Twin-2K-500 50명 풀 (`Panel.source='twin2k500'`)과 1:1 메신저 채팅. 토큰 비용 폭주 방지를 위해 IP 단위 일일 30회 메시지 한도(인메모리 카운터). 채팅은 sessionStorage에만 저장(DB 영속화 X). 상세는 [ADR-0005](./docs/adr/0005-lab-twin-2k-500-integration.md).
- **Lab 발화 — Toubia 풀-프롬프트 방식:** 채팅 매 턴 `panels.persona_full`(persona_json 원본 ~42k tokens)을 통째로 시스템 프롬프트에 주입한다. RAG 검색 사용 안 함. 모델은 `LAB_LLM_MODEL` 환경변수(기본 `gpt-4o-mini`, 논문 재현 시 `gpt-4o`).
- **`source` 컬럼 분리 규칙:** `panels` / `panel_memories`의 모든 쿼리는 `source` 필터 필수. 본 서비스 = `'fgi500'`, Lab = `'twin2k500'`. 누락 시 두 도메인 데이터가 섞일 수 있음.
- **`cluster` 공간 분리:** FGI(500명)는 K-means 0~24, Twin(50명)은 오프셋 100을 둔 K-means 100~104. `seed_twin.py`가 50명 적재 직후 K-means(K=5)를 한 번 더 돌려 자동 할당한다. `panel_selector`는 source 필터 후 자체 클러스터 안에서만 동작하므로 두 공간이 충돌하지 않는다.
