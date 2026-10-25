import { useRef, useState } from 'react';
import { parseRoomId } from '../lib/roomId';
import { hasWebGL } from '../interaction/webgl';

interface Props {
  loading: boolean;
  viewMode: '3d' | '2d';
  onDemo: () => void;
  onPair: () => void;
  onOpenRoom: (roomId: string) => void;
  onView: (mode: '3d' | '2d') => void;
  onImport: (file?: File) => void;
  onExport: () => void;
}

export function Topbar({ loading, viewMode, onDemo, onPair, onOpenRoom, onView, onImport, onExport }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [roomInput, setRoomInput] = useState('');
  const [roomError, setRoomError] = useState(false);
  const openRoom = (event: React.FormEvent) => {
    event.preventDefault();
    const id = parseRoomId(roomInput);
    setRoomError(!id);
    if (id) { onOpenRoom(id); setRoomInput(''); }
  };
  return <header className="topbar">
    <div className="brand"><div className="brand-mark">S</div><div><strong>SweetSpot</strong><small>AV ROOM PLANNER</small></div></div>
    <div className="top-actions">
      <button className="quiet" onClick={onDemo} disabled={loading}>{loading ? 'Loading room…' : 'Use demo room'}</button>
      <button className="quiet" onClick={onPair}>Pair your iPhone</button>
      <div className="view-segment" aria-label="View mode">
        <button className={viewMode === '2d' ? 'active' : ''} onClick={() => onView('2d')}>2D</button>
        <button className={viewMode === '3d' ? 'active' : ''} onClick={() => onView('3d')} disabled={!hasWebGL()} title={!hasWebGL() ? '3D requires WebGL' : undefined}>3D</button>
      </div>
      <button className="quiet" onClick={() => fileRef.current?.click()}>Load room file</button>
      <form className="room-id-form" onSubmit={openRoom} aria-label="Open a scanned room by its ID">
        <input value={roomInput} onChange={event => { setRoomInput(event.target.value); setRoomError(false); }}
          placeholder="Room ID (r_xxxx)" aria-label="Room ID" aria-invalid={roomError} spellCheck={false} autoCapitalize="off" />
        <button className="quiet" type="submit" disabled={!roomInput.trim()}>Open</button>
      </form>
      <button className="primary" onClick={onExport}>Export setup</button>
      <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={event => onImport(event.target.files?.[0])} />
    </div>
  </header>;
}
