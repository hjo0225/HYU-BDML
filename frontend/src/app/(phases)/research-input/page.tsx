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

const EMPTY_BRIEF: ResearchBrief = {
  background: '',
  objective: '',
  usage_plan: '',
  category: '',
  target_customer: '',
};

export default function Phase1Page() {
  const router = useRouter();
  const { project, resetAfterBriefChange, setCurrentPhase } = useProject();

  const [form, setForm] = useState<ResearchBrief>({
    ...EMPTY_BRIEF,
    ...(project.brief ?? {}),
  });

  const update = (key: keyof ResearchBrief, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const isValid =
    form.background.trim() &&
    form.objective.trim() &&
    form.usage_plan.trim() &&
    form.category &&
    form.target_customer.trim();
  const [showWarning, setShowWarning] = useState(false);

  // form이 저장된 brief와 다르면 "작성 중", 같으면 "저장됨"
  const isSaved = project.brief !== null && (
    form.background === project.brief.background &&
    form.objective === project.brief.objective &&
    form.usage_plan === project.brief.usage_plan &&
    form.category === project.brief.category &&
    form.target_customer === project.brief.target_customer
  );

  // 하위 단계에 이미 데이터가 있으면 경고 필요
  const hasDownstreamData = !!(project.refined || project.agents.length > 0 || project.messages.length > 0);

  const doSubmit = () => {
    resetAfterBriefChange(form);
    setCurrentPhase(2);
    router.push('/market-research');
  };

  const submit = () => {
    if (!isValid) return;
    if (hasDownstreamData) {
      setShowWarning(true);
      return;
    }
    doSubmit();
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">📋 연구 정보 입력</div>
        <span className={`badge ${isSaved ? 'badge-optional' : ''}`} style={!isSaved ? { background: '#fff8e1', color: '#7a5f00' } : undefined}>
          {isSaved ? '저장됨' : '작성 중'}
        </span>
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
        <div style={{ marginTop: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          현재 상황, 왜 이 조사가 필요한지, 내부에서 이미 알고 있는 문제를 함께 적어주세요.
        </div>
      </div>

      {/* 연구 목적 */}
      <div className="field-group">
        <div className="field-label">
          연구 목적 / 목표 <span className="badge badge-required">필수</span>
        </div>
        <textarea
          className="field-textarea"
          placeholder="이 연구를 통해 알고 싶은 것, 검증하고 싶은 가설, 답을 얻고 싶은 핵심 질문을 함께 작성하세요."
          value={form.objective}
          onChange={(e) => update('objective', e.target.value)}
          rows={4}
        />
        <div style={{ marginTop: 5, fontSize: 11, color: 'var(--text-muted)' }}>
          알고 싶은 질문을 문장 안에 자연스럽게 적어주세요. 예: 어떤 고객군이 가장 시급한 니즈를 느끼는가, 경쟁 대안 대비 왜 이탈하는가.
        </div>
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
          타깃 고객 / 사용자 정의 <span className="badge badge-required">필수</span>
        </div>
        <textarea
          className="field-textarea"
          style={{ minHeight: 52 }}
          placeholder="연구 대상의 인구통계·행동·심리 특성을 적어주세요. 예: 25-35세, 서울 거주, 주 3회 이상 배달 주문, 건강식에 관심이 많음"
          value={form.target_customer}
          onChange={(e) => update('target_customer', e.target.value)}
          rows={2}
        />
        <div style={{ marginTop: 5, fontSize: 11, color: 'var(--ai)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span>✦</span>
          <span>연령 정보(예: 20-30대)를 입력하면 AI가 에이전트 나이를 정확히 맞춥니다.</span>
        </div>
      </div>

      {/* 데이터 손실 경고 배너 */}
      {showWarning && (
        <div className="mb-3 p-3 rounded-md text-xs" style={{ background: '#fff8e1', border: '1px solid #ffe082', color: '#7a5f00' }}>
          <div className="font-semibold mb-2">⚠️ 이전 단계 결과가 초기화됩니다. 계속하시겠습니까?</div>
          <div style={{ color: 'var(--text-muted)', marginBottom: 10 }}>시장조사, 에이전트 구성, 회의 내용이 모두 삭제됩니다.</div>
          <div className="flex gap-2">
            <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 12px' }} onClick={doSubmit}>확인</button>
            <button className="btn btn-secondary" style={{ fontSize: 11, padding: '4px 12px' }} onClick={() => setShowWarning(false)}>취소</button>
          </div>
        </div>
      )}

      {/* 액션 바 */}
      <div className="action-bar">
        <div />
        <button className="btn btn-primary" onClick={submit} disabled={!isValid}>
          저장 후 계속 →
        </button>
      </div>
    </div>
  );
}
