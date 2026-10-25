import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Layout, Room } from '../api/client';
import { clampSpeaker, rayAtHeight, sceneMetersToFeet, svgPointToFeet } from './coordinates';
import { shouldPoll } from './polling';
import { createScoreQueue } from './scoreQueue';

const room = { dimensions: { width: 12, length: 15, height: 9 } } as Room;
const layout = (x: number): Layout => ({ speakers: [{ role: 'L', position: [x, 3, 2], aim: [6, 3, 9] }] });
afterEach(() => vi.useRealTimers());

describe('drag coordinates', () => {
  it('keeps speaker height, clamps within the room, and reverses scene recentering', () => {
    expect(clampSpeaker([-2, 7, 20], room)).toEqual([.25, 7, 14.75]);
    expect(sceneMetersToFeet([0, 0.9144, 0], room)).toEqual([6, 3, 7.5]);
  });
  it('keeps a dragged speaker inside a polygon outline', () => {
    const polygonRoom = { ...room, outline: [[0, 0], [12, 0], [12, 5], [5, 5], [5, 15], [0, 15]] } as Room;
    expect(clampSpeaker([9, 3, 10], polygonRoom)).toEqual([4.75, 3, 10]);
  });
  it('intersects the current height plane only in front of the camera', () => {
    expect(rayAtHeight([0, 6, 0], [1, -1, 2], 3)).toEqual([3, 3, 6]);
    expect(rayAtHeight([0, 6, 0], [1, 0, 2], 3)).toBeNull();
  });
  it('maps a pointer through the SVG screen matrix to room feet', () => {
    const svg = { createSVGPoint: () => ({ x: 0, y: 0, matrixTransform: () => ({ x: 4.5, y: 8 }) }), getScreenCTM: () => ({ inverse: () => ({}) }) } as unknown as SVGSVGElement;
    expect(svgPointToFeet(svg, 200, 300)).toEqual([4.5, 8]);
  });
});

describe('scoring queue', () => {
  it('sends one at a time and applies only the latest response', async () => {
    vi.useFakeTimers();
    const complete: Array<(value: { metrics: { score: number } }) => void> = [];
    const sent: Layout[] = [];
    const score = vi.fn((value: Layout) => { sent.push(value); return new Promise<{ metrics: { score: number } }>(resolve => complete.push(resolve)); });
    const apply = vi.fn();
    const queue = createScoreQueue(score, apply, 100);
    queue.schedule(layout(1));
    await vi.advanceTimersByTimeAsync(100);
    queue.schedule(layout(2)); queue.schedule(layout(3));
    complete[0]({ metrics: { score: 1 } }); await Promise.resolve();
    expect(apply).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(100);
    expect(score).toHaveBeenCalledTimes(2);
    expect(sent[1].speakers[0].position[0]).toBe(3);
    complete[1]({ metrics: { score: 3 } }); await Promise.resolve();
    expect(apply).toHaveBeenCalledWith({ score: 3 });
  });
  it('does not accept a response after stop', async () => {
    vi.useFakeTimers();
    let complete!: (value: { metrics: { score: number } }) => void;
    const apply = vi.fn();
    const queue = createScoreQueue(() => new Promise(resolve => { complete = resolve; }), apply, 10);
    queue.schedule(layout(1)); queue.flush(); queue.stop();
    complete({ metrics: { score: 1 } }); await Promise.resolve();
    expect(apply).not.toHaveBeenCalled();
  });
});

it('polls only while a quick result is active and the tab is visible', () => {
  expect(shouldPoll('quick', true, false)).toBe(true);
  expect(shouldPoll('refining', false, false)).toBe(false);
  expect(shouldPoll('refined', true, false)).toBe(false);
});
