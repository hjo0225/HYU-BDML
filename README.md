# interactive multiagent

정성조사 기획을 위한 멀티 에이전트 워크플로우 애플리케이션이다.  
사용자가 연구 정보를 입력하면 AI가 이를 정제하고, 한국 시장 기준 딥리서치를 수행하고, 조사 목적에 맞는 가상 참여자를 구성한 뒤, FGI 형식의 회의를 시뮬레이션하고, 마지막으로 회의록까지 작성한다.

프론트엔드는 Next.js, 백엔드는 FastAPI로 구성되어 있다.  
백엔드는 OpenAI Agents SDK, LangGraph, LangChain OpenAI를 함께 사용해 각 단계를 오케스트레이션한다.

## 무엇을 하는 프로젝트인가

이 프로젝트는 아래 5단계를 하나의 흐름으로 연결한다.

1. 연구 배경, 목적, 활용방안, 타깃 고객을 입력한다.
2. AI가 입력을 더 조사 가능한 형태로 정제한다.
3. AI가 웹 검색 기반 시장조사 보고서를 생성한다.
4. AI가 가상 고객과 전문가 에이전트를 추천하고 수정 가능하게 제공한다.
5. 에이전트들이 FGI처럼 토론하고, 그 결과를 회의록으로 정리한다.

즉, 단순 챗봇이 아니라 "리서치 브리프 작성 -> 시장 탐색 -> 페르소나 구성 -> 그룹 인터뷰 시뮬레이션 -> 문서화"까지 이어지는 실험용 리서치 워크벤치에 가깝다.

## 핵심 기능

### 1. 연구 정보 입력

- 연구 배경, 목적, 활용방안, 카테고리, 타깃 고객을 입력한다.
- 현재 프로젝트 상태는 프론트의 `sessionStorage`에 저장된다.
- 상위 단계를 수정하면 하위 결과를 초기화해 흐름 불일치를 방지한다.

### 2. 연구 정보 정제 + 시장조사

- 입력한 브리프를 AI가 더 명확한 연구 입력으로 정제한다.
- 정제된 입력을 바탕으로 시장조사 보고서를 생성한다.
- 시장조사는 OpenAI Agents SDK의 `WebSearchTool`을 사용한다.
- 검색 위치는 한국(`country = "KR"`)으로 설정되어 있다.
- 검색 결과를 종합한 뒤 주요 claim을 다시 검색해 교차검증한다.

보고서 섹션은 다음 5개로 고정되어 있다.

- 시장 개요
- 경쟁 환경
- 타깃 고객 분석
- 관련 트렌드
- 시사점

### 3. 에이전트 추천 및 편집

- 시장조사 결과를 기반으로 FGI 참여자 역할을 AI가 추천한다.
- 소비자(customer), 전문가(expert), 커스텀(custom) 타입을 지원한다.
- 소비자 에이전트는 나이, 성별, 직업, 성향, 경험, pain point, 말투까지 포함한 페르소나 구조를 가진다.
- 프론트에서 에이전트를 수정, 삭제, 추가할 수 있다.
- 소비자/전문가 페르소나는 system prompt로 다시 합성된다.

### 4. 회의 시뮬레이션

- 선택된 에이전트와 모더레이터가 FGI 형식으로 대화한다.
- 백엔드는 SSE(`text/event-stream`)로 발언을 토큰 단위 스트리밍한다.
- 회의 주제는 시작 전에 한 번 더 정제된다.
- 라운드 진행 중 다음 발언자는 대화 맥락을 보고 선택된다.
- 새 인사이트가 반복적으로 줄어들면 회의를 조기 종료한다.

### 5. 회의록 생성

- 회의 로그를 바탕으로 Markdown 회의록을 생성한다.
- 회의록 생성 시 시장 근거 보강을 위해 다시 웹 검색을 사용할 수 있다.
- 최종 결과에는 부록 형태로 실제 회의 발화록이 함께 붙는다.
- 프론트에서 복사 및 Markdown 다운로드를 지원한다.

## 사용자 흐름

### Phase 1. 연구 정보 입력

- 페이지: `frontend/src/app/(phases)/phase-1/page.tsx`
- 입력값 저장 후 다음 단계로 이동한다.

### Phase 2. 시장조사 · 딥리서치

- 페이지: `frontend/src/app/(phases)/phase-2/page.tsx`
- 먼저 연구 정보를 정제한다.
- 이어서 정제본을 기준으로 시장조사 보고서를 생성한다.
- 정제본은 사용자 수정 후 다시 보고서 생성에 사용할 수 있다.

### Phase 3. 에이전트 구성

- 페이지: `frontend/src/app/(phases)/phase-3/page.tsx`
- AI 추천 에이전트를 받아오고, 사용자가 직접 편집 가능하다.

### Phase 4. 회의 시뮬레이션

- 페이지: `frontend/src/app/(phases)/phase-4/page.tsx`
- 회의 주제를 입력하면 에이전트 대화가 실시간 스트리밍된다.

### Phase 5. 회의록 · 내보내기

- 페이지: `frontend/src/app/(phases)/phase-5/page.tsx`
- 회의 로그를 분석해 회의록을 만들고 복사/다운로드할 수 있다.

## 아키텍처

```text
frontend (Next.js)
  └─ 사용자 입력 / 단계별 UI / 상태 저장 / SSE 수신
       ↓
backend (FastAPI)
  ├─ /api/research   : 연구 정보 정제 + 시장조사
  ├─ /api/agents     : 에이전트 추천
  ├─ /api/meeting    : SSE 기반 회의 시뮬레이션
  ├─ /api/minutes    : 회의록 생성
  └─ /api/usage      : 토큰 사용량 요약
       ↓
LLM orchestration
  ├─ OpenAI Agents SDK
  ├─ WebSearchTool
  ├─ LangGraph
  └─ LangChain OpenAI
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

## 백엔드 구성

### 엔드포인트

- `POST /api/research`
  - 입력: 연구 브리프
  - 출력: 정제된 연구 정보 + 시장조사 보고서
- `POST /api/agents`
  - 입력: 브리프 + 정제본 + 시장조사 보고서
  - 출력: 추천 에이전트 목록
- `POST /api/agents/synthesize-prompt`
  - 입력: 이름, 타입, persona_profile
  - 출력: system prompt
- `POST /api/meeting`
  - 입력: 참여 에이전트, 회의 주제, 연구 맥락, 최대 라운드 수
  - 출력: SSE 스트림
- `POST /api/minutes`
  - 입력: 회의 메시지, 브리프, 참여 에이전트
  - 출력: Markdown 회의록
- `GET /api/usage`
  - 누적 토큰 사용량 요약
- `POST /api/usage/reset`
  - 사용량 기록 초기화
- `GET /api/health`
  - 헬스체크

### 주요 서비스

- `backend/services/research_service.py`
  - LangGraph 기반 시장조사 파이프라인
  - 키워드 추출 -> 병렬 검색 -> 종합 -> claim 검증 -> 연구 정보 정제
- `backend/services/agent_service.py`
  - 시장조사 결과를 바탕으로 에이전트 추천
  - 소비자 나이 범위 검증 및 재생성 로직 포함
- `backend/services/meeting_service.py`
  - LangGraph + LangChain OpenAI 기반 회의 진행
  - 토큰 스트리밍 SSE 생성
- `backend/services/minutes_service.py`
  - 회의록 생성 및 회의 발화록 부록 추가
- `backend/services/usage_tracker.py`
  - 서비스별 토큰, 추정 비용(USD/KRW) 집계

## 프론트엔드 구성

### 상태 관리

- `frontend/src/contexts/ProjectContext.tsx`
- 프로젝트 단위 상태를 저장한다.
- 브라우저 `sessionStorage` 키는 `bigmarlab_project`다.

### API 연동

- `frontend/src/lib/api.ts`
- 개발 환경에서는 기본적으로 `http://localhost:8000/api`를 직접 호출한다.
- 운영 환경에서는 `/api` 상대 경로를 사용한다.
- 시장조사 결과는 프론트에서 섹션별 출처 구조로 정규화한다.

### 초기 라우팅

- `/` 진입 시 현재 phase에 맞춰 `/phase-1` ~ `/phase-5`로 리다이렉트한다.

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
- LangChain OpenAI

## 로컬 실행

### 1. 환경 변수

백엔드 루트 또는 프로젝트 루트에서 `.env`를 읽을 수 있어야 한다.

```env
OPENAI_API_KEY=your_api_key
```

현재 코드상 필수 환경 변수는 `OPENAI_API_KEY` 하나다.

### 2. 백엔드 실행

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

기본 주소:

- `http://localhost:8000`
- 헬스체크: `http://localhost:8000/api/health`

### 3. 프론트엔드 실행

```powershell
cd frontend
npm install
npm run dev
```

기본 주소:

- `http://localhost:3000`

## API 예시

### 시장조사 요청

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

### 에이전트 추천 요청

`/api/agents`는 브리프, 정제본, 보고서를 모두 요구한다. 보통 프론트에서 이전 단계 결과를 그대로 전달한다.

### 회의 시뮬레이션 요청

`/api/meeting`은 JSON POST 이후 SSE 응답을 유지하는 형태다. 일반 REST 응답이 아니라 스트림 소비 코드가 필요하다.

## 현재 구현상 주의사항

- `backend/services/meeting_service.py`는 `langchain_openai`, `langchain_core`를 import하지만 `backend/requirements.txt`에는 명시되어 있지 않다.
  회의 기능까지 실행하려면 해당 패키지를 별도로 설치해야 할 가능성이 높다.
- 사용량 추적은 서버 프로세스 메모리 기반이라 재시작 시 초기화된다.
- 프로젝트 상태는 프론트 `sessionStorage` 기반이라 브라우저 세션이 바뀌면 사라진다.
- 실제 사용자 조사 결과가 아니라 AI 시뮬레이션 결과물이므로, 의사결정 전 검증이 필요하다.
- 웹 검색 위치가 한국으로 고정되어 있어 글로벌 시장 탐색에는 그대로 맞지 않을 수 있다.

## 파일 빠른 참조

- `backend/main.py`
- `backend/models/schemas.py`
- `backend/routers/research.py`
- `backend/routers/agents.py`
- `backend/routers/meeting.py`
- `backend/routers/minutes.py`
- `backend/services/research_service.py`
- `backend/services/agent_service.py`
- `backend/services/meeting_service.py`
- `backend/services/minutes_service.py`
- `frontend/src/contexts/ProjectContext.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/app/(phases)/phase-1/page.tsx`
- `frontend/src/app/(phases)/phase-2/page.tsx`
- `frontend/src/app/(phases)/phase-3/page.tsx`
- `frontend/src/app/(phases)/phase-4/page.tsx`
- `frontend/src/app/(phases)/phase-5/page.tsx`

## 한 줄 요약

이 프로젝트는 정성조사 기획을 위해 연구 브리프 작성부터 시장조사, 가상 참여자 구성, FGI 시뮬레이션, 회의록 생성까지를 하나로 묶은 멀티 에이전트 리서치 애플리케이션이다.
