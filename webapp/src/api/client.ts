export type Vec2 = [number, number];
export type Vec3 = [number, number, number];

export interface SessionResponse {
  session_id: string;
  code: string;
  expires_at: string;
  pair_url: string;
}

export interface SessionStatus {
  session_id: string;
  status: 'waiting' | 'ready' | 'expired';
  room_id: string | null;
}

export interface Room {
  schema_version: 1;
  units: 'ft';
  room_id: string;
  session_id: string | null;
  source: 'rectangle' | 'roomplan';
  dimensions: { width: number; length: number; height: number };
  outline?: Vec2[] | null;
  surfaces: Array<{ id: string; kind: string; polygon: Vec3[]; material: string; absorption: Record<string, number> }>;
  objects: Array<{ id: string; category: string; center: Vec3; size: Vec3; rotation_y: number }>;
  listener: { position: Vec3; facing: Vec2 };
  budget: number;
  warnings: string[];
  frame: { yaw_deg: number; offset: Vec3 } | null;
  captured_room: unknown | null;
}

export interface Layout {
  speakers: Array<{
    role: string;
    position: Vec3;
    aim: Vec3;
    yaw_deg?: number;
    pitch_deg?: number;
    mount?: string;
    model_id?: string;
    distance_ft?: number;
    receiver_delay_ms?: number;
    receiver_trim_db?: number;
    [key: string]: unknown;
  }>;
  screen?: { wall_id: string; center: Vec3; width: number; height: number } | null;
  preset?: string;
  standard?: string;
  stage?: 'quick' | 'refining' | 'refined';
  [key: string]: unknown;
}

export interface Metrics {
  score?: number;
  reflections?: Array<{ speaker: string; surface_id: string; delay_ms: number; level_db: number; point: Vec3 }>;
  treatment_patches?: Array<{ surface_id: string; center: Vec3; size: Vec2 }>;
  sub_modes?: { schroeder_hz: number; axial_modes_hz: number[]; sub_position: Vec3 };
  warnings?: string[];
  engine?: unknown;
  [key: string]: unknown;
}

export interface LayoutResult { layout: Layout; metrics: Metrics }
export interface ScoreResult { metrics: Metrics }

export interface ProductAlternative {
  title: string;
  price: number;
  link: string;
  seller: string | null;
  thumbnail: string | null;
  source: string;
  specs: Record<string, string>;
  dimensions: { width: number; height: number; depth: number; source: 'listing' | 'default' } | null;
  price_delta: number;
}

export interface Product {
  role: string;
  title: string;
  price: number;
  currency: string;
  link: string;
  thumbnail: string | null;
  source: string;
  seller?: string | null;
  specs?: Record<string, string>;
  dimensions?: { width: number; height: number; depth: number; source: 'listing' | 'default' } | null;
  pair_with?: string | null;
  included_in?: string;
  alternatives?: ProductAlternative[];
}
export interface ProductsResult { budget: number; total: number; items: Product[]; warnings?: string[] }

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const data = body && typeof body === 'object' ? body as Record<string, unknown> : {};
      const nested = data.error && typeof data.error === 'object' ? data.error as Record<string, unknown> : {};
      const message = String(data.detail ?? nested.message ?? (response.status === 501 ? 'Not available yet' : `Request failed (${response.status})`));
      const code = String(nested.code ?? data.code ?? `HTTP_${response.status}`);
      const retry = response.headers.get('Retry-After');
      const retryAfter = retry === null ? null : Number.isFinite(Number(retry))
        ? Number(retry)
        : Number.isFinite(Date.parse(retry)) ? Math.max(0, Math.ceil((Date.parse(retry) - Date.now()) / 1000)) : null;
      throw new ApiError(message, response.status, code, retryAfter);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error instanceof DOMException && error.name === 'AbortError' ? 'Request timed out' : "Can't reach the server", 0, 'NETWORK');
  } finally {
    clearTimeout(timer);
  }
}

const post = <T>(path: string, body: unknown, timeoutMs?: number) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) }, timeoutMs);

export const api = {
  createSession: () => post<SessionResponse>('/sessions', {}),
  getSession: (id: string) => request<SessionStatus>(`/sessions/${encodeURIComponent(id)}`),
  demoRoom: (sessionId?: string) => post<Room>('/rooms/demo', sessionId ? { session_id: sessionId } : {}),
  getRoom: (id: string) => request<Room>(`/rooms/${encodeURIComponent(id)}`),
  optimize: (id: string, options?: Record<string, unknown>) => post<LayoutResult>(`/rooms/${encodeURIComponent(id)}/optimize`, options ? { options } : {}, 30_000),
  score: (id: string, layout: Layout) => post<ScoreResult>(`/rooms/${encodeURIComponent(id)}/score`, { layout }),
  getLayout: (id: string) => request<LayoutResult>(`/rooms/${encodeURIComponent(id)}/layout`),
  getProducts: (id: string, budget: number) => request<ProductsResult>(`/rooms/${encodeURIComponent(id)}/products?budget=${encodeURIComponent(budget)}`),
};
