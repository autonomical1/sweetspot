import { api, type SessionResponse, type SessionStatus } from './client';

export interface PairingSession { sessionId: string; pairUrl: string; expiresAt: string }
export interface PairingStatus { sessionId: string; status: 'waiting' | 'ready' | 'expired'; roomId: string | null }

function toSession(response: SessionResponse): PairingSession {
  return { sessionId: response.session_id, pairUrl: response.pair_url, expiresAt: response.expires_at };
}
function toStatus(response: SessionStatus): PairingStatus {
  return { sessionId: response.session_id, status: response.status, roomId: response.room_id };
}
export async function createSession(): Promise<PairingSession> { return toSession(await api.createSession()); }
export async function getSession(sessionId: string): Promise<PairingStatus> { return toStatus(await api.getSession(sessionId)); }
