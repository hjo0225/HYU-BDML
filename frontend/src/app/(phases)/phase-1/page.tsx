'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import type { ResearchBrief } from '@/lib/types';

/* 카테고리 옵션 */
const CATEGORIES = [
  '문제 발견 / Pain Point 파악',
  '니즈 / 인사이트 도출',
  '고객 여정 이해',
  '컨셉 / 아이디어 검증',
  '사용성 / UX 개선',
  '시장 탐색 / 경쟁 분석',
];

export default function Phase1Page() {
  const router = useRouter();
  const { project, setBrief, setRefined, setMarketReport, setAgents, setMessages, setMinutes, setCurrentPhase } = useProject();

  const [form, setForm] = useState<ResearchBrief>(
    project.brief ?? {
      background: '',
      objective: '',
      usage_plan: '',
      category: '',
      target_customer: '',
    },
  );

  const update = (key: keyof ResearchBrief, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const isValid = form.background.trim() && form.objective.trim() && form.usage_plan.trim() && form.category;

  const submit = () => {
    if (!isValid) return;
    setBrief(form);
    // 하위 단계 데이터 초기화
    setRefined(null);
    setMarketReport(null);
    setAgents([]);
    setMessages([]);
    setMinutes(null);
    setCurrentPhase(2);
    router.push('/phase-2');
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">📋 연구 정보 입력</div>
        <span className="badge badge-optional">자동 저장됨</span>
      </div>

      {/* 연구 배경 */}
      <div className="field-group">
        <div className="field-label">
          연구 배경 / 맥락 <span className="badge badge-required">필수</span>
        </div>
        <textarea
          className="field-textarea"
          placeholder="왜 이 연구가 필요한지, 현재 상황과 문제 인식을 작성하세요. 예) 20-30대 직장인 대상 건강식 배달 서비스를 기획 중이며, 기존 배달 앱 대비 차별화 포인트를 찾고자 합니다..."
          value={form.background}
          onChange={(e) => update('background', e.target.value)}
          rows={4}
        />
      </div>

      {/* 연구 목적 */}
      <div className="field-group">
        <div className="field-label">
          연구 목적 / 목표 <span className="badge badge-required">필수</span>
        </div>
        <textarea
          className="field-textarea"
          placeholder="이 연구를 통해 알고 싶은 것, 해결하려는 핵심 질문을 작성하세요."
          value={form.objective}
          onChange={(e) => update('objective', e.target.value)}
          rows={3}
        />
      </div>

      {/* 활용방안 */}
      <div className="field-group">
        <div className="field-label">
          연구결과 활용방안 <span className="badge badge-required">필수</span>
        </div>
        <textarea
          className="field-textarea"
          placeholder="결과물을 어디에, 어떻게 사용할 계획인가요? (의사결정, 투자 유치, 제품 개선 등)"
          value={form.usage_plan}
          onChange={(e) => update('usage_plan', e.target.value)}
          rows={3}
        />
      </div>

      {/* 카테고리 */}
      <div className="field-group">
        <div className="field-label">
          연구 목적 카테고리 <span className="badge badge-required">필수</span>
        </div>
        <div className="radio-group">
          {CATEGORIES.map((cat) => (
            <div
              key={cat}
              className={`radio-item ${form.category === cat ? 'selected' : ''}`}
              onClick={() => update('category', cat)}
            >
              {cat}
            </div>
          ))}
        </div>
      </div>

      {/* 타깃 고객 */}
      <div className="field-group">
        <div className="field-label">
          타깃 고객 / 사용자 정의 <span className="badge badge-optional">선택</span>
        </div>
        <textarea
          className="field-textarea"
          style={{ minHeight: 52 }}
          placeholder="연구 대상의 인구통계·행동·심리 특성 (예: 25-35세, 서울 거주, 주 3회 이상 배달 주문)"
          value={form.target_customer}
          onChange={(e) => update('target_customer', e.target.value)}
          rows={2}
        />
      </div>

      {/* 액션 바 */}
      <div className="action-bar">
        <div />
        <button className="btn btn-primary" onClick={submit} disabled={!isValid}>
          시장조사 시작 →
        </button>
      </div>
    </div>
  );
}
