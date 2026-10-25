import { useEffect, useState } from 'react';
import { Topbar } from '../components/Topbar';
import { Sidebar } from '../components/Sidebar';
import { Viewport } from '../components/Viewport';
import { exampleConfig } from '../config/example';
import { parseRoomConfig, type RoomConfig } from '../config/schema';
import { useAppStore } from '../store';
import { View2D } from '../views/View2D';

const STORAGE = 'roomtone-config-v1';
const bundledModels = new Map(exampleConfig.equipment.filter(item => item.modelUrl).map(item => [item.id, item.modelUrl!]));

function withBundledModels(room: RoomConfig): RoomConfig {
  return { ...room, equipment: room.equipment.map(item =>
    item.modelUrl || !bundledModels.has(item.id) ? item : { ...item, modelUrl: bundledModels.get(item.id) }) };
}

function savedConfig(): RoomConfig {
  try {
    const saved = localStorage.getItem(STORAGE);
    return saved ? withBundledModels(parseRoomConfig(JSON.parse(saved))) : exampleConfig;
  } catch {
    return exampleConfig;
  }
}

interface Props {
  roomId: string | null;
  initialView: '3d' | '2d';
  navigate: (search: string) => void;
}

export function Viewer({ roomId, initialView, navigate }: Props) {
  const [config, setConfig] = useState(savedConfig);
  const [walls, setWalls] = useState(true);
  const [ceiling, setCeiling] = useState(config.room.showCeiling);
  const [projection, setProjection] = useState(true);
  const [seatView, setSeatView] = useState(false);
  const [topView, setTopView] = useState(false);
  const [notice, setNotice] = useState('');
  const { room, selected, viewMode, stage, error, setSelected, setViewMode, loadRoom, useDemoRoom } = useAppStore();

  useEffect(() => { localStorage.setItem(STORAGE, JSON.stringify(config)); }, [config]);
  useEffect(() => { setViewMode(initialView); }, [initialView, setViewMode]);
  useEffect(() => {
    if (roomId && useAppStore.getState().room?.room_id !== roomId) void loadRoom(roomId);
  }, [roomId, loadRoom]);

  const importJson = async (file?: File) => {
    if (!file) return;
    try {
      const next = withBundledModels(parseRoomConfig(JSON.parse(await file.text())));
      setConfig(next);
      setCeiling(next.room.showCeiling);
      setSelected(null);
      setNotice('Configuration loaded');
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Invalid configuration');
    }
  };
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'room-config.json';
    link.click();
    URL.revokeObjectURL(url);
  };
  const demo = async () => {
    await useDemoRoom();
    const current = useAppStore.getState();
    if (current.room && current.stage !== 'error') navigate(`?room=${encodeURIComponent(current.room.room_id)}&view=${viewMode}`);
  };
  const chooseView = (mode: '3d' | '2d') => {
    setViewMode(mode);
    navigate(room ? `?room=${encodeURIComponent(room.room_id)}&view=${mode}` : mode === '2d' ? '?view=2d' : '');
  };

  return <main className="app-shell">
    <Topbar loading={stage === 'loading'} viewMode={viewMode} onDemo={() => void demo()} onPair={() => navigate('?pair')}
      onOpenRoom={id => navigate(`?room=${encodeURIComponent(id)}&view=${viewMode}`)}
      onView={chooseView} onImport={file => void importJson(file)} onExport={exportJson} />
    {error && <div className="api-error" role="alert">{error} <button onClick={() => roomId ? void loadRoom(roomId) : void demo()}>Retry</button></div>}
    <div className="workspace">
      <Sidebar config={config} room={room} selected={selected} projection={projection} onSelect={setSelected} onProjection={() => setProjection(value => !value)} />
      {viewMode === '2d' ? <View2D /> : <Viewport config={config} selected={selected} walls={walls} ceiling={ceiling} projection={projection}
        seatView={seatView} topView={topView} notice={notice} onSelect={setSelected} onWalls={() => setWalls(value => !value)}
        onCeiling={() => { setCeiling(value => !value); setConfig(current => ({ ...current, room: { ...current.room, showCeiling: !current.room.showCeiling } })); }}
        onSeatView={setSeatView} onTopView={setTopView} onNotice={setNotice} />}
    </div>
  </main>;
}
