import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, type ProductAlternative } from '../src/api/client';

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

  it('shows "Not available yet" for HTTP 501 even when the body has a detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'not implemented' }), { status: 501 })));
    await expect(api.getRoom('r_x')).rejects.toMatchObject({ status: 501, message: 'Not available yet' });
  });

  it('maps wrapped errors and network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'GONE', message: 'Expired' } }), { status: 410 })));
    await expect(api.getSession('s_old')).rejects.toMatchObject({ code: 'GONE', message: 'Expired' });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(api.demoRoom()).rejects.toEqual(new ApiError("Can't reach the server", 0, 'NETWORK'));
  });

  it('accepts product alternatives with the documented listing fields', async () => {
    const alternative: ProductAlternative = {
      title: 'Different speaker', price: 199, link: 'https://example.invalid/other',
      seller: 'Shop', thumbnail: null, source: 'google_shopping', specs: {},
      dimensions: null, price_delta: -26,
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      budget: 500, total: 225, items: [{
        role: 'L', title: 'Speaker', price: 225, currency: 'USD', link: 'https://example.invalid/pick',
        thumbnail: null, source: 'google_shopping', alternatives: [alternative],
      }],
    }), { status: 200 })));
    const result = await api.getProducts('r_one', 500);
    expect(result.items[0].alternatives?.[0]).toEqual(alternative);
    expect(result.items[0].alternatives?.[0]).not.toHaveProperty('role');
  });
});
