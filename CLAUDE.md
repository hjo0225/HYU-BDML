# Ditto — Agent Conventions

## 한 줄 정의

**Ditto** 는 에이전트 생성·1:1 대화·FGI·성능 평가 대시보드를 통합한 리서치 플랫폼입니다.

## Tech Stack

### Frontend (`frontend/` — Phase 2 이후 신설)

- Next.js 14 (App Router) + TypeScript 5
- Tailwind CSS 3.4 + **Pretendard** 웹폰트
- React Context + sessionStorage (상태관리)
- Recharts (대시보드 시각화 — 게이지·레이더·산점도·막대)
- fetch → backend FastAPI 호출 (SSE/NDJSON 스트리밍)

### Backend (`backend/` — Phase 2 이후 신설)

- FastAPI 0.115+ (Python 3.12)
- OpenAI `gpt-4o` (대화·발화·Judge) + `text-embedding-3-small` (1536차원 임베딩)
- Anthropic `claude-3.5-sonnet` (V2 모델 신뢰도 평가 전용 — Phase 5 부터)
- LangGraph + LangChain — FGI 회의 상태머신
- SQLAlchemy 2.0+ (async) + Cloud SQL PostgreSQL / SQLite (aiosqlite)
- Alembic — DB 마이그레이션
- JWT (python-jose) + bcrypt — 인증
- Pydantic v2

## Directory Map

모노레포 구조 — `frontend/`(UI 전담)와 `backend/`(LLM·데이터 전담)를 완전히 분리한다.

```
HYU_BDML/  (※ Phase 6 에 GitHub 리포명을 Ditto 로 rename 예정)
├── archive/bdml-fgi/        # 동결된 BDML-FGI 코드·문서. read-only 참조 전용. 직접 import 금지.
├── frontend/                # (Phase 2 이후) Next.js — UI 전담
├── backend/                 # (Phase 2 이후) FastAPI — LLM·데이터 전담
├── docs/                    # SSOT (Single Source of Truth)
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── api-spec.md
│   ├── EVAL_SPEC.md         # V1~V5 평가 지표 명세
│   ├── 6-LENS_MAPPING.md    # Twin-2K-500 234문항 → L1~L6 매핑
│   ├── adr/                 # 아키텍처 결정 기록
│   └── plans/active|completed/
├── DESIGN.md                # 디자인 토큰 + 컴포넌트 규칙 (UI 작업 시 SSOT)
├── CLAUDE.md
├── README.md
└── .cursorrules
```

## 핵심 도메인 모델 (요약)

```
User → ResearchProject
       ├─ Survey (질문 + 응답)        ← v1.0 Phase 6
       ├─ Agent (Twin 또는 Survey 기반)
       │   ├─ PersonaParams (수치 — L1~L6 정량 지표)
       │   ├─ PersonaPrompt (시스템 프롬프트 — 수치+원문 하이브리드)
       │   ├─ Memory (base / conversation / fgi 누적)
       │   └─ EvaluationSnapshot (V1~V5 점수 시계열)
       ├─ Conversation (1:1 대화 + Turn[])
       └─ FGISession (다자 회의 + Turn[] + 사용자 개입)
```

## Reference Documents (Progressive Disclosure)

필요한 시점에만 다음 문서를 읽으세요. 자동 로드하지 마세요. **`docs/` 안 파일들이 단일 진실 공급원(SSOT)입니다.**

### Product Requirements — `@docs/PRD.md`

**Read when:** 새 기능 추가, 사용자 흐름 변경, 수용 기준 확인 시.

### API Specification — `@docs/api-spec.md`

**Read when:** API 엔드포인트 추가/수정, 요청·응답 스키마 변경, SSE/NDJSON 페이로드 변경 시. 변경 시 `frontend/src/lib/types.ts` 와 같은 PR 에서 동기화.

### Architecture — `@docs/ARCHITECTURE.md`

**Read when:** frontend ↔ backend 경계 변경, 새 외부 의존성 추가, 6-Lens·Persona·Evaluation 파이프라인의 데이터 흐름 변경, 배포 토폴로지 변경 시.

### Data Model — `@docs/DATA_MODEL.md`

**Read when:** Cloud SQL 스키마, Alembic 마이그레이션, `agents` / `agent_memories` / `evaluation_snapshots` 처리 로직 작업 시.

### Evaluation Spec — `@docs/EVAL_SPEC.md`

**Read when:** V1~V5 평가 채점 공식, 자극 세트(원본 234문항·반사실적 변형·Judge 프롬프트) 변경, 대시보드 점수 표시 규칙 변경 시.

### 6-Lens Mapping — `@docs/6-LENS_MAPPING.md`

**Read when:** Twin-2K-500 문항을 L1~L6 카테고리로 분류하거나, 새 문항을 어디에 넣을지 결정할 때.

### Decision Log — `@docs/adr/`

**Read when:** "왜 이렇게 설계됐는지" 알아야 할 때. 새 아키텍처 결정 시 새 ADR 추가 + 이전 결정은 "Superseded by ADR-XXXX" 로 표시.

### Design — `@DESIGN.md`

**Read when:** UI/스타일 코드를 쓸 때만. 토큰(색·타이포·간격·라운드)과 컴포넌트(Button/Input/Gauge/RadarChart/ScoreBadge/ChatBubble/FGIInterventionInput) 규칙의 SSOT.

## 코드 컨벤션

### Frontend

- 한국어 주석, 함수형 컴포넌트 + hooks
- `'use client'` 명시, API 호출은 `frontend/src/lib/api.ts` 경유 (직접 fetch 금지)
- Backend Pydantic ↔ Frontend `lib/types.ts` 항상 동기화
- 디자인은 `DESIGN.md` 토큰만 사용 — 임의의 hex/rgb, 매직 px, 인라인 스타일 금지
- Recharts 차트는 컴포넌트로 추출 (`components/dashboard/`)

### Backend

- 한국어 주석/docstring
- 라우터 → 서비스 → (lenses / scoring / persona / evaluation) → OpenAI/Anthropic/DB (계층 분리)
- 프롬프트는 `prompts/` 에 별도 파일. 서비스 코드 인라인 금지.
- request/response 는 Pydantic 스키마 (`models/schemas.py`)

## Workflow Rules

- **Plan-First:** 코드 변경 전 `docs/plans/active/<slug>.md` 가 있어야 한다. 없으면 plan 부터 작성.
- **명세 우선 갱신:** 코드 변경이 명세서와 어긋나면, 반드시 `docs/` 안 해당 문서를 먼저 갱신한 뒤 코드를 수정한다.
- **API 시그니처 변경 시:** `docs/api-spec.md` + `frontend/src/lib/types.ts`(Pydantic ↔ TypeScript) 를 같은 PR 에서 갱신. SSE/NDJSON 페이로드도 동일.
- **평가 지표 변경 시:** `docs/EVAL_SPEC.md` 갱신 후 `backend/evaluation/` + `frontend/components/dashboard/` 수정.
- **6-Lens 매핑 변경 시:** `docs/6-LENS_MAPPING.md` 갱신 후 `backend/lenses/mapping.py` 수정.
- **아키텍처 결정 변경 시:** 기존 ADR 을 수정하지 말고, 새 ADR 을 `docs/adr/` 에 추가하고 이전 것을 "Superseded by ADR-XXXX" 로 표시.
- **frontend ↔ backend 통신:** 모든 API 호출은 `frontend/src/lib/api.ts` 경유. 직접 fetch 금지.
- **DB 스키마 변경:** Alembic 마이그레이션 작성 + `docs/DATA_MODEL.md` 갱신. Cloud SQL(PostgreSQL)과 로컬 SQLite(aiosqlite) 양쪽 호환을 항상 확인.
- **모노레포 경계:** frontend 는 LLM/DB 직접 호출 금지, backend 는 UI 로직(렌더링·sessionStorage) 인지 금지.
- **archive 격리:** `archive/` 안 코드는 read-only 참조용. 신규 코드가 직접 import 하지 말고, 필요한 부분만 새 위치에 복사·재작성.
- **커밋 메시지:** `<type>(<scope>): <subject>` (type: feat|fix|chore|docs|refactor|test|perf|hotfix). master 직접 커밋 금지, 브랜치 prefix 필수.

## IMPORTANT

- 명세서 없이 추측으로 코드를 작성하지 않습니다. 불명확하면 사용자에게 질문합니다.
- `docs/` 안 파일들이 **단일 진실 공급원(Single Source of Truth)** 입니다.
- **에이전트 생성:** Twin-2K-500 한국어 30명을 시작으로, 이후 사용자 자체 Survey 응답으로 확장. 6-Lens(L1~L6) + 정성 그룹 카테고리 분할이 모든 다운스트림(평가·대화·FGI)의 토대.
- **Persona 프롬프트:** 수치(`persona_params`) + 원문(`scratch.aspire/ought/actual`) 하이브리드. 시스템 프롬프트 ≤ 8k tokens (Lost-in-the-middle 회피).
- **평가 지표:** Identity(V1/V2/V3) + Logic(V4/V5). 결과는 `EvaluationSnapshot` 테이블에 시계열로 저장하여 에이전트 성장 추적 가능.
- **FGI 사용자 개입:** LangGraph 노드를 yield/resume 가능 구조로 설계. 모더레이터 라운드 사이에 사용자 입력 hook.
- **Phase 간 데이터 전달:** sessionStorage(`ProjectContext`) — 서버 라운드트립 없이 즉각 전환.
- **`source` 컬럼 분리 규칙:** Twin v2 적재본은 `agents.source_type='twin'`, Survey 기반은 `'survey'`. 신규 `agents` 테이블은 `archive/` 의 `panels` 테이블과 **별도**로 운영.
- **archive 데이터 자산:** Cloud SQL `panels` (`source='fgi500'` 500명 + `source='twin2k500'` 50명) 은 BDML 시절 자산. Ditto 가 직접 사용하지 않으며, 통합·삭제 여부는 별도 ADR 에서 결정.
- **DB 덤프·CSV 원본·`embedding_cache.json` 절대 git 커밋 금지.**
