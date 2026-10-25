import { describe, expect, it } from 'vitest';
import { objectSvgRotation, roomToSvgTransform } from './plan';

describe('roomToSvgTransform', () => {
  it('keeps room coordinates in feet with a small SVG margin', () => {
    expect(roomToSvgTransform({ width: 12, length: 15 })).toEqual({ bounds: { minX: 0, maxX: 12, minZ: 0, maxZ: 15 }, viewBox: '-0.75 -0.75 13.5 16.5' });
  });
});
describe('objectSvgRotation', () => { it('flips a 90 degree room rotation in a south-down SVG plane', () => expect(objectSvgRotation(90)).toBe(-90)); });
