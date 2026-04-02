// src/components/CapabilityDashboard.jsx
// Stage 10 — Capability radar, submission history, and live stats.

import { useState, useEffect, useCallback } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip as RechartTooltip,
} from 'recharts';
import {
  Cpu, TrendingUp, Clock, Target, RefreshCw, Award,
} from 'lucide-react';
import { fetchCapability, fetchSubmissionHistory } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { mockCapability, mockSubmissionHistory, TOPICS } from '../mock/mockData';

// ─── ZPD zone helpers ─────────────────────────────────────────────────────────
function zpdColor(score) {
  if (score < 0.35) return '#10b981'; // emerald — mastery
  if (score < 0.75) return '#f59e0b'; // amber   — learning zone
  return '#ef4444';                   // red     — too difficult
}

function zpdLabel(score) {
  if (score < 0.35) return 'Mastered';
  if (score < 0.75) return 'ZPD';
  return 'Frontier';
}

// ─── Custom radar dot ─────────────────────────────────────────────────────────
function ZPDDot(props) {
  const { cx, cy, payload } = props;
  const color = zpdColor(payload.score);
  return (
    <circle cx={cx} cy={cy} r={4} fill={color} stroke="var(--bg-surface)" strokeWidth={1.5} />
  );
}

// Custom radar tooltip
function RadarTooltipContent({ active, payload }) {
  if (!active || !payload?.[0]) return null;
  const { topic, score } = payload[0].payload;
  return (
    <div style={{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '6px 10px',
      fontSize: 11,
      fontFamily: 'var(--font-mono)',
    }}>
      <div style={{ color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2 }}>{topic}</div>
      <div style={{ color: zpdColor(score) }}>{(score * 100).toFixed(0)}% · {zpdLabel(score)}</div>
    </div>
  );
}

// ─── Stats row ────────────────────────────────────────────────────────────────
function StatsRow({ capability }) {
  const avgScore = capability.radar
    ? (capability.radar.reduce((s, r) => s + r.score, 0) / capability.radar.length)
    : 0;
  const masteredCount = capability.radar?.filter(r => r.score < 0.35).length || 0;

  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
      <div className="stat-box">
        <div className="stat-value" style={{ color: 'var(--accent)' }}>
          {capability.streak || 0}
        </div>
        <div className="stat-label">Day Streak</div>
      </div>
      <div className="stat-box">
        <div className="stat-value">{capability.problems_solved || 0}</div>
        <div className="stat-label">Solved</div>
      </div>
      <div className="stat-box">
        <div className="stat-value">{(avgScore * 100).toFixed(0)}%</div>
        <div className="stat-label">Avg Capability</div>
      </div>
      <div className="stat-box" style={{ flex: 1, borderRight: 'none' }}>
        <div className="stat-value" style={{ color: 'var(--accent)' }}>{masteredCount}</div>
        <div className="stat-label">Topics Mastered</div>
      </div>
    </div>
  );
}

// ─── Submission table ─────────────────────────────────────────────────────────
function SubmissionTable({ history }) {
  function scoreCell(score) {
    const pct = Math.round(score * 100);
    const color = score === 1.0 ? 'var(--accent)' : score >= 0.5 ? 'var(--amber)' : 'var(--red)';
    return <span style={{ color, fontWeight: 500 }}>{pct}%</span>;
  }

  function relTime(iso) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Problem</th>
            <th>Topic</th>
            <th>Visible</th>
            <th>Hidden</th>
            <th>Feedback</th>
            <th style={{ textAlign: 'right' }}>When</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr key={row.id}>
              <td style={{ color: 'var(--text-primary)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {row.problem}
              </td>
              <td><span className="badge badge-slate">{row.topic}</span></td>
              <td>{scoreCell(row.visible_score)}</td>
              <td>{scoreCell(row.hidden_score)}</td>
              <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
                {row.brain_a_feedback}
              </td>
              <td style={{ textAlign: 'right', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
                {relTime(row.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {history.length === 0 && (
        <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
          No submissions yet. Start solving to see your history.
        </div>
      )}
    </div>
  );
}

// ─── Topic bar ────────────────────────────────────────────────────────────────
function TopicBars({ radar }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '12px 16px' }}>
      {[...radar].sort((a, b) => a.score - b.score).map(({ topic, score }) => {
        const pct = Math.round(score * 100);
        const color = zpdColor(score);
        return (
          <div key={topic} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 90, fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0 }}>
              {topic.replace('_', ' ')}
            </div>
            <div style={{ flex: 1, height: 4, background: 'var(--bg-base)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                width: `${pct}%`, height: '100%', background: color,
                borderRadius: 2, transition: 'width 0.5s ease',
              }} />
            </div>
            <div style={{ width: 30, textAlign: 'right', fontSize: 10, color, fontWeight: 500 }}>
              {pct}%
            </div>
            <div style={{ width: 50, fontSize: 10, color: 'var(--text-muted)' }}>
              {zpdLabel(score)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main CapabilityDashboard ─────────────────────────────────────────────────
export default function CapabilityDashboard({ userId = 'current' }) {
  const [capability, setCapability] = useState(mockCapability);
  const [history, setHistory] = useState(mockSubmissionHistory);
  const [tab, setTab] = useState('radar'); // 'radar' | 'bars' | 'history'
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [cap, hist] = await Promise.allSettled([
        fetchCapability(userId),
        fetchSubmissionHistory(userId),
      ]);
      if (cap.status === 'fulfilled') setCapability(cap.value);
      if (hist.status === 'fulfilled') setHistory(hist.value);
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
    }
  }, [userId]);

  usePolling(refresh, 10000, true);

  // Radar chart data
  const radarData = (capability.radar || []).map(r => ({
    topic: r.topic.replace('_', ' '),
    score: r.score,
    fullMark: 1.0,
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* Header */}
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Cpu size={12} color="var(--accent)" />
          <span className="panel-title">Capability Dashboard</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {lastRefresh && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={refresh} disabled={loading} className="btn btn-ghost" style={{ padding: '3px 8px' }}>
            <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
        </div>
      </div>

      {/* Stats strip */}
      <StatsRow capability={capability} />

      {/* Tab selector */}
      <div style={{ padding: '10px 14px 0', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div className="tab-list" style={{ width: 'fit-content' }}>
          {[
            { id: 'radar',   label: 'Radar' },
            { id: 'bars',    label: 'Breakdown' },
            { id: 'history', label: 'History' },
          ].map(t => (
            <div
              key={t.id}
              className={`tab-item ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'radar' && (
          <div style={{ flex: 1, padding: '8px 0', display: 'flex', flexDirection: 'column' }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                <PolarGrid stroke="var(--bg-elevated)" strokeDasharray="3 3" />
                <PolarAngleAxis
                  dataKey="topic"
                  tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 1]}
                  tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
                  tickCount={4}
                  stroke="var(--border)"
                />
                <Radar
                  name="Capability"
                  dataKey="score"
                  stroke="var(--accent)"
                  fill="var(--accent)"
                  fillOpacity={0.12}
                  strokeWidth={1.5}
                  dot={<ZPDDot />}
                />
                <RechartTooltip content={<RadarTooltipContent />} />
              </RadarChart>
            </ResponsiveContainer>

            {/* ZPD legend */}
            <div style={{ display: 'flex', gap: 16, padding: '0 16px 12px', justifyContent: 'center' }}>
              {[
                { color: '#10b981', label: 'Mastered (< 35%)' },
                { color: '#f59e0b', label: 'ZPD (35–75%)' },
                { color: '#ef4444', label: 'Frontier (> 75%)' },
              ].map(z => (
                <div key={z.label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: 'var(--text-muted)' }}>
                  <span className="zpd-dot" style={{ background: z.color }} />
                  {z.label}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'bars' && (
          <div style={{ flex: 1, overflow: 'auto' }}>
            <TopicBars radar={capability.radar || []} />
          </div>
        )}

        {tab === 'history' && (
          <SubmissionTable history={Array.isArray(history) ? history : []} />
        )}
      </div>
    </div>
  );
}
