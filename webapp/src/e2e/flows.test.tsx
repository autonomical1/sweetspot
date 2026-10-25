// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import type { Layout, Metrics, Room } from '../api/client';
import { ShopPanel } from '../components/panels/ShopPanel';
import { useAppStore } from '../store';

vi.mock('../interaction/webgl', () => ({ hasWebGL: () => false }));
vi.mock('../scene/RoomCanvas', () => ({
  RoomCanvas: () => <div>{(useAppStore.getState().layout?.speakers ?? []).map(speaker => <span key={speaker.role} data-testid={`speaker-${speaker.role}`} />)}</div>,
}));
vi.mock('qrcode.react', () => ({ QRCodeSVG: ({ value }: { value: string }) => <div data-testid="qr-value" data-value={value} /> }));

const roles = ['L', 'R', 'C', 'LFE', 'Ls', 'Rs'];
const room: Room = { schema_version: 1, units: 'ft', room_id: 'r_demo', session_id: null, source: 'rectangle', dimensions: { width: 18, length: 13, height: 9 }, outline: null, surfaces: [], objects: [], listener: { position: [9, 3.6, 11.5], facing: [0, -1] }, budget: 1500, warnings: [], frame: null, captured_room: null };
function makeLayout(stage: Layout['stage'] = 'quick', suffix = ''): Layout { return { stage, speakers: roles.map((role, index) => ({ role, position: [1 + index, 3.6, 1], aim: [9, 3.6, 11], model_id: `${role}${suffix}` })) }; }
const quick = makeLayout();
const refined = makeLayout('refined', '-refined');
const metrics: Metrics = { score: 0.5262, warnings: [] };
function json(payload: unknown, init: ResponseInit = {}) { return new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' }, ...init }); }
function fakeFetch(responses: Record<string, unknown | (() => unknown)>) { return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => { const url = String(input); const key = `${init?.method ?? 'GET'} ${url}`; const value = responses[key] ?? responses[`${init?.method ?? 'GET'} ${url.split('?')[0]}`]; if (value instanceof Response) return value; if (typeof value === 'function') return json(value()); if (value !== undefined) return json(value); return json({ detail: `Unhandled ${key}` }, { status: 500 }); }); }
function demoResponses(optimize: () => { layout: Layout; metrics: Metrics } = () => ({ layout: quick, metrics })) { return { 'POST /rooms/demo': room, 'GET /rooms/r_demo': room, 'POST /rooms/r_demo/optimize': optimize }; }

beforeEach(() => {
  cleanup();
  window.history.replaceState({}, '', '/app/');
  vi.stubGlobal('fetch', fakeFetch(demoResponses()));
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {}, removeItem: () => {}, clear: () => {} });
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); useAppStore.setState({ room: null, layout: null, metrics: null, stage: 'idle', selected: null, error: null, refinedConflict: false, edited: false }); });

describe('web end-to-end flows', () => {
  it('uses demo, draws all speakers, and shows the score', async () => { render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Use demo room' })); await waitFor(() => expect(screen.getAllByTestId(/^speaker-/)).toHaveLength(6)); expect(screen.getByText('52.6')).toBeTruthy(); });

  it('accepts a refined layout unless the user edited the quick one', async () => {
    vi.stubGlobal('fetch', fakeFetch({ ...demoResponses(), 'GET /rooms/r_demo/optimize/status': { state: 'done', preset: '5.1', started_at: null, elapsed_s: 1, error: null }, 'GET /rooms/r_demo/layout': { layout: refined, metrics } }));
    render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Use demo room' })); await waitFor(() => expect(screen.getByText(/Showing the quick layout/)).toBeTruthy());
    useAppStore.getState().moveSpeaker('L', [2, 3.6, 2]); await act(async () => { await useAppStore.getState().pollRefinement(); });
    expect(screen.getByRole('dialog', { name: 'Refined layout available' })).toBeTruthy(); fireEvent.click(screen.getByRole('button', { name: 'Keep my edit' })); expect(useAppStore.getState().refinedConflict).toBe(false);
  });

  it('throttles drag scoring and ignores stale results', async () => {
    const calls: Array<(value: { metrics: Metrics }) => void> = [];
    const fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => { if (String(input).endsWith('/optimize')) return Promise.resolve(json({ layout: quick, metrics })); if (String(input).endsWith('/score')) return new Promise<Response>(resolve => { calls.push(value => resolve(json(value))); }); const key = `${init?.method ?? 'GET'} ${String(input)}`; return Promise.resolve(json((demoResponses() as Record<string, unknown>)[key] ?? room)); });
    vi.stubGlobal('fetch', fetch); render(<App />); fireEvent.click(screen.getByRole('button', { name: 'Use demo room' })); await waitFor(() => expect(useAppStore.getState().layout).not.toBeNull()); vi.useFakeTimers();
    act(() => { useAppStore.getState().moveSpeaker('L', [2, 3.6, 2]); }); expect(calls).toHaveLength(0); await act(async () => { vi.advanceTimersByTime(100); }); expect(calls).toHaveLength(1); act(() => { useAppStore.getState().moveSpeaker('L', [3, 3.6, 3]); }); await act(async () => { calls[0]({ metrics: { score: 0.1 } }); await vi.advanceTimersByTimeAsync(100); }); expect(calls).toHaveLength(2); await act(async () => { calls[1]({ metrics: { score: 0.9 } }); }); expect(useAppStore.getState().metrics?.score).toBe(0.9);
  });

  it('uses the pair URL, hides the code, and stops polling when ready', async () => {
    const fetch = fakeFetch({ 'POST /sessions': { session_id: 's_one', code: 'SECRET', pair_url: 'https://sweetspotav.tech/pair/s_one', expires_at: '2030-01-01T00:00:00Z' }, 'GET /sessions/s_one': { session_id: 's_one', status: 'ready', room_id: 'r_demo' }, ...demoResponses() }); vi.stubGlobal('fetch', fetch); window.history.replaceState({}, '', '/app/?pair'); vi.useFakeTimers(); render(<App />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); }); expect(screen.getByTestId('qr-value').getAttribute('data-value')).toBe('https://sweetspotav.tech/pair/s_one'); expect(document.body.textContent).not.toContain('SECRET'); await act(async () => { await vi.advanceTimersByTimeAsync(1500); }); expect(window.location.search).toContain('room=r_demo'); const polls = fetch.mock.calls.filter(call => String(call[0]) === '/sessions/s_one').length; await act(async () => { vi.advanceTimersByTime(3000); }); expect(fetch.mock.calls.filter(call => String(call[0]) === '/sessions/s_one')).toHaveLength(polls);
  });

  it('shows the Gemini retry countdown', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Gemini is busy' }), { status: 429, headers: { 'Retry-After': '12' } }))); render(<ShopPanel room={room} hasLayout />); fireEvent.click(screen.getByRole('button', { name: 'Get products' })); await waitFor(() => expect(screen.getByText(/retry in 12 s/)).toBeTruthy()); });

});
