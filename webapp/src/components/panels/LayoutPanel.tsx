import type { Layout, Metrics, Room } from '../../api/client';
import { formatFtIn } from '../../lib/format';
import { position, RoleChip, section } from './shared';

interface Props { room: Room | null; layout: Layout | null; metrics: Metrics | null; onSelect: (id: string) => void }
export function LayoutPanel({ room, layout, metrics, onSelect }: Props) {
  if (!layout) return <div className="panel-empty">Place the speakers to see the layout.</div>;
  const score = Math.max(0, Math.min(100, (metrics?.score ?? 0) * 100));
  const placements = ((metrics?.engine as { placements?: Array<{ role: string; model_id?: string; toe_in_deg?: number; predicted_spl_db?: number }> } | undefined)?.placements ?? []);
  const placement = (role: string) => placements.find(item => item.role === role);
  const screen = layout.screen;
  return <div className="panel-content">
    {(layout.stage === 'quick' || layout.stage === 'refining') && <div className="panel-banner">Showing the quick layout, refining in 3D…</div>}
    <div className={`score score-${score < 40 ? 'low' : score > 75 ? 'high' : 'mid'}`}><b>{score.toFixed(1)}</b><span>/ 100</span><small>heuristic: speaker angles vs. ITU-R BS.775 and early reflections</small></div>
    {section('Speakers', <div className="speaker-list">{layout.speakers.map(speaker => {
      const detail = placement(speaker.role); const distance = speaker.distance_ft ?? (room ? Math.hypot(speaker.position[0] - room.listener.position[0], speaker.position[1] - room.listener.position[1], speaker.position[2] - room.listener.position[2]) : 0);
      return <button className="speaker-row" key={speaker.role} onClick={() => onSelect(speaker.role)}><RoleChip role={speaker.role} /><span>{position(speaker.position)}</span><small>{formatFtIn(distance)}{detail?.model_id ? ` · ${detail.model_id}` : ''}{detail?.toe_in_deg !== undefined ? ` · ${detail.toe_in_deg.toFixed(0)}° toe-in` : ''}{detail?.predicted_spl_db !== undefined ? ` · ${detail.predicted_spl_db.toFixed(0)} dB` : ''}</small></button>;
    })}</div>)}
    {screen && section('Screen', <div className="panel-copy">On {screen.wall_id.replace('wall_', '')} wall · {formatFtIn(screen.width)} × {formatFtIn(screen.height)}<br />{(screen.width * 12 / .8716).toFixed(0)}″ diagonal</div>)}
    {(metrics?.warnings ?? []).filter(warning => !warning.startsWith('INFO:')).length > 0 && section('Warnings', <ul className="panel-list">{metrics!.warnings!.filter(warning => !warning.startsWith('INFO:')).map(warning => <li key={warning}>{warning}</li>)}</ul>)}
  </div>;
}
