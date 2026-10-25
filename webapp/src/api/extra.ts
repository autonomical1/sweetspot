import { ApiError, type Product, type ProductsResult } from './client';

export interface PhotoTarget { surface_id: string; kind: string; label: string }
export interface MaterialsStatus { state: 'idle' | 'running'; started_at: string | null; elapsed_s: number | null; photos: number }

async function get<T>(path: string): Promise<T> {
  try {
    const response = await fetch(path);
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const data = body && typeof body === 'object' ? body as Record<string, unknown> : {};
      const retry = response.headers.get('Retry-After');
      const retryAfter = retry && Number.isFinite(Number(retry)) ? Number(retry) : null;
      throw new ApiError(String(data.detail ?? `Request failed (${response.status})`), response.status, `HTTP_${response.status}`, retryAfter);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error instanceof DOMException && error.name === 'AbortError' ? 'Request timed out' : "Can't reach the server", 0, 'NETWORK');
  }
}

export type { Product, ProductsResult };
export const getProducts = (roomId: string, budget: number) => get<ProductsResult>(`/rooms/${encodeURIComponent(roomId)}/products?budget=${encodeURIComponent(budget)}`);
export const getPhotoTargets = (roomId: string) => get<PhotoTarget[]>(`/rooms/${encodeURIComponent(roomId)}/photo-targets`);
export const getMaterialsStatus = (roomId: string) => get<MaterialsStatus>(`/rooms/${encodeURIComponent(roomId)}/materials/status`);
export const extraApi = { getProducts, getPhotoTargets, getMaterialsStatus };
