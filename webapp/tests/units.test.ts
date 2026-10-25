import { describe, expect, it } from 'vitest';
import { FT_TO_M, ftToM, mToFt } from '../src/lib/units';
import { formatFtIn } from '../src/lib/format';

describe('units', () => {
  it('converts feet and meters at the boundary', () => {
    expect(FT_TO_M).toBe(0.3048);
    expect(ftToM(10)).toBeCloseTo(3.048);
    expect(mToFt(3.048)).toBeCloseTo(10);
  });

  it('formats feet and inches with rounding across foot boundaries', () => {
    expect(formatFtIn(7.5)).toBe('7\' 6"');
    expect(formatFtIn(11.999)).toBe('12\' 0"');
    expect(formatFtIn(-0.5)).toBe('-0\' 6"');
    expect(() => formatFtIn(Infinity)).toThrow(RangeError);
  });
});
