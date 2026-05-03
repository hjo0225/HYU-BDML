'use client';

import type { LabJudgeResponse, LabVerdict } from '@/lib/types';

const VERDICT_META: Record<
  LabVerdict,
  { icon: string; label: string; tone: string }
> = {
  consistent:  { icon: '🟢', label: '일관됨',     tone: 'consistent' },
  partial:     { icon: '🟡', label: '부분 일치',  tone: 'partial' },
  contradicts: { icon: '🔴', label: '모순',       tone: 'contradicts' },
  evasive:     { icon: '⚪', label: '회피/판단 불가', tone: 'evasive' },
};

interface Props {
  verdict: LabJudgeResponse;
}

export default function JudgeVerdictCard({ verdict }: Props) {
  const meta = VERDICT_META[verdict.verdict] ?? VERDICT_META.evasive;
  return (
    <div className={`lab-verdict lab-verdict--${meta.tone}`}>
      <div className="lab-verdict__head">
        <span className="lab-verdict__icon">{meta.icon}</span>
        <span className="lab-verdict__label">{meta.label}</span>
      </div>
      <p className="lab-verdict__reason">{verdict.reason}</p>
      {(verdict.matched_categories.length > 0 || verdict.contradicted_categories.length > 0) && (
        <div className="lab-verdict__cats">
          {verdict.matched_categories.length > 0 && (
            <div className="lab-verdict__cats-row">
              <span className="lab-verdict__cats-label">일치:</span>
              {verdict.matched_categories.map((c) => (
                <span key={`m-${c}`} className="lab-verdict__chip lab-verdict__chip--match">
                  {c}
                </span>
              ))}
            </div>
          )}
          {verdict.contradicted_categories.length > 0 && (
            <div className="lab-verdict__cats-row">
              <span className="lab-verdict__cats-label">모순:</span>
              {verdict.contradicted_categories.map((c) => (
                <span key={`x-${c}`} className="lab-verdict__chip lab-verdict__chip--contra">
                  {c}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
