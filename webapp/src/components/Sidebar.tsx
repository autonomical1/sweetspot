import type { Room } from '../api/client';
import type { Equipment, RoomConfig } from '../config/schema';
import { formatFtIn } from '../lib/format';
import { calculateProjection } from '../scene/projection';

export const descriptions: Record<Equipment['type'], string> = {
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

export function Sidebar({ config, room, selected, projection, onSelect, onProjection }: Props) {
  const selectedItem = config.equipment.find(item => item.id === selected);
  const projector = config.equipment.find(item => item.type === 'projector');
  const screen = config.equipment.find(item => item.type === 'screen');
  const preview = projector && screen ? calculateProjection(projector, screen) : null;
  return <aside className="sidebar"><div className="side-scroll">
    <div className="section-heading"><div><span className="eyebrow">YOUR SPACE</span><h1>Room setup</h1></div><span className="live"><i /> SAVED</span></div>
    <div className="room-card"><div className="room-icon">▱</div><div className="room-meta"><b>Listening room</b>
      <span>{room
        ? `${formatFtIn(room.dimensions.width)} × ${formatFtIn(room.dimensions.length)} × ${formatFtIn(room.dimensions.height)}`
        : `${config.room.width.toFixed(1)} × ${config.room.length.toFixed(1)} × ${config.room.height.toFixed(1)} m`}</span>
      {room && <small>Backend room · feet</small>}
    </div></div>
    <div className="section-label"><span>OBJECTS FROM ROOM FILE</span></div>
    <div className="device-list">{config.equipment.map(item => <button key={item.id} className={`device-row ${selected === item.id ? 'selected' : ''}`} onClick={() => onSelect(item.id)}>
      <span className={`device-icon ${item.type}`}>{item.type === 'speaker' ? '◉' : item.type === 'projector' ? '▣' : item.type === 'screen' ? '▤' : '⌂'}</span>
      <span className="device-copy"><b>{item.name}</b><small>{item.type[0].toUpperCase() + item.type.slice(1)}</small></span><span className="row-arrow">›</span>
    </button>)}</div>
    {selectedItem ? <section className="hint-card"><div className="hint-glyph">◉</div><b>{selectedItem.type}</b><p>{selectedItem.description || descriptions[selectedItem.type]}</p></section>
      : <section className="hint-card"><div className="hint-glyph">↖</div><b>Select an object to identify it</b><p>Click an object in the room or choose one from the list.</p></section>}
    <section className="preview-card"><div className="card-title"><div><span className="eyebrow">PROJECTION</span><h3>Image preview</h3></div><button className="toggle" aria-label="Toggle projection" onClick={onProjection}><i className={projection ? 'on' : ''} /></button></div>
      {preview && projector && screen ? <><div className="projection-screen"><div className="screen-glow" /><b>{preview.supported ? `${preview.width.toFixed(2)} × ${preview.height.toFixed(2)} m` : '—'}</b><small>{preview.supported ? 'PROJECTED IMAGE' : 'NO PREVIEW'}</small></div>
        <div className={`fit-status ${preview.supported && preview.fits ? 'good' : 'bad'}`}><i />{preview.supported ? preview.fits ? 'Fits screen' : 'Image exceeds screen' : preview.reason}</div></>
        : <p className="muted">Projection information comes from the loaded room file.</p>}
    </section>
  </div><footer className="sidebar-footer"><span>ROOM CONFIGURATION <b>v{config.version}</b></span><span>READ ONLY</span></footer></aside>;
}
