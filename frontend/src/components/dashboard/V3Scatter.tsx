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
 * EVAL_SPEC.md §3 임계: ≥3.0 high / 1.5~3.0 moderate / <1.5 mode collapse.
 */
export function V3Scatter({ points, distinct, height = 320, colorByCluster = true }: V3ScatterProps) {
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

  const distinctLabel =
    distinct == null ? '—' :
    distinct >= 3.0 ? `${distinct.toFixed(2)} · High diversity` :
    distinct >= 1.5 ? `${distinct.toFixed(2)} · Moderate` :
    `${distinct.toFixed(2)} · Mode collapse 의심`;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="text-sm font-semibold text-text-secondary">V3 페르소나 독립성</h3>
        <span className="text-xs text-text-muted">distinct = <span className="text-text-primary font-medium">{distinctLabel}</span></span>
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
      <p className="text-[10px] text-text-muted mt-2">
        ≥ 3.0 high diversity · 1.5~3.0 moderate · &lt; 1.5 mode collapse 의심 (EVAL_SPEC §3)
      </p>
    </div>
  );
}
