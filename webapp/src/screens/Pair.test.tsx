// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { Pair } from './Pair';

const { createSession, getSession } = vi.hoisted(() => ({ createSession: vi.fn(), getSession: vi.fn() }));
vi.mock('../api/sessions', () => ({ createSession, getSession }));

const futureSession = { sessionId: 's_one', pairUrl: 'https://example.test/pair/s_one', expiresAt: '2030-01-01T00:30:00Z' };

async function flush() { await act(async () => { await Promise.resolve(); }); }

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2030-01-01T00:00:00Z'));
  window.history.replaceState({}, '', '/app/?pair');
  createSession.mockReset().mockResolvedValue(futureSession);
  getSession.mockReset().mockResolvedValue({ sessionId: 's_one', status: 'waiting', roomId: null });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe('Pair', () => {
  it('creates a session and polls every 1.5 seconds', async () => {
    render(<Pair onBack={vi.fn()} />); await flush();
    expect(createSession).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(getSession).toHaveBeenCalledWith('s_one');
  });

  it('stops polling after ready and switches to the 3D room URL', async () => {
    getSession.mockResolvedValue({ sessionId: 's_one', status: 'ready', roomId: 'r_ready' });
    render(<Pair onBack={vi.fn()} />); await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(window.location.search).toBe('?room=r_ready&view=3d');
    await act(async () => { await vi.advanceTimersByTimeAsync(3_000); });
    expect(getSession).toHaveBeenCalledTimes(1);
  });

  it('stops polling on unmount and expiry, then offers a new QR code', async () => {
    const view = render(<Pair onBack={vi.fn()} />); await flush();
    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(3_000); });
    expect(getSession).not.toHaveBeenCalled();

    render(<Pair onBack={vi.fn()} />); await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(30 * 60 * 1_000); });
    expect(screen.getByRole('button', { name: 'New QR code' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'New QR code' })); await flush();
    expect(createSession).toHaveBeenCalledTimes(3);
  });

  it('shows a retryable API error', async () => {
    createSession.mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(futureSession);
    render(<Pair onBack={vi.fn()} />); await flush();
    expect(screen.getByRole('alert').textContent).toContain('Offline');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' })); await flush();
    expect(createSession).toHaveBeenCalledTimes(2);
  });

  it('treats a missing session as expired and never renders its manual code', async () => {
    getSession.mockRejectedValue(new ApiError('Missing', 404, 'HTTP_404'));
    render(<Pair onBack={vi.fn()} />); await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1_500); });
    expect(screen.getByRole('button', { name: 'New QR code' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('SECRET');
  });
});
