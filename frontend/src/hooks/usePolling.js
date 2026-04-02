// src/hooks/usePolling.js
import { useEffect, useRef } from 'react';

/**
 * Calls `fn` immediately and then every `intervalMs` while mounted.
 * Pauses polling when the tab is hidden to avoid unnecessary requests.
 */
export function usePolling(fn, intervalMs = 10000, enabled = true) {
  const savedFn = useRef(fn);
  useEffect(() => { savedFn.current = fn; }, [fn]);

  useEffect(() => {
    if (!enabled) return;
    let timer;

    const tick = () => savedFn.current();

    const handleVisibility = () => {
      if (document.hidden) {
        clearInterval(timer);
      } else {
        tick();
        timer = setInterval(tick, intervalMs);
      }
    };

    tick();
    timer = setInterval(tick, intervalMs);
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [intervalMs, enabled]);
}

// src/hooks/useSplitPane.js  (inline below for single import)
