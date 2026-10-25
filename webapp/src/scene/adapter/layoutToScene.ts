import type { Layout, Metrics, Room, Vec2, Vec3 } from '../../api/client';
import { ftToM } from '../../lib/units';
import { roleColors, roleFamily } from './roleColors';

export type Point = [number, number, number];
export interface SceneModel {
  room: { width: number; length: number; height: number };
  listener: { position: Point; facing: Vec2 };
  surfaces: Array<{ id: string; kind: string; polygon: Point[]; material: string }>;
  objects: Array<{ id: string; category: string; center: Point; size: Point; rotation_y: number }>;
  speakers: Array<{ role: string; position: Point; aim: Point; size: Point; color: string; known: boolean }>;
  screen?: { id: string; wall_id: string; center: Point; width: number; height: number };
  projector?: { id: string; position: Point; aim: Point; size: Point };
  seats: Array<{ id: string; position: Point; ear_height: number }>;
  patches: Array<{ surface_id: string; center: Point; size: Vec2 }>;
  reflections: Array<{ speaker: string; point: Point; listener: Point }>;
}

export function speakerSize(role: string, size: unknown): Point {
  const supplied = size && typeof size === 'object' ? size as Record<string, unknown> : {};
  const defaults = roleFamily(role) === 'lfe' ? [.9, .9, .9] :
    roleFamily(role) === 'overhead' ? [.7, .35, .7] : [.8, 1.5, .8];
  return (['width', 'height', 'depth'] as const).map((key, i) =>
    ftToM(typeof supplied[key] === 'number' && Number.isFinite(supplied[key]) && supplied[key] > 0 ? supplied[key] : defaults[i])) as Point;
}

export function layoutToScene(room: Room, layout: Layout, metrics: Metrics | null = null): SceneModel {
  const width = ftToM(room.dimensions.width);
  const length = ftToM(room.dimensions.length);
  const point = (p: Vec3): Point => [ftToM(p[0]) - width / 2, ftToM(p[1]), ftToM(p[2]) - length / 2];
  const raw = layout as Layout & {
    projector?: { position: Vec3; aim: Vec3 } | null;
    seats?: Array<{ row?: number; seat?: number; position: Vec3; ear_height?: number }>;
  };
  const listener = point(room.listener.position);
  return {
    room: { width, length, height: ftToM(room.dimensions.height) },
    listener: { position: listener, facing: room.listener.facing },
    surfaces: room.surfaces.map(s => ({ id: s.id, kind: s.kind, polygon: s.polygon.map(point), material: s.material })),
    objects: room.objects.map(o => ({ id: o.id, category: o.category, center: point(o.center), size: o.size.map(ftToM) as Point, rotation_y: o.rotation_y })),
    speakers: layout.speakers.map(s => ({ role: s.role, position: point(s.position), aim: point(s.aim), size: speakerSize(s.role, s.size), color: roleColors[roleFamily(s.role)], known: roleFamily(s.role) !== 'unknown' })),
    ...(layout.screen ? { screen: { id: 'screen', wall_id: layout.screen.wall_id, center: point(layout.screen.center), width: ftToM(layout.screen.width), height: ftToM(layout.screen.height) } } : {}),
    ...(raw.projector ? { projector: { id: 'projector', position: point(raw.projector.position), aim: point(raw.projector.aim), size: [ftToM(1.1), ftToM(.45), ftToM(1)] } } : {}),
    seats: (raw.seats ?? []).map((s, i) => ({ id: `seat-${s.row ?? 0}-${s.seat ?? i}`, position: point(s.position), ear_height: ftToM(s.ear_height ?? 3.6) })),
    patches: (metrics?.treatment_patches ?? []).map(p => ({ surface_id: p.surface_id, center: point(p.center), size: p.size.map(ftToM) as Vec2 })),
    reflections: (metrics?.reflections ?? []).map(r => ({ speaker: r.speaker, point: point(r.point), listener })),
  };
}
