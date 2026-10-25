import { QRCodeSVG } from 'qrcode.react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { createSession, getSession, type PairingSession } from '../api/sessions';
import './Pair.css';

const POLL_INTERVAL_MS = 1_500;
type State = 'creating' | 'waiting' | 'expired' | 'error';

function secondsRemaining(expiresAt: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1_000));
}

function formatCountdown(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

export function Pair({ onBack }: { onBack: () => void }) {
  const [session, setSession] = useState<PairingSession | null>(null);
  const [state, setState] = useState<State>('creating');
  const [message, setMessage] = useState('');
  const [now, setNow] = useState(Date.now());
  const sessionRef = useRef<PairingSession | null>(null);

  const navigateToRoom = useCallback((roomId: string) => {
    window.history.pushState({}, '', `/app/?room=${encodeURIComponent(roomId)}&view=3d`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, []);

  const startSession = useCallback(async () => {
    setState('creating'); setMessage(''); setSession(null); sessionRef.current = null;
    try {
      const next = await createSession();
      sessionRef.current = next;
      setSession(next); setNow(Date.now()); setState('waiting');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Can't create a pairing session");
      setState('error');
    }
  }, []);

  const poll = useCallback(async () => {
    const active = sessionRef.current;
    if (!active || document.hidden) return;
    try {
      const status = await getSession(active.sessionId);
      if (sessionRef.current?.sessionId !== active.sessionId) return;
      if (status.status === 'ready' && status.roomId) {
        sessionRef.current = null;
        navigateToRoom(status.roomId);
      } else if (status.status === 'expired') {
        sessionRef.current = null;
        setState('expired');
      }
    } catch (error) {
      if (sessionRef.current?.sessionId !== active.sessionId) return;
      if (error instanceof ApiError && error.status === 404) {
        sessionRef.current = null; setState('expired'); return;
      }
      setMessage(error instanceof Error ? error.message : "Can't reach the server");
      setState('error');
    }
  }, [navigateToRoom]);

  useEffect(() => { void startSession(); }, [startSession]);

  useEffect(() => {
    if (state !== 'waiting' || !session) return;
    const tick = () => {
      const current = Date.now();
      setNow(current);
      if (secondsRemaining(session.expiresAt, current) === 0) { sessionRef.current = null; setState('expired'); }
    };
    tick();
    const timer = window.setInterval(tick, 1_000);
    return () => window.clearInterval(timer);
  }, [session, state]);

  useEffect(() => {
    if (state !== 'waiting' || !session) return;
    let pollTimer: number | undefined;
    const stopPolling = () => { if (pollTimer !== undefined) window.clearInterval(pollTimer); pollTimer = undefined; };
    const startPolling = () => { if (!document.hidden && pollTimer === undefined) pollTimer = window.setInterval(() => void poll(), POLL_INTERVAL_MS); };
    const visibilityChanged = () => { stopPolling(); startPolling(); };
    startPolling();
    document.addEventListener('visibilitychange', visibilityChanged);
    return () => { stopPolling(); document.removeEventListener('visibilitychange', visibilityChanged); };
  }, [poll, session, state]);

  const retry = () => {
    if (session && state === 'error') { setMessage(''); setState('waiting'); void poll(); }
    else void startSession();
  };
  const remaining = session ? secondsRemaining(session.expiresAt, now) : 0;

  return <main className="pair-screen">
    <section className="pair-card" aria-live="polite">
      <p className="pair-eyebrow">SWEETSPOT SETUP</p><h1>Pair your iPhone</h1>
      {state === 'creating' && <p className="pair-status">Creating your QR code…</p>}
      {state === 'waiting' && session && <>
        <div className="pair-qr" aria-label="QR code for pairing your iPhone"><QRCodeSVG value={session.pairUrl} size={280} level="M" includeMargin /></div>
        <p className="pair-status">Scan this QR code with the Sweetspot app.</p>
        <p className="pair-countdown">Expires in <time>{formatCountdown(remaining)}</time></p>
      </>}
      {state === 'expired' && <><p className="pair-status">This QR code has expired.</p><button className="pair-primary" onClick={() => void startSession()}>New QR code</button></>}
      {state === 'error' && <><p className="pair-error" role="alert">{message}</p><button className="pair-primary" onClick={retry}>Retry</button></>}
      <button className="pair-back" onClick={onBack}>Back to room planner</button>
    </section>
  </main>;
}
