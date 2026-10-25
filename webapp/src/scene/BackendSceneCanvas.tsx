import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { fitModel, loadModel } from './modelLoader';
import type { Props } from './RoomCanvas';
import { sceneMetersToFeet } from '../interaction/coordinates';
import { formatFtIn } from '../lib/format';
import { ftToM } from '../lib/units';
import { useAppStore } from '../store';
import type { Point, SceneModel } from './adapter/layoutToScene';

type SceneProps = Props & { model: SceneModel; showReflections?: boolean };
type SceneState = {
  scene: THREE.Scene; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer;
  orbit: OrbitControls; root: THREE.Group; ray: THREE.Raycaster;
  groups: Map<string, { signature: string; object: THREE.Object3D }>;
  frame: number; observer: ResizeObserver;
};
const v = (p: Point) => new THREE.Vector3(...p);
const box = (size: Point, color: string, opacity = 1) => new THREE.Mesh(
  new THREE.BoxGeometry(...size), new THREE.MeshStandardMaterial({ color, transparent: opacity < 1, opacity, roughness: .8 }));

function planeFromPolygon(points: Point[], color: string, opacity: number): THREE.Mesh | null {
  if (points.length < 3) return null;
  const origin = v(points[0]);
  const x = v(points[1]).sub(origin).normalize();
  const normal = new THREE.Vector3().crossVectors(v(points[1]).sub(origin), v(points[2]).sub(origin)).normalize();
  if (normal.lengthSq() < .1) return null;
  const y = new THREE.Vector3().crossVectors(normal, x).normalize();
  const flat = points.map(p => { const delta = v(p).sub(origin); return new THREE.Vector2(delta.dot(x), delta.dot(y)); });
  const triangles = THREE.ShapeUtils.triangulateShape(flat, []);
  const positions = points.flatMap(p => p);
  const indices = triangles.flatMap(t => t);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide, transparent: opacity < 1, opacity, depthWrite: opacity === 1 }));
}

function labelSprite(value: string): THREE.Sprite {
  const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 96;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#131e2bd9'; ctx.fillRect(60, 10, 136, 76);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 48px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(value, 128, 48);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }));
  sprite.scale.set(.42, .16, 1);
  return sprite;
}

function line(points: Point[], color: string, opacity = 1): THREE.Line {
  const geometry = new THREE.BufferGeometry().setFromPoints(points.map(v));
  return new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }));
}

function wallFacing(model: SceneModel, wallId: string, center: Point): THREE.Vector3 {
  const wall = model.surfaces.find(s => s.id === wallId);
  if (!wall || wall.polygon.length < 3) return v(model.listener.position).sub(v(center)).setY(0).normalize();
  const edge = v(wall.polygon[1]).sub(v(wall.polygon[0])).setY(0).normalize();
  const normal = new THREE.Vector3(-edge.z, 0, edge.x);
  if (normal.dot(v(model.listener.position).sub(v(center))) < 0) normal.negate();
  return normal;
}

function orientToAim(object: THREE.Object3D, position: Point, aim: Point) {
  const target = v(aim);
  if (target.distanceToSquared(v(position)) > .0001) object.lookAt(target);
}

function selectionFrame(size: Point): THREE.LineSegments {
  const geometry = new THREE.BoxGeometry(size[0] * 1.08, size[1] * 1.08, size[2] * 1.08);
  const edges = new THREE.EdgesGeometry(geometry);
  geometry.dispose();
  return new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: '#ffffff' }),
  );
}

function addModel(group: THREE.Group, model: THREE.Group, size: Point, color?: string) {
  fitModel(model, size);
  model.traverse(child => {
    if (child instanceof THREE.Mesh) {
      child.userData.sharedGeometry = true;
      if (color) {
        child.material = Array.isArray(child.material) ? child.material.map(m => m.clone()) : child.material.clone();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach(m => { if ('color' in m && m.color instanceof THREE.Color) m.color.set(color); });
      } else child.userData.sharedMaterial = true;
    }
  });
  group.add(model);
}

function createItem(key: string, model: SceneModel, showReflections: boolean, selected: string | null): THREE.Object3D | null {
  const [kind, id] = key.split(':');
  if (kind === 'surface') {
    const s = model.surfaces.find(item => item.id === id);
    if (!s) return null;
    const color = s.kind === 'floor' ? '#58616a' : s.kind === 'ceiling' ? '#dadfe0' : s.kind === 'window' ? '#64b8e8' : s.kind === 'door' ? '#a77450' : '#aeb9be';
    const mesh = planeFromPolygon(s.polygon, color, s.kind === 'window' ? .5 : s.kind === 'floor' ? .55 : .2);
    if (!mesh) return null;
    mesh.userData.kind = s.kind;
    if (s.kind === 'door' || s.kind === 'window' || s.kind === 'opening') {
      const center = new THREE.Vector3(); s.polygon.forEach(p => center.add(v(p))); center.divideScalar(s.polygon.length);
      mesh.position.addScaledVector(wallFacing(model, s.id, center.toArray() as Point), .012);
      if (s.kind === 'opening') mesh.visible = false;
    }
    return mesh;
  }
  if (kind === 'object') {
    const item = model.objects.find(o => o.id === id); if (!item) return null;
    const mesh = box(item.size, item.category === 'sofa' ? '#b57f5d' : item.category === 'television' ? '#263846' : '#899098');
    mesh.position.set(...item.center); mesh.rotation.y = THREE.MathUtils.degToRad(item.rotation_y);
    return mesh;
  }
  if (kind === 'speaker') {
    const item = model.speakers.find(s => s.role === id); if (!item) return null;
    const group = new THREE.Group(); group.position.set(...item.position);
    const aimed = new THREE.Group(); group.add(aimed);
    const body = box(item.size, item.color);
    aimed.add(body);
    if (selected === item.role) aimed.add(selectionFrame(item.size));
    const direction = v(item.aim).sub(v(item.position));
    if (direction.lengthSq() > .0001) aimed.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction.normalize());
    const label = labelSprite(item.role); label.position.y = item.size[1] / 2 + .15; group.add(label);
    group.add(line([[0, -item.position[1], 0], [0, 0, 0]], item.color, .55));
    group.userData.selectId = item.role;
    if (selected === item.role) body.material.emissive.set('#63717a');
    if (item.known) {
      void loadModel('/models/bookshelf_speaker.glb').then(glb => {
        if (!group.parent) return;
        glb.traverse(child => { child.userData.selectId = item.role; });
        aimed.remove(body); body.geometry.dispose(); body.material.dispose(); addModel(aimed, glb, item.size, item.color);
      }).catch(() => { /* colored box is the local fallback */ });
    } else if (!warned.has(item.role)) { console.warn(`Unknown speaker role: ${item.role}`); warned.add(item.role); }
    return group;
  }
  if (kind === 'screen' && model.screen) {
    const item = model.screen;
    const group = new THREE.Group(); group.position.set(...item.center);
    const face = wallFacing(model, item.wall_id, item.center);
    group.position.addScaledVector(face, .016);
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(item.width, item.height), new THREE.MeshStandardMaterial({ color: '#f8f8ef', side: THREE.DoubleSide, emissive: selected === item.id ? '#52616c' : '#000000' }));
    group.add(mesh); orientToAim(group, group.position.toArray() as Point, v(item.center).add(face).toArray() as Point);
    if (selected === item.id) group.add(selectionFrame([item.width, item.height, .05]));
    group.userData.selectId = item.id; mesh.userData.selectId = item.id;
    void loadModel('/models/fixed_frame_screen_16_9.glb').then(glb => { if (!group.parent) return; glb.userData.selectId = item.id; group.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); addModel(group, glb, [item.width, item.height, .05]); }).catch(() => {});
    return group;
  }
  if (kind === 'projector' && model.projector) {
    const item = model.projector; const group = new THREE.Group(); group.position.set(...item.position);
    const mesh = box(item.size, selected === item.id ? '#ffffff' : '#bdc7cf'); group.add(mesh);
    if (selected === item.id) group.add(selectionFrame(item.size));
    orientToAim(group, item.position, item.aim); group.userData.selectId = item.id;
    void loadModel('/models/projector.glb').then(glb => { if (!group.parent) return; glb.userData.selectId = item.id; group.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); addModel(group, glb, item.size); }).catch(() => {});
    return group;
  }
  if (kind === 'seat') {
    const seat = model.seats.find(s => s.id === id); if (!seat) return null;
    const mesh = box([.15, .06, .15], '#47dbc2'); mesh.position.set(...seat.position); return mesh;
  }
  if (kind === 'patch') {
    const p = model.patches[Number(id)]; if (!p) return null;
    const normal = wallFacing(model, p.surface_id, p.center);
    const group = new THREE.Group(); group.position.copy(v(p.center).addScaledVector(normal, .01));
    group.add(new THREE.Mesh(new THREE.PlaneGeometry(...p.size), new THREE.MeshBasicMaterial({ color: '#efaf43', transparent: true, opacity: .48, side: THREE.DoubleSide, depthWrite: false })));
    orientToAim(group, group.position.toArray() as Point, group.position.clone().add(normal).toArray() as Point);
    return group;
  }
  if (kind === 'reflection') {
    const r = model.reflections[Number(id)]; if (!r || (!showReflections && r.speaker !== selected)) return null;
    const speaker = model.speakers.find(s => s.role === r.speaker); if (!speaker) return null;
    return line([speaker.position, r.point, r.listener], '#e8c970', .8);
  }
  return null;
}

const warned = new Set<string>();
function dispose(object: THREE.Object3D) {
  object.traverse(child => {
    if (child instanceof THREE.Mesh || child instanceof THREE.Line || child instanceof THREE.LineSegments) {
      if (!child.userData.sharedGeometry) child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      if (!child.userData.sharedMaterial) materials.forEach(m => m.dispose());
    }
    if (child instanceof THREE.Sprite) { child.material.map?.dispose(); child.material.dispose(); }
  });
}

export function BackendSceneCanvas({ model, selectedId, selectedName, selectedDescription, walls, ceiling, onSelect, topView, showReflections = false }: SceneProps) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef<SceneState | null>(null);
  const onSelectRef = useRef(onSelect); onSelectRef.current = onSelect;
  useEffect(() => {
    const el = host.current!;
    const scene = new THREE.Scene(); scene.background = new THREE.Color('#141a21');
    const camera = new THREE.PerspectiveCamera(48, el.clientWidth / Math.max(el.clientHeight, 1), .05, 100);
    camera.position.set(7, 6, 9);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(el.clientWidth, el.clientHeight);
    el.prepend(renderer.domElement);
    const orbit = new OrbitControls(camera, renderer.domElement); orbit.enableDamping = true; orbit.target.set(0, 1, 0);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x56616b, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2); light.position.set(-4, 9, 5); scene.add(light);
    const root = new THREE.Group(); scene.add(root);
    const ray = new THREE.Raycaster();
    const tip = document.createElement('div'); tip.className = 'drag-tip'; tip.hidden = true; el.appendChild(tip);
    const showTip = (text: string, e: PointerEvent) => {
      const bounds = el.getBoundingClientRect();
      tip.textContent = text; tip.hidden = false;
      tip.style.left = `${Math.min(e.clientX - bounds.left + 14, bounds.width - 230)}px`; tip.style.top = `${Math.max(8, e.clientY - bounds.top - 34)}px`;
    };
    let down: [number, number] | null = null;
    // Dragging a speaker slides it across the floor plane at its own height instead of orbiting the camera.
    let dragging: { role: string; height: number; pointerId: number } | null = null;
    const pointerAt = (e: PointerEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2((e.clientX - bounds.left) / bounds.width * 2 - 1, -(e.clientY - bounds.top) / bounds.height * 2 + 1), camera);
    };
    const speakerAt = (e: PointerEvent): string | null => {
      pointerAt(e);
      // The nearest selectable object decides: transparent walls carry no selectId, so they never block a speaker.
      for (const hit of ray.intersectObject(root, true)) {
        let node: THREE.Object3D | null = hit.object;
        while (node && !node.userData.selectId) node = node.parent;
        if (!node) continue;
        const id = String(node.userData.selectId);
        return useAppStore.getState().layout?.speakers.some(item => item.role === id) ? id : null;
      }
      return null;
    };
    const dragStart = (e: PointerEvent) => {
      if (e.button !== 0) return;
      const role = speakerAt(e);
      const speaker = role ? useAppStore.getState().layout?.speakers.find(item => item.role === role) : undefined;
      if (!role || !speaker) return;
      dragging = { role, height: ftToM(speaker.position[1]), pointerId: e.pointerId };
      orbit.enabled = false;
      e.stopImmediatePropagation(); // the orbit controls listen on the same element: they must never see this press
      e.preventDefault();
      renderer.domElement.setPointerCapture(e.pointerId);
      onSelectRef.current(role);
    };
    const dragMove = (e: PointerEvent) => {
      if (!dragging) {
        const role = e.buttons ? null : speakerAt(e);
        renderer.domElement.style.cursor = role ? 'grab' : '';
        if (role) showTip(`Drag to move ${role} · slides along the floor, the score updates when you let go`, e); else tip.hidden = true;
        return;
      }
      if (e.pointerId !== dragging.pointerId) return;
      e.stopImmediatePropagation();
      const room = useAppStore.getState().room;
      if (!room) return;
      pointerAt(e);
      const point = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -dragging.height), new THREE.Vector3());
      if (!point) return;
      const [x, , z] = sceneMetersToFeet([point.x, point.y, point.z], room);
      const speaker = useAppStore.getState().layout?.speakers.find(item => item.role === dragging?.role);
      if (speaker) {
        useAppStore.getState().moveSpeaker(dragging.role, [x, speaker.position[1], z]);
        const moved = useAppStore.getState().layout?.speakers.find(item => item.role === dragging?.role);
        if (moved) {
          const [lx, , lz] = room.listener.position;
          showTip(`${dragging.role} · ${formatFtIn(moved.position[0])}, ${formatFtIn(moved.position[2])} · ${formatFtIn(Math.hypot(moved.position[0] - lx, moved.position[2] - lz))} from your seat`, e);
        }
        renderer.domElement.style.cursor = 'grabbing';
      }
    };
    const dragEnd = (e: PointerEvent) => {
      if (!dragging || e.pointerId !== dragging.pointerId) return;
      e.stopImmediatePropagation();
      dragging = null; down = null; orbit.enabled = true; tip.hidden = true; renderer.domElement.style.cursor = '';
      useAppStore.getState().finishDrag();
    };
    const pointerDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const pointerUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
      down = null;
      const bounds = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2((e.clientX - bounds.left) / bounds.width * 2 - 1, -(e.clientY - bounds.top) / bounds.height * 2 + 1), camera);
      const hit = ray.intersectObject(root, true).find(h => { let node: THREE.Object3D | null = h.object; while (node && !node.userData.selectId) node = node.parent; return !!node; });
      let node: THREE.Object3D | null = hit?.object ?? null;
      while (node && !node.userData.selectId) node = node.parent;
      onSelectRef.current(node?.userData.selectId ?? null);
    };
    renderer.domElement.addEventListener('pointerdown', dragStart, true); renderer.domElement.addEventListener('pointermove', dragMove); renderer.domElement.addEventListener('pointercancel', dragEnd);
    renderer.domElement.addEventListener('pointerdown', pointerDown); renderer.domElement.addEventListener('pointerup', dragEnd, true); renderer.domElement.addEventListener('pointerup', pointerUp);
    const observer = new ResizeObserver(() => { camera.aspect = el.clientWidth / Math.max(el.clientHeight, 1); camera.updateProjectionMatrix(); renderer.setSize(el.clientWidth, el.clientHeight); }); observer.observe(el);
    const s: SceneState = { scene, camera, renderer, orbit, root, ray, groups: new Map(), frame: 0, observer };
    const draw = () => { s.frame = requestAnimationFrame(draw); orbit.update(); renderer.render(scene, camera); }; draw(); state.current = s;
    return () => { cancelAnimationFrame(s.frame); observer.disconnect(); tip.remove(); renderer.domElement.removeEventListener('pointerdown', dragStart, true); renderer.domElement.removeEventListener('pointermove', dragMove); renderer.domElement.removeEventListener('pointercancel', dragEnd); renderer.domElement.removeEventListener('pointerup', dragEnd, true); renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointerup', pointerUp); s.groups.forEach(({ object }) => dispose(object)); orbit.dispose(); renderer.dispose(); renderer.domElement.remove(); state.current = null; };
  }, []);
  useEffect(() => {
    const s = state.current; if (!s) return;
    const keys = [
      ...model.surfaces.map(item => `surface:${item.id}`), ...model.objects.map(item => `object:${item.id}`),
      ...model.speakers.map(item => `speaker:${item.role}`), ...(model.screen ? ['screen:screen'] : []),
      ...(model.projector ? ['projector:projector'] : []), ...model.seats.map(item => `seat:${item.id}`),
      ...model.patches.map((_, i) => `patch:${i}`), ...model.reflections.map((_, i) => `reflection:${i}`),
    ];
    const active = new Set(keys);
    for (const [key, existing] of s.groups) if (!active.has(key)) { s.root.remove(existing.object); dispose(existing.object); s.groups.delete(key); }
    for (const key of keys) {
      const [kind, id] = key.split(':');
      const source = kind === 'surface' ? model.surfaces.find(item => item.id === id) : kind === 'object' ? model.objects.find(item => item.id === id) : kind === 'speaker' ? model.speakers.find(item => item.role === id) : kind === 'screen' ? model.screen : kind === 'projector' ? model.projector : kind === 'seat' ? model.seats.find(item => item.id === id) : kind === 'patch' ? model.patches[Number(id)] : model.reflections[Number(id)];
      const signature = JSON.stringify([source, kind === 'reflection' && (showReflections || selectedId === (source as SceneModel['reflections'][number])?.speaker), selectedId === id]);
      const previous = s.groups.get(key);
      if (previous?.signature === signature) continue;
      if (previous) { s.root.remove(previous.object); dispose(previous.object); }
      const object = createItem(key, model, showReflections, selectedId);
      if (object) { s.root.add(object); s.groups.set(key, { signature, object }); } else s.groups.delete(key);
    }
    for (const [key, value] of s.groups) {
      value.object.visible = !(key.startsWith('surface:') && ((value.object.userData.kind === 'wall' && !walls) || (value.object.userData.kind === 'ceiling' && !ceiling)));
    }
  }, [model, selectedId, showReflections, walls, ceiling]);
  useEffect(() => {
    const s = state.current; if (!s) return;
    s.camera.up.set(0, 1, 0);
    if (topView) { s.camera.position.set(0, Math.max(model.room.width, model.room.length) * 1.25, .001); s.orbit.target.set(0, 0, 0); }
    else if (s.camera.position.distanceToSquared(new THREE.Vector3(0, 0, 0)) < 1) s.camera.position.set(model.room.width, model.room.height * 1.7, model.room.length);
    s.orbit.update();
  }, [model, topView]);
  return <div className="viewport" ref={host}><div className="object-callout" style={{ opacity: selectedId ? 1 : 0 }}><b>{selectedName ?? selectedId}</b><span>{selectedDescription}</span></div></div>;
}
