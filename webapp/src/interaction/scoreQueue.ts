import type { Layout, Metrics } from '../api/client';

export function createScoreQueue(score: (layout: Layout) => Promise<{ metrics: Metrics }>, apply: (metrics: Metrics) => void, delay = 100) {
  let pending: Layout | null = null;
  let running = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let sequence = 0;
  let stopped = false;
  const run = async () => {
    timer = null;
    if (running || !pending || stopped) return;
    const layout = pending;
    pending = null;
    const mine = sequence;
    running = true;
    try { const result = await score(layout); if (!stopped && mine === sequence) apply(result.metrics); }
    catch { /* A later drag can still retry scoring. */ }
    finally { running = false; if (pending && !stopped) timer = setTimeout(run, delay); }
  };
  return {
    schedule(layout: Layout) { if (stopped) return; pending = layout; sequence += 1; if (!running && !timer) timer = setTimeout(run, delay); },
    flush() { if (timer) clearTimeout(timer); timer = null; void run(); },
    stop() { stopped = true; pending = null; sequence += 1; if (timer) clearTimeout(timer); timer = null; },
  };
}
