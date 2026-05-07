# archive/

이 폴더는 **이전 프로젝트의 동결된 코드·문서를 보관하는 read-only 공간**입니다. 활성 개발은 항상 리포 루트에서 이루어집니다.

## 폴더

### `bdml-fgi/`

**빅데이터마케팅랩(BDML) — AI FGI 시뮬레이션 웹앱**.

- 활동 기간: 2026-03-28 ~ 2026-05-07
- 마지막 커밋(아카이브 직전): `chore/archive-bdml-bootstrap-ditto` 브랜치, plan `docs/plans/active/0001-archive-and-bootstrap-ditto.md` 참조
- 핵심 자산:
  - 5-Phase 위저드: research-input → market-research → agent-setup → meeting → minutes
  - Lab Twin-2K-500 1:1 메신저 (50명)
  - Cloud SQL FGI 패널 500명 + Twin 50명 + 5,373건 메모리 임베딩
- 명세 SSOT: `bdml-fgi/docs/PRD.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `api-spec.md`, `adr/0001~0006`

## 사용 규칙

1. **읽기만.** 이 폴더의 코드·문서는 신규 개발 시 **참조용**으로만 사용합니다. 직접 수정하지 마세요.
2. **import 금지.** 루트의 신규 코드(Ditto 등)는 `archive/` 안의 모듈을 직접 import 해선 안 됩니다. 필요한 모듈은 명시적으로 신규 위치에 복사·재작성합니다.
3. **데이터 보존.** 적재된 Cloud SQL 데이터(`panels.source='fgi500'`, `panel_memories.source='fgi500'`)는 BDML 시절 자산이며, Ditto 가 별도 결정 전까지는 그대로 둡니다.
4. **삭제 시점.** archive 의 하위 프로젝트는 1년 이상 신규 코드에서 참조되지 않은 경우, 별도 ADR 결정 후 제거합니다.

## 신규 프로젝트 (Ditto)로

이전 프로젝트와의 차이·이식 계획은 `docs/plans/completed/0001-archive-and-bootstrap-ditto.md` (또는 active/) 를 참조하세요.
