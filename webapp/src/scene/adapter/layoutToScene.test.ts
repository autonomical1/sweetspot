import { describe, expect, it } from 'vitest';
import type { Layout, Metrics, Room } from '../../api/client';
import roomJson from '../../__fixtures__/room_demo.json';
import optimizeJson from '../../__fixtures__/optimize_demo.json';
import engine51 from '../../__fixtures__/engine_layout_5.1.json';
import engine714 from '../../__fixtures__/engine_layout_7.1.4.json';
import { layoutToScene, speakerSize } from './layoutToScene';
import { roleColors, roleFamily } from './roleColors';

const room = roomJson as unknown as Room;
const result = optimizeJson as unknown as { layout: Layout; metrics: Metrics };

describe('backend scene mapping', () => {
  it('converts feet to meters and centers the room frame', () => {
    const scene = layoutToScene(room, result.layout, result.metrics);
    expect(scene.room).toEqual({ width: 18 * .3048, length: 13 * .3048, height: 9 * .3048 });
    expect(scene.surfaces.find(s => s.id === 'wall_n')?.polygon[0]).toEqual([-9 * .3048, 0, -6.5 * .3048]);
    expect(scene.speakers[0].position[0]).toBeCloseTo((result.layout.speakers[0].position[0] - 9) * .3048);
    expect(scene.speakers).toHaveLength(result.layout.speakers.length);
    expect(scene.patches).toHaveLength(result.metrics.treatment_patches?.length ?? 0);
    expect(scene.reflections).toHaveLength(result.metrics.reflections?.length ?? 0);
  });

  it('keeps positive rotation about Y: local +x points toward -z at 90 degrees', () => {
    const rotated = { ...room, objects: [{ id: 'rotated', category: 'table', center: [9, 1, 6.5] as [number, number, number], size: [2, 2, 2] as [number, number, number], rotation_y: 90 }] };
    const object = layoutToScene(rotated, result.layout).objects[0];
    expect(object.rotation_y).toBe(90);
    expect([Math.cos(object.rotation_y * Math.PI / 180), -Math.sin(object.rotation_y * Math.PI / 180)]).toEqual([expect.closeTo(0), expect.closeTo(-1)]);
  });

  it('maps every 5.1 and 7.1.4 role family and uses fallback sizes', () => {
    const roles51 = (engine51.speakers as Array<{ channel?: string; type?: string }>).map(s => s.channel ?? s.type);
    const roles714 = (engine714.speakers as Array<{ channel?: string; type?: string }>).map(s => s.channel ?? s.type);
    expect(roles51.length).toBeGreaterThanOrEqual(5);
    expect(roles714.length).toBeGreaterThan(roles51.length);
    for (const role of ['L', 'R', 'C', 'LFE', 'Ls', 'Rs', 'Lss', 'Rss', 'Lrs', 'Rrs', 'Ltf', 'Rtf', 'Ltr', 'Rtr', 'Ltm', 'Rtm', 'LFE2']) {
      expect(roleFamily(role)).not.toBe('unknown');
      expect(roleColors[roleFamily(role)]).toMatch(/^#/);
      expect(speakerSize(role, undefined).every(value => value > 0)).toBe(true);
    }
    expect(roleFamily('future-role')).toBe('unknown');
    expect(speakerSize('future-role', undefined)).toEqual([.8 * .3048, 1.5 * .3048, .8 * .3048]);
    expect(speakerSize('L', { width: 2, height: 3, depth: 1 })).toEqual([2 * .3048, 3 * .3048, .3048]);
  });

  it('accepts unknown roles and absent optional display, seats, and sizes', () => {
    const scene = layoutToScene(room, { speakers: [{ role: 'future-role', position: [9, 3, 6], aim: [9, 3, 0] }] });
    expect(scene.speakers[0].known).toBe(false);
    expect(scene.speakers[0].color).toBe(roleColors.unknown);
    expect(scene.projector).toBeUndefined();
    expect(scene.screen).toBeUndefined();
    expect(scene.seats).toEqual([]);
  });

  it('maps the optional 3D projector and seats', () => {
    const layout = { ...result.layout, projector: { position: [9, 8, 10], aim: [9, 4, 0] }, seats: [{ row: 1, seat: 1, position: [9, 3.6, 8], ear_height: 3.6 }] } as Layout;
    const scene = layoutToScene(room, layout);
    expect(scene.projector?.position).toEqual([0, 8 * .3048, (10 - 6.5) * .3048]);
    expect(scene.seats[0].position).toEqual([0, 3.6 * .3048, (8 - 6.5) * .3048]);
  });
});
