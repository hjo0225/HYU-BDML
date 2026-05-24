'use client';

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import type { ScatterPoint } from '@/lib/types';

interface V3ScatterProps {
  points: ScatterPoint[];
  distinct: number | null;
  /** 0~1 정규화 다양성 점수 (distinct / 0.47). 라벨·밴드 판정에 사용. */
  distinctNorm?: number | null;
  height?: number;
  /** cluster 별 색 분류. 같은 cluster=같은 색. */
  colorByCluster?: boolean;
}

const CLUSTER_COLORS = [
  'var(--indigo)',
  'var(--violet)',
  'var(--success)',
  'var(--warning)',
  'var(--error)',
  '#0ea5e9', // sky-500 — 5번째 cluster 폴백
];

/**
 * V3 페르소나 독립성 산점도 (PCA 2D 투영).
 * EVAL_SPEC.md §3 임계(정규화): ≥0.85 다양 / 0.50~0.85 보통 / 0.20~0.50 낮음 / <0.20 collapse.
 */
export function V3Scatter({ points, distinct, distinctNorm, height = 320, colorByCluster = true }: V3ScatterProps) {
  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center border border-dashed border-border rounded-xl bg-bg" style={{ height }}>
        <p className="text-sm text-text-muted">아직 V3 평가 데이터가 없습니다. 에이전트 상세에서 평가를 실행하세요.</p>
      </div>
    );
  }

  // cluster 별 그룹핑 — Recharts 가 series 단위로 색을 칠하기 때문
  const groups = colorByCluster
    ? Array.from(new Set(points.map(p => p.cluster ?? -1))).sort((a, b) => a - b)
    : [-1];

  const norm = distinctNorm ?? null;
  const distinctLabel =
    norm == null ? '—' :
    norm >= 0.85 ? `${Math.round(norm * 100)}% · 다양한 사람들` :
    norm >= 0.50 ? `${Math.round(norm * 100)}% · 보통` :
    norm >= 0.20 ? `${Math.round(norm * 100)}% · 서로 비슷` :
    `${Math.round(norm * 100)}% · 거의 동일 (경고)`;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-semibold text-text-secondary">에이전트 다양성 분포</h3>
        <span className="text-xs text-text-muted">점수 <span className="text-text-primary font-medium">{distinctLabel}</span></span>
      </div>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="2 2" />
            <XAxis
              type="number"
              dataKey="x"
              name="PC1"
              tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="PC2"
              tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <ZAxis type="number" range={[60, 60]} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3', stroke: 'var(--border)' }}
              contentStyle={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value, name) => {
                if (name === 'sync' && typeof value === 'number') return [value.toFixed(3), 'V1 sync'];
                return [String(value ?? ''), String(name ?? '')];
              }}
              labelFormatter={() => ''}
            />
            {groups.map((cluster, idx) => {
              const series = colorByCluster
                ? points.filter(p => (p.cluster ?? -1) === cluster)
                : points;
              const color = CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
              return (
                <Scatter
                  key={cluster}
                  name={cluster === -1 ? '미분류' : `cluster ${cluster}`}
                  data={series.map(p => ({
                    x: p.x,
                    y: p.y,
                    name: p.display_name || p.agent_id.slice(0, 6),
                    sync: p.sync ?? undefined,
                  }))}
                  fill={color}
                />
              );
            })}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-2xs text-text-muted mt-2">
        85% 이상이면 다양 · 50~85% 보통 · 20% 미만은 비슷한 사람만 모인 경고 신호
      </p>
    </div>
  );
}
