'use client';

// 질문 관리 (plan 0014/0015) — 종류별 탭 + 첫 진입 시 조사 정보 입력(초기 설정).
// 경량 구현: 시드는 demoScenario, 정보/문항 모두 sessionStorage 에 프로젝트별로 보관(서버 저장은 후속).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useAuth } from '@/contexts/AuthContext';
import { DEMO_SURVEYS, DEMO_INTERVIEW, DEMO_BRIEF, SURVEY_LENS_LABELS } from '@/lib/demoScenario';

interface SurveyItem { id: string; lens?: string; scaleName?: string; scale?: string; q: string }
interface Survey { key: string; title: string; desc?: string; items: SurveyItem[] }
interface SurveyInfo { title: string; objective: string; target: string; types: string[] }

const uid = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2));

// 문항을 렌즈(L1~L6·통제 / 인터뷰 Part)별로 묶는다. 첫 등장 순서 보존.
function groupByLens(items: SurveyItem[]): [string, SurveyItem[]][] {
  const map = new Map<string, SurveyItem[]>();
  for (const it of items) {
    const k = it.lens || '기타';
    const arr = map.get(k);
    if (arr) arr.push(it); else map.set(k, [it]);
  }
  return Array.from(map.entries());
}

// 포함 가능한 질문지 종류 (초기 설정에서 선택).
const TYPE_OPTIONS = [
  { key: 'mindlens', label: '공통 설문 (기본 소비자 특성)' },
  { key: 'domain', label: '도메인 특화 설문' },
  { key: 'interview', label: '심층 인터뷰' },
];

// 선택한 종류만 편집 가능한 형태로 시드.
function seedSurveys(types: string[]): Survey[] {
  const out: Survey[] = [];
  for (const s of DEMO_SURVEYS) {
    if (!types.includes(s.key)) continue;
    out.push({ key: s.key, title: s.title, desc: s.desc, items: s.items.map((it) => ({ id: uid(), lens: it.lens, scaleName: (it as { scaleName?: string }).scaleName, scale: it.scale, q: it.q })) });
  }
  if (types.includes('interview')) {
    out.push({
      key: 'interview',
      // 질문지 탭에서는 제목 뒤 괄호(예: "(1종, 약 60분)")를 떼고 간결하게 표시.
      title: DEMO_INTERVIEW.title.replace(/\s*\([^)]*\)\s*$/, ''),
      desc: DEMO_INTERVIEW.desc,
      items: DEMO_INTERVIEW.parts.flatMap((p) => p.questions.map((q) => ({ id: uid(), lens: `Part ${p.part}`, q }))),
    });
  }
  return out;
}

export function SurveyManager({ projectId }: { projectId: string }) {
  const { user } = useAuth();
  const isDemo = user?.role === 'demo';   // 데모면 초기 설정값을 미리 채워 '생성하기'만 누르게.
  const surveysKey = useMemo(() => `mb_surveys_${projectId}`, [projectId]);
  const infoKey = useMemo(() => `mb_survey_info_${projectId}`, [projectId]);

  const [info, setInfo] = useState<SurveyInfo | null>(null);
  const [surveys, setSurveys] = useState<Survey[]>([]);
  const [activeKey, setActiveKey] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [loaded, setLoaded] = useState(false);

  // 초기 설정 폼 상태
  const [form, setForm] = useState<SurveyInfo>({ title: '', objective: '', target: '', types: TYPE_OPTIONS.map((t) => t.key) });

  // 로드 — 정보가 저장돼 있으면 관리 화면, 없으면 초기 설정 폼.
  useEffect(() => {
    try {
      const rawInfo = sessionStorage.getItem(infoKey);
      const rawSurveys = sessionStorage.getItem(surveysKey);
      if (rawInfo) {
        setInfo(JSON.parse(rawInfo));
        setSurveys(rawSurveys ? JSON.parse(rawSurveys) : []);
      }
    } catch {}
    setLoaded(true);
  }, [infoKey, surveysKey]);

  useEffect(() => {
    if (surveys.length && !surveys.some((s) => s.key === activeKey)) setActiveKey(surveys[0].key);
  }, [surveys, activeKey]);

  // 데모: 아직 생성 전이면 초기 설정 폼을 포토이즘 의뢰 정보로 미리 채운다(생성하기만 누르면 됨).
  useEffect(() => {
    if (loaded && isDemo && !info && !form.title) {
      setForm((f) => ({
        ...f,
        title: `${DEMO_BRIEF.company} 재방문율 진단 설문`,
        objective: DEMO_BRIEF.objective,
        target: DEMO_BRIEF.target,
      }));
    }
  }, [loaded, isDemo, info, form.title]);

  const persist = useCallback((next: Survey[]) => {
    setSurveys(next);
    try { sessionStorage.setItem(surveysKey, JSON.stringify(next)); } catch {}
  }, [surveysKey]);

  // 초기 설정 제출 → 정보 저장 + 선택 종류 시드.
  const submitSetup = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (form.types.length === 0) return;
    const seeded = seedSurveys(form.types);
    setInfo(form);
    persist(seeded);
    setActiveKey(seeded[0]?.key ?? '');
    try { sessionStorage.setItem(infoKey, JSON.stringify(form)); } catch {}
  }, [form, infoKey, persist]);

  const resetAll = useCallback(() => {
    try { sessionStorage.removeItem(infoKey); sessionStorage.removeItem(surveysKey); } catch {}
    setInfo(null);
    setSurveys([]);
    setForm({ title: info?.title || '', objective: info?.objective || '', target: info?.target || '', types: TYPE_OPTIONS.map((t) => t.key) });
  }, [infoKey, surveysKey, info]);

  const totalItems = surveys.reduce((n, s) => n + s.items.length, 0);
  const active = surveys.find((s) => s.key === activeKey) ?? surveys[0];

  const updateItem = (sk: string, id: string, q: string) =>
    persist(surveys.map((s) => s.key !== sk ? s : { ...s, items: s.items.map((it) => it.id === id ? { ...it, q } : it) }));
  const removeItem = (sk: string, id: string) =>
    persist(surveys.map((s) => s.key !== sk ? s : { ...s, items: s.items.filter((it) => it.id !== id) }));
  const addItem = (sk: string, lens?: string) => {
    const it: SurveyItem = { id: uid(), lens, q: '' };
    persist(surveys.map((s) => s.key !== sk ? s : { ...s, items: [...s.items, it] }));
    setEditing(it.id);
    setDraft('');
  };
  const startEdit = (it: SurveyItem) => { setEditing(it.id); setDraft(it.q); };
  const saveEdit = (sk: string, id: string) => {
    const q = draft.trim();
    if (!q) removeItem(sk, id); else updateItem(sk, id, q);
    setEditing(null); setDraft('');
  };

  const toggleType = (key: string) =>
    setForm((f) => ({ ...f, types: f.types.includes(key) ? f.types.filter((k) => k !== key) : [...f.types, key] }));

  if (!loaded) return null;

  // ── 첫 진입: 조사 정보 입력(초기 설정) ──────────────────────────────────
  if (!info) {
    return (
      <Card padding="lg">
        <CardHeader title="질문지 초기 설정" subtitle="이 조사의 정보를 입력하면 그에 맞는 질문지를 구성합니다." />
        <form onSubmit={submitSetup} className="mt-3 space-y-4">
          <Input
            label="조사명"
            name="survey_title"
            placeholder="예: 포토이즘 재방문율 진단 설문"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            maxLength={120}
          />
          <Textarea
            label="조사 목적·주제"
            name="survey_objective"
            placeholder="예: 재방문율 하락 원인을 진단하고 회복 액션을 도출"
            value={form.objective}
            onChange={(e) => setForm((f) => ({ ...f, objective: e.target.value }))}
            rows={2}
          />
          <Textarea
            label="조사 대상"
            name="survey_target"
            placeholder="예: 최근 6개월 내 셀프 사진관을 1회 이상 이용한 20·30대"
            value={form.target}
            onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
            rows={2}
          />
          <div>
            <p className="mb-1.5 text-xs font-medium text-text-secondary">포함할 질문지 종류</p>
            <div className="flex flex-wrap gap-2">
              {TYPE_OPTIONS.map((t) => {
                const on = form.types.includes(t.key);
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => toggleType(t.key)}
                    className={
                      'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ' +
                      (on
                        ? 'border-ditto-indigo bg-ditto-indigo-light text-ditto-indigo'
                        : 'border-border text-text-muted hover:border-ditto-indigo')
                    }
                  >
                    {on ? '✓ ' : ''}{t.label}
                  </button>
                );
              })}
            </div>
          </div>
          <Button type="submit" disabled={form.types.length === 0}>질문지 생성</Button>
        </form>
      </Card>
    );
  }

  // ── 관리 화면: 종류별 탭 + 문항 편집 ───────────────────────────────────
  return (
    <div className="space-y-4">
      <Card padding="md">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text-primary">{info.title || '(제목 없는 조사)'}</p>
            {info.objective && <p className="mt-0.5 text-xs text-text-muted">목적 · {info.objective}</p>}
            {info.target && <p className="text-xs text-text-muted">대상 · {info.target}</p>}
          </div>
          <Button size="sm" variant="ghost" onClick={resetAll}>조사 정보 재설정</Button>
        </div>
      </Card>

      <p className="text-sm text-text-secondary">
        질문지 <strong className="text-text-primary">{surveys.length}</strong>종 ·
        문항 <strong className="text-text-primary">{totalItems}</strong>개. 종류 탭에서 문항을 수정·추가·삭제할 수 있어요.
      </p>

      {/* 질문 종류별 탭 */}
      <div className="flex flex-wrap gap-1 border-b border-border">
        {surveys.map((s) => (
          <button
            key={s.key}
            onClick={() => setActiveKey(s.key)}
            className={
              'px-3 py-2 text-sm font-semibold transition-colors -mb-px border-b-2 ' +
              (s.key === active?.key
                ? 'border-ditto-indigo text-ditto-indigo'
                : 'border-transparent text-text-muted hover:text-text-primary')
            }
          >
            {s.title} <span className="text-2xs text-text-muted">({s.items.length})</span>
          </button>
        ))}
      </div>

      {active && (
        <Card padding="md">
          <CardHeader
            title={active.title}
            subtitle={active.desc}
            action={<Badge variant="neutral" size="sm">{active.items.length}문항</Badge>}
          />
          {active.items.length === 0 ? (
            <p className="mt-3 rounded-lg border border-dashed border-border p-3 text-center text-xs text-text-muted">
              이 종류에는 아직 문항이 없습니다.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {groupByLens(active.items).map(([lensKey, items]) => (
                <details
                  key={lensKey}
                  open={active.items.length <= 24}
                  className="group rounded-lg border border-border bg-bg/40"
                >
                  <summary className="flex cursor-pointer select-none items-center gap-1.5 px-3 py-2 text-sm font-semibold text-text-primary">
                    <span className="text-text-muted transition-transform group-open:rotate-90">▸</span>
                    {SURVEY_LENS_LABELS[lensKey] ?? lensKey}
                    <span className="text-2xs font-normal text-text-muted">({items.length}문항)</span>
                  </summary>
                  <ul className="space-y-2 px-3 pb-3">
                    {items.map((it) => (
                      <li key={it.id} className="rounded-lg border border-border bg-surface p-2.5">
                        <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          {it.scaleName && <span className="text-2xs font-medium text-text-secondary">{it.scaleName}</span>}
                          {it.scale && <span className="text-2xs text-text-muted">· {it.scale}</span>}
                        </div>
                        {editing === it.id ? (
                          <div className="space-y-2">
                            <Textarea name={`q_${it.id}`} value={draft} onChange={(e) => setDraft(e.target.value)} rows={2} autoFocus />
                            <div className="flex items-center gap-2">
                              <Button size="sm" onClick={() => saveEdit(active.key, it.id)}>저장</Button>
                              <Button size="sm" variant="ghost" onClick={() => { setEditing(null); setDraft(''); }}>취소</Button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-text-secondary">{it.q || <span className="text-text-muted">(빈 문항)</span>}</p>
                            <div className="flex shrink-0 gap-1">
                              <button onClick={() => startEdit(it)} className="text-2xs text-text-muted hover:text-ditto-indigo">수정</button>
                              <button onClick={() => removeItem(active.key, it.id)} className="text-2xs text-text-muted hover:text-error">삭제</button>
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                    <li>
                      <button
                        onClick={() => addItem(active.key, lensKey === '기타' ? undefined : lensKey)}
                        className="rounded-lg border border-dashed border-border px-3 py-1.5 text-2xs font-medium text-text-muted hover:border-ditto-indigo hover:text-ditto-indigo"
                      >
                        + {SURVEY_LENS_LABELS[lensKey] ?? lensKey}에 문항 추가
                      </button>
                    </li>
                  </ul>
                </details>
              ))}
            </div>
          )}
        </Card>
      )}

      <p className="text-2xs text-text-muted">
        ※ 현재 편집 내용은 이 브라우저 세션에만 저장됩니다. (서버 영속 저장은 후속 작업)
      </p>
    </div>
  );
}
