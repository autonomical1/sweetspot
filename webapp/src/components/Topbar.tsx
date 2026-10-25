import { useRef } from 'react';

interface Props {
  loading: boolean;
  viewMode: '3d' | '2d';
  onDemo: () => void;
  onPair: () => void;
  onView: (mode: '3d' | '2d') => void;
  onImport: (file?: File) => void;
  onExport: () => void;
}

export function Topbar({ loading, viewMode, onDemo, onPair, onView, onImport, onExport }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  return <header className="topbar">
    <div className="brand"><div className="brand-mark">S</div><div><strong>SweetSpot</strong><small>AV ROOM PLANNER</small></div></div>
    <div className="top-actions">
      <button className="quiet" onClick={onDemo} disabled={loading}>{loading ? 'Loading room…' : 'Use demo room'}</button>
      <button className="quiet" onClick={onPair}>Pair your iPhone</button>
      <div className="view-segment" aria-label="View mode">
        <button className={viewMode === '3d' ? 'active' : ''} onClick={() => onView('3d')}>3D</button>
        <button className={viewMode === '2d' ? 'active' : ''} onClick={() => onView('2d')}>2D</button>
      </div>
      <button className="quiet" onClick={() => fileRef.current?.click()}>Load room file</button>
      <button className="primary" onClick={onExport}>Export setup</button>
      <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={event => onImport(event.target.files?.[0])} />
    </div>
  </header>;
}
