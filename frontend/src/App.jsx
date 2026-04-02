// src/App.jsx
// Stage 10 — AdaptLab Clinical Cockpit root layout.

import { useState, useEffect, useCallback } from 'react';
import TopNav from './components/TopNav';
import CodingInterface from './components/CodingInterface';
import CapabilityDashboard from './components/CapabilityDashboard';
import ProblemSidebar from './components/ProblemSidebar';
import { fetchCurrentProblem, fetchCapability, isBackendOnline } from './services/api';
import { mockProblem, mockCapability } from './mock/mockData';

const USER_ID = 'current'; // Replace with real auth when available

export default function App() {
  const [view, setView] = useState('code');           // 'code' | 'dash'
  const [problem, setProblem] = useState(null);
  const [capability, setCapability] = useState(null);
  const [submitResult, setSubmitResult] = useState(null);
  const [booting, setBooting] = useState(true);
  const [offline, setOffline] = useState(false);

  // ── Boot: load initial problem + capability ──────────────────────────────
  useEffect(() => {
    const boot = async () => {
      try {
        const [p, cap] = await Promise.allSettled([
          fetchCurrentProblem(),
          fetchCapability(USER_ID),
        ]);
        setProblem(p.status === 'fulfilled' ? p.value : mockProblem);
        setCapability(cap.status === 'fulfilled' ? cap.value : mockCapability);
        setOffline(!isBackendOnline());
      } catch {
        setProblem(mockProblem);
        setCapability(mockCapability);
        setOffline(true);
      } finally {
        setBooting(false);
      }
    };
    boot();
  }, []);

  // Update capability when a submission comes in
  const handleSubmitResult = useCallback((result) => {
    setSubmitResult(result);
    // Apply delta to local capability state optimistically
    if (result?.capability_delta && capability?.radar) {
      setCapability(prev => ({
        ...prev,
        radar: prev.radar.map(r => {
          const delta = result.capability_delta[r.topic] || 0;
          return { ...r, score: Math.min(1.0, Math.max(0, r.score + delta)) };
        }),
      }));
    }
  }, [capability]);

  // ── Loading screen ───────────────────────────────────────────────────────
  if (booting) {
    return (
      <div style={{
        height: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-base)', gap: 16
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--accent)',
            borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#020617', fontFamily: 'var(--font-mono)' }}>AL</span>
          </div>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
            AdaptLab
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 11 }}>
          <div className="spinner" />
          Initializing workspace…
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

      {/* Top navigation */}
      <TopNav activeView={view} onNavigate={setView} />

      {/* Offline banner */}
      {offline && (
        <div className="offline-banner">
          <span>⚠</span>
          Backend unreachable — running in mock data mode. Submissions and help requests simulate real responses.
        </div>
      )}

      {/* Main content area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Sidebar — visible in code view only */}
        {view === 'code' && (
          <ProblemSidebar
            problem={problem}
            capability={capability}
            onProblemChange={setProblem}
          />
        )}

        {/* Primary view */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {view === 'code' ? (
            <CodingInterface
              problem={problem}
              onSubmitResult={handleSubmitResult}
            />
          ) : (
            <CapabilityDashboard userId={USER_ID} />
          )}
        </div>
      </div>
    </div>
  );
}
