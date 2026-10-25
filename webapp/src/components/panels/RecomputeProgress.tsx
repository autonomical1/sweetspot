import { useEffect, useState } from 'react';
import { useAppStore } from '../../store';

export function RecomputeProgress() {
  const progress = useAppStore(state => state.progress);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!progress) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [progress?.startedAt, progress?.label]);
  if (!progress) return null;
  const elapsed = Math.max(0, (now - progress.startedAt) / 1000);
  const remaining = Math.max(0, Math.ceil(progress.estimate - elapsed));
  const percent = Math.min(95, (elapsed / progress.estimate) * 100);
  return <div className="recompute-progress" role="status">
    <div className="recompute-progress-label"><span>{progress.label}</span>
      <small>{remaining > 0 ? `about ${remaining} s left` : 'taking longer than usual…'}</small></div>
    <div className="recompute-progress-bar" role="progressbar" aria-label={progress.label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}>
      <div className={remaining > 0 ? '' : 'stalled'} style={{ width: `${percent}%` }} />
    </div>
  </div>;
}
