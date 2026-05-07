'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { fetchLabTwins } from '@/lib/api';
import type { LabTwin, LabTwinBig5 } from '@/lib/types';
import { FaithfulnessBadge, FaithfulnessBars } from '@/components/lab/FaithfulnessBar';

// Big5 차원 표기
const BIG5_LABELS: Array<{ key: keyof LabTwinBig5; ko: string; lowKo: string; highKo: string }> = [
  { key: 'openness',          ko: '개방성',     lowKo: '관습적',   highKo: '개방적' },
  { key: 'conscientiousness', ko: '성실성',     lowKo: '자유로움', highKo: '체계적' },
  { key: 'extraversion',      ko: '외향성',     lowKo: '내향적',   highKo: '외향적' },
  { key: 'agreeableness',     ko: '우호성',     lowKo: '독립적',   highKo: '협조적' },
  { key: 'neuroticism',       ko: '신경성',     lowKo: '안정적',   highKo: '예민함' },
];

function TwinDetailModal({
  twin,
  onClose,
  onStart,
}: {
  twin: LabTwin;
  onClose: () => void;
  onStart: () => void;
}) {
  const ageStr =
    twin.age != null
      ? `${twin.age}세${twin.age_range ? ` (${twin.age_range})` : ''}`
      : twin.age_range || null;

  const facts: Array<[string, string]> = [];
  if (ageStr) facts.push(['나이', ageStr]);
  if (twin.gender) facts.push(['성별', twin.gender]);
  if (twin.race) facts.push(['인종', twin.race]);
  if (twin.region) facts.push(['지역', `${twin.region} US`]);
  if (twin.occupation) facts.push(['직업', twin.occupation]);
  if (twin.education) facts.push(['학력', twin.education]);
  if (twin.marital_status) facts.push(['결혼', twin.marital_status]);
  if (twin.household_size) {
    const hs = twin.household_size;
    facts.push(['가구원', /^\d+$/.test(hs) ? `${hs}명` : hs]);
  }
  if (twin.income) facts.push(['소득', twin.income]);
  if (twin.religion) facts.push(['종교', twin.religion]);

  const politicsTag =
    twin.political_views || twin.political_affiliation
      ? [twin.political_views, twin.political_affiliation].filter(Boolean).join(' · ')
      : null;

  const big5Entries = BIG5_LABELS.map((row) => {
    const v = twin.big5?.[row.key];
    return v != null ? { ...row, value: v } : null;
  }).filter(Boolean) as Array<(typeof BIG5_LABELS)[number] & { value: number }>;

  return (
    <div
      className="lab-modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="twin-modal-name"
    >
      <div className="lab-modal lab-modal--rich" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="lab-modal__close" onClick={onClose} aria-label="닫기">
          ×
        </button>

        <div className="lab-modal__header">
          <div className="lab-modal__avatar">{twin.emoji || '🧑'}</div>
          <div className="lab-modal__header-text">
            <div id="twin-modal-name" className="lab-modal__name">
              {twin.name}
            </div>
            <div className="lab-modal__id">{twin.twin_id}</div>
            {politicsTag && <div className="lab-modal__politics">🗳 {politicsTag}</div>}
          </div>
        </div>

        <p className="lab-modal__intro-line">{twin.intro}</p>

        {facts.length > 0 && (
          <section className="lab-modal__section">
            <div className="lab-modal__section-label">프로필</div>
            <dl className="lab-modal__facts">
              {facts.map(([k, v]) => (
                <div key={k} className="lab-modal__fact-row">
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        {big5Entries.length > 0 && (
          <section className="lab-modal__section">
            <div className="lab-modal__section-label">
              Big5 성격 <span className="lab-modal__section-hint">(백분위)</span>
            </div>
            <ul className="lab-big5">
              {big5Entries.map((row) => (
                <li key={row.key} className="lab-big5__row">
                  <span className="lab-big5__name">{row.ko}</span>
                  <span className="lab-big5__bar-wrap" aria-label={`${row.ko} ${row.value}`}>
                    <span
                      className="lab-big5__bar"
                      style={{ width: `${Math.max(2, Math.min(100, row.value))}%` }}
                    />
                  </span>
                  <span className="lab-big5__value">{row.value}</span>
                </li>
              ))}
              <li className="lab-big5__legend">
                <span>{big5Entries[0].lowKo} ←</span>
                <span>→ {big5Entries[0].highKo}</span>
              </li>
            </ul>
          </section>
        )}

        {twin.faithfulness && (
          <section className="lab-modal__section">
            <div className="lab-modal__section-label">
              데이터 충실도{' '}
              <span className="lab-modal__section-hint">
                (LLM-as-judge 평가, 카테고리당 1문항)
              </span>
            </div>
            <FaithfulnessBars faithfulness={twin.faithfulness} />
          </section>
        )}

        {(twin.aspire || twin.actual || twin.aspire_ko || twin.actual_ko) && (
          <section className="lab-modal__section">
            <div className="lab-modal__section-label">자기 인식</div>
            <div className="lab-self">
              {(twin.aspire_ko || twin.aspire) && (
                <div className="lab-self__item">
                  <span className="lab-self__tag lab-self__tag--aspire">이상적 자아</span>
                  <span className="lab-self__text">
                    &ldquo;{twin.aspire_ko || twin.aspire}&rdquo;
                    {twin.aspire_ko && twin.aspire && (
                      <span className="lab-self__original">{twin.aspire}</span>
                    )}
                  </span>
                </div>
              )}
              {(twin.actual_ko || twin.actual) && (
                <div className="lab-self__item">
                  <span className="lab-self__tag lab-self__tag--actual">현재 자아</span>
                  <span className="lab-self__text">
                    &ldquo;{twin.actual_ko || twin.actual}&rdquo;
                    {twin.actual_ko && twin.actual && (
                      <span className="lab-self__original">{twin.actual}</span>
                    )}
                  </span>
                </div>
              )}
            </div>
          </section>
        )}

        <div className="lab-modal__actions">
          <button type="button" className="lab-modal__btn lab-modal__btn--ghost" onClick={onClose}>
            닫기
          </button>
          <button type="button" className="lab-modal__btn lab-modal__btn--primary" onClick={onStart}>
            대화 시작 →
          </button>
        </div>
      </div>
    </div>
  );
}

export default function LabTwinChatListPage() {
  const router = useRouter();
  const [twins, setTwins] = useState<LabTwin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<LabTwin | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchLabTwins();
        if (!cancelled) setTwins(list);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : '목록을 불러올 수 없습니다.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ESC로 모달 닫기
  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelected(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selected]);

  const startChat = (twin: LabTwin) => {
    router.push(`/lab/twin-chat/${encodeURIComponent(twin.twin_id)}`);
  };

  return (
    <>
      <main className="lab-main">
        <div className="lab-breadcrumb">
          <Link href="/lab" className="lab-breadcrumb__link">
            ← 실험실 메뉴
          </Link>
        </div>

        <div className="lab-section-head">
          <h1 className="lab-section-title">디지털 트윈 1:1 메신저</h1>
          <p className="lab-section-sub">
            Twin-2K-500 데이터셋(Toubia et al. 2025, Marketing Science) 기반의 디지털 트윈
            페르소나입니다. 카드를 선택해 정보를 확인한 뒤 대화를 시작하세요.
          </p>
        </div>

        {loading && (
          <div className="lab-twin-grid">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="lab-twin-card" style={{ pointerEvents: 'none' }}>
                <div className="skeleton" style={{ height: 24, width: '40%' }} />
                <div className="skeleton" style={{ height: 12, width: '70%' }} />
                <div className="skeleton" style={{ height: 12, width: '90%' }} />
              </div>
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="lab-chat__error" style={{ maxWidth: 480 }}>
            {error}
          </div>
        )}

        {!loading && !error && twins.length === 0 && (
          <div className="project-list-empty">
            <div className="project-list-empty__icon">🧪</div>
            <p className="project-list-empty__text">
              아직 적재된 Twin이 없습니다. <code>python -m scripts.seed_twin</code> 실행 후 다시 확인하세요.
            </p>
          </div>
        )}

        {!loading && twins.length > 0 && (
          <div className="lab-twin-grid">
            {twins.map((t) => (
              <button
                key={t.twin_id}
                type="button"
                onClick={() => setSelected(t)}
                className="lab-twin-card lab-twin-card--button"
              >
                <div className="lab-twin-card__head">
                  <div className="lab-twin-card__avatar">{t.emoji || '🧑'}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      className="lab-twin-card__name"
                      style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}
                    >
                      <span>{t.name}</span>
                      {t.faithfulness && (
                        <FaithfulnessBadge faithfulness={t.faithfulness} compact />
                      )}
                    </div>
                    <div className="lab-twin-card__meta">
                      {[t.age ? `${t.age}세` : null, t.gender, t.region]
                        .filter(Boolean)
                        .join(' · ')}
                    </div>
                  </div>
                </div>
                {t.tags && t.tags.length > 0 && (
                  <div className="lab-twin-card__tags">
                    {t.tags.map((tag) => (
                      <span key={tag} className="lab-twin-card__tag">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
                <span className="lab-twin-card__cta">자세히 보기 →</span>
              </button>
            ))}
          </div>
        )}
      </main>

      {selected && <TwinDetailModal twin={selected} onClose={() => setSelected(null)} onStart={() => startChat(selected)} />}
    </>
  );
}
