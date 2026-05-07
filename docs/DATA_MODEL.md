# Data Model — Ditto

DB 스키마, 도메인 모델, 데이터 적재 파이프라인, 마이그레이션 규칙.

## DB 엔진

- **운영:** Cloud SQL PostgreSQL (`asia-northeast3:bigmarlab-db` 재사용 vs 신규 인스턴스 미결정 — Phase 6 결정).
- **로컬 개발:** SQLite (aiosqlite). 마이그레이션 변경 시 양쪽 호환을 항상 확인.
- **ORM:** SQLAlchemy 2.0+ (async).
- **마이그레이션:** Alembic.

## 도메인 모델 (개요)

```
Workspace (v1.1)
  └─ User
       └─ ResearchProject
              ├─ Survey (질문 + 응답, v1.0 Phase 6)
              │     └─ SurveyResponse
              ├─ Agent (Twin 또는 Survey 응답 기반)
              │     ├─ persona_params (수치 JSONB)
              │     ├─ persona_full_prompt (시스템 프롬프트 텍스트)
              │     └─ AgentMemory[] (base / conversation / fgi)
              │     └─ EvaluationSnapshot[] (V1~V5 시계열)
              ├─ Conversation
              │     └─ Turn[] (사용자 + 에이전트)
              └─ FGISession
                    └─ Turn[] (모더레이터 + 에이전트 + 사용자 개입)
```

## 테이블 스키마

### `users`

(archive 에서 이식, 변경 없음.)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| email | string | unique |
| hashed_password | string | bcrypt |
| name | string | |
| role | string | `user` / `admin` |
| is_active | bool | |

### `refresh_tokens`

(archive 에서 이식, 변경 없음.)

### `activity_logs`

토큰 사용량 추적. 평가 비용 (`action='evaluation_v1' | 'evaluation_v2' | ...`) 도 같이 기록.

### `research_projects`

리서치 프로젝트 단위. archive 의 `projects` 와는 **별개 테이블** (archive `projects` 는 Alembic 으로 `projects_v1_bdml` 로 rename).

| 컬럼 | 타입 | 의미 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| title | string | 사용자 입력 또는 자동 생성 |
| description | Text | 자유 입력 |
| status | string | `draft` / `active` / `archived` |
| created_at, updated_at | datetime | |

### `agents`

에이전트 단위. Twin-2K-500 또는 Survey 응답에서 생성.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| project_id | UUID FK | `research_projects.id` |
| source_type | string | `twin` (Twin-2K-500 v2) / `survey` (사용자 자체 Survey) |
| source_ref | string | Twin pid 또는 SurveyResponse id |
| display_name | string | UI 표기 (예: "직장인 30대 여성 A") |
| emoji | string | 카드 표시용 이모지 |
| intro_ko | Text | 짧은 한국어 소개 |
| persona_params | JSONB | 6-Lens 정량 지표 (`{l1: {...}, l2: {...}, ...}`) |
| persona_full_prompt | Text | 시스템 프롬프트 합성 결과 (≤ 8k tokens) |
| scratch | JSONB | 인구통계 + 정성 원문 (self_actual/aspire/ought 등) |
| avg_embedding | vector(1536) | 메모리 평균 벡터 — 다양성 클러스터링·1차 스코어링 |
| cluster | INT | 다양성 K-means 라벨 (적재 후 채워짐, NULL 허용) |
| created_at, updated_at | datetime | |

### `agent_memories`

에이전트별 자전적 기억 + 임베딩.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| agent_id | UUID FK | `agents.id` |
| source | string | `base` (Twin/Survey 원본) / `conversation` (1:1 대화 누적) / `fgi` (FGI 누적) |
| category | string | L1~L6 + qualitative + 후속 카테고리 (자유 string) |
| text | Text | 자연어 (한국어) |
| importance | float | 0~1, retrieval 가중치 |
| embedding | vector(1536) | OpenAI text-embedding-3-small |
| metadata | JSONB | source 별 부가 정보 (FGI session_id, conversation_id 등) |
| created_at | datetime | |

**검색 인덱스:** `(agent_id, source)` + pgvector ivfflat.

### `evaluation_snapshots`

에이전트의 V1~V5 평가 결과 시계열. **에이전트 성장 추적의 핵심.**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| agent_id | UUID FK | |
| version | int | 같은 에이전트의 평가 회차 (1, 2, 3, ...) |
| identity_stats | JSONB | `{ "sync": 0.88, "stability": 0.82, "distinct": 2.8 }` |
| logic_stats | JSONB | `{ "humanity": 4.2, "reasoning_delta": 0.15 }` |
| verdict | string | `verified_s3` / `partial` / `failed` (EVAL_SPEC 임계값 기준 자동 산정) |
| eval_config | JSONB | 사용한 평가 설정 (모델, CF 자극 세트 버전 등) |
| evaluated_at | datetime | |

### `conversations`

1:1 대화 세션.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| project_id | UUID FK | |
| agent_id | UUID FK | |
| user_id | UUID FK | |
| title | string | |
| started_at, ended_at | datetime | |

### `conversation_turns`

| 컬럼 | 타입 |
|---|---|
| id | UUID |
| conversation_id | UUID FK |
| role | `user` / `agent` |
| content | Text |
| citations | JSONB (V1 인용 마커 검증 결과) |
| confidence | string (`direct` / `inferred` / `guess` / `unknown`) |
| created_at | datetime |

### `fgi_sessions`

다자 회의 세션.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| project_id | UUID FK | |
| user_id | UUID FK | (호스트) |
| topic | Text | 회의 주제 |
| agent_ids | JSONB array | 참여 에이전트 |
| status | string | `running` / `completed` / `cancelled` |
| minutes_md | Text | 자동 생성 회의록 (Markdown) |
| started_at, ended_at | datetime | |

### `fgi_turns`

| 컬럼 | 타입 |
|---|---|
| id | UUID |
| session_id | UUID FK |
| round | int |
| role | `moderator` / `agent` / `user` |
| agent_id | UUID FK NULL (role='agent' 일 때) |
| content | Text |
| metadata | JSONB (retrieval 컨텍스트 메모리 ID 등) |
| created_at | datetime |

### `surveys` (Phase 6)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| project_id | UUID FK | |
| title | string | |
| questions | JSONB array | 질문 정의 |
| share_token | string | 배포 링크용 unique 토큰 |
| status | string | `draft` / `published` / `closed` |

### `survey_responses` (Phase 6)

| 컬럼 | 타입 |
|---|---|
| id | UUID |
| survey_id | UUID FK |
| respondent_token | string |
| answers | JSONB |
| submitted_at | datetime |

## archive 테이블과의 관계

| archive 테이블 | Ditto 처리 |
|---|---|
| `panels` (`source='fgi500'` 500명 + `source='twin2k500'` 50명) | **별도 운영, 손대지 않음**. Phase 6 정리 시 통합/삭제 결정 |
| `panel_memories` | 동일 |
| `projects`, `project_edits` | Alembic 으로 `projects_v1_bdml`, `project_edits_v1_bdml` 로 rename. 신규 `research_projects` 도입 |
| `users`, `refresh_tokens`, `activity_logs` | **그대로 재사용** (스키마 호환) |

## Twin-2K-500 v2 적재 파이프라인

```
load_dataset("LLM-Digital-Twin/Twin-2K-500", "full_persona", split="data")[0:30]
   │ + Twin2K500_KR_Localized_v1_1.pdf 한국어 매핑 테이블
   │
   ▼
backend/lenses/mapping.py
   ├─ 234문항 → L1~L6 + qualitative 카테고리 분할
   └─ scratch (인구통계 + 정성 원문 한국어) 추출
   │
   ▼
backend/scoring/
   ├─ reverse_score   (L2 인지 욕구, L6 성실성 등 역방향 변환)
   ├─ economic        (L1-1 위험 회피 CE, L6-1 할인율 연환산)
   └─ ability         (C-2 금융 + C-3 수리 합산)
   │
   ▼
backend/persona/builder.py
   ├─ persona_params 산출 (수치 JSONB)
   ├─ persona_full_prompt 합성 (≤ 8k tokens, Hybrid: 수치 + 원문)
   └─ category 별 메모리 텍스트 + 임베딩
   │
   ▼
INSERT INTO agents (source_type='twin', persona_params, persona_full_prompt, scratch, avg_embedding)
INSERT INTO agent_memories (agent_id, source='base', category, text, embedding) × N
   │
   ▼ (모든 적재 후)
sklearn KMeans(K=5) on agents.avg_embedding → cluster 라벨 업데이트
```

### 적재 명령

```bash
cd backend
python -m scripts.seed_twin_v2 --limit 30
# 옵션:
#   --limit N          : 적재 인원 (기본 30)
#   --resume           : 기존 적재본 건너뛰고 이어서
#   --refresh-prompt   : 시스템 프롬프트만 재합성
```

- 30명 × ~30 메모리 = 약 900개 임베딩. 비용 ~$0.003.
- 재실행 안전: 동일 `source_ref` 존재 시 자동 건너뜀.

## 마이그레이션 규칙

- 모든 스키마 변경은 Alembic 마이그레이션 작성.
- Cloud SQL(PostgreSQL)과 SQLite(aiosqlite) **양쪽 호환** 확인. JSONB 는 SQLite 에서 JSON 으로, vector 타입은 SQLite 에서 BLOB/JSON 폴백.
- 스키마 변경 시 본 문서를 같은 PR 에서 갱신.
- archive 의 테이블에 영향이 가는 마이그레이션은 작성 금지 (격리 원칙).

## 보안 / git 정책

- 응답 원본·DB 덤프·`embedding_cache.json` 은 **절대 git 커밋 금지**.
- 외부 도구·AI 도구에 응답 데이터 업로드 금지.
- `.env`, 서비스 계정 JSON 도 `.gitignore` 가 강제 (예외 화이트리스트만 허용).

## 관련 ADR

- [ADR-0002 — 6-Lens 카테고리 분할](./adr/0002-six-lens-categorization.md)
- [ADR-0003 — Hybrid Persona Prompt](./adr/0003-hybrid-persona-prompt.md)
- [ADR-0004 — V1~V5 평가 채택](./adr/0004-evaluation-v1-to-v5.md)
