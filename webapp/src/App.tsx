import { useEffect, useState } from 'react';
import { Pair } from './screens/Pair';
import { Start } from './screens/Start';
import { Viewer } from './screens/Viewer';
import { useAppStore } from './store';
import { svgPointToFeet } from './interaction/coordinates';

export default function App() {
  const [query, setQuery] = useState(() => window.location.search);
  const { refinedConflict, notice, chooseRefined, clearNotice } = useAppStore();
  useEffect(() => {
    const update = () => setQuery(window.location.search);
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);
  useEffect(() => {
    let dragging: { role: string; pointerId: number; svg: SVGSVGElement } | null = null;
    const down = (event: PointerEvent) => {
      const target = event.target as Element | null;
      const speaker = target?.closest('[data-testid^="speaker-"]');
      const svg = speaker?.closest('svg');
      if (!speaker || !(svg instanceof SVGSVGElement) || event.button !== 0) return;
      dragging = { role: speaker.getAttribute('data-testid')!.slice('speaker-'.length), pointerId: event.pointerId, svg };
      useAppStore.getState().setSelected(dragging.role);
      event.preventDefault();
    };
    const move = (event: PointerEvent) => {
      if (!dragging || event.pointerId !== dragging.pointerId) return;
      try {
        const [x, z] = svgPointToFeet(dragging.svg, event.clientX, event.clientY);
        const speaker = useAppStore.getState().layout?.speakers.find(item => item.role === dragging?.role);
        if (speaker) useAppStore.getState().moveSpeaker(dragging.role, [x, speaker.position[1], z]);
      } catch { /* SVG may have unmounted during a view switch. */ }
    };
    const up = (event: PointerEvent) => {
      if (dragging?.pointerId === event.pointerId) { dragging = null; useAppStore.getState().finishDrag(); }
    };
    const key = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches('input, textarea, select, [contenteditable="true"]')) return;
      if (event.key.startsWith('Arrow') && useAppStore.getState().room) {
        const step = event.shiftKey ? 1 : .25;
        const delta: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
        const [dx, dz] = delta[event.key];
        useAppStore.getState().nudgeListener(dx, dz); event.preventDefault();
      }
    };
    document.addEventListener('pointerdown', down, true);
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
    document.addEventListener('pointercancel', up);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('pointerdown', down, true); document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); document.removeEventListener('pointercancel', up); document.removeEventListener('keydown', key); };
  }, []);
  useEffect(() => {
    const tick = () => {
      const state = useAppStore.getState();
      if (document.visibilityState === 'visible' && (state.stage === 'quick' || state.stage === 'refining')) void state.pollRefinement();
    };
    const timer = window.setInterval(tick, 3000);
    document.addEventListener('visibilitychange', tick);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', tick); };
  }, []);
  const navigate = (search: string) => {
    window.history.pushState({}, '', `/app/${search}`);
    setQuery(window.location.search);
  };
  const params = new URLSearchParams(query);
  if (params.has('pair')) return <Pair onBack={() => navigate('')} />;
  const roomId = params.get('room');
  const page = roomId ? <Viewer roomId={roomId} navigate={navigate} /> : <Start navigate={navigate} />;
  return <>{page}{refinedConflict && <div className="toast" role="dialog" aria-label="Refined layout available" style={{ position:'fixed', zIndex:20 }}>
    Refined 3D layout is ready. <button onClick={() => chooseRefined(false)}>Keep my edit</button><button onClick={() => chooseRefined(true)}>Use refined layout</button>
  </div>}{notice && <div className="toast" role="status" style={{ position:'fixed', zIndex:20 }} onClick={clearNotice}>{notice}<button aria-label="Dismiss notice">×</button></div>}</>;
}
