# Data Model

DB 스키마, 패널 데이터 적재 파이프라인, 마이그레이션 규칙.

## DB 엔진

- **운영**: Cloud SQL PostgreSQL (asia-northeast3:bigmarlab-db).
- **로컬 개발**: SQLite (aiosqlite). 마이그레이션 변경 시 양쪽 호환을 항상 확인.
- **ORM**: SQLAlchemy 2.0+ (async).
- **마이그레이션**: Alembic.

## 테이블 스키마

### `users`

사용자 계정.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| email | string | unique |
| hashed_password | string | bcrypt |
| name | string | |
| role | string | `user` / `admin` |
| is_active | bool | |

### `refresh_tokens`

JWT 리프레시 토큰. 무효화를 위해 해시 저장.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| token_hash | string | SHA-256 |
| expires_at | datetime | |
| is_revoked | bool | |

### `projects`

연구 세션. Phase 1~5의 모든 산출물을 단일 행에 보관 (JSONB/Text).

| 컬럼 | 타입 | 의미 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK |
| title | string | 자동 생성 가능 (`project_service`) |
| brief | JSONB | Phase 1 입력 |
| refined | JSONB | Phase 1 정제 결과 |
| market_report | Text | Phase 2 보고서 |
| agents | JSONB | Phase 3 선정 에이전트 |
| meeting_topic | Text | Phase 3 Step 1 주제 |
| meeting_messages | JSONB | Phase 4 발언 로그 |
| minutes | Text | Phase 5 회의록 (Markdown) |

### `project_edits`

수정 이력 감사 로그.

| 컬럼 | 타입 |
|---|---|
| project_id | UUID FK |
| field | string |
| old_value | Text |
| new_value | Text |
| changed_at | datetime |

### `activity_logs`

토큰 사용량 추적. 관리자 조회 (`/api/usage/*`).

| 컬럼 | 타입 |
|---|---|
| user_id | UUID |
| action | string (예: `meeting_turn`, `research`) |
| model | string |
| input_tokens | int |
| output_tokens | int |
| cost_usd | float |

### `panels`

패널 풀 (FGI 500명 + Lab Twin-2K-500 50명). 인구통계 + 행동 차원 + 사전 계산된 평균 임베딩.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | UUID | PK |
| source | VARCHAR(20) | `'fgi500'` (기본) / `'twin2k500'` (Lab) |
| cluster | INT (NOT NULL) | FGI: K-means 라벨 0~24 / Twin: 100~104 (오프셋 100, K=5) — 두 source의 클러스터 공간 완전 분리 |
| 인구통계(age, gender, occupation, region 등) | various | |
| 8개 행동 차원 | various | FGI 전용 (Twin은 NULL) |
| scratch | JSONB | `{age, gender, occupation, region, traits, life_events, ...}` |
| avg_embedding | vector(1536) | 패널 메모리 평균 벡터 — FGI 1차 스코어링용. Twin은 다양성 K-means에 사용 |
| persona_full | TEXT | Twin 전용 — Toubia 풀-프롬프트 채팅용 persona_json 원본 (~170k chars). FGI는 NULL |

**source 필터링 규칙:**

- 본 서비스(Phase 3 RAG 패널 선정)는 `source='fgi500'`로 필터.
- Lab(`/api/lab/*`)은 `source='twin2k500'`로 필터.
- 두 도메인이 섞이지 않도록 모든 쿼리에 `source` 조건 필수.

**cluster 공간 분리:**

- FGI(500명): K-means 25 클러스터 → 라벨 `0~24`. CSV 적재 시 사전 계산.
- Twin(50명): 적재 후 `seed_twin.py`가 K-means(K=5) 재실행 → 라벨 `100~104`. 오프셋 100으로 FGI와 ID 충돌 방지. K는 `SEED_TWIN_K` 환경변수로 조정 가능.
- 다양성 샘플링(`panel_selector`)은 source 필터 후 자체 `cluster` 라벨 안에서 동작하므로, 두 도메인이 같은 selector 코드를 재사용해도 클러스터가 섞이지 않음.

### `panel_memories`

패널별 자전적 기억 + 임베딩. FGI는 14개 카테고리 약 5,373건, Twin은 6~10개 카테고리 (영어 원본).

| 컬럼 | 타입 | 비고 |
|---|---|---|
| panel_id | UUID FK | `panels.id` |
| source | VARCHAR(20) | `'fgi500'` / `'twin2k500'` (조회 인덱스용 — 빠진 source 필터를 방어) |
| category | string | FGI: ps_A, ps_B, ps_D, pay_*, lbs_*, app_* 등 / Twin: lifestyle, work, family, technology, finance, health, media, opinions 등 |
| text | Text | 자연어 압축 (FGI: 한국어, Twin: 영어) |
| importance | float | |
| embedding | vector(1536) | OpenAI text-embedding-3-small |

## 패널 데이터 파이프라인

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

### 적재 명령

```bash
cd backend && python -m scripts.seed_panels
```

- **사전 조건:**
  - Cloud SQL Proxy 실행 (`cloud-sql-proxy bdml-492404:asia-northeast3:bigmarlab-db --port=5432`).
  - `backend/.env`에 `DATABASE_URL`, `OPENAI_API_KEY` 필요.
- **동작:** 확인 없이 한 사람씩 즉시 저장. 중단 후 재실행 시 이어서 적재.
- **소요:** 전체 500명 약 10~20분, OpenAI 임베딩 비용 ~$0.02.

### `compute_avg_embeddings.py`

기존 패널의 `avg_embedding`을 1회성으로 계산하여 `panels.avg_embedding`에 채워 넣는 스크립트. `seed_panels`는 이제 적재 시 함께 계산하지만, 과거 적재본을 백필할 때 사용.

## 적재 완료 상태

- Cloud SQL에 500명 FGI 패널(`source='fgi500'`) + 5,373개 메모리(1536차원 임베딩) 적재 완료.
- `seed_panels.py`는 재적재용으로 유지하되 CSV 원본(별도 백업 보관) 필요.

## Twin-2K-500 적재 (Lab 전용)

`backend/scripts/seed_twin.py`로 Hugging Face `LLM-Digital-Twin/Twin-2K-500` 데이터셋에서 50명을 샘플링하여 적재.

### 데이터셋 구조 (실측 확인)

`load_dataset("LLM-Digital-Twin/Twin-2K-500", "full_persona", split="data")` 로드 시 각 행:

| 필드 | 설명 |
|---|---|
| `pid` | 응답자 ID (총 2,058명) |
| `persona_text` | 모든 Q/A를 풀어쓴 영어 평문 (~130k chars) |
| `persona_summary` | 정형화된 인구통계 + 30+ 심리척도 + 정성응답 3개 (영어, ~12-18k chars) |
| `persona_json` | 동일 정보의 JSON 문자열 (~170k chars) — 본 적재에서 미사용 |

본 적재는 **`persona_summary`만 사용**한다 — 매우 정형화되어 카테고리 분할이 정확하고, embedder 입력 단위가 적절하다.

### 적재 파이프라인

```
load_dataset(...)["data"]  → pid + persona_summary
   │
   ├─ rag/twin_scratch_builder.build_scratch(pid, persona_summary)
   │     "Header: value" 라인 정규식 파싱
   │     출력: {age (midpoint), age_range, gender, region, occupation,
   │            education, race, marital_status, religion, income,
   │            political_affiliation, political_views, household_size,
   │            traits[Big5/percentile], big5(scores),
   │            aspire/ought/actual (정성응답 영어 원문),
   │            display_name, emoji, intro_ko}
   │     → panels (source='twin2k500')
   │
   └─ rag/twin_memory_builder.build_memories(persona_summary)
         "The person's <X> score(s) are the following:" 헤더 단위 섹션 분할
         + 정성응답 3개(self_aspire/ought/actual) 별도 메모리화
         결과: 응답자당 ~32개 메모리 카테고리:
            demographics, personality_big5,
            cognition_general · cognition_reflection · cognition_intelligence
              · cognition_logic · cognition_numeracy · cognition_closure,
            values_agency · values_minimalism · values_environment
              · values_individualism · values_regulatory · values_uniqueness,
            decision_risk · decision_loss · decision_maximization,
            finance_mental · finance_literacy · finance_time_pref · finance_tightwad,
            social_ultimatum · social_trust · social_dictator · social_desirability,
            emotion_empathy · emotion_anxiety · emotion_depression,
            self_monitoring · self_clarity,
            self_aspire · self_ought · self_actual
         │
         └─ embedder.embed(text)  # 영어 그대로
            → panel_memories (source='twin2k500', text=영어, embedding=1536d)

   최종 단계 (모든 패널 적재 후):
   └─ scripts/seed_twin._recluster_twin()
         sklearn KMeans(K=5)를 panels.avg_embedding 50개에 적용
         → cluster = 100 + label (라벨 100~104)
         → UPDATE panels SET cluster=… WHERE source='twin2k500'
```

### 적재 명령

```bash
# 사전: pip install datasets huggingface_hub
# 사전: python -m scripts.migrate_add_source  (1회)
cd backend && python -m scripts.seed_twin

# 옵션:
SEED_TWIN_LIMIT=100 SEED_TWIN_SEED=7 python -m scripts.seed_twin
SEED_TWIN_STREAM=1 python -m scripts.seed_twin   # 전체 다운로드 대신 스트리밍
```

- 50명 × ~32 메모리 = 약 1,600개 임베딩. 비용 ~$0.005.
- 재실행 안전: 동일 `panel_id` 존재 시 자동 건너뜀.

### Toubia 풀-프롬프트 백필

Lab 채팅은 RAG가 아닌 풀-프롬프트(persona_json 원본 통째 주입) 방식이므로, seed_twin
이후 1회 추가 백필이 필요하다.

```bash
cd backend && python -m scripts.seed_twin_persona_full
```

- `panels.persona_full TEXT` 컬럼 추가 (멱등) + 기존 50명에 HF persona_json 채워넣기.
- 응답 발화 시 `prompts/twin_utterance.py`가 `persona_full`을 시스템 프롬프트에 통째로 주입하고
  "위 영어 응답 데이터 기반으로 한국어 1인칭으로 답하라" 지시.

## 마이그레이션 규칙

- 모든 스키마 변경은 Alembic 마이그레이션 작성.
- Cloud SQL(PostgreSQL)과 SQLite(aiosqlite) **양쪽 호환** 확인. JSONB는 SQLite에서 JSON으로, vector 타입은 SQLite에서 BLOB/JSON 폴백.
- 본 문서를 같은 PR에서 갱신.

## 보안 / git 정책

- 패널 CSV 원본·DB 덤프·`backend/.cache/embedding_cache.json`은 **절대 git 커밋 금지**.
- 외부 도구·AI 도구에 패널 데이터 업로드 금지.

## 관련 ADR

- [0002 — RAG 패널 연령 필터 제거](./adr/0002-rag-panel-no-age-filter.md)
- [0003 — `avg_embedding` 1차 스코어링 도입](./adr/0003-avg-embedding-first-pass-scoring.md)
- [0005 — Lab + Twin-2K-500 통합](./adr/0005-lab-twin-2k-500-integration.md)
