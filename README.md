# Interactive Multiagent

정성조사 기획 과정을 하나의 흐름으로 연결한 멀티 에이전트 리서치 애플리케이션입니다.  
사용자가 연구 브리프를 입력하면 AI가 내용을 정제하고, 한국 시장 중심의 웹 리서치를 수행하고, 조사 목적에 맞는 가상 참여자를 구성한 뒤, FGI 형식의 회의를 시뮬레이션하고 마지막으로 회의록까지 생성합니다.

프론트엔드는 Next.js, 백엔드는 FastAPI로 구성되어 있으며, 백엔드에서는 OpenAI SDK, OpenAI Agents SDK, LangGraph, LangChain OpenAI를 함께 사용해 단계별 작업을 오케스트레이션합니다.

## 프로젝트 개요

이 프로젝트는 아래 5단계를 하나의 사용자 흐름으로 제공합니다.

1. 연구 배경, 목적, 활용 방안, 카테고리, 타깃 고객을 입력합니다.
2. 입력한 브리프를 AI가 조사 가능한 형태로 정제합니다.
3. 정제된 내용을 기반으로 시장조사 보고서를 생성합니다.
4. 보고서를 바탕으로 FGI 참여자 역할을 추천하고 편집합니다.
5. 참여자 토론을 시뮬레이션하고 회의록을 생성합니다.

단순 질의응답형 챗봇이 아니라, `연구 브리프 작성 -> 시장 탐색 -> 참여자 설계 -> 토론 시뮬레이션 -> 문서화`까지 이어지는 리서치 워크플로우에 가깝습니다.

## 주요 기능

### 1. 연구 브리프 입력

- 연구 배경, 목적, 활용 방안, 카테고리, 타깃 고객을 입력합니다.
- 프론트엔드 상태는 `sessionStorage`의 `bigmarlab_project` 키에 저장됩니다.
- 상위 단계 입력이 바뀌면 하위 단계 결과를 초기화해 흐름 불일치를 막습니다.

### 2. 연구 정보 정제와 시장조사

- `POST /api/research/refine`에서 브리프를 빠르게 정제합니다.
- `POST /api/research`에서 NDJSON 스트리밍 방식으로 시장조사를 진행합니다.
- 네이버 검색 결과와 OpenAI 웹 검색 결과를 함께 모아 섹션별 근거를 구성합니다.
- 보고서는 `market_overview`, `competitive_landscape`, `target_analysis`, `trends`, `implications` 다섯 섹션으로 고정됩니다.

### 3. 에이전트 추천과 페르소나 편집

- 시장조사 결과를 바탕으로 소비자, 전문가, 커스텀 에이전트를 추천합니다.
- 소비자 페르소나는 나이, 성별, 직업, 성향, 경험, pain point, 말투를 포함합니다.
- 프론트엔드에서 에이전트를 수정, 삭제, 추가할 수 있습니다.
- 저장된 페르소나를 다시 system prompt로 합성할 수 있습니다.

### 4. 회의 시뮬레이션

- `POST /api/meeting`은 SSE(`text/event-stream`)로 발언을 토큰 단위 스트리밍합니다.
- 회의 시작 전에 주제를 한 번 더 정제합니다.
- 각 라운드에서 다음 발언자를 선택하고, 반복되는 인사이트가 줄어들면 회의를 종료합니다.
- 필요 시 회의 맥락을 보강하기 위한 추가 검색을 제한적으로 수행합니다.

### 5. 회의록 생성

- `POST /api/minutes`에서 회의 로그를 바탕으로 Markdown 회의록을 생성합니다.
- 회의록 생성 시 시장 근거 보강을 위해 추가 검색을 사용할 수 있습니다.
- 최종 결과에는 회의 발화록이 부록으로 포함됩니다.
- 프론트엔드에서 복사 및 Markdown 다운로드를 지원합니다.

## 사용자 흐름

현재 프론트엔드 라우트는 다음과 같습니다.

- `/research-input`: 연구 브리프 입력
- `/market-research`: 연구 정보 정제와 시장조사
- `/agent-setup`: 에이전트 추천 및 편집
- `/meeting`: 회의 시뮬레이션
- `/minutes`: 회의록 생성 및 내보내기

루트 경로 `/`로 진입하면 저장된 `currentPhase` 값에 따라 적절한 단계로 자동 이동합니다.

## 아키텍처

```text
frontend (Next.js)
  ├─ 단계별 UI
  ├─ sessionStorage 기반 상태 유지
  └─ NDJSON/SSE 스트림 수신
       ↓
backend (FastAPI)
  ├─ /api/research         : 연구 정제 + 시장조사 스트림
  ├─ /api/research/refine  : 빠른 정제
  ├─ /api/agents           : 에이전트 추천
  ├─ /api/meeting          : 회의 시뮬레이션 SSE
  ├─ /api/minutes          : 회의록 생성
  └─ /api/usage            : 사용량 요약
       ↓
LLM orchestration
  ├─ OpenAI SDK / Agents SDK
  ├─ LangGraph
  ├─ LangChain OpenAI
  ├─ Naver Search
  └─ OpenAI Web Search
```

## 디렉터리 구조

```text
interactive multiagent/
├─ backend/
│  ├─ main.py
│  ├─ models/
│  ├─ prompts/
│  ├─ routers/
│  ├─ services/
│  └─ requirements.txt
├─ frontend/
│  ├─ src/app/
│  ├─ src/components/
│  ├─ src/contexts/
│  ├─ src/lib/
│  └─ package.json
├─ docs/
└─ README.md
```

## 백엔드 엔드포인트

- `POST /api/research/refine`
  - 입력: `ResearchBrief`
  - 출력: `RefinedResearch`
- `POST /api/research`
  - 입력: `ResearchBrief`
  - 출력: NDJSON 스트림
- `POST /api/agents`
  - 입력: `AgentRequest`
  - 출력: `AgentSchema[]`
- `POST /api/agents/synthesize-prompt`
  - 입력: 이름, 타입, `persona_profile`
  - 출력: `system_prompt`
- `POST /api/meeting`
  - 입력: 참여 에이전트, 회의 주제, 연구 맥락, 최대 라운드 수
  - 출력: SSE 스트림
- `POST /api/minutes`
  - 입력: 회의 메시지, 브리프, 에이전트, 선택적 회의 주제
  - 출력: Markdown 회의록
- `GET /api/usage`
  - 누적 토큰 사용량 요약
- `POST /api/usage/reset`
  - 사용량 기록 초기화
- `GET /api/health`
  - 헬스체크

## 주요 코드 위치

- `backend/services/research_service.py`: 시장조사 스트리밍 파이프라인
- `backend/services/agent_service.py`: 에이전트 추천과 페르소나 후처리
- `backend/services/meeting_service.py`: FGI 시뮬레이션과 SSE 스트리밍
- `backend/services/minutes_service.py`: 회의록 생성
- `frontend/src/contexts/ProjectContext.tsx`: 프로젝트 전역 상태와 단계 초기화 규칙
- `frontend/src/lib/api.ts`: 프론트엔드 API 호출과 스트림 파싱
- `frontend/src/app/page.tsx`: 현재 단계에 맞는 첫 화면 라우팅

## 기술 스택

### Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

### Backend

- FastAPI
- Pydantic v2
- Uvicorn
- OpenAI Python SDK
- OpenAI Agents SDK
- LangGraph
- LangChain Core
- LangChain OpenAI

## 로컬 실행

### 1. 환경 변수

프로젝트 루트 또는 `backend/`에서 `.env`를 읽을 수 있어야 합니다.

```env
OPENAI_API_KEY=your_api_key
```

프론트엔드에서 별도 백엔드 주소를 사용하려면 아래 값을 추가할 수 있습니다.

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
BACKEND_URL=http://localhost:8000
```

### 2. 백엔드 실행

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

기본 주소:

- `http://localhost:8000`
- `http://localhost:8000/api/health`

### 3. 프론트엔드 실행

```powershell
cd frontend
npm install
npm run dev
```

기본 주소:

- `http://localhost:3000`

개발 환경에서는 Next.js 프록시 타임아웃을 피하기 위해 프론트엔드가 기본적으로 `http://localhost:8000/api`를 직접 호출합니다.

## 배포 메모

프론트엔드와 백엔드를 분리 배포하는 구성이 가장 단순합니다.

GitHub Actions에서 GCP 인증은 서비스 계정 키 대신 Workload Identity Federation을 사용합니다.

필요한 GitHub repository secrets:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `BACKEND_URL`
- `FRONTEND_URL`

`GCP_WORKLOAD_IDENTITY_PROVIDER` 값 예시:

```text
projects/1030831007575/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

GitHub OIDC를 서비스 계정 `github-actions@bdml-492404.iam.gserviceaccount.com`에 연결하려면 아래와 같이 설정합니다.

```bash
gcloud iam workload-identity-pools create github-pool \
  --project=bdml-492404 \
  --location=global \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --project=bdml-492404 \
  --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref"

gcloud iam service-accounts add-iam-policy-binding github-actions@bdml-492404.iam.gserviceaccount.com \
  --project=bdml-492404 \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/1030831007575/locations/global/workloadIdentityPools/github-pool/attribute.repository/OWNER/REPO"
```

위 명령의 `OWNER/REPO`는 실제 GitHub 저장소 경로로 바꿔야 합니다. 브랜치를 `main`으로 제한하려면 provider 생성 시 `--attribute-condition="assertion.repository=='OWNER/REPO' && assertion.ref=='refs/heads/main'"`를 추가하면 됩니다.

### 백엔드

권장 환경 변수:

```env
OPENAI_API_KEY=your_api_key
CORS_ORIGINS=https://your-frontend-domain.vercel.app,http://localhost:3000,http://localhost:3001
```

실행 예시:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 프론트엔드

환경 변수:

```env
NEXT_PUBLIC_BACKEND_URL=https://your-backend-domain
BACKEND_URL=https://your-backend-domain
```

운영 환경에서는 Next.js rewrite가 `/api/:path*`를 위 백엔드로 프록시합니다.

## 개발 시 주의사항

- 사용량 추적은 서버 메모리 기반이라 프로세스가 재시작되면 초기화됩니다.
- 프론트엔드 프로젝트 상태는 `sessionStorage` 기반이라 브라우저 세션이 바뀌면 사라집니다.
- 회의 시뮬레이션과 회의록은 실제 사용자 조사 결과가 아니라 AI 생성 결과이므로, 의사결정 전에 반드시 검토가 필요합니다.
- 현재 리서치 파이프라인은 한국 시장 맥락에 맞춰 설계되어 있습니다.

## API 예시

```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "background": "셀프 포토 스튜디오 이용 경험을 이해하고 싶다",
    "objective": "20대 고객의 재방문 요인을 파악하고 싶다",
    "usage_plan": "FGI 질문지 설계와 서비스 개선에 활용",
    "category": "시장 탐색 / 경쟁 분석",
    "target_customer": "20대 여성"
  }'
```

## 한 줄 요약

연구 브리프 작성부터 시장조사, 가상 참여자 구성, FGI 시뮬레이션, 회의록 생성까지를 하나로 묶은 멀티 에이전트 리서치 워크플로우입니다.
