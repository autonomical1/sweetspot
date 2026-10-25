import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type Layout, type Room } from './api/client';
import { useAppStore } from './store';

const room = { room_id: 'r_test', dimensions: { width: 12, length: 15, height: 9 }, listener: { position: [6, 3.6, 8], facing: [0, -1] } } as Room;
const quick: Layout = { stage: 'quick', speakers: [{ role: 'L', position: [2, 3, 2], aim: [6, 3, 8] }] };
const refined: Layout = { ...quick, stage: 'refined', speakers: [{ ...quick.speakers[0], position: [3, 3, 2] }] };

afterEach(() => {
  vi.restoreAllMocks();
  useAppStore.getState().chooseRefined(false);
  useAppStore.setState({ room: null, layout: null, metrics: null, stage: 'idle', selected: null, edited: false, refinedConflict: false, notice: null, error: null });
});

describe('refinement', () => {
  it('adopts a refined result and preserves selection', async () => {
    vi.spyOn(api, 'getOptimizeStatus').mockResolvedValue({ state: 'done', preset: '5.1', started_at: null, elapsed_s: null, error: null });
    vi.spyOn(api, 'getLayout').mockResolvedValue({ layout: refined, metrics: { score: 80 } });
    useAppStore.setState({ room, layout: quick, stage: 'quick', selected: 'L' });
    await useAppStore.getState().pollRefinement();
    expect(useAppStore.getState()).toMatchObject({ layout: refined, stage: 'refined', selected: 'L', notice: '3D layout refined' });
  });

  it('offers a choice when an edit arrives during polling', async () => {
    let resolveStatus!: (value: Awaited<ReturnType<typeof api.getOptimizeStatus>>) => void;
    vi.spyOn(api, 'getOptimizeStatus').mockReturnValue(new Promise(resolve => { resolveStatus = resolve; }));
    vi.spyOn(api, 'getLayout').mockResolvedValue({ layout: refined, metrics: { score: 80 } });
    vi.spyOn(api, 'score').mockResolvedValue({ metrics: { score: 70 } });
    useAppStore.setState({ room, layout: quick, stage: 'quick' });
    const polling = useAppStore.getState().pollRefinement();
    useAppStore.getState().moveSpeaker('L', [4, 5, 2]);
    resolveStatus({ state: 'done', preset: '5.1', started_at: null, elapsed_s: null, error: null });
    await polling;
    expect(useAppStore.getState()).toMatchObject({ refinedConflict: true, stage: 'refined' });
    expect(useAppStore.getState().layout?.speakers[0].position).toEqual([4, 3, 2]);
    useAppStore.getState().chooseRefined(false);
    expect(useAppStore.getState().layout?.speakers[0].position).toEqual([4, 3, 2]);
  });

  it('does not overlap status requests and stops after failure', async () => {
    let resolveStatus!: (value: Awaited<ReturnType<typeof api.getOptimizeStatus>>) => void;
    const status = vi.spyOn(api, 'getOptimizeStatus').mockReturnValue(new Promise(resolve => { resolveStatus = resolve; }));
    useAppStore.setState({ room, layout: quick, stage: 'quick' });
    const first = useAppStore.getState().pollRefinement();
    await useAppStore.getState().pollRefinement();
    expect(status).toHaveBeenCalledTimes(1);
    resolveStatus({ state: 'failed', preset: '5.1', started_at: null, elapsed_s: null, error: 'failed' });
    await first;
    await useAppStore.getState().pollRefinement();
    expect(status).toHaveBeenCalledTimes(1);
  });
});
