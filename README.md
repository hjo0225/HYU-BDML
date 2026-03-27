# Fast Research Agent

인터뷰 질문지 설계 / 보고서 작성을 위한 배경 조사 에이전트 (Phase 1).

## 사전 준비

### 1. Tavily API 키 발급 (무료, 2분 소요)

1. [tavily.com](https://tavily.com) 접속 → "Get API Key" 또는 "Sign Up" 클릭
2. 이메일 또는 Google/GitHub 계정으로 가입 (신용카드 불필요)
3. 대시보드에서 API 키 복사 (`tvly-` 로 시작)
4. 무료 티어: 월 1,000 크레딧 (Fast Research 1회 = ~5크레딧 → 월 200회 가능)

### 2. 프로젝트 세팅

```bash
mkdir fast-research-agent && cd fast-research-agent

python -m venv venv

# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 API 키 입력:
```
OPENAI_API_KEY=sk-your-openai-key-here
TAVILY_API_KEY=tvly-your-tavily-key-here
```

### 4. 실행

```bash
python pipeline.py
```

## 출력

- `output/research_result.json` — Phase 2 입력용 구조화 데이터
- `output/summary_report.md` — 사용자 확인용 마크다운 리포트

## 비용 (1회 실행당)

| 항목 | 비용 |
|------|------|
| OpenAI GPT-4o (3회 호출) | ~$0.03-0.08 |
| Tavily 검색 | 5 크레딧 (무료) |
| Jina Reader | 무료 |
