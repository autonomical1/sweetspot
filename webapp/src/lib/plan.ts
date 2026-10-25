import type { Vec2, Vec3 } from '../api/client';

export interface PlanBounds { minX: number; maxX: number; minZ: number; maxZ: number; }
export interface PlanTransform { bounds: PlanBounds; viewBox: string; }
const padding = 0.75;

export function roomPlanBounds(dimensions: { width: number; length: number }, outline?: Vec2[] | null): PlanBounds {
  const points = outline?.filter(point => Number.isFinite(point[0]) && Number.isFinite(point[1])) ?? [];
  if (!points.length) return { minX: 0, maxX: dimensions.width, minZ: 0, maxZ: dimensions.length };
  return { minX: Math.min(...points.map(point => point[0])), maxX: Math.max(...points.map(point => point[0])), minZ: Math.min(...points.map(point => point[1])), maxZ: Math.max(...points.map(point => point[1])) };
}

export function roomToSvgTransform(dimensions: { width: number; length: number }, outline?: Vec2[] | null): PlanTransform {
  const bounds = roomPlanBounds(dimensions, outline);
  const width = Math.max(0.1, bounds.maxX - bounds.minX), length = Math.max(0.1, bounds.maxZ - bounds.minZ);
  return { bounds, viewBox: `${bounds.minX - padding} ${bounds.minZ - padding} ${width + padding * 2} ${length + padding * 2}` };
}

/** SVG z points grow south/down, so positive 3D y rotation is negative in SVG. */
export function objectSvgRotation(rotationYDegrees: number): number { return -rotationYDegrees; }

export function wallSegment(polygon: Vec3[]): [[number, number], [number, number]] | null {
  let best: [[number, number], [number, number]] | null = null, longest = 0;
  for (let i = 0; i < polygon.length; i += 1) for (let j = i + 1; j < polygon.length; j += 1) {
    const a = polygon[i], b = polygon[j], length = Math.hypot(b[0] - a[0], b[2] - a[2]);
    if (length > longest) { longest = length; best = [[a[0], a[2]], [b[0], b[2]]]; }
  }
  return best;
}

export function labelPosition(position: Vec3, offset = 0.36): Vec2 { return [position[0], position[2] - offset]; }
