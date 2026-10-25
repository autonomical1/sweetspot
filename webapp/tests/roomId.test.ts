import { describe, expect, it } from 'vitest';
import { parseRoomId } from '../src/lib/roomId';

describe('parseRoomId', () => {
  it('accepts a bare id and trims spaces', () => {
    expect(parseRoomId('  r_1jPUQqCDd20 ')).toBe('r_1jPUQqCDd20');
  });
  it('extracts the id from a pasted link', () => {
    expect(parseRoomId('https://sweetspotav.tech/app/?room=r_abc-12&view=3d')).toBe('r_abc-12');
  });
  it('rejects empty or unsafe input', () => {
    expect(parseRoomId('')).toBeNull();
    expect(parseRoomId('r_x/../../etc')).toBeNull();
    expect(parseRoomId('a b')).toBeNull();
  });
});
