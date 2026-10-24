export function formatFtIn(feet) {
  if (!Number.isFinite(feet)) throw new RangeError('feet must be finite');
  const inches = Math.floor(Math.abs(feet) * 12 + 0.5);
  const whole = Math.floor(inches / 12);
  const sign = feet < 0 && inches ? '-' : '';
  return `${sign}${whole}' ${inches % 12}"`;
}

export function parseFtIn(text) {
  const value = String(text).trim();
  const decimal = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.exec(value);
  if (decimal) return Number(value);
  const match = /^([+-]?)\s*(\d+)\s*(?:'|ft|-|feet)\s*(\d+(?:\.\d+)?)\s*(?:"|in|inches)?$/i.exec(value);
  if (!match || Number(match[3]) >= 12) throw new RangeError('Enter feet and inches, such as 7\' 6"');
  return (match[1] === '-' ? -1 : 1) * (Number(match[2]) + Number(match[3]) / 12);
}

export function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

export function rotatePoint(x, z, angle) {
  const cos = Math.cos(angle), sin = Math.sin(angle);
  return [x * cos - z * sin, x * sin + z * cos];
}

export function polygonToWallSegment(polygon) {
  if (!Array.isArray(polygon) || polygon.length < 2) return null;
  const points = polygon.filter(point => Array.isArray(point) && point.length >= 3);
  if (points.length < 2) return null;
  let best = null, longest = -1;
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      const a = points[i], b = points[j];
      const length = Math.hypot(b[0] - a[0], b[2] - a[2]);
      if (length > longest) { longest = length; best = [[a[0], a[2]], [b[0], b[2]]]; }
    }
  }
  return longest > 0 ? best : null;
}
