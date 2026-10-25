import { RoomCanvas } from '../scene/RoomCanvas';
import type { Equipment, RoomConfig } from '../config/schema';
import { descriptions } from './Sidebar';

interface Props {
  config: RoomConfig;
  selected: string | null;
  walls: boolean;
  ceiling: boolean;
  projection: boolean;
  topView: boolean;
  notice: string;
  onSelect: (id: string | null) => void;
  onWalls: () => void;
  onCeiling: () => void;
  onTopView: (value: boolean) => void;
  onNotice: (value: string) => void;
}

export function Viewport(props: Props) {
  const { config, selected, walls, ceiling, projection, topView, notice } = props;
  const selectedItem: Equipment | undefined = config.equipment.find(item => item.id === selected);
  const orbit = () => props.onTopView(false);
  return <section className="canvas-area">
    <div className="canvas-top"><div><span className="eyebrow">3D VIEW</span><b>Room overview</b></div>
      <div className="canvas-tools">
        <button className={`view-btn ${!topView ? 'active' : ''}`} onClick={orbit}>⊞ <span>Orbit</span></button>
        <button className={`view-btn ${topView ? 'active' : ''}`} onClick={() => props.onTopView(true)}>⌑ <span>Top</span></button>
        <span className="tool-divider" />
        <button className={`tool-btn ${walls ? 'active' : ''}`} title="Toggle walls" onClick={props.onWalls}>▱</button>
        <button className={`tool-btn ${ceiling ? 'active' : ''}`} title="Toggle ceiling" onClick={props.onCeiling}>⌃</button>
      </div>
    </div>
    <RoomCanvas key={`${config.room.width}:${config.room.length}:${config.room.height}:${config.room.floorColor}:${config.room.wallColor}`}
      config={config} selectedId={selected} selectedName={selectedItem?.type}
      selectedDescription={selectedItem ? selectedItem.description || descriptions[selectedItem.type] : undefined}
      walls={walls} ceiling={ceiling} showProjection={projection} onSelect={props.onSelect} topView={topView} />
    <div className="canvas-bottom"><span><i />LEFT DRAG ORBIT · RIGHT DRAG PAN · SCROLL ZOOM</span>
      <button onClick={orbit}>⌖ <span>Reset view</span></button></div>
    {notice && <div className="toast" role="alert" onClick={() => props.onNotice('')}>{notice}<button>×</button></div>}
  </section>;
}
