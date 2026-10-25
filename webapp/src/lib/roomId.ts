/** Accepts a bare room id ("r_abc123") or a pasted link containing `room=<id>`; returns null if unusable. */
export function parseRoomId(input: string): string | null {
  const text = input.trim();
  if (!text) return null;
  const fromLink = /[?&]room=([^&#\s]+)/.exec(text);
  const id = decodeURIComponent(fromLink ? fromLink[1] : text);
  return /^[A-Za-z0-9_-]{3,64}$/.test(id) ? id : null;
}
