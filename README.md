# 🚀 Interactive Multiagent

> **한 줄 요약:** 연구 브리프 입력 하나로 시장조사 → 가상 참여자 구성 → FGI 시뮬레이션 → 회의록 생성까지 자동 수행하는 멀티 에이전트 리서치 워크플로우

[![Deploy to GCP](https://github.com/hjo0225/interactive-multiagent/actions/workflows/deploy.yml/badge.svg?style=for-the-badge)](https://github.com/hjo0225/interactive-multiagent/actions/workflows/deploy.yml)
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=for-the-badge&logo=openai&logoColor=white)
![GCP](https://img.shields.io/badge/GCP-Cloud_Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)

## 1. 개요

- **핵심 가치:** 정성조사 기획에 필요한 시장 탐색 → 참여자 설계 → 토론 시뮬레이션 → 문서화를 하나의 사용자 흐름으로 통합. 리서처의 반복 작업을 AI 오케스트레이션으로 대체합니다.
- **배포 URL:** GCP Cloud Run (프론트엔드 · 백엔드 분리 배포)
- **주요 기술:** `Next.js 14`, `FastAPI`, `OpenAI Agents SDK`, `LangGraph`, `SSE`

### 사용자 흐름 (5단계)

| 단계 | 라우트             | 기능                               |
| ---- | ------------------ | ---------------------------------- |
| 1    | `/research-input`  | 연구 브리프 입력                   |
| 2    | `/market-research` | 연구 정보 정제 + 시장조사 스트리밍 |
| 3    | `/agent-setup`     | 가상 참여자(에이전트) 추천 및 편집 |
| 4    | `/meeting`         | FGI 회의 시뮬레이션 (SSE)          |
| 5    | `/minutes`         | 회의록 생성 및 Markdown 내보내기   |

## 2. 핵심 문제 해결

### 🏗 Architecture

```text
Browser (Next.js)
  ├─ sessionStorage  ← 단계 간 상태 유지
  ├─ NDJSON 스트림 수신  ← 시장조사
  └─ SSE 스트림 수신    ← 회의 시뮬레이션
       │  HTTP / SSE
       ▼
FastAPI (Backend)
  ├─ POST /api/research/refine   브리프 정제
  ├─ POST /api/research          시장조사 NDJSON 스트림
  ├─ POST /api/agents            에이전트 추천
  ├─ POST /api/agents/synthesize-prompt
  ├─ POST /api/meeting           회의 시뮬레이션 SSE
  ├─ POST /api/minutes           회의록 생성
  ├─ GET  /api/usage             토큰 사용량 요약
  └─ GET  /api/health            헬스체크
       │
       ▼
LLM Orchestration
  ├─ OpenAI SDK / Agents SDK  (GPT-4.1)
  ├─ LangGraph                (회의 흐름 상태머신)
  ├─ LangChain OpenAI
  ├─ Naver Search API         (한국 시장 맥락)
  └─ OpenAI Web Search
```

### ⚖️ Why this tech? (Trade-offs)

| 선택한 기술                  | 도입 이유                                                            | 고려했던 대안 및 포기한 이유                                                    |
| ---------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **LangGraph**                | 회의 시뮬레이션의 라운드 전환·종료 조건을 상태머신으로 명확하게 표현 | LangChain LCEL만으로는 분기·루프 로직 표현이 장황해짐                           |
| **SSE (Server-Sent Events)** | 회의 발언을 토큰 단위로 실시간 스트리밍, 연결 유지 단순              | WebSocket은 양방향이 필요 없는 단방향 스트림에 과도한 설계                      |
| **NDJSON 스트리밍**          | 시장조사 섹션을 순서대로 점진적 렌더링 가능                          | 단일 JSON 응답은 전체 완료 전까지 화면이 비어있어 UX 저하                       |
| **Naver Search API**         | 한국어 시장 정보의 밀도·신뢰도 확보                                  | OpenAI Web Search만 사용 시 한국 시장 맥락 데이터 부족                          |
| **sessionStorage**           | 별도 DB 없이 단계 간 상태 전달, 프로토타입 속도 우선                 | Redux/Zustand는 새로고침 시 소실 문제 동일하면서 설정 비용 높음                 |
| **GCP Cloud Run**            | 컨테이너 단위 분리 배포, Workload Identity로 키 관리 불필요          | EC2/GCE는 인스턴스 관리 부담, Vercel은 백엔드 장시간 SSE 스트림에 타임아웃 이슈 |

## 3. 핵심 기능 및 트러블슈팅

### 🛠 회의 시뮬레이션 SSE — Next.js 프록시 타임아웃

- **상황:** 회의 시뮬레이션은 수 분간 지속되는 SSE 스트림인데, Next.js rewrites 프록시를 경유하면 30초 타임아웃으로 연결이 끊어짐
- **해결:** 개발 환경에서는 프론트엔드가 `http://localhost:8000/api`를 직접 호출하도록 분기 처리. 운영 환경에서는 백엔드 Cloud Run URL을 `NEXT_PUBLIC_BACKEND_URL`로 직접 지정해 프록시 우회
- **결과:** 긴 회의(20+ 라운드)에서도 스트림 단절 없이 전체 발언 수신 가능

### 🛠 시장조사 스트리밍 — 섹션별 점진적 렌더링

- **상황:** 시장조사 보고서 전체 생성에 30~60초 소요. 단일 응답 방식은 빈 화면 대기 시간이 길어 UX 저하
- **해결:** 5개 고정 섹션(`market_overview`, `competitive_landscape`, `target_analysis`, `trends`, `implications`)을 NDJSON으로 순차 스트리밍. 각 섹션 완료 시 즉시 렌더링
- **결과:** 첫 번째 섹션이 3~5초 내 표시되어 체감 대기 시간 대폭 감소

### 🛠 에이전트 페르소나 일관성 — system prompt 합성

- **상황:** 사용자가 편집한 페르소나 필드(나이·성향·말투 등)와 회의에서 실제 사용되는 system prompt가 불일치하는 문제
- **해결:** `POST /api/agents/synthesize-prompt`에서 편집된 페르소나 프로필을 받아 LLM이 일관된 system prompt로 재합성. 저장 전 프리뷰 가능
- **결과:** 페르소나 편집 내용이 회의 발언 톤·관점에 실제로 반영됨

## 4. 실행 방법

### 💻 Local

**환경 변수 설정**

```env
# backend/.env
OPENAI_API_KEY=your_openai_api_key
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret

# frontend/.env.local (선택)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
BACKEND_URL=http://localhost:8000
```

**백엔드 실행**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# http://localhost:8000
```

**프론트엔드 실행**

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

### 🐳 Docker (배포)

```bash
# 백엔드
docker build -t interactive-multiagent-backend ./backend
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e CORS_ORIGINS=http://localhost:3000 \
  interactive-multiagent-backend

# 프론트엔드
docker build -t interactive-multiagent-frontend ./frontend \
  --build-arg NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
docker run -p 3000:3000 interactive-multiagent-frontend
```

## 5. 유지보수

- **CI/CD:** GitHub Actions + GCP Workload Identity Federation → Cloud Run 자동 배포 (`deploy.yml`)

  - 서비스 계정 키 대신 OIDC 기반 인증으로 시크릿 관리 최소화
  - 필요 secrets: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `BACKEND_URL`, `FRONTEND_URL`

- **API Document:** `http://localhost:8000/docs` (FastAPI 자동 생성 Swagger UI)

- **Test Strategy:**

  - 현재 E2E 위주 수동 검증 (각 Phase 입출력 확인)
  - 핵심 검증 대상: SSE 스트림 단절 여부, 페르소나 합성 정합성, 단계 초기화 규칙 (상위 단계 변경 시 하위 단계 결과 리셋)

- **주의사항:**
  - 사용량 추적은 서버 메모리 기반 → 프로세스 재시작 시 초기화
  - 프론트엔드 상태는 `sessionStorage` 기반 → 브라우저 세션 종료 시 소실
  - 회의 시뮬레이션·회의록은 AI 생성 결과이므로 실제 의사결정 전 반드시 검토 필요
