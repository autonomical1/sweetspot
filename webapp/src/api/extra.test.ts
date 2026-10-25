import { afterEach, describe, expect, it, vi } from 'vitest';
import { extraApi } from './extra';

afterEach(() => vi.unstubAllGlobals());

describe('extra API client', () => {
  it('requests products with the selected budget', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ budget: 500, total: 0, items: [] })));
    vi.stubGlobal('fetch', fetch);
    await extraApi.getProducts('r one', 500);
    expect(fetch).toHaveBeenCalledWith('/rooms/r%20one/products?budget=500');
  });

  it('preserves Gemini retry information', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Gemini is busy' }), { status: 429, headers: { 'Retry-After': '12' } })));
    await expect(extraApi.getMaterialsStatus('r_one')).rejects.toMatchObject({ status: 429, retryAfter: 12, message: 'Gemini is busy' });
  });
});
