export function formatFtIn(feet: number): string {
  if (!Number.isFinite(feet)) throw new RangeError('feet must be finite');
  const inches = Math.floor(Math.abs(feet) * 12 + 0.5);
  const whole = Math.floor(inches / 12);
  const sign = feet < 0 && inches ? '-' : '';
  return `${sign}${whole}' ${inches % 12}"`;
}
