import type { Metrics, Room } from '../../api/client';
import { formatFtIn } from '../../lib/format';
import { RoleChip, section } from './shared';

export function AcousticsPanel({ room, metrics, onSelect }: { room: Room | null; metrics: Metrics | null; onSelect: (id: string) => void }) {
  if (!metrics) return <div className="panel-empty">Acoustic details appear after placement.</div>;
  const surface = (id: string) => room?.surfaces.find(item => item.id === id);
  const reflections = [...(metrics.reflections ?? [])].sort((a, b) => b.level_db - a.level_db);
  const modes = metrics.sub_modes;
  return <div className="panel-content">
    {section('Early reflections', reflections.length ? <div className="reflection-list">{reflections.map((item, index) => {
      const target = surface(item.surface_id); const strong = item.level_db > -10 && item.delay_ms < 15;
      return <button key={`${item.speaker}-${item.surface_id}-${index}`} className={`reflection-row ${strong ? 'strong' : ''}`} onClick={() => onSelect(`${item.speaker}:${item.surface_id}`)}><RoleChip role={item.speaker} /><span>{target ? `${target.kind} · ${target.material}` : 'Room surface'}{strong && <em>strong</em>}</span><small>{item.delay_ms.toFixed(1)} ms · {item.level_db.toFixed(1)} dB</small></button>;
    })}</div> : <p className="muted">No reflection paths were returned.</p>)}
    {section('Treatment', <p className="panel-copy">Put absorption panels at the {metrics.treatment_patches?.length ?? 0} amber spots to tame the strongest early reflections.</p>)}
    {modes && section('Room modes', <><div className="mode-strip">{modes.axial_modes_hz.filter(value => value >= 20 && value <= 300).map((value, index) => <i key={index} style={{ left: `${((value - 20) / 280) * 100}%` }} title={`${value.toFixed(0)} Hz`} />)}<b style={{ left: `${((modes.schroeder_hz - 20) / 280) * 100}%` }} /></div><p className="panel-copy">Below about {modes.schroeder_hz.toFixed(0)} Hz the room's modes dominate; the sub position was chosen to even them out. Sub: {formatFtIn(modes.sub_position[0])}, {formatFtIn(modes.sub_position[2])}.</p></>)}
    <p className="model-note">2D/first-order model; materials estimated from photos; not a measurement.</p>
  </div>;
}
