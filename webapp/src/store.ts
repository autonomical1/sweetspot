import { create } from 'zustand';
import { api, type Layout, type Metrics, type Room, type Vec3 } from './api/client';
import { clampSpeaker } from './interaction/coordinates';
import { createScoreQueue } from './interaction/scoreQueue';

export interface PairSession {
  id: string;
  pairUrl: string;
  expiresAt: string;
  status: 'waiting' | 'ready' | 'expired';
}

export interface Progress { label: string; startedAt: number; estimate: number }

const REFINE_BASE_SECONDS: Record<string, number> = { '2.1': 45, '5.1': 75, '5.1.2': 80, '5.1.4': 85, '7.1': 90, '7.1.2': 92, '7.1.4': 95 };
// The 3D run takes about 75 to 95 s for a 15 x 18 ft room and grows with the room; scale by volume.
export function estimateRefineSeconds(preset: string | null | undefined, room: Room | null): number {
  const base = REFINE_BASE_SECONDS[preset ?? '5.1'] ?? 85;
  const size = room ? room.dimensions.width * room.dimensions.length * room.dimensions.height : 2430;
  return Math.round(base * Math.min(3, Math.max(1, Math.sqrt(size / 2430))));
}

interface AppState {
  progress: Progress | null;
  room: Room | null;
  layout: Layout | null;
  metrics: Metrics | null;
  stage: 'idle' | 'loading' | 'quick' | 'refining' | 'refined' | 'error';
  selected: string | null;
  session: PairSession | null;
  error: string | null;
  notice: string | null;
  refinedConflict: boolean;
  edited: boolean;
  setSelected: (id: string | null) => void;
  setSession: (session: PairSession | null) => void;
  loadRoom: (roomId: string) => Promise<void>;
  useDemoRoom: () => Promise<void>;
  moveSpeaker: (role: string, position: Vec3) => void;
  finishDrag: () => void;
  nudgeListener: (dx: number, dz: number) => void;
  pollRefinement: () => Promise<void>;
  chooseRefined: (useRefined: boolean) => void;
  recompute: (preset: string) => Promise<void>;
  clearNotice: () => void;
}

let generation = 0;
let scoreQueue: ReturnType<typeof createScoreQueue> | null = null;
let editSequence = 0;
let pendingRefined: { layout: Layout; metrics: Metrics } | null = null;
let polling = false;

function resetQueue() { scoreQueue?.stop(); scoreQueue = null; editSequence += 1; pendingRefined = null; }

async function optimizeRoom(room: Room, current: () => boolean, set: (value: Partial<AppState>) => void, preset?: string) {
  const progress: Progress = { label: preset ? `Computing the ${preset} layout` : 'Computing a quick layout', startedAt: Date.now(), estimate: 45 };
  set(preset ? { stage: 'loading', error: null, progress } : { room, layout: null, metrics: null, selected: null, stage: 'loading', error: null, progress });
  try {
    const result = await api.optimize(room.room_id, preset ? { preset } : undefined);
    if (current()) set({ layout: result.layout, metrics: result.metrics, stage: result.layout.stage ?? 'quick', progress: null });
  } catch (error) {
    if (current()) set({ stage: 'error', progress: null, error: error instanceof Error ? error.message : 'Could not optimize room' });
  }
}

export const useAppStore = create<AppState>((set, get) => ({
  room: null,
  layout: null,
  metrics: null,
  stage: 'idle',
  progress: null,
  selected: null,
  session: null,
  error: null,
  notice: null,
  refinedConflict: false,
  edited: false,
  setSelected: selected => set({ selected }),
  setSession: session => set({ session }),
  clearNotice: () => set({ notice: null }),
  moveSpeaker: (role, position) => {
    const { room, layout } = get();
    if (!room || !layout || !layout.speakers.some(item => item.role === role)) return;
    const speaker = layout.speakers.find(item => item.role === role)!;
    const next: Layout = { ...layout, speakers: layout.speakers.map(item => item.role === role ? { ...item, position: clampSpeaker([position[0], speaker.position[1], position[2]], room) } : item) };
    editSequence += 1;
    set({ layout: next, edited: true });
    if (!scoreQueue) scoreQueue = createScoreQueue(value => api.score(room.room_id, value), metrics => { if (get().room?.room_id === room.room_id) set({ metrics }); });
    scoreQueue.schedule(next);
  },
  finishDrag: () => scoreQueue?.flush(),
  nudgeListener: (dx, dz) => {
    const { room, layout } = get();
    if (!room || !layout) return;
    const position = clampSpeaker([room.listener.position[0] + dx, room.listener.position[1], room.listener.position[2] + dz], room);
    const nextRoom = { ...room, listener: { ...room.listener, position } };
    editSequence += 1;
    set({ room: nextRoom, edited: true });
    // The score endpoint reads the stored listener. Local nudges are visual until the
    // listener endpoint persists them; then this score reflects the new position.
    void api.patchListener(room.room_id, nextRoom.listener).then(() => {
      if (get().room?.room_id === room.room_id && get().layout) {
        if (!scoreQueue) scoreQueue = createScoreQueue(value => api.score(room.room_id, value), metrics => set({ metrics }));
        scoreQueue.schedule(get().layout!);
      }
    }).catch(error => set({ error: error instanceof Error ? error.message : 'Could not move listener' }));
  },
  pollRefinement: async () => {
    const { room, stage } = get();
    if (polling || !room || (stage !== 'quick' && stage !== 'refining')) return;
    polling = true;
    const run = generation, edits = editSequence;
    try {
      const status = await api.getOptimizeStatus(room.room_id);
      if (run !== generation || get().room?.room_id !== room.room_id) return;
      if (status.state === 'failed') { set({ stage: 'error', progress: null, error: status.error ?? '3D refinement failed' }); return; }
      if (status.state === 'superseded') { set({ stage: 'refined', progress: null }); return; }
      if (status.state === 'queued' || status.state === 'running') {
        set({ stage: 'refining', progress: { label: `Refining the ${status.preset ?? ''} layout in 3D`.replace('  ', ' '), startedAt: Date.now() - (status.elapsed_s ?? 0) * 1000, estimate: estimateRefineSeconds(status.preset, room) } });
        return;
      }
      if (status.state !== 'done' && status.state !== 'idle') return;
      const result = await api.getLayout(room.room_id);
      if (run !== generation || get().room?.room_id !== room.room_id) return;
      if (result.layout.stage !== 'refined') return;
      if (get().edited || edits !== editSequence) {
        pendingRefined = result;
        set({ stage: 'refined', refinedConflict: true, progress: null });
      } else { scoreQueue?.stop(); scoreQueue = null; set({ layout: result.layout, metrics: result.metrics, stage: 'refined', progress: null, notice: '3D layout refined' }); }
    } catch (error) { if (run === generation) set({ error: error instanceof Error ? error.message : 'Could not check refinement' }); }
    finally { polling = false; }
  },
  chooseRefined: useRefined => {
    if (useRefined && pendingRefined) { resetQueue(); set({ ...pendingRefined, edited: false, notice: '3D layout refined' }); }
    pendingRefined = null;
    set({ refinedConflict: false });
  },
  recompute: async preset => {
    const { room } = get();
    if (!room || get().stage === 'loading') return;
    const run = ++generation;
    resetQueue();
    set({ edited: false, refinedConflict: false, notice: null });
    await optimizeRoom(room, () => run === generation, set, preset);
  },
  loadRoom: async roomId => {
    const run = ++generation;
    resetQueue();
    set({ edited: false, refinedConflict: false, notice: null });
    if (get().room?.room_id !== roomId) {
      set({ room: null, layout: null, metrics: null, selected: null, stage: 'loading', error: null });
    } else {
      set({ stage: 'loading', error: null });
    }
    try {
      const room = await api.getRoom(roomId);
      if (run === generation) await optimizeRoom(room, () => run === generation, set);
    } catch (error) {
      if (run === generation) set({ stage: 'error', error: error instanceof Error ? error.message : 'Could not load room' });
    }
  },
  useDemoRoom: async () => {
    const run = ++generation;
    resetQueue();
    set({ room: null, layout: null, metrics: null, selected: null, stage: 'loading', error: null });
    try {
      const room = await api.demoRoom();
      if (run === generation) await get().loadRoom(room.room_id);
    } catch (error) {
      if (run === generation) set({ stage: 'error', error: error instanceof Error ? error.message : 'Could not load demo room' });
    }
  },
}));
