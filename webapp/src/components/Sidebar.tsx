import { useState, type KeyboardEvent } from 'react';
import type { Room } from '../api/client';
import type { RoomConfig } from '../config/schema';
import { useAppStore } from '../store';
import { AcousticsPanel } from './panels/AcousticsPanel';
import { LayoutPanel } from './panels/LayoutPanel';
import './panels/panels.css';
import { RoomPanel } from './panels/RoomPanel';
import { ShopPanel } from './panels/ShopPanel';

export const descriptions = {
  speaker: 'Audio output · Sets the left or right sound channel in your room.',
  projector: 'Image source · Projects toward the configured screen.',
  screen: 'Projection surface · The image is sized against this screen.',
  seat: 'Listening position · Use this viewpoint to preview the room.',
};

interface Props {
  config: RoomConfig;
  room: Room | null;
  selected: string | null;
  projection: boolean;
  onSelect: (id: string) => void;
  onProjection: () => void;
}

const tabs = ['Layout', 'Acoustics', 'Shop', 'Room'] as const;
type Tab = typeof tabs[number];

export function Sidebar({ room, onSelect }: Props) {
  const [tab, setTab] = useState<Tab>('Layout');
  const { layout, metrics, stage, recompute } = useAppStore();
  const choose = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    setTab(tabs[next]);
    document.getElementById(`panel-tab-${tabs[next]}`)?.focus();
  };
  return <aside className="panel-sidebar">
    <div className="panel-tabs" role="tablist" aria-label="Room details">
      {tabs.map((name, index) => <button key={name} id={`panel-tab-${name}`} role="tab" aria-selected={tab === name} aria-controls={`panel-${name}`} tabIndex={tab === name ? 0 : -1} onKeyDown={event => choose(event, index)} onClick={() => setTab(name)}>{name}</button>)}
    </div>
    <div className="panel-scroll" id={`panel-${tab}`} role="tabpanel" aria-labelledby={`panel-tab-${tab}`}>
      {tab === 'Layout' && <LayoutPanel room={room} layout={layout} metrics={metrics} onSelect={onSelect} onRecompute={preset => void recompute(preset)} busy={stage === 'loading'} />}
      {tab === 'Acoustics' && <AcousticsPanel room={room} metrics={metrics} onSelect={onSelect} />}
      {tab === 'Shop' && <ShopPanel room={room} hasLayout={Boolean(layout)} />}
      {tab === 'Room' && <RoomPanel room={room} />}
    </div>
  </aside>;
}
