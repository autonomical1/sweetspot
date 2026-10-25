import { useEffect, useState } from 'react';
import type { Room } from '../../api/client';
import { extraApi, type PhotoTarget } from '../../api/extra';
import { formatFtIn } from '../../lib/format';
import { section } from './shared';

export function RoomPanel({ room }: { room: Room | null }) {
  const [targets, setTargets] = useState<PhotoTarget[]>([]);
  useEffect(() => { if (!room) { setTargets([]); return; } void extraApi.getPhotoTargets(room.room_id).then(setTargets).catch(() => setTargets([])); }, [room?.room_id]);
  if (!room) return <div className="panel-empty">Load a room to see its details.</div>;
  const { width, length, height } = room.dimensions;
  return <div className="panel-content"><div className="room-stats"><b>{formatFtIn(width)} × {formatFtIn(length)} × {formatFtIn(height)}</b><span>{(width * length).toFixed(0)} sq ft · {(width * length * height).toFixed(0)} cu ft</span><em>{room.source}</em></div>
    {room.warnings.length > 0 && section('Room warnings', <ul className="panel-list">{room.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>)}
    {section('Surfaces', <div className="surface-list">{room.surfaces.map(surface => <div key={surface.id}><b>{surface.kind}</b><span>{surface.material}{surface.material !== 'drywall' && <em> from photo</em>}</span><small>α {surface.absorption['500']?.toFixed(2) ?? '—'} / {surface.absorption['1000']?.toFixed(2) ?? '—'} at 500 / 1000 Hz</small></div>)}</div>)}
    {section('Photo targets', targets.length ? <ul className="panel-list">{targets.map(target => <li key={target.surface_id}>{target.label}</li>)}</ul> : <p className="muted">No photo targets available.</p>)}
  </div>;
}
