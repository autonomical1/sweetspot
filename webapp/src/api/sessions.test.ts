import { afterEach, describe, expect, it, vi } from 'vitest';
import { createSession, getSession } from './sessions';

afterEach(() => vi.unstubAllGlobals());

describe('session API', () => {
  it('creates a session through the documented endpoint without exposing the manual code', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      session_id: 's_one', code: 'SECRET', pair_url: 'https://example.test/pair/s_one', expires_at: '2030-01-01T00:00:00Z',
    })));
    vi.stubGlobal('fetch', fetch);
    await expect(createSession()).resolves.toEqual({ sessionId: 's_one', pairUrl: 'https://example.test/pair/s_one', expiresAt: '2030-01-01T00:00:00Z' });
    expect(fetch).toHaveBeenCalledWith('/sessions', expect.objectContaining({ method: 'POST', body: '{}' }));
  });

  it('gets the current session status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ session_id: 's_one', status: 'ready', room_id: 'r_one' }))));
    await expect(getSession('s_one')).resolves.toEqual({ sessionId: 's_one', status: 'ready', roomId: 'r_one' });
  });
});
