# Plan 0001 — BDML-FGI 아카이브 + Ditto 프로젝트 부트스트랩

- **상태:** Active (작성일 2026-05-07)
- **종류:** chore + feat (대규모 리포지터리 재구조화)
- **브랜치:** `chore/archive-bdml-bootstrap-ditto` (Phase 0~1) → 이후 기능 단위 brach 분기
- **PR 분할:** Phase 별 1 PR. Phase 0/1은 합쳐서 1 PR로 가능 (코드 변경 없음, 이동 + 문서만).

## Open Questions 결정 사항 (2026-05-07)

| Q | 결정 |
|---|---|
| **Q1 — Ditto 브랜드 컬러** | 루트 `DESIGN.md` 의 토큰 채택 → **Indigo (`#4F46E5`) + Violet (`#8B5CF6`) + Pretendard**. BDML Navy/Cyan 과 명확히 구분되는 fresh 브랜드. |
| **Q2 — 시각화 라이브러리** | **Recharts** (게이지/레이더/산점도/막대 모두 커버, React 친화). |
| **Q4 — Twin-2K-500 v2 적재 인원** | **30명으로 시작** (현재 한국어 응답 모집 계획), 이후 확장. `seed_twin_v2.py --limit 30` 기본값. |
| **Q6 — 리포 이름** | **Phase 6 시점에 GitHub 리포 `Ditto` 로 rename**. README 배지/링크 갱신 포함. |
| Q3 | 미결정 — Phase 5 진입 시점에 결정 (V5 CF 자극 세트 설계 방식). |
| Q5 | 미결정 — v1.1로 미루기 (워크스페이스 모델). |
| Q7 | 미결정 — Phase 6 정리 시점에 결정 (`panels`/`panel_memories` 통합 여부). |

---

## 1. 배경 & 목표

현재 리포(`HYU_BDML`)는 **빅데이터마케팅랩(BDML) 5-Phase FGI 시뮬레이션 + Lab Twin-2K-500 1:1 메신저** 두 모듈로 굳어져 있다. 사용자가 새로 추진하는 **Ditto** 는 다음 차이가 있다.

| 축 | 현재 BDML | 신규 Ditto |
|---|---|---|
| **포지셔닝** | "정성조사 시뮬레이터" (단발 회의 자동화) | "**리서치 플랫폼**" (지속적 에이전트 성장) |
| **사용자** | 한양대 BDML 연구원 + 데모용 | 스타트업/기업의 리서처·PO |
| **에이전트 재료** | 자체 패널 500명(`fgi500`) + Twin-2K-500 50명(`twin2k500`) | 사용자 자체 설문/인터뷰 응답 + Twin-2K-500 한국어 로컬라이즈 |
| **에이전트 수명** | 회의 1회 종료 후 폐기 | **장기 메모리 + 대화 누적 기반 성장** |
| **핵심 산출물** | 회의록(Markdown) | **인사이트** + **에이전트 성능 평가 대시보드(Identity / Logic 5지표)** |
| **MVP 범위** | 5-Phase 전체 자동화 | **에이전트 생성(Twin-2K-500) + FGI + 평가 대시보드 V1/V4/V5** |
| **사용자 개입** | Phase 4 회의는 관전만 | FGI에 사용자가 토론 참여 가능 |

목표는 **현 자산을 깨끗하게 박제(archive/) 하고, 재사용 가능한 모듈만 선별 이식하면서 새 디렉터리 트리를 시작**하는 것. 한 번에 다 이식하지 않고, **MVP에 필요한 최소 모듈만** 포팅하여 진입 비용을 줄인다.

### 비범위 (이번 plan)

- 신규 코드 작성 (Phase 2 이후로 미룸).
- 데이터 마이그레이션 (Cloud SQL 패널 데이터는 그대로 유지, 신규 Ditto 스키마 도입 후 별도 plan).
- 배포 파이프라인 변경 (`.github/workflows/deploy.yml`은 archive와 함께 일단 박제하고, Ditto 첫 배포 plan에서 새로 작성).

---

## 2. 자산 인벤토리 — 재사용 가능 vs 폐기

### 2.1 재사용 가능 (Ditto에서 그대로 또는 약간 변형)

| 자산 | 위치 | Ditto 매핑 |
|---|---|---|
| Twin-2K-500 적재 스크립트 | `backend/scripts/seed_twin.py`, `seed_twin_persona_full.py`, `migrate_add_source.py` | **MVP 1순위.** Raw Data Layer의 베이스. 234문항 한국어 v1.1 기반으로 확장 |
| Twin scratch / memory builder | `backend/rag/twin_scratch_builder.py`, `twin_memory_builder.py` | **6-Lens 카테고리 분할로 재설계** (현 ~32 카테고리 → L1~L6 + 정성 6개 그룹) |
| 임베딩 파이프라인 | `backend/rag/embedder.py` | 그대로. (캐시 `embedding_cache.json`은 archive에 보존) |
| 패널 선택기 (다양성 + 관련성) | `backend/rag/panel_selector.py` | **FGI 패널 그룹 자동 선정**에 재활용 |
| RAG 검색 | `backend/rag/retriever.py` | 1:1 대화 / FGI 발화 컨텍스트에 재활용 |
| 회의 시뮬레이션 (LangGraph) | `backend/services/meeting_service.py` | **FGI 모듈 베이스.** 사용자 개입 hook 추가 필요 |
| 1:1 채팅 SSE | `backend/services/lab_service.py`, `routers/lab.py` | **Ditto 1:1 대화 모듈 베이스** |
| 인용 + 신뢰도 시각화 | `backend/services/lab_citation_service.py`, `frontend/src/components/lab/CitationToggle.tsx` | **평가 대시보드 V1(응답 동기화율) 시각화에 재활용** |
| Faithfulness 평가 (offline) | `backend/scripts/eval_lab_faithfulness.py`, `seed_lab_probe_questions.py`, `services/lab_judge_service.py`, `prompts/lab_judge.py`, `frontend/src/components/lab/FaithfulnessBar.tsx` | **V1 응답 동기화율 + V4 인격 자연스러움**의 토대. 평가 카테고리 → 6-Lens 매핑으로 갈아끼움 |
| 인증 (JWT + bcrypt + httpOnly 쿠키) | `backend/routers/auth.py`, `services/auth_service.py`, `frontend/src/contexts/AuthContext.tsx`, `components/auth/AuthGuard.tsx` | 그대로. SaaS 다중 워크스페이스 추가는 v1.1 |
| 토큰 사용량 추적 | `backend/services/usage_tracker.py`, `routers/usage.py` | 그대로. 평가 비용 추적에 유용 |
| SSE/NDJSON 프론트엔드 클라이언트 | `frontend/src/lib/api.ts` | 그대로. Ditto 신규 엔드포인트만 추가 |
| 프로젝트 컨텍스트 (sessionStorage) | `frontend/src/contexts/ProjectContext.tsx` | **"리서치 프로젝트" 단위로 재정의**. 단계가 아닌 자산(Survey/Agents/Conversations) 컨테이너 |
| 디자인 토큰 (Navy/Cyan + IBM Plex Sans KR) | `tailwind.config.ts`, `frontend/src/styles/globals.css` | **폐기.** Ditto 는 루트 `DESIGN.md` 토큰 (Indigo `#4F46E5` + Violet `#8B5CF6` + Pretendard, 8px 라운드)으로 신규 설정 |
| Dockerfile (백/프론트) | `backend/Dockerfile`, `frontend/Dockerfile` | 그대로 (Ditto 배포 plan에서 검토) |

### 2.2 폐기 (archive로 이동, Ditto에는 미이식)

| 자산 | 폐기 사유 |
|---|---|
| 5-Phase 위저드 페이지 (`frontend/src/app/(phases)/*`) | Ditto는 "Phase" 모델 폐기, "프로젝트 자산"(Survey/Agents/Conversations) 모델 채택 |
| 시장조사 모듈 (`backend/services/research_*.py`, `naver_search_service.py`, `openai_web_search_service.py`, `prompts/research.py`) | Ditto 핵심 가치(에이전트 성장)와 직접 관련 없음. 추후 별도 모듈로 부활 가능 |
| FGI 패널 500명 (`source='fgi500'`) | Ditto 데모는 Twin-2K-500 한국어 로컬라이즈로 시작. CSV 원본도 별도 백업에만 보관 |
| 회의록 모듈 (`backend/services/minutes_service.py`, `routers/minutes.py`, `prompts/minutes.py`, `frontend/src/app/(phases)/minutes/page.tsx`) | Ditto는 "인사이트 도출" 단위 산출물 (단순 회의록 X). 후속 plan에서 재설계 |
| 에이전트 추천 (LLM 모드) | `backend/services/agent_service.py`, `prompts/agent_recommend.py` | Ditto는 데이터(설문/Twin) 기반만 지원. 추측형 LLM 페르소나 폐기 |
| `RAG/` 폴더 (PoC 잔재) | 이미 `backend/rag/`로 통합됨. 중복 코드 |
| `backend/services/meeting_service_backup.py`, `backend/test_tool.py` | 데드 코드 |
| `scripts/playwright-audit/` | BDML UI 감사 1회성. Ditto에서 재구성 시 별도 plan |
| 기존 `docs/` (PRD, ARCHITECTURE, DATA_MODEL, api-spec, adr/0001~0006, README, ui-audit) | BDML 명세. **참조용으로 archive에 통째 보존**, Ditto 명세는 새로 작성 |

### 2.3 데이터 자산 (DB / 외부)

| 자산 | 처리 |
|---|---|
| Cloud SQL `panels` / `panel_memories` (`source='fgi500'` 500명 + `source='twin2k500'` 50명) | **DB는 건드리지 않는다.** Ditto는 Twin 50명을 그대로 재사용하되, 6-Lens 메모리 빌더 v2가 가동되면 별도 `source='ditto_twin_v2'`로 신규 적재 (기존 데이터는 회귀 비교용으로 유지) |
| Cloud SQL `users`, `refresh_tokens`, `activity_logs` | 그대로. Ditto에서 호환 |
| Cloud SQL `projects`, `project_edits` | **Ditto 스키마와 충돌**. Ditto 첫 번째 마이그레이션 plan에서 `projects_v1_bdml`로 rename 후 신규 `projects` 도입 |
| `backend/rag/embedding_cache.json` (~10MB) | git 미추적. archive 폴더에는 포함 안함 (`.gitignore` 유지). 로컬 파일은 그대로 둠 |
| `backend/.cache/twin_sample.jsonl` | 미추적. 그대로 둠 |
| `backend/raw/` (CSV) | 미추적. Ditto에서 사용 안함 |
| `backend/app.db` (로컬 SQLite) | 미추적. 신규 dev에서는 새 db 파일로 시작 |

---

## 3. Ditto 신규 아키텍처 개요 (요약)

상세는 `docs/ARCHITECTURE.md` (Phase 1에서 작성)에서 정의. 여기서는 마이그레이션 의사결정의 근거가 되는 핵심 형태만 적는다.

### 3.1 도메인 모델

```
Workspace (조직 단위, v1.1)
  └─ User (워크스페이스 멤버)
       └─ ResearchProject (Ditto 프로젝트)
              ├─ Survey (질문 세트 + 배포 링크 + 응답)
              │     └─ Response (응답자별 raw answers)
              ├─ Agent (Response 기반 생성, 또는 Twin 베이스)
              │     ├─ PersonaLayer (수치 + 원문 하이브리드 프롬프트)
              │     ├─ Memory (대화 누적 — 성장 메커니즘)
              │     └─ EvaluationSnapshot (V1~V5 점수 시계열)
              ├─ Conversation (1:1 대화 세션)
              │     └─ Turn (사용자/에이전트 메시지)
              └─ FGISession (다자 회의)
                    └─ Turn (모더레이터/에이전트/사용자 발언)
```

### 3.2 핵심 모듈

| 영역 | 핵심 디렉터리 | 비고 |
|---|---|---|
| 6-Lens 데이터 그룹화 | `backend/lenses/{l1_economic,l2_decision,l3_motivation,l4_social,l5_value,l6_time,qualitative}.py` | Twin-2K-500 234문항 → L1~L6 매핑 테이블 + 카테고리별 영문/한국어 라벨 |
| Scoring Engine | `backend/scoring/` | 역채점, 경제 수치화(CE, 연환산율), 능력치 합산. 산출 결과 = `Agent.persona_params` JSONB |
| Persona Builder v2 | `backend/persona/` (← `backend/services/persona_builder.py` 진화) | 수치 가이드 + 원문 가이드 합성, 시스템 프롬프트 조립 |
| Conversation Engine | `backend/conversation/` (← `lab_service.py` 진화) | 1:1 대화 SSE + 메모리 업데이트 hook |
| FGI Engine | `backend/fgi/` (← `meeting_service.py` 진화) | LangGraph 상태머신 + **사용자 개입 hook** (FocusAgent 참고) |
| Evaluation Engine | `backend/evaluation/` | V1 (cosine sim), V2 (multi-LLM judge), V3 (페르소나 간 거리), V4 (LLM judge), V5 (CF Δ) |
| Dashboard API | `backend/routers/dashboard.py` | 평가 결과 → 레이더/산점도/게이지 시각화 데이터 |
| Survey Module (v1.1) | `backend/survey/` | 질문 생성 (LLM) + 배포 링크 + 응답 수집. **MVP 단계는 Twin-2K-500 응답을 가짜 Survey로 주입하여 다운스트림만 검증** |

### 3.3 외부 의존성 변동

| 의존성 | BDML 사용 | Ditto 사용 |
|---|---|---|
| OpenAI `gpt-4o` | 모든 LLM | 동일 |
| OpenAI `text-embedding-3-small` | 임베딩 | 동일 |
| **Anthropic `claude-3.5-sonnet`** | 미사용 | **신규** (Phase 5). V2 모델 신뢰도 측정용 멀티 LLM 비교 |
| LangGraph + LangChain | 회의 상태머신 | 동일 (FGI에서 계속) |
| **Recharts** | 미사용 | **신규** (Phase 3~5). 게이지/레이더/산점도/막대 시각화 (Q2 결정) |
| **Pretendard 폰트** | 미사용 (BDML 은 IBM Plex Sans KR) | **신규.** `frontend/public/fonts/` 또는 `cdn.jsdelivr.net/gh/orioncactus/pretendard/...` 로드 |
| Naver Search | 시장조사 | 폐기 |
| OpenAI Web Search | 시장조사 | 폐기 |

---

## 4. 마이그레이션 단계

총 7개 Phase. 각 Phase = 1 PR (Phase 0/1은 합칠 수 있음).

### Phase 0 — Archive (코드 변경 0)

**브랜치:** `chore/archive-bdml-bootstrap-ditto`

#### 0.1 `archive/bdml-fgi/` 생성 + 이동

```
archive/bdml-fgi/
├── backend/         (현 backend/ 통째로 git mv)
├── frontend/        (현 frontend/ 통째로 git mv)
├── RAG/             (현 RAG/ 통째로 git mv)
├── scripts/         (현 scripts/ 통째로 git mv)
├── docs/            (현 docs/의 PRD/ARCHITECTURE/DATA_MODEL/api-spec/README/ui-audit + adr/* 통째로 git mv)
├── README.md        (현 README.md 그대로 git mv → BDML 소개 보존)
├── DESIGN.md        (현 DESIGN.md 그대로 git mv)
├── CLAUDE.md        (현 CLAUDE.md 그대로 git mv)
└── .cursorrules     (현 .cursorrules 그대로 git mv)
```

`docs/plans/active/0001-archive-and-bootstrap-ditto.md` (이 문서) 와 `docs/plans/completed/`는 **archive에 들어가지 않는다** — Ditto의 첫 plan이므로 신규 docs 트리 안에 남는다.

#### 0.2 `git mv` 명령 (Windows PowerShell)

```powershell
# 폴더 신설
New-Item -ItemType Directory archive\bdml-fgi -Force | Out-Null

# 코드 이동
git mv backend  archive\bdml-fgi\backend
git mv frontend archive\bdml-fgi\frontend
git mv RAG      archive\bdml-fgi\RAG
git mv scripts  archive\bdml-fgi\scripts

# docs는 plans/만 남기고 모두 이동
New-Item -ItemType Directory archive\bdml-fgi\docs -Force | Out-Null
git mv docs\PRD.md           archive\bdml-fgi\docs\PRD.md
git mv docs\ARCHITECTURE.md  archive\bdml-fgi\docs\ARCHITECTURE.md
git mv docs\DATA_MODEL.md    archive\bdml-fgi\docs\DATA_MODEL.md
git mv docs\api-spec.md      archive\bdml-fgi\docs\api-spec.md
git mv docs\README.md        archive\bdml-fgi\docs\README.md
git mv docs\ui-audit.md      archive\bdml-fgi\docs\ui-audit.md
git mv docs\adr              archive\bdml-fgi\docs\adr

# 루트 메타파일 이동 (Ditto 버전으로 새로 작성할 것이므로)
git mv README.md     archive\bdml-fgi\README.md
git mv CLAUDE.md     archive\bdml-fgi\CLAUDE.md
git mv .cursorrules  archive\bdml-fgi\.cursorrules

# DESIGN.md 는 이동하지 않는다 — 루트 DESIGN.md 토큰을 Ditto 가 그대로 채택 (Q1 결정).
# BDML 도 같은 토큰을 참조했었으므로 archive 에 별도 사본 불필요. 변경이 필요해지면 Phase 1 에서 추가만.
```

#### 0.3 archive README

`archive/bdml-fgi/README.md` (BDML 원본을 그대로 유지). 추가로 archive 루트에 안내 작성.

```
archive/
└── README.md   (← Phase 0에서 신규 작성. "이 폴더는 동결된 BDML-FGI 코드, 참조용. 활성 개발은 루트 디렉터리에서.")
└── bdml-fgi/
    ├── README.md (BDML 원본)
    └── ...
```

#### 0.4 `.gitignore` 정리

루트 `.gitignore`에서 BDML 한정 항목은 archive 경로로 갱신:

```diff
- backend/raw/
- backend/personas/
- backend/rag/embedding_cache.json
- backend/.cache/
- backend/rag_test_results.json
+ archive/bdml-fgi/backend/raw/
+ archive/bdml-fgi/backend/personas/
+ archive/bdml-fgi/backend/rag/embedding_cache.json
+ archive/bdml-fgi/backend/.cache/
+ archive/bdml-fgi/backend/rag_test_results.json
+ # Ditto 신규 경로 ignore (Phase 1에서 추가될 예정)
```

`.gitignore` 자체는 archive에 넣지 않고 루트에 둔다 (앞으로도 작동해야 함).

#### 0.5 검증

- [ ] `git status`에서 모든 이동이 rename 으로 인식되는지 확인 (R 표시).
- [ ] `archive/bdml-fgi/backend/main.py` 가 정상 read 되는지 확인.
- [ ] 루트에 `docs/plans/`, `archive/`, `.git/`, `.github/`, `.gitignore` 만 남는지 확인.

### Phase 1 — Ditto SSOT 문서 부트스트랩 (코드 변경 0)

#### 1.1 신규 루트 메타파일 작성

| 파일 | 내용 |
|---|---|
| `README.md` | Ditto 한 줄 소개, MVP 범위, 빠른 시작, archive 안내 |
| `CLAUDE.md` | Ditto 컨벤션 (현 BDML CLAUDE.md를 토대로, 5-Phase 흐름·Lab 분리 섹션 제거하고 6-Lens·평가 대시보드·Survey/Agent/Conversation/FGI 4 모듈 섹션 신설) |
| `.cursorrules` | 그대로 복사 + Ditto 디렉터리 맵으로 갱신 |
| `DESIGN.md` | **루트 위치 그대로 유지.** 컴포넌트 primitives 섹션에 Ditto 신규 컴포넌트(`Gauge`, `RadarChart`, `ScoreBadge`, `ChatBubble`, `FGIInterventionInput`) 규칙 추가만. 토큰(Indigo/Violet/Pretendard/8px) 변경 없음. |

#### 1.2 신규 `docs/` 트리

```
docs/
├── PRD.md                 # Ditto 제품 요구사항 (사용자가 제공한 §1~5를 정제하여 옮김)
├── ARCHITECTURE.md        # §3 정리 + 모듈 경계
├── DATA_MODEL.md          # §3.1 도메인 모델 + DB 스키마 초안
├── api-spec.md            # 신규 엔드포인트 명세 (회의/대화/평가)
├── EVAL_SPEC.md           # V1~V5 측정 정의·공식·자극 세트 명세 (신규, Ditto 핵심 문서)
├── 6-LENS_MAPPING.md      # Twin-2K-500 234문항 → L1~L6 매핑 테이블 (PDF 분석 결과)
├── adr/
│   ├── 0001-archive-bdml-bootstrap-ditto.md   # 이 plan의 ADR 버전 (요약)
│   ├── 0002-six-lens-categorization.md        # 6-Lens 채택 이유
│   ├── 0003-hybrid-persona-prompt.md          # 수치+원문 하이브리드 프롬프트
│   └── 0004-evaluation-v1-to-v5.md            # 평가 5지표 채택
└── plans/
    ├── active/
    │   └── 0001-archive-and-bootstrap-ditto.md   # 이 문서
    └── completed/
```

각 ADR은 ✅ Accepted 상태로 작성 (이미 사용자가 §4에서 결정한 내용이므로). 단, **`6-LENS_MAPPING.md` 는 Twin-2K-500 한국어 PDF 분석 후 채워지므로 Phase 2 입구에서 작성**한다 (Phase 1에서는 헤더 + TODO만).

#### 1.3 검증

- [ ] `docs/PRD.md` 읽기만으로 신규 컨트리뷰터가 Ditto 컨셉을 이해 가능.
- [ ] 모든 ADR 파일이 cross-reference 깨지지 않게 링크.

### Phase 2 — 신규 코드 셸 + 6-Lens 데이터 구조화 (MVP-1)

**브랜치:** `feat/ditto-mvp-1-six-lens`

#### 2.1 신규 `backend/`, `frontend/` 셸

| 행위 | 출처 → 대상 |
|---|---|
| FastAPI 셸 | `archive/bdml-fgi/backend/main.py` 의 lifespan/CORS 골격 → 신규 `backend/main.py` (라우터 등록은 빈 상태) |
| DB 셸 | `archive/bdml-fgi/backend/database.py` → 신규 `backend/database.py` (테이블 정의는 비움, 신규 모델만) |
| 임베더 | `archive/bdml-fgi/backend/rag/embedder.py` → 신규 `backend/embedding/embedder.py` |
| Twin 적재기 | `archive/bdml-fgi/backend/scripts/seed_twin*.py` → 신규 `backend/scripts/seed_twin_v2.py` (다음 단계에서 6-Lens 빌더 호출하도록 개조) |
| 인증 | `archive/bdml-fgi/backend/routers/auth.py`, `services/auth_service.py` → 신규 동일 경로 |
| Next.js 셸 | `archive/bdml-fgi/frontend/{package.json, tsconfig, tailwind.config, next.config, postcss.config, src/app/layout.tsx, src/styles/globals.css}` → 신규 frontend |
| 디자인 토큰 적용 | `DESIGN.md` v2 토큰 → `tailwind.config.ts` |

#### 2.2 6-Lens 모듈 신규 작성

```
backend/
├── lenses/
│   ├── __init__.py
│   ├── mapping.py            # 234문항 → L1~L6 + qualitative 그룹 매핑 (docs/6-LENS_MAPPING.md 의 코드화)
│   ├── l1_economic.py        # 위험/손실 회피, 심적 회계, 소비 습관
│   ├── l2_decision.py        # 극대화 성향, 인지 욕구, CRT
│   ├── l3_motivation.py      # 조절초점, 자기지향/타인지향 가치, 미니멀리즘 (L3 + L5 통합 가능, ADR 0002에서 결정)
│   ├── l4_social.py          # 자기 감시, 집단주의, 공감도, 정책 찬반
│   ├── l6_time.py            # 할인율, 현재 편향, 성실성
│   └── qualitative.py        # '실제 자기' 서술문 + 독재자 게임 사고
├── scoring/
│   ├── __init__.py
│   ├── reverse_score.py      # 역채점 변환 (max+1-x)
│   ├── economic.py           # CE 계산, 연환산율 (L1, L6)
│   └── ability.py            # 금융이해/수리 합산 (L2)
└── persona/
    ├── __init__.py
    ├── builder.py            # PersonaParams + 원문 → 시스템 프롬프트 조립
    └── prompts/
        └── persona_system.py # 하이브리드 프롬프트 템플릿
```

#### 2.3 데이터 모델 신설

`docs/DATA_MODEL.md` 따라 SQLAlchemy 모델 작성. 신규 테이블:

- `agents` (id, project_id, source_type='twin'|'survey', persona_params JSONB, persona_full_prompt TEXT, created_at)
- `agent_memories` (agent_id, source='base'|'conversation'|'fgi', text, embedding vector(1536), created_at)
- `evaluation_snapshots` (agent_id, version, identity_stats JSONB, logic_stats JSONB, evaluated_at)

기존 `panels` / `panel_memories` 테이블은 archive backend 가 아직 참조 가능하므로 손대지 않는다 (Phase 6 정리 시점에 결정).

#### 2.4 검증

- [ ] `python -m scripts.seed_twin_v2 --limit 3` 으로 트윈 3명을 신규 `agents` 테이블에 적재 성공 (smoke test).
- [ ] `python -m scripts.seed_twin_v2 --limit 30` 으로 본격 30명 적재 (Q4 결정 — 한국어 응답 모집 계획에 맞춤). 추후 확장 시 `--limit` 만 늘리면 됨.
- [ ] 적재된 agent의 `persona_params` 가 Q3.4-3.6 형식(`{l1: {risk_aversion: 0.9, ...}, ...}`)으로 들어감.
- [ ] `persona/builder.py.build()` 가 시스템 프롬프트 ≤ 8k tokens 으로 압축됨 (Toubia 풀-프롬프트 42k token 대비 5배 압축 — Lost-in-the-middle 회피).

### Phase 3 — 1:1 대화 + 평가 V1 (MVP-2)

**브랜치:** `feat/ditto-mvp-2-chat-eval-v1`

#### 3.1 1:1 대화 모듈 이식

`archive/bdml-fgi/backend/services/lab_service.py` + `prompts/twin_utterance.py` → 신규 `backend/conversation/`. 차이:

- Toubia 풀-프롬프트 대신 Phase 2 의 `persona/builder.py` 결과 주입.
- `archive/bdml-fgi/backend/services/lab_citation_service.py` 그대로 가져와 인용 마커 처리.
- 대화 종료 시 메모리 업데이트 hook 호출 (요약 → `agent_memories` source='conversation').

#### 3.2 평가 엔진 — V1 응답 동기화율

`archive/bdml-fgi/backend/scripts/eval_lab_faithfulness.py` + `seed_lab_probe_questions.py` 의 구조 유지하되:

- Probe 질문 = Twin-2K-500 원본 234문항 자체 (V1 정의: "원문과의 의미론적 유사도").
- 평가 = `Agent` 의 답변 임베딩 vs 원본 응답 임베딩 cosine similarity.
- 결과 → `EvaluationSnapshot.identity_stats.sync`.

#### 3.3 대시보드 (최소)

`frontend/src/app/dashboard/agents/[id]/page.tsx` — 게이지 차트 1개 (V1 점수). 시각화 라이브러리 ❓ Open Question Q2.

#### 3.4 검증

- [ ] 트윈 1명에게 원문 질문 5개 던져 평균 cosine sim 산출.
- [ ] 점수가 `EvaluationSnapshot` 테이블에 저장되고 대시보드에서 게이지로 표시됨.

### Phase 4 — FGI + 평가 V4 인격 자연스러움 (MVP-3)

**브랜치:** `feat/ditto-mvp-3-fgi-eval-v4`

#### 4.1 FGI 모듈 이식 + 사용자 개입

`archive/bdml-fgi/backend/services/meeting_service.py` (LangGraph) → 신규 `backend/fgi/engine.py`. 신규 기능:

- 사용자 발언 hook (FocusAgent 참고). 모더레이터 다음 턴에 사용자 입력 대기 → 입력 시 turn에 삽입.
- SSE 이벤트에 `type: "user_turn_required"` 추가.
- FGI 종료 시 메모리 업데이트 hook (`agent_memories` source='fgi').

#### 4.2 평가 엔진 — V4 인격 자연스러움

`archive/bdml-fgi/backend/services/lab_judge_service.py` + `prompts/lab_judge.py` 그대로. Judge 프롬프트는 페르소나 프로필 + 답변 → {natural, neutral, mechanical} 채점. 점수 → `EvaluationSnapshot.logic_stats.humanity`.

#### 4.3 대시보드 (확장)

레이더 차트 추가 (현재 V1, V4 두 축. V5 까지 채워지면 5축).

#### 4.4 검증

- [ ] 3명 에이전트로 FGI 1회 진행 + 사용자 1회 개입 발언 정상.
- [ ] FGI 후 V4 점수 산출 + 대시보드 레이더 갱신.

### Phase 5 — 평가 V2 / V3 / V5 + 대시보드 완성 (MVP-4)

**브랜치:** `feat/ditto-mvp-4-eval-v2-v3-v5`

| 지표 | 구현 |
|---|---|
| **V2 모델 신뢰도** | Anthropic Claude SDK 추가. `backend/evaluation/model_stability.py` — 동일 페르소나 + 동일 질문을 GPT-4o, Claude-3.5에 던져 답변 cosine sim |
| **V3 페르소나 독립성** | `backend/evaluation/diversity.py` — 모든 에이전트 답변 임베딩 평균, 페르소나 간 평균 거리 (mode collapse 검출) |
| **V5 상황 대응 일관성** | `backend/evaluation/counterfactual.py` — `docs/EVAL_SPEC.md` 의 CF 자극 세트로 답변 → 원문 답변 대비 벡터 Δ. 민감도 높은 페르소나(L1 위험 회피 高)는 큰 Δ 가 정상 |

CF 자극 세트는 ❓ Open Question Q3 (수작업 설계 vs LLM 생성).

`docs/EVAL_SPEC.md` 의 JSON 스키마 그대로 구현:

```json
{
  "persona_id": "...",
  "identity_stats": { "sync": 0.88, "stability": 0.82, "distinct": 2.8 },
  "logic_stats": { "humanity": 4.2, "reasoning_delta": 0.15 },
  "verdict": "Verified (S3 Entry)"
}
```

대시보드 5축 레이더 + 산점도 (V3 페르소나 분포) + 게이지 (V1) + 막대 (V4 카테고리별).

### Phase 6 — Survey 모듈 + 정리 + 리포 rename (v1.0 출시)

**브랜치:** `feat/ditto-survey-module` + `chore/cleanup-archive-deps` + `chore/rename-repo-to-ditto`

- Survey 질문 생성 (LLM) + 배포 링크 + 응답 수집 (`backend/survey/`).
- Survey 응답 → 6-Lens 매핑 → `agents` 테이블 적재 파이프라인.
- `archive/bdml-fgi/` 의존 가능성 재점검. 만약 archive 의 코드를 신규 코드가 import 한 흔적이 있으면 제거.
- 배포 파이프라인 (`.github/workflows/deploy.yml`) 신규 작성. archive 의 deploy.yml 은 비활성화.
- **GitHub 리포 rename: `HYU_BDML` → `Ditto`** (Q6 결정).
  - `gh repo rename Ditto` 또는 GitHub Settings UI.
  - `README.md` 의 GitHub Actions 배지 URL `hjo0225/interactive-multiagent` → 새 리포 경로로 갱신.
  - 로컬 origin URL 업데이트: `git remote set-url origin <new-url>`.
  - GitHub 자동 redirect 가 6개월 유지되지만, 직접 링크 갱신 권장.
  - Cloud Run 서비스 이름·GCP 프로젝트는 그대로 (rename 비용/리스크 큼).

---

## 5. 신규 디렉터리 트리 (Phase 6 종료 시 형태)

```
HYU_BDML/                      # repo 이름은 그대로. 후속 plan에서 GitHub 리포명 변경 검토
├── archive/
│   └── bdml-fgi/              # ← 동결, read-only 참조용
│       ├── README.md
│       ├── CLAUDE.md
│       ├── DESIGN.md
│       ├── .cursorrules
│       ├── backend/
│       ├── frontend/
│       ├── RAG/
│       ├── scripts/
│       └── docs/
├── backend/                   # Ditto FastAPI
│   ├── main.py
│   ├── database.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── agents.py          # 에이전트 CRUD + 생성 트리거
│   │   ├── conversation.py    # 1:1 대화 SSE
│   │   ├── fgi.py             # FGI 다자 회의 SSE (사용자 개입 hook)
│   │   ├── evaluation.py      # 평가 트리거 + 결과 조회
│   │   ├── dashboard.py       # 대시보드 데이터 API
│   │   ├── survey.py          # (Phase 6) 질문 생성/배포/응답
│   │   └── usage.py
│   ├── lenses/                # 6-Lens 매핑 + 카테고리별 추출
│   ├── scoring/               # 정량 지표 (역채점, CE, 능력치)
│   ├── persona/               # 하이브리드 프롬프트 빌더
│   ├── conversation/          # 1:1 대화 엔진 (← lab_service 진화)
│   ├── fgi/                   # FGI 엔진 (← meeting_service 진화)
│   ├── evaluation/            # V1~V5 평가 엔진
│   ├── embedding/             # 임베더 + 캐시
│   ├── prompts/               # 모든 LLM 프롬프트
│   ├── services/              # 인증/사용량 등 횡단 서비스
│   ├── scripts/
│   │   ├── seed_twin_v2.py    # Twin-2K-500 한국어 → agents 적재
│   │   ├── eval_run.py        # V1~V5 일괄 실행
│   │   └── ...
│   ├── migrations/            # Alembic
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  # Ditto Next.js
│   └── src/
│       ├── app/
│       │   ├── page.tsx                          # 랜딩
│       │   ├── login/, register/
│       │   ├── dashboard/                        # 프로젝트 목록
│       │   ├── projects/[id]/
│       │   │   ├── page.tsx                      # 프로젝트 개요
│       │   │   ├── agents/page.tsx               # 에이전트 목록
│       │   │   ├── agents/[agentId]/page.tsx     # 에이전트 상세 + 평가 대시보드
│       │   │   ├── chat/[agentId]/page.tsx       # 1:1 대화
│       │   │   ├── fgi/[sessionId]/page.tsx      # FGI 회의실
│       │   │   └── survey/page.tsx               # (Phase 6)
│       ├── components/
│       │   ├── auth/
│       │   ├── layout/
│       │   ├── chat/                             # 메신저 UI
│       │   ├── fgi/                              # 회의실 UI + 개입 입력창
│       │   └── dashboard/                        # 게이지/레이더/산점도/막대 차트 컴포넌트
│       ├── contexts/
│       │   ├── AuthContext.tsx
│       │   └── ProjectContext.tsx                # 프로젝트 자산 컨테이너 (sessionStorage)
│       ├── lib/
│       │   ├── api.ts                            # SSE/NDJSON
│       │   ├── types.ts                          # backend Pydantic 미러
│       │   └── eval.ts                           # 평가 점수 → 색/배지 헬퍼
│       └── styles/globals.css
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── api-spec.md
│   ├── EVAL_SPEC.md
│   ├── 6-LENS_MAPPING.md
│   ├── adr/
│   └── plans/
├── .github/workflows/         # Phase 6에서 신규 작성
├── .gitignore
├── .cursorrules
├── CLAUDE.md
├── DESIGN.md
└── README.md
```

---

## 6. 마일스톤 & 일정 (가이드, 1인 풀타임 기준)

| Phase | 산출물 | 기간 |
|---|---|---|
| 0 + 1 | 아카이브 + 신규 SSOT 문서 7종 + ADR 4종 | 2~3일 |
| 2 | 신규 코드 셸 + 6-Lens + 페르소나 빌더 + Twin v2 적재 | 1~2주 |
| 3 | 1:1 대화 + V1 평가 + 게이지 대시보드 | 1주 |
| 4 | FGI + 사용자 개입 + V4 평가 + 레이더 대시보드 | 2주 |
| 5 | V2/V3/V5 + 대시보드 완성 + EVAL_SPEC 자극 세트 확정 | 2주 |
| 6 | Survey 모듈 + 배포 + 정리 | 2주 |
| **합계** | **약 8~10주 (스프린트 7회)** | |

각 Phase 종료 시 plan 파일을 `completed/`로 이동.

---

## 7. 리스크 & 미결정 사항

### 7.1 리스크

| ID | 리스크 | 완화 |
|---|---|---|
| R1 | Twin-2K-500 한국어 PDF (`Twin2K500_KR_Localized_v1_1.pdf`) 가 234문항 전부 커버하지 않을 가능성 | Phase 1 입구에서 PDF 전체 추출 → `docs/6-LENS_MAPPING.md` 작성 시 빈 칸 식별, 누락 시 영문 fallback |
| R2 | V2 (Claude API) 비용 — 에이전트 1명 평가에 GPT-4o + Claude 양쪽 호출 | Phase 5 진입 시 비용 견적 → 무료 평가는 V1/V4만, V2/V5는 사용자 명시 트리거 |
| R3 | 사용자 개입 FGI에서 LangGraph 상태 일시 정지 패턴 | `meeting_service.py` 의 LangGraph 노드를 yield/resume 가능 구조로 분해 (Phase 4에서 spike) |
| R4 | 6-Lens 분류가 234문항을 깔끔하게 못 가르는 항목 (overlap) | L1~L6 외 `qualitative` + `meta`(연구목적용) 그룹 허용. ADR-0002 에서 재가능 명시 |
| R5 | DB 마이그레이션 — 기존 `projects` 테이블과 신규 충돌 | Phase 2 시작 전 Alembic revision 으로 `projects` → `projects_v1_bdml` rename + 신규 `projects` 도입 |
| R6 | `.github/workflows/deploy.yml` 이 archive 코드 경로를 가리키는 동안 CI 실패 | Phase 0 PR 에서 deploy.yml 도 archive 로 이동 + 임시 비활성화 |

### 7.2 Open Questions

**해결됨 (2026-05-07)** — 문서 상단 "Open Questions 결정 사항" 표 참조.

| Q | 상태 | 결정 / 결정 시점 |
|---|---|---|
| Q1 — 브랜드 컬러 | ✅ 해결 | 루트 `DESIGN.md` 토큰 채택 (Indigo + Violet + Pretendard) |
| Q2 — 시각화 라이브러리 | ✅ 해결 | Recharts |
| Q4 — Twin v2 적재 인원 | ✅ 해결 | 30명 시작, 이후 확장 |
| Q6 — 리포 이름 | ✅ 해결 | Phase 6 시점에 `Ditto` 로 rename |
| **Q3 — V5 CF 자극 세트 설계** | ⏳ 미결정 | Phase 5 진입 시 결정. 권장: 하이브리드 — L1/L6 핵심 10~15개는 수작업 + 나머지 LLM 생성 + 검수 |
| **Q5 — 워크스페이스 모델 (다중 조직)** | ⏳ 미결정 | v1.0 출시 후 결정. 잠정: v1.1 로 미룸 |
| **Q7 — `panels`/`panel_memories` 통합 vs 병존** | ⏳ 미결정 | Phase 6 정리 시점 결정. 잠정: 병존 (회귀 비교 가능) |

---

## 8. 첫 PR 체크리스트 (Phase 0+1)

- [ ] 브랜치 `chore/archive-bdml-bootstrap-ditto` 생성
- [ ] §0.2 의 `git mv` 일괄 실행 (단, `DESIGN.md` 는 루트 유지)
- [ ] `archive/README.md` 신규 작성
- [ ] 루트 `.gitignore` 경로 갱신 (BDML 한정 항목 → archive 경로)
- [ ] `README.md` (Ditto 버전), `CLAUDE.md` (Ditto 버전), `.cursorrules` (Ditto 디렉터리 맵) 신규 작성
- [ ] 루트 `DESIGN.md` 에 Ditto 신규 컴포넌트 (`Gauge`, `RadarChart`, `ScoreBadge`, `ChatBubble`, `FGIInterventionInput`) 규칙 섹션 추가
- [ ] `docs/PRD.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `api-spec.md`, `EVAL_SPEC.md`, `6-LENS_MAPPING.md`(헤더만) 작성
- [ ] `docs/adr/0001~0004` 작성
- [ ] 본 plan 파일 (`docs/plans/active/0001-archive-and-bootstrap-ditto.md`) 그대로 유지
- [ ] `git status` 에서 모든 이동이 rename(R) 으로 잡히는지 확인
- [ ] Squash merge 후 plan 을 `docs/plans/completed/` 로 이동 + 새 plan `0002-ditto-mvp-1-six-lens.md` 생성
