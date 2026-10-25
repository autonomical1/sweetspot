import type { Room, Vec3 } from '../api/client';
import { mToFt } from '../lib/units';

export function clampSpeaker(position: Vec3, room: Room, margin = 0.25): Vec3 {
  const clamp = (value: number, extent: number) => Math.min(Math.max(value, margin), Math.max(margin, extent - margin));
  const x = clamp(position[0], room.dimensions.width), z = clamp(position[2], room.dimensions.length);
  const polygon = room.outline;
  if (!polygon || polygon.length < 3) return [x, position[1], z];
  const inside = (px: number, pz: number) => polygon.reduce((hit, a, i) => {
    const b = polygon[(i + 1) % polygon.length];
    return ((a[1] > pz) !== (b[1] > pz)) && px < (b[0] - a[0]) * (pz - a[1]) / (b[1] - a[1]) + a[0] ? !hit : hit;
  }, false);
  const signedArea = polygon.reduce((sum, a, i) => { const b = polygon[(i + 1) % polygon.length]; return sum + a[0] * b[1] - b[0] * a[1]; }, 0);
  let nearest: [number, number] | null = null, distance = Infinity;
  for (let i = 0; i < polygon.length; i += 1) {
    const a = polygon[i], b = polygon[(i + 1) % polygon.length];
    const dx = b[0] - a[0], dz = b[1] - a[1], length = Math.hypot(dx, dz);
    if (!length) continue;
    const t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (z - a[1]) * dz) / (length * length)));
    const edgeX = a[0] + t * dx, edgeZ = a[1] + t * dz;
    const d = Math.hypot(x - edgeX, z - edgeZ);
    if (d < distance) {
      distance = d;
      const sign = signedArea >= 0 ? 1 : -1;
      nearest = [edgeX - sign * dz / length * margin, edgeZ + sign * dx / length * margin];
    }
  }
  if (inside(x, z) && distance >= margin) return [x, position[1], z];
  if (nearest && inside(nearest[0], nearest[1])) return [clamp(nearest[0], room.dimensions.width), position[1], clamp(nearest[1], room.dimensions.length)];
  return [x, position[1], z];
}

export function svgPointToFeet(svg: SVGSVGElement, clientX: number, clientY: number): [number, number] {
  const point = svg.createSVGPoint();
  point.x = clientX; point.y = clientY;
  const matrix = svg.getScreenCTM();
  if (!matrix) throw new Error('SVG coordinates unavailable');
  const local = point.matrixTransform(matrix.inverse());
  return [local.x, local.y];
}

/** The scene adapter recenters a feet room and converts each axis to metres. */
export function sceneMetersToFeet(point: Vec3, room: Room): Vec3 {
  return [mToFt(point[0]) + room.dimensions.width / 2, mToFt(point[1]), mToFt(point[2]) + room.dimensions.length / 2];
}

export function rayAtHeight(origin: Vec3, direction: Vec3, height: number): Vec3 | null {
  if (Math.abs(direction[1]) < 1e-8) return null;
  const distance = (height - origin[1]) / direction[1];
  if (distance < 0) return null;
  return [origin[0] + direction[0] * distance, height, origin[2] + direction[2] * distance];
}
