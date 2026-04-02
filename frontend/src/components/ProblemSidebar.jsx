// src/components/ProblemSidebar.jsx
// Left sidebar: topic picker + active problem metadata.

import { useState } from 'react';
import { Target, ChevronRight, RefreshCw, Loader2 } from 'lucide-react';
import { TOPICS } from '../mock/mockData';
import { fetchProblemsForTopic } from '../services/api';

function zpdColor(score) {
  if (score < 0.35) return '#10b981';
  if (score < 0.75) return '#f59e0b';
  return '#ef4444';
}

export default function ProblemSidebar({ problem, onProblemChange, capability }) {
  const [loading, setLoading] = useState(null); // topic string being loaded

  const handleTopicSelect = async (topic) => {
    if (loading) return;
    setLoading(topic);
    try {
      // Build student vector from capability radar
      const studentVector = {};
      (capability?.radar || []).forEach(r => { studentVector[r.topic] = r.score; });
      const p = await fetchProblemsForTopic(topic, studentVector);
      onProblemChange(p);
    } finally {
      setLoading(null);
    }
  };

  // Score for each topic from capability vector
  const scoreMap = {};
  (capability?.radar || []).forEach(r => { scoreMap[r.topic] = r.score; });

  return (
    <div style={{
      width: 180,
      background: 'var(--bg-surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Target size={11} color="var(--text-muted)" />
          <span className="panel-title">Topics</span>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '6px 0' }}>
        {TOPICS.map(topic => {
          const score = scoreMap[topic];
          const isActive = problem?.topic === topic;
          const isLoading = loading === topic;
          const color = score !== undefined ? zpdColor(score) : 'var(--text-muted)';

          return (
            <button
              key={topic}
              onClick={() => handleTopicSelect(topic)}
              disabled={!!loading}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 14px',
                background: isActive ? 'var(--bg-elevated)' : 'transparent',
                borderLeft: `2px solid ${isActive ? 'var(--accent)' : 'transparent'}`,
                border: 'none',
                cursor: loading ? 'default' : 'pointer',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                textAlign: 'left',
                transition: 'all 0.1s',
                opacity: loading && !isLoading ? 0.5 : 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                {score !== undefined && (
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
                )}
                <span style={{ textTransform: 'capitalize', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {topic.replace(/_/g, ' ')}
                </span>
              </div>
              {isLoading ? (
                <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5, flexShrink: 0 }} />
              ) : (
                score !== undefined && (
                  <span style={{ fontSize: 9, color, flexShrink: 0 }}>
                    {Math.round(score * 100)}%
                  </span>
                )
              )}
            </button>
          );
        })}
      </div>

      {/* Current problem summary */}
      {problem && (
        <div style={{
          padding: '10px 14px',
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-base)',
        }}>
          <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 5 }}>
            Active
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.4 }}>
            {problem.title}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
            {problem.topic} · {Math.round(problem.difficulty * 100)}%
          </div>
        </div>
      )}
    </div>
  );
}
