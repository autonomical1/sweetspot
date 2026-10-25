import { create } from 'zustand';
import { api, type Layout, type Room } from './api/client';

export interface PairSession {
  id: string;
  pairUrl: string;
  expiresAt: string;
  status: 'waiting' | 'ready' | 'expired';
}

interface AppState {
  room: Room | null;
  layout: Layout | null;
  stage: 'idle' | 'loading' | 'quick' | 'refining' | 'refined' | 'error';
  selected: string | null;
  viewMode: '3d' | '2d';
  session: PairSession | null;
  error: string | null;
  setSelected: (id: string | null) => void;
  setViewMode: (mode: '3d' | '2d') => void;
  setSession: (session: PairSession | null) => void;
  loadRoom: (roomId: string) => Promise<void>;
  useDemoRoom: () => Promise<void>;
}

let generation = 0;

async function optimizeRoom(room: Room, current: () => boolean, set: (value: Partial<AppState>) => void) {
  set({ room, layout: null, stage: 'loading', error: null });
  try {
    const result = await api.optimize(room.room_id);
    if (current()) set({ layout: result.layout, stage: result.layout.stage ?? 'quick' });
  } catch (error) {
    if (current()) set({ stage: 'error', error: error instanceof Error ? error.message : 'Could not optimize room' });
  }
}

export const useAppStore = create<AppState>((set, get) => ({
  room: null,
  layout: null,
  stage: 'idle',
  selected: null,
  viewMode: '3d',
  session: null,
  error: null,
  setSelected: selected => set({ selected }),
  setViewMode: viewMode => set({ viewMode }),
  setSession: session => set({ session }),
  loadRoom: async roomId => {
    const run = ++generation;
    set({ stage: 'loading', error: null });
    try {
      const room = await api.getRoom(roomId);
      if (run === generation) await optimizeRoom(room, () => run === generation, set);
    } catch (error) {
      if (run === generation) set({ stage: 'error', error: error instanceof Error ? error.message : 'Could not load room' });
    }
  },
  useDemoRoom: async () => {
    const run = ++generation;
    set({ stage: 'loading', error: null });
    try {
      const room = await api.demoRoom();
      if (run === generation) await get().loadRoom(room.room_id);
    } catch (error) {
      if (run === generation) set({ stage: 'error', error: error instanceof Error ? error.message : 'Could not load demo room' });
    }
  },
}));
