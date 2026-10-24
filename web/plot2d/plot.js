import { formatFtIn, parseFtIn, clamp, polygonToWallSegment } from './format.js';

const $ = id => document.getElementById(id);
const svg = $('canvas');
const NS = 'http://www.w3.org/2000/svg';
let room = null, layout = null, metrics = null, products = null;
let bounds = { minX: 0, maxX: 12, minZ: 0, maxZ: 15 };
let selected = null, dragging = null, generation = 0;
let scoreTimer = null, scoreBusy = false, scoreQueued = false, lastScoreAt = 0;

function node(tag, attributes = {}, parent = svg, label = null) {
  const element = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (label !== null) element.textContent = label;
  parent.appendChild(element);
  return element;
}

function showError(error) {
  $('error-text').textContent = error instanceof Error ? error.message : String(error);
  $('error').hidden = false;
}
function hideError() { $('error').hidden = true; }
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch (error) { throw new Error(`Network error: ${error.message}`); }
  let data;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    let detail = data?.detail ?? response.statusText;
    if (typeof detail !== 'string') detail = JSON.stringify(detail);
    throw new Error(`${response.status}: ${detail}`);
  }
  return data;
}
const json = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
async function action(task, button) {
  hideError();
  const previousLabel = button?.textContent;
  if (button) {
    button.disabled = true; button.classList.add('busy');
    if (['btn-optimize', 'btn-reset'].includes(button.id)) button.textContent = 'Optimizing…';
    if (button.id === 'btn-products') button.textContent = 'Loading products…';
  }
  try { await task(); } catch (error) { showError(error); }
  finally { if (button) { button.textContent = previousLabel; button.classList.remove('busy'); updateControls(); } }
}
function updateControls() {
  $('btn-optimize').disabled = !room;
  $('btn-reset').disabled = !room;
  $('btn-products').disabled = !room || !layout;
}
function setRoom(nextRoom, nextLayout = null) {
  generation++;
  if (scoreTimer) clearTimeout(scoreTimer);
  scoreTimer = null; scoreQueued = false;
  room = nextRoom; layout = nextLayout?.layout ?? null; metrics = nextLayout?.metrics ?? null;
  products = null; selected = null; dragging = null;
  $('status').textContent = `Room id: ${room.room_id}`;
  $('room-id').value = room.room_id;
  $('budget').value = room.budget ?? 1500;
  updateControls(); render();
}
function setLayout(result) {
  generation++;
  if (scoreTimer) clearTimeout(scoreTimer);
  scoreTimer = null; scoreQueued = false;
  layout = result.layout; metrics = result.metrics; products = null; selected = null;
  updateControls(); render();
}
function computeBounds() {
  const points = room.surfaces.filter(s => s.kind === 'floor' || s.kind === 'wall').flatMap(s => s.polygon || []);
  const xs = points.map(p => p[0]).filter(Number.isFinite);
  const zs = points.map(p => p[2]).filter(Number.isFinite);
  if (room.source === 'rectangle' || !xs.length || !zs.length) return { minX: 0, maxX: room.dimensions.width, minZ: 0, maxZ: room.dimensions.length };
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minZ: Math.min(...zs), maxZ: Math.max(...zs) };
}
function drawGrid() {
  for (let x = Math.ceil(bounds.minX); x <= bounds.maxX; x++) {
    node('line', { x1: x, x2: x, y1: bounds.minZ, y2: bounds.maxZ, class: x % 5 ? 'grid' : 'grid grid-major' });
    if (x % 5 === 0) node('text', { x, y: bounds.minZ - .19, class: 'grid-label', 'text-anchor': 'middle' }, svg, formatFtIn(x));
  }
  for (let z = Math.ceil(bounds.minZ); z <= bounds.maxZ; z++) {
    node('line', { x1: bounds.minX, x2: bounds.maxX, y1: z, y2: z, class: z % 5 ? 'grid' : 'grid grid-major' });
    if (z % 5 === 0) node('text', { x: bounds.minX - .18, y: z + .06, class: 'grid-label', 'text-anchor': 'end' }, svg, formatFtIn(z));
  }
}
function drawSurfaces() {
  for (const surface of room.surfaces) {
    if (surface.kind !== 'wall') continue;
    const segment = polygonToWallSegment(surface.polygon);
    if (segment) {
      const wall = node('line', { x1: segment[0][0], y1: segment[0][1], x2: segment[1][0], y2: segment[1][1], class: 'wall' });
      wall.addEventListener('pointermove', event => tooltip(event, surface.id, [(segment[0][0] + segment[1][0]) / 2, 0, (segment[0][1] + segment[1][1]) / 2]));
      wall.addEventListener('pointerleave', hideTooltip);
    }
  }
  for (const surface of room.surfaces) {
    if (!['window', 'door', 'opening'].includes(surface.kind)) continue;
    const segment = polygonToWallSegment(surface.polygon);
    if (!segment) continue;
    const [[x1, z1], [x2, z2]] = segment;
    const mark = node('line', { x1, y1: z1, x2, y2: z2, class: `opening ${surface.kind === 'door' ? 'door' : ''}` });
    mark.addEventListener('pointermove', event => tooltip(event, surface.kind, [x1, 0, z1]));
    mark.addEventListener('pointerleave', hideTooltip);
  }
}
function drawObjects() {
  for (const object of room.objects || []) {
    const [x, , z] = object.center, [width, , depth] = object.size;
    const group = node('g', { transform: `translate(${x} ${z}) rotate(${(object.rotation_y || 0) * 180 / Math.PI})` });
    node('rect', { x: -width / 2, y: -depth / 2, width, height: depth, rx: .08, class: 'object' }, group);
    node('text', { x: 0, y: .06, class: 'object-label' }, group, object.category);
    group.addEventListener('pointermove', event => tooltip(event, object.category, object.center));
    group.addEventListener('pointerleave', hideTooltip);
  }
}
function drawPatches() {
  for (const patch of metrics?.treatment_patches || []) {
    const surface = room.surfaces.find(s => s.id === patch.surface_id);
    const segment = surface && polygonToWallSegment(surface.polygon);
    if (!segment) continue;
    const [[x1, z1], [x2, z2]] = segment;
    const length = Math.hypot(x2 - x1, z2 - z1);
    const dx = (x2 - x1) / length, dz = (z2 - z1) / length;
    const [x, , z] = patch.center;
    const half = (patch.size?.[0] || 1) / 2;
    const mark = node('line', { x1: x - dx * half, y1: z - dz * half, x2: x + dx * half, y2: z + dz * half, class: 'patch', 'stroke-width': .25 });
    mark.addEventListener('pointermove', event => tooltip(event, 'Treatment', patch.center));
    mark.addEventListener('pointerleave', hideTooltip);
  }
}
function drawScreen() {
  const screen = layout?.screen;
  if (!screen) return;
  const surface = room.surfaces.find(s => s.id === screen.wall_id);
  const segment = surface && polygonToWallSegment(surface.polygon);
  if (!segment) return;
  const [[x1, z1], [x2, z2]] = segment;
  const distance = Math.hypot(x2 - x1, z2 - z1);
  const dx = (x2 - x1) / distance, dz = (z2 - z1) / distance;
  const [x, , z] = screen.center, half = screen.width / 2;
  const mark = node('line', { x1: x - dx * half, y1: z - dz * half, x2: x + dx * half, y2: z + dz * half, class: 'screen' });
  mark.addEventListener('pointermove', event => tooltip(event, 'Screen', screen.center));
  mark.addEventListener('pointerleave', hideTooltip);
  node('text', { x, y: z + (Math.abs(dz) < .5 ? -.24 : .35), class: 'screen-label' }, svg, `Screen ${formatFtIn(screen.width)}`);
}
function drawListener() {
  const [x, , z] = room.listener.position;
  const [fx, fz] = room.listener.facing;
  const mark = node('circle', { cx: x, cy: z, r: .14, class: 'listener' });
  mark.addEventListener('pointermove', event => tooltip(event, 'Listener', room.listener.position));
  mark.addEventListener('pointerleave', hideTooltip);
  node('path', { d: `M ${x} ${z} L ${x + fx * .55} ${z + fz * .55}`, class: 'listener-arrow', 'marker-end': 'url(#arrow)' });
  node('text', { x, y: z + .48, class: 'listener-label' }, svg, 'Listener');
}
function drawSpeakers() {
  for (const speaker of layout?.speakers || []) {
    const [x, , z] = speaker.position, [ax, , az] = speaker.aim || room.listener.position;
    node('line', { x1: x, y1: z, x2: ax, y2: az, class: 'aim' });
  }
  for (const speaker of layout?.speakers || []) {
    const [x, , z] = speaker.position;
    const group = node('g', { class: `speaker ${selected === speaker.role ? 'selected' : ''}`, transform: `translate(${x} ${z})`, tabindex: '0', role: 'button', 'aria-label': `${speaker.role} speaker` });
    node('circle', { r: .22 }, group);
    node('text', { y: .01 }, group, speaker.role);
    group.addEventListener('pointerdown', event => startDrag(event, speaker.role));
    group.addEventListener('pointermove', event => tooltip(event, speaker.role, speaker.position));
    group.addEventListener('pointerleave', hideTooltip);
    group.addEventListener('focus', () => {
      selected = speaker.role;
      svg.querySelectorAll('.speaker').forEach(item => item.classList.toggle('selected', item === group));
    });
  }
}
function render() {
  svg.replaceChildren();
  if (!room) { renderInfo(); return; }
  bounds = computeBounds();
  const width = Math.max(.1, bounds.maxX - bounds.minX), length = Math.max(.1, bounds.maxZ - bounds.minZ);
  svg.setAttribute('viewBox', `${bounds.minX - .7} ${bounds.minZ - .7} ${width + 1.4} ${length + 1.4}`);
  $('room-size').textContent = `${formatFtIn(width)} × ${formatFtIn(length)} × ${formatFtIn(room.dimensions.height)}`;
  const defs = node('defs');
  const marker = node('marker', { id: 'arrow', markerWidth: 6, markerHeight: 6, refX: 5, refY: 3, orient: 'auto', markerUnits: 'strokeWidth' }, defs);
  node('path', { d: 'M0,0 L6,3 L0,6 Z', fill: '#f5b75d' }, marker);
  drawGrid(); drawSurfaces(); drawPatches(); drawObjects(); drawScreen(); drawListener(); drawSpeakers(); renderInfo();
}
function renderInfo() {
  $('score').textContent = Number.isFinite(metrics?.score) ? String(Math.round(metrics.score * 100)) : '—';
  const warnings = $('warnings'); warnings.replaceChildren();
  for (const warning of metrics?.warnings || []) {
    const item = document.createElement('div'); item.className = 'warning'; item.textContent = warning;
    warnings.appendChild(item);
  }
  const list = $('speaker-list'); list.replaceChildren();
  if (!layout?.speakers?.length) list.textContent = 'Optimize to see speakers.';
  for (const speaker of layout?.speakers || []) {
    const row = document.createElement('div'); row.className = 'speaker-row';
    const title = document.createElement('strong'); title.textContent = speaker.role;
    const [x, y, z] = speaker.position;
    const position = document.createElement('span'); position.textContent = `${formatFtIn(x)}, ${formatFtIn(z)} (${formatFtIn(y)} high)`;
    row.append(title, position); list.appendChild(row);
  }
  const reflections = $('reflections'); reflections.replaceChildren();
  if (!metrics?.reflections?.length) reflections.textContent = 'No reflections.';
  else {
    const table = document.createElement('table'); table.className = 'reflection-table';
    const head = document.createElement('tr');
    for (const label of ['Speaker', 'Surface', 'Delay', 'Level']) { const cell = document.createElement('th'); cell.textContent = label; head.appendChild(cell); }
    table.appendChild(head);
    for (const reflection of metrics.reflections) {
      const row = document.createElement('tr');
      for (const value of [reflection.speaker, reflection.surface_id, `${reflection.delay_ms} ms`, `${reflection.level_db} dB`]) { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); }
      table.appendChild(row);
    }
    reflections.appendChild(table);
  }
  const productList = $('products'); productList.replaceChildren();
  if (!products) productList.textContent = 'Get products for the current layout.';
  else {
    for (const item of products.items || []) {
      const row = document.createElement('div'); row.className = 'product-row';
      const role = document.createElement('strong'); role.textContent = item.role;
      const link = document.createElement('a'); link.textContent = item.title; link.href = item.link; link.target = '_blank'; link.rel = 'noopener noreferrer';
      const price = document.createElement('span'); price.textContent = ` · ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(item.price)}`;
      row.append(role, link, price); productList.appendChild(row);
    }
    const total = document.createElement('div'); total.className = 'product-total';
    total.textContent = `${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(products.total)} of ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(products.budget)}`;
    productList.appendChild(total);
  }
}
function tooltip(event, label, position) {
  const tip = $('tooltip'), box = svg.parentElement.getBoundingClientRect();
  tip.textContent = `${label} · ${formatFtIn(position[0])}, ${formatFtIn(position[2])} (${formatFtIn(position[1])} high)`;
  tip.style.left = `${clamp(event.clientX - box.left + 12, 0, box.width - 180)}px`;
  tip.style.top = `${clamp(event.clientY - box.top + 12, 0, box.height - 28)}px`;
  tip.hidden = false;
}
function hideTooltip() { $('tooltip').hidden = true; }
function pointerRoom(event) {
  const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
  const p = point.matrixTransform(svg.getScreenCTM().inverse());
  return [clamp(p.x, bounds.minX, bounds.maxX), clamp(p.y, bounds.minZ, bounds.maxZ)];
}
function moveSpeaker(role, x, z) {
  const speaker = layout?.speakers.find(s => s.role === role);
  if (!speaker) return;
  speaker.position[0] = clamp(x, bounds.minX, bounds.maxX);
  speaker.position[2] = clamp(z, bounds.minZ, bounds.maxZ);
  render(); queueScore();
}
function startDrag(event, role) {
  event.preventDefault(); selected = role; dragging = event.pointerId;
  svg.setPointerCapture(event.pointerId);
  const [x, z] = pointerRoom(event); moveSpeaker(role, x, z);
}
svg.addEventListener('pointermove', event => {
  if (dragging !== event.pointerId || !selected) return;
  const [x, z] = pointerRoom(event); moveSpeaker(selected, x, z);
});
function endDrag(event) {
  if (dragging !== event.pointerId) return;
  const [x, z] = pointerRoom(event); moveSpeaker(selected, x, z);
  dragging = null; hideTooltip(); queueScore(true);
}
svg.addEventListener('pointerup', endDrag);
svg.addEventListener('pointercancel', endDrag);
document.addEventListener('keydown', event => {
  if (!selected || !layout || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
  if (event.target instanceof HTMLInputElement) return;
  event.preventDefault();
  const speaker = layout.speakers.find(s => s.role === selected);
  if (!speaker) return;
  const step = event.shiftKey ? 1 : 1 / 12;
  const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
  const dz = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
  moveSpeaker(selected, speaker.position[0] + dx, speaker.position[2] + dz);
});
function queueScore(final = false) {
  if (!room || !layout) return;
  scoreQueued = true;
  if (scoreTimer) clearTimeout(scoreTimer);
  scoreTimer = null;
  if (scoreBusy) return;
  const wait = Math.max(0, 100 - (performance.now() - lastScoreAt));
  scoreTimer = setTimeout(sendScore, final ? wait : Math.max(wait, 45));
}
async function sendScore() {
  scoreTimer = null;
  if (scoreBusy || !scoreQueued || !room || !layout) return;
  scoreQueued = false; scoreBusy = true; lastScoreAt = performance.now();
  const version = generation, roomId = room.room_id;
  const snapshot = structuredClone(layout);
  try {
    const result = await api(`/rooms/${encodeURIComponent(roomId)}/score`, json({ layout: snapshot }));
    if (version === generation && room?.room_id === roomId) { metrics = result.metrics; renderInfo(); hideError(); }
  } catch (error) { if (version === generation) showError(error); }
  finally {
    scoreBusy = false;
    if (scoreQueued && room && layout) queueScore(true);
  }
}
$('dismiss-error').addEventListener('click', hideError);
$('btn-demo').addEventListener('click', () => action(async () => setRoom(await api('/rooms/demo', json({}))), $('btn-demo')));
$('rect-form').addEventListener('submit', event => {
  event.preventDefault(); action(async () => {
    const width = parseFtIn($('width').value), length = parseFtIn($('length').value), height = parseFtIn($('height').value);
    if (![width, length, height].every(n => Number.isFinite(n) && n > 0)) throw new Error('Room dimensions must be positive.');
    setRoom(await api('/rooms/rect', json({ width, length, height })));
  }, $('rect-form').querySelector('button'));
});
$('open-form').addEventListener('submit', event => {
  event.preventDefault(); action(async () => {
    const id = encodeURIComponent($('room-id').value.trim());
    const nextRoom = await api(`/rooms/${id}`);
    let nextLayout = null;
    try { nextLayout = await api(`/rooms/${id}/layout`); }
    catch (error) { if (!String(error.message).startsWith('404:')) throw error; }
    setRoom(nextRoom, nextLayout);
  }, $('open-form').querySelector('button'));
});
async function optimize(button) {
  await action(async () => setLayout(await api(`/rooms/${encodeURIComponent(room.room_id)}/optimize`, json({}))), button);
}
$('btn-optimize').addEventListener('click', () => optimize($('btn-optimize')));
$('btn-reset').addEventListener('click', () => optimize($('btn-reset')));
$('btn-products').addEventListener('click', () => action(async () => {
  const budget = Number($('budget').value);
  if (!Number.isFinite(budget) || budget <= 0) throw new Error('Enter a positive budget.');
  products = await api(`/rooms/${encodeURIComponent(room.room_id)}/products?budget=${encodeURIComponent(budget)}`);
  renderInfo();
}, $('btn-products')));

// Opening the dev page immediately shows the same demo room used by the button.
action(async () => {
  setRoom(await api('/rooms/demo', json({})));
  setLayout(await api(`/rooms/${encodeURIComponent(room.room_id)}/optimize`, json({})));
});
