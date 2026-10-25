import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, type Room } from '../src/api/client';
import { useAppStore } from '../src/store';

const oldRoom = { room_id: 'r_old' } as Room;

afterEach(() => {
  vi.restoreAllMocks();
  useAppStore.setState({ room: null, layout: null, metrics: null, selected: null, stage: 'idle', error: null });
});

describe('room loading', () => {
  it('clears another room before fetch and keeps it cleared if navigation fails', async () => {
    useAppStore.setState({
      room: oldRoom,
      layout: { speakers: [] },
      metrics: { score: 90 },
      selected: 'speaker_L',
    });
    let rejectRoom!: (error: Error) => void;
    vi.spyOn(api, 'getRoom').mockReturnValue(new Promise((_resolve, reject) => { rejectRoom = reject; }));

    const loading = useAppStore.getState().loadRoom('r_new');
    expect(useAppStore.getState()).toMatchObject({
      room: null, layout: null, metrics: null, selected: null, stage: 'loading',
    });
    rejectRoom(new Error('Room not found'));
    await loading;
    expect(useAppStore.getState()).toMatchObject({
      room: null, layout: null, metrics: null, selected: null, stage: 'error', error: 'Room not found',
    });
  });

  it('clears the previous room before a demo request resolves', async () => {
    useAppStore.setState({ room: oldRoom, layout: { speakers: [] }, metrics: { score: 90 }, selected: 'speaker_L' });
    let rejectDemo!: (error: Error) => void;
    vi.spyOn(api, 'demoRoom').mockReturnValue(new Promise((_resolve, reject) => { rejectDemo = reject; }));

    const loading = useAppStore.getState().useDemoRoom();
    expect(useAppStore.getState()).toMatchObject({ room: null, layout: null, metrics: null, selected: null });
    rejectDemo(new Error('Demo unavailable'));
    await loading;
    expect(useAppStore.getState()).toMatchObject({ room: null, layout: null, metrics: null, selected: null, stage: 'error' });
  });
});
