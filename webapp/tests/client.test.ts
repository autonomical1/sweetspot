import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../src/api/client';

afterEach(() => vi.unstubAllGlobals());

describe('API client', () => {
  it('uses relative URLs and sends the optimize body', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ layout: { speakers: [] }, metrics: {} }), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    await api.optimize('r_abc');
    expect(fetch).toHaveBeenCalledWith('/rooms/r_abc/optimize', expect.objectContaining({ method: 'POST', body: '{}' }));
  });

  it('maps FastAPI detail and Retry-After', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Gemini is busy' }), {
      status: 429, headers: { 'Retry-After': '12' },
    })));
    await expect(api.getRoom('r_missing')).rejects.toMatchObject({ status: 429, message: 'Gemini is busy', retryAfter: 12 });
  });

  it('maps wrapped errors and network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'GONE', message: 'Expired' } }), { status: 410 })));
    await expect(api.getSession('s_old')).rejects.toMatchObject({ code: 'GONE', message: 'Expired' });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(api.demoRoom()).rejects.toEqual(new ApiError("Can't reach the server", 0, 'NETWORK'));
  });
});
