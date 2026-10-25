import { useEffect, useMemo, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import { formatFtIn } from '../lib/format';
import { labelPosition, objectSvgRotation, roomToSvgTransform, wallSegment } from '../lib/plan';
import { useAppStore } from '../store';

// Local until web-adapter exports its shared roleColors map.
export const roleColors: Record<string, string> = { L:'#5cddc5', R:'#5cddc5', C:'#f2c66f', LFE:'#c38ef1', LFE2:'#c38ef1', Ls:'#73a9ec', Rs:'#73a9ec', Lss:'#73a9ec', Rss:'#73a9ec', Lrs:'#73a9ec', Rrs:'#73a9ec', Ltf:'#eb8a8a', Rtf:'#eb8a8a', Ltr:'#eb8a8a', Rtr:'#eb8a8a', Ltm:'#eb8a8a', Rtm:'#eb8a8a' };
const overhead = new Set(['Ltf', 'Rtf', 'Ltr', 'Rtr', 'Ltm', 'Rtm']);

export function View2D() {
  const { room, layout, metrics, selected, setSelected } = useAppStore();
  const svgRef = useRef<SVGSVGElement>(null);
  const transform = useMemo(() => room && roomToSvgTransform(room.dimensions, room.outline), [room]);
  const speakers = layout?.speakers ?? [];
  const projector = layout?.projector as { position: number[] } | undefined;
  useEffect(() => { svgRef.current?.focus(); }, [room?.room_id]);
  if (!room || !transform) return <div className="viewport" style={{ display:'grid', placeItems:'center', color:'#89959f' }}>Load a room to see its 2D plan.</div>;
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key === 'Escape') setSelected(null);
    if (event.key === 'Tab' && speakers.length) { event.preventDefault(); const index = speakers.findIndex(speaker => speaker.role === selected); setSelected(speakers[(index + 1) % speakers.length].role); }
  };
  const { bounds, viewBox } = transform;
  return <section className="viewport" aria-label="2D room plan" style={{ position:'relative' }}>
    {layout?.stage === 'refining' && <span style={{ position:'absolute', zIndex:1, top:18, left:20, padding:'6px 9px', borderRadius:6, background:'#2b3b40', color:'#6cddc8', fontSize:11 }}>Refining 3D...</span>}
    <svg ref={svgRef} style={{ width:'100%', height:'100%', display:'block', background:'#11171e' }} viewBox={viewBox} preserveAspectRatio="xMidYMid meet" tabIndex={0} onKeyDown={onKeyDown} aria-label="Room plan in feet, north at top">
      {Array.from({ length: Math.floor(bounds.maxX) - Math.ceil(bounds.minX) + 1 }, (_, i) => Math.ceil(bounds.minX) + i).map(x => <line key={`x${x}`} x1={x} x2={x} y1={bounds.minZ} y2={bounds.maxZ} stroke={x % 5 ? '#24303a' : '#3b4a53'} strokeWidth={x % 5 ? .012 : .025} />)}
      {Array.from({ length: Math.floor(bounds.maxZ) - Math.ceil(bounds.minZ) + 1 }, (_, i) => Math.ceil(bounds.minZ) + i).map(z => <line key={`z${z}`} x1={bounds.minX} x2={bounds.maxX} y1={z} y2={z} stroke={z % 5 ? '#24303a' : '#3b4a53'} strokeWidth={z % 5 ? .012 : .025} />)}
      {room.surfaces.filter(surface => surface.kind === 'wall').map(surface => { const segment = wallSegment(surface.polygon); return segment && <line key={surface.id} x1={segment[0][0]} y1={segment[0][1]} x2={segment[1][0]} y2={segment[1][1]} stroke="#dce2df" strokeWidth=".12" strokeLinecap="round" />; })}
      {room.objects.map(object => { const [x,,z] = object.center, [width,,depth] = object.size; return <g key={object.id} transform={`translate(${x} ${z}) rotate(${objectSvgRotation(object.rotation_y)})`}><rect x={-width / 2} y={-depth / 2} width={width} height={depth} rx=".08" fill="#57616a" stroke="#aab4bd" strokeWidth=".035" /><text y=".05" textAnchor="middle" fontSize=".27" fill="#e4e9eb">{object.category}</text></g>; })}
      {metrics?.treatment_patches?.map((patch, index) => <circle key={`${patch.surface_id}-${index}`} cx={patch.center[0]} cy={patch.center[2]} r={(patch.size[0] || 1) / 2} fill="#d5a64b" fillOpacity=".55" />)}
      {layout?.screen && <line x1={layout.screen.center[0] - layout.screen.width / 2} y1={layout.screen.center[2]} x2={layout.screen.center[0] + layout.screen.width / 2} y2={layout.screen.center[2]} stroke="#f2d58d" strokeWidth=".14" />}
      {projector && <circle cx={projector.position[0]} cy={projector.position[2]} r=".16" fill="#a5dfd2" />}
      {selected && metrics?.reflections?.filter(reflection => reflection.speaker === selected).map((reflection, index) => { const speaker = speakers.find(item => item.role === selected); return speaker && <polyline key={`${reflection.surface_id}-${index}`} points={`${speaker.position[0]},${speaker.position[2]} ${reflection.point[0]},${reflection.point[2]}`} fill="none" stroke="#dca45b" strokeWidth=".035" strokeDasharray=".12 .1" />; })}
      {speakers.map(speaker => { const [x,y,z] = speaker.position, [labelX,labelZ] = labelPosition(speaker.position), isOverhead = overhead.has(speaker.role), color = roleColors[speaker.role] ?? '#aeb8c1'; return <g key={speaker.role} data-testid={`speaker-${speaker.role}`} role="button" tabIndex={-1} aria-label={`${speaker.role} speaker`} onClick={() => setSelected(speaker.role)} style={{ cursor:'pointer' }}>{!isOverhead && <line x1={x} y1={z} x2={speaker.aim[0]} y2={speaker.aim[2]} stroke={color} strokeWidth=".035" />}{isOverhead ? <circle cx={x} cy={z} r=".16" fill="none" stroke={color} strokeWidth=".07" /> : <rect x={x-.19} y={z-.19} width=".38" height=".38" rx=".05" fill={color} stroke={selected === speaker.role ? '#fff' : '#162027'} strokeWidth={selected === speaker.role ? '.07' : '.035'} />}<text x={labelX} y={labelZ} textAnchor="middle" fontSize=".28" fill="#edf2f3">{speaker.role}{isOverhead ? ` ${formatFtIn(y)}` : ''}</text></g>; })}
      <g aria-label="Listener"><circle cx={room.listener.position[0]} cy={room.listener.position[2]} r=".15" fill="#f5b75d" /><line x1={room.listener.position[0]} y1={room.listener.position[2]} x2={room.listener.position[0]+room.listener.facing[0]*.55} y2={room.listener.position[2]+room.listener.facing[1]*.55} stroke="#f5b75d" strokeWidth=".07" /></g>
      <g transform={`translate(${bounds.minX+.35} ${bounds.minZ+.65})`} fill="#d8e4e6"><text textAnchor="middle" fontSize=".38">N</text><path d="M 0 .1 L -.13 .38 L 0 .3 L .13 .38 Z" /></g>
      <g transform={`translate(${bounds.maxX-2.2} ${bounds.maxZ-.32})`} stroke="#d8e4e6" strokeWidth=".05"><line x2="2" /><line y1="-.12" y2=".12" /><line x1="2" x2="2" y1="-.12" y2=".12" /><text x="1" y="-.18" textAnchor="middle" fill="#d8e4e6" stroke="none" fontSize=".24">2 ft</text></g>
    </svg>
  </section>;
}
