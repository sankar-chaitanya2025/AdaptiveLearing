// src/components/TopNav.jsx
// Clinical top navigation bar — always visible.

import { useState, useEffect } from 'react';
import { Code2, BarChart2, Wifi, WifiOff, Settings, Circle } from 'lucide-react';
import { checkHealth } from '../services/api';

export default function TopNav({ activeView, onNavigate }) {
  const [online, setOnline] = useState(null); // null = checking
  const [stage, setStage] = useState(null);

  useEffect(() => {
    const check = async () => {
      const data = await checkHealth();
      setOnline(!!data);
      if (data?.stage) setStage(data.stage);
    };
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <nav style={{
      height: 42,
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: 0,
      flexShrink: 0,
      userSelect: 'none',
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 24 }}>
        <div style={{
          width: 20, height: 20,
          background: 'var(--accent)',
          borderRadius: 3,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: '#020617', fontFamily: 'var(--font-mono)' }}>AL</span>
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', letterSpacing: '-0.01em' }}>
          AdaptLab
        </span>
        {stage && (
          <span className="badge badge-slate">Stage {stage}</span>
        )}
      </div>

      {/* Nav items */}
      <div style={{ display: 'flex', gap: 2 }}>
        {[
          { id: 'code',    icon: Code2,     label: 'Code Forge' },
          { id: 'dash',    icon: BarChart2, label: 'Dashboard' },
        ].map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '5px 12px',
              background: activeView === id ? 'var(--bg-elevated)' : 'transparent',
              border: '1px solid',
              borderColor: activeView === id ? 'var(--border)' : 'transparent',
              borderRadius: 'var(--radius)',
              color: activeView === id ? 'var(--text-primary)' : 'var(--text-muted)',
              fontSize: 11, fontFamily: 'var(--font-mono)',
              cursor: 'pointer', transition: 'all 0.12s',
            }}
          >
            <Icon size={11} />
            {label}
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Connection status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        {online === null ? (
          <><Circle size={8} style={{ opacity: 0.4 }} /> connecting…</>
        ) : online ? (
          <>
            <Circle size={8} fill="var(--accent)" color="var(--accent)" style={{ animation: 'pulse-emerald 2s ease-out infinite' }} />
            <span style={{ color: 'var(--accent)' }}>live</span>
          </>
        ) : (
          <>
            <WifiOff size={10} color="var(--amber)" />
            <span style={{ color: 'var(--amber)' }}>offline · mock mode</span>
          </>
        )}
      </div>
    </nav>
  );
}
