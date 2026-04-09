# 빅마랩 (BigDataMarketingLab)

AI 에이전트 기반 정성조사 시뮬레이션 웹앱. 사용자가 연구 정보를 입력하면 AI가 시장조사 → 에이전트 구성 → 회의 시뮬레이션 → 회의록 생성까지 자동 수행.

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
│   └── design-reference.html
├── frontend/                     # Next.js — UI 전담
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── (phases)/
│   │   │       ├── phase-1/page.tsx
│   │   │       ├── phase-2/page.tsx
│   │   │       ├── phase-3/page.tsx
│   │   │       ├── phase-4/page.tsx
│   │   │       └── phase-5/page.tsx
│   │   ├── components/
│   │   │   ├── layout/Sidebar.tsx
│   │   │   └── phase-{1~5}/
│   │   ├── contexts/
│   │   │   └── ProjectContext.tsx
│   │   ├── lib/
│   │   │   ├── api.ts            # backend 호출 유틸리티
│   │   │   └── types.ts          # 타입 (backend schemas와 동기화)
│   │   └── styles/globals.css
│   ├── next.config.js
│   ├── package.json
│   └── tailwind.config.ts
│
├── backend/                      # FastAPI — LLM·데이터 전담
│   ├── main.py                   # FastAPI 앱 + CORS
│   ├── routers/
│   │   ├── research.py           # POST /api/research
│   │   ├── agents.py             # POST /api/agents
│   │   ├── meeting.py            # POST /api/meeting (SSE)
│   │   └── minutes.py            # POST /api/minutes
│   ├── services/
│   │   ├── openai_client.py
│   │   ├── research_service.py
│   │   ├── agent_service.py
│   │   ├── meeting_service.py    # 회의 엔진 (핵심)
│   │   └── minutes_service.py
│   ├── prompts/
│   │   ├── research.py
│   │   ├── agent_recommend.py
│   │   ├── moderator.py
│   │   └── minutes.py
│   ├── models/
│   │   └── schemas.py            # Pydantic 스키마
│   ├── requirements.txt
│   └── .env                      # OPENAI_API_KEY
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
- OpenAI API (`gpt-4o`) — `openai` 패키지
- SSE: `StreamingResponse` (starlette)
- Pydantic v2 (스키마 검증)
- python-dotenv (환경변수)

## 통신 규칙

- Frontend `lib/api.ts`를 통해 backend 호출
- 개발: Next.js `rewrites`로 `/api/*` → `http://localhost:8000/api/*` 프록시
- SSE 엔드포인트: `fetch + ReadableStream.getReader()`로 수신
- 요청/응답 JSON (SSE 제외)
- Backend Pydantic ↔ Frontend TypeScript 타입 동기화

## 개발 명령어

```bash
# Backend
cd backend && pip install -r requirements.txt
&& uvicorn main:app --reload --port 8000

# Frontend (별도 터미널)
cd frontend && npm install && npm run dev

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

- 프로토타입: DB, 인증, 파일 업로드 미구현
- Phase 4: AI 자동 진행만 (사용자 개입 X)
- 내보내기: Markdown + 클립보드 복사만
- sessionStorage로 Phase 간 데이터 전달

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
