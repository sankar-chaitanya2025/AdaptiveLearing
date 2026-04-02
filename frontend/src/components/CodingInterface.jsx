// src/components/CodingInterface.jsx
// Stage 10 — Code Forge + Problem Forge in a resizable split layout.

import { useState, useRef, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import {
  ChevronDown, ChevronRight, Send, HelpCircle, RotateCcw,
  CheckCircle2, XCircle, AlertCircle, Clock, Zap, BookOpen,
  MessageSquare, Terminal, X, Loader2,
} from 'lucide-react';
import { submitSolution, requestHelp, continueDialogue } from '../services/api';

const STARTER_CODE = {
  python: `def solution(nums, target):
    # Your code here
    pass
`,
};

// ─── Markdown renderer (no external dep) ─────────────────────────────────────
function SimpleMarkdown({ text }) {
  const html = text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[h|p|u|o|l|p])/gm, '');
  return (
    <div
      className="prose"
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}

// ─── Difficulty badge ─────────────────────────────────────────────────────────
function DifficultyBadge({ score }) {
  const pct = Math.round(score * 100);
  const cls = score < 0.35 ? 'badge-emerald' : score < 0.75 ? 'badge-amber' : 'badge-red';
  const label = score < 0.35 ? 'Easy' : score < 0.75 ? 'Medium' : 'Hard';
  return <span className={`badge ${cls}`}>{label} · {pct}%</span>;
}

// ─── Test result strip ────────────────────────────────────────────────────────
function TestResultStrip({ tests }) {
  if (!tests) return null;
  const { visible_passed, visible_total, hidden_passed, hidden_total } = tests;
  const vPct = Math.round((visible_passed / visible_total) * 100);
  const hPct = hidden_total ? Math.round((hidden_passed / hidden_total) * 100) : null;
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
      <div className="badge badge-slate">
        Visible {visible_passed}/{visible_total} · {vPct}%
      </div>
      {hPct !== null && (
        <div className={`badge ${hPct === 100 ? 'badge-emerald' : hPct >= 50 ? 'badge-amber' : 'badge-red'}`}>
          Hidden {hidden_passed}/{hidden_total} · {hPct}%
        </div>
      )}
    </div>
  );
}

// ─── Feedback alert ───────────────────────────────────────────────────────────
function FeedbackAlert({ result, onClose }) {
  if (!result) return null;
  const allPassed =
    result.visible_score === 1.0 && result.hidden_score === 1.0;
  const cls = allPassed ? 'alert-success' : result.hidden_score >= 0.5 ? 'alert-warn' : 'alert-error';
  const Icon = allPassed ? CheckCircle2 : result.hidden_score >= 0.5 ? AlertCircle : XCircle;

  return (
    <div className={`alert ${cls} slide-up`} style={{ marginBottom: 0 }}>
      <Icon size={13} style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, marginBottom: 3 }}>
          {allPassed ? 'All tests passed' : 'Feedback'}
        </div>
        <div style={{ fontSize: 11, opacity: 0.85 }}>{result.feedback}</div>
      </div>
      <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', opacity: 0.6, padding: 0 }}>
        <X size={12} />
      </button>
    </div>
  );
}

// ─── Socratic Drawer ──────────────────────────────────────────────────────────
function SocraticDrawer({ open, onClose, submissionId, initialResponse }) {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (initialResponse) {
      setSessionId(initialResponse.session_id);
      setHistory(initialResponse.history || []);
    }
  }, [initialResponse]);

  useEffect(() => {
    if (open && submissionId && !initialResponse) {
      setLoading(true);
      requestHelp(submissionId).then(res => {
        setSessionId(res.session_id);
        setHistory(res.history || [
          { role: 'plato', content: res.socratic_question || res.message }
        ]);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [open, submissionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, open]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput('');
    setHistory(h => [...h, { role: 'student', content: msg }]);
    setLoading(true);
    try {
      const res = await continueDialogue(sessionId, msg);
      setHistory(h => [...h, {
        role: 'plato',
        content: res.socratic_question || res.message || 'Interesting — can you elaborate?',
      }]);
    } catch {
      setHistory(h => [...h, { role: 'plato', content: '[Connection error — please retry]' }]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      height: '55%', background: 'var(--bg-surface)',
      borderTop: '2px solid var(--accent-border)',
      display: 'flex', flexDirection: 'column', zIndex: 20,
    }}>
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Terminal size={12} color="var(--accent)" />
          <span className="panel-title">Socratic Dialogue</span>
          {sessionId && (
            <span className="badge badge-slate">session #{sessionId}</span>
          )}
        </div>
        <button onClick={onClose} className="btn btn-ghost" style={{ padding: '3px 8px' }}>
          <X size={12} />
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        {loading && history.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
            <div className="spinner" /> Connecting to Socratic engine…
          </div>
        )}
        {history.map((msg, i) => (
          <div key={i} className="chat-message">
            <div className={`chat-role ${msg.role === 'plato' ? 'text-accent' : 'text-secondary'}`}>
              {msg.role === 'plato' ? '◈ plato' : '> you'}
            </div>
            <div className={`chat-bubble ${msg.role === 'plato' ? 'plato' : 'student'}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && history.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: 11, marginLeft: 4 }}>
            <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
        <input
          className="input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Respond to the question…"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()} className="btn btn-primary" style={{ flexShrink: 0 }}>
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

// ─── Main CodingInterface ─────────────────────────────────────────────────────
export default function CodingInterface({ problem, onSubmitResult }) {
  const [code, setCode] = useState(STARTER_CODE.python);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [showDrawer, setShowDrawer] = useState(false);
  const [submissionId, setSubmissionId] = useState(null);
  const [splitPct, setSplitPct] = useState(42); // left panel %
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef(null);
  const editorRef = useRef(null);

  // ─── Resizable split drag ──────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    e.preventDefault();
    setDragging(true);
    const startX = e.clientX;
    const startPct = splitPct;
    const container = containerRef.current;

    const onMove = (me) => {
      const dx = me.clientX - startX;
      const w = container.getBoundingClientRect().width;
      const newPct = Math.min(65, Math.max(25, startPct + (dx / w) * 100));
      setSplitPct(newPct);
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [splitPct]);

  // ─── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!problem || submitting) return;
    setSubmitting(true);
    setResult(null);

    try {
      const res = await submitSolution(problem.id, code);
      setResult(res);
      setSubmissionId(res.submission_id);
      if (onSubmitResult) onSubmitResult(res);
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Help ──────────────────────────────────────────────────────────────────
  const handleHelp = () => {
    setShowDrawer(true);
  };

  if (!problem) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', flexDirection: 'column', gap: 12 }}>
        <BookOpen size={24} style={{ opacity: 0.4 }} />
        <span style={{ fontSize: 12 }}>No problem loaded</span>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

      {/* ── LEFT: Problem Forge ─────────────────────────────────────────── */}
      <div style={{ width: `${splitPct}%`, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
        
        {/* Header */}
        <div className="panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <BookOpen size={12} color="var(--text-muted)" />
            <span className="panel-title">Problem Forge</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <DifficultyBadge score={problem.difficulty} />
            <span className={`badge badge-emerald`}>{problem.topic}</span>
            <div className="tooltip-wrap">
              <HelpCircle size={13} color="var(--text-muted)" style={{ cursor: 'help' }} />
              <div className="tooltip-content">
                {problem.insight || 'Selected by ZPD router based on your capability vector and learning zone.'}
              </div>
            </div>
          </div>
        </div>

        {/* Problem body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 18px' }}>
          <h2 style={{ fontSize: 15, marginBottom: 12, fontFamily: 'var(--font-sans)', fontWeight: 600 }}>
            {problem.title}
          </h2>
          <SimpleMarkdown text={problem.statement} />
        </div>

        {/* Visible tests */}
        {problem.visible_tests?.length > 0 && (
          <div style={{ padding: '10px 18px', borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8 }}>
              Visible Tests ({problem.visible_tests.length})
            </div>
            {problem.visible_tests.map((t, i) => (
              <div key={i} style={{
                background: 'var(--bg-base)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '6px 10px',
                marginBottom: 6,
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
              }}>
                <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>
                  in: <span style={{ color: 'var(--text-secondary)' }}>{t.input}</span>
                </div>
                <div style={{ color: 'var(--text-muted)' }}>
                  out: <span style={{ color: 'var(--accent)' }}>{t.expected}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Test results strip */}
        {result?.tests && (
          <div style={{ padding: '8px 18px', borderTop: '1px solid var(--border)' }}>
            <TestResultStrip tests={result.tests} />
          </div>
        )}
      </div>

      {/* ── DRAG HANDLE ─────────────────────────────────────────────────── */}
      <div
        className={`split-handle ${dragging ? 'dragging' : ''}`}
        onMouseDown={onMouseDown}
      />

      {/* ── RIGHT: Code Forge ───────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>

        {/* Code header */}
        <div className="panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={12} color="var(--text-muted)" />
            <span className="panel-title">Code Forge</span>
            <span className="badge badge-slate">Python</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              className="btn btn-ghost"
              style={{ padding: '4px 8px', fontSize: 11 }}
              onClick={() => setCode(STARTER_CODE.python)}
              title="Reset to starter code"
            >
              <RotateCcw size={11} />
            </button>
          </div>
        </div>

        {/* Monaco Editor */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Editor
            theme="vs-dark"
            language="python"
            value={code}
            onChange={v => setCode(v || '')}
            onMount={editor => { editorRef.current = editor; }}
            options={{
              fontSize: 13,
              fontFamily: 'JetBrains Mono, Consolas, monospace',
              fontLigatures: true,
              lineNumbers: 'on',
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              tabSize: 4,
              insertSpaces: true,
              renderLineHighlight: 'line',
              padding: { top: 12, bottom: 12 },
              overviewRulerLanes: 0,
              hideCursorInOverviewRuler: true,
              scrollbar: { vertical: 'auto', horizontal: 'auto', verticalScrollbarSize: 4, horizontalScrollbarSize: 4 },
              lineDecorationsWidth: 6,
              lineNumbersMinChars: 3,
              glyphMargin: false,
            }}
          />
        </div>

        {/* Feedback strip */}
        {result && (
          <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
            <FeedbackAlert result={result} onClose={() => setResult(null)} />
          </div>
        )}

        {/* Action bar */}
        <div style={{
          padding: '8px 12px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-surface)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {result?.capability_delta && Object.keys(result.capability_delta).length > 0 && (
              <div style={{ display: 'flex', gap: 4 }}>
                {Object.entries(result.capability_delta).map(([topic, delta]) => (
                  <span key={topic} className={`badge ${delta >= 0 ? 'badge-emerald' : 'badge-red'}`}>
                    {topic} {delta >= 0 ? '+' : ''}{(delta * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-ghost"
              onClick={handleHelp}
              disabled={submitting}
            >
              <MessageSquare size={12} />
              Socratic Help
            </button>
            <button
              className={`btn btn-primary ${submitting ? 'pulse-success' : ''}`}
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? <><div className="spinner" /> Evaluating…</> : <><Zap size={12} /> Submit</>}
            </button>
          </div>
        </div>

        {/* Socratic Drawer */}
        <SocraticDrawer
          open={showDrawer}
          onClose={() => setShowDrawer(false)}
          submissionId={submissionId}
        />
      </div>
    </div>
  );
}
