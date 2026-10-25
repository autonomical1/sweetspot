import { useState } from 'react';
import type { Layout, Metrics, Room } from '../../api/client';
import { formatFtIn } from '../../lib/format';
import { position, RoleChip, section } from './shared';

interface Props { room: Room | null; layout: Layout | null; metrics: Metrics | null; onSelect: (id: string) => void; onRecompute?: (preset: string) => void; busy?: boolean }
const bases = ['2.1', '5.1', '7.1'], heights = ['None', '2', '4'];
export const presetOf = (base: string, height: string) => base === '2.1' || height === 'None' ? base : `${base}.${height}`;
function parsePreset(preset?: string) {
  const [a = '5', b = '1', c] = (preset ?? '5.1').split('.');
  return { base: `${a}.${b}`, height: c ?? 'None' };
}
function ConfigPicker({ current, busy, onRecompute }: { current?: string; busy?: boolean; onRecompute: (preset: string) => void }) {
  const initial = parsePreset(current);
  const [base, setBase] = useState(initial.base), [height, setHeight] = useState(initial.height);
  const preset = presetOf(base, height);
  const group = (label: string, values: string[], value: string, set: (value: string) => void, disabled = false) =>
    <div className="config-group" role="group" aria-label={label}><small>{label}</small>
      <div className="config-options">{values.map(item => <button key={item} type="button" className={item === value ? 'active' : ''} aria-pressed={item === value} disabled={disabled || busy} onClick={() => set(item)}>{item === 'None' ? 'None' : label === 'Height speakers' ? `.${item}` : item}</button>)}</div></div>;
  return <div className="config-picker">
    {group('Speaker layout', bases, base, setBase)}
    {group('Height speakers', heights, base === '2.1' ? 'None' : height, setHeight, base === '2.1')}
    <button type="button" className="primary" disabled={busy || preset === current} onClick={() => onRecompute(preset)}>{busy ? 'Recomputing…' : `Recompute as ${preset}`}</button>
  </div>;
}
export function LayoutPanel({ room, layout, metrics, onSelect, onRecompute, busy }: Props) {
  if (!layout) return <div className="panel-empty">Place the speakers to see the layout.</div>;
  const score = Math.max(0, Math.min(100, (metrics?.score ?? 0) * 100));
  const placements = ((metrics?.engine as { placements?: Array<{ role: string; model_id?: string; toe_in_deg?: number; predicted_spl_db?: number }> } | undefined)?.placements ?? []);
  const placement = (role: string) => placements.find(item => item.role === role);
  const screen = layout.screen;
  return <div className="panel-content">
    {onRecompute && section('Configuration', <ConfigPicker key={layout.preset} current={layout.preset} busy={busy} onRecompute={onRecompute} />)}
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
