import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { RoomConfig, Equipment } from '../config/schema';
import { makeDevice } from './factories';
import { degreesToEuler } from './coordinates';
import { fitModel, loadModel } from './modelLoader';
import { createRoomShell } from './roomShell';
import { addProjectionLines } from './projectionLines';
import { updateCameraView } from './seatPov';
import { useAppStore } from '../store';
import { layoutToScene } from './adapter/layoutToScene';
import { BackendSceneCanvas } from './BackendSceneCanvas';

export type Props = {
  config: RoomConfig;
  selectedId: string | null;
  selectedName?: string;
  selectedDescription?: string;
  walls: boolean;
  ceiling: boolean;
  showProjection: boolean;
  onSelect: (id: string | null) => void;
  seatView: boolean;
  topView: boolean;
};
export function RoomCanvas(props: Props) {
  const room = useAppStore(state => state.room);
  const layout = useAppStore(state => state.layout);
  const metrics = useAppStore(state => state.metrics);
  if (room && layout) return <BackendSceneCanvas {...props} model={layoutToScene(room, layout, metrics)} />;
  return <LegacyRoomCanvas {...props} />;
}

function LegacyRoomCanvas({ config, selectedId, selectedName, selectedDescription, walls, ceiling, showProjection, onSelect, seatView, topView }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<string | null>(selectedId);
  const seatModeRef = useRef(seatView);
  const state = useRef<any>({});

  useEffect(() => {
    const el = host.current!;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#141a21');
    const camera = new THREE.PerspectiveCamera(48, el.clientWidth / el.clientHeight, .05, 100);
    camera.position.set(7, 6, 9);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = true;
    el.prepend(renderer.domElement);
    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.target.set(0, 1, 0);
    orbit.enableDamping = true;
    orbit.dampingFactor = .075;
    orbit.rotateSpeed = .7;
    orbit.panSpeed = .8;
    orbit.screenSpacePanning = true;
    orbit.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    renderer.domElement.style.touchAction = 'none';
    scene.add(new THREE.HemisphereLight(0xffffff, 0x55606c, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2.2);
    light.position.set(-4, 9, 5);
    light.castShadow = true;
    scene.add(light);
    const root = new THREE.Group();
    scene.add(root);
    const { floorMat, wallMat, wallGroup, ceilingMat, ceilingGroup } = createRoomShell(root, config.room, walls, ceiling);
    const objects = new Map<string, THREE.Group>();
    for (const item of config.equipment) {
      const device = makeDevice(item);
      device.traverse(o => {
        if (o instanceof THREE.Mesh) {
          o.castShadow = true;
          o.userData.equipmentId = item.id;
        }
      });
      root.add(device);
      objects.set(item.id, device);
    }
    const seatMarkers: THREE.Mesh[] = [];
    config.seats.forEach(seat => {
      const marker = new THREE.Mesh(new THREE.SphereGeometry(.08), new THREE.MeshBasicMaterial({ color: '#47dbc2' }));
      marker.position.set(...seat.position);
      root.add(marker);
      seatMarkers.push(marker);
    });
    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let down: {
      x: number;
      y: number;
      lastX: number;
      lastY: number;
      button: number;
    } | null = null;
    const startPick = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, button: e.button };
      if (seatModeRef.current && e.button === 0) {
        renderer.domElement.setPointerCapture(e.pointerId);
        renderer.domElement.style.cursor = 'grabbing';
      }
    };
    const look = (e: PointerEvent) => {
      if (!seatModeRef.current || !down || down.button !== 0) return;
      const dx = e.clientX - down.lastX;
      const dy = e.clientY - down.lastY;
      down.lastX = e.clientX;
      down.lastY = e.clientY;
      state.current.lookYaw = (state.current.lookYaw ?? 0) - dx * .004;
      state.current.lookPitch = THREE.MathUtils.clamp((state.current.lookPitch ?? 0) - dy * .004, -Math.PI / 2 + .03, Math.PI / 2 - .03);
      camera.rotation.set(state.current.lookPitch, state.current.lookYaw, 0, 'YXZ');
    };
    const finishPick = (e: PointerEvent) => {
      if (!down) return;
      const wasClick = down.button === 0 && e.button === 0 && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 4;
      down = null;
      renderer.domElement.style.cursor = seatModeRef.current ? 'grab' : '';
      if (!wasClick) return;
      const bounds = renderer.domElement.getBoundingClientRect();
      mouse.set((e.clientX - bounds.left) / bounds.width * 2 - 1, -((e.clientY - bounds.top) / bounds.height * 2 - 1));
      ray.setFromCamera(mouse, camera);
      const hit = ray.intersectObjects(root.children, true).find(result => result.object.userData.equipmentId);
      onSelect(hit ? hit.object.userData.equipmentId : null);
    };
    renderer.domElement.addEventListener('pointerdown', startPick);
    renderer.domElement.addEventListener('pointermove', look);
    renderer.domElement.addEventListener('pointerup', finishPick);
    renderer.domElement.addEventListener('pointercancel', finishPick);
    const observer = new ResizeObserver(() => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    });
    observer.observe(el);
    let frame = 0;
    const draw = () => {
      frame = requestAnimationFrame(draw);
      if (!seatModeRef.current) orbit.update();
      const selectedObject = objects.get(selectedRef.current ?? '');
      if (selectedObject && label.current) {
        const point = selectedObject.position.clone();
        point.x += Number((selectedObject.userData.dimensions as number[] | undefined)?.[0] ?? .7) * .58;
        point.y += Number((selectedObject.userData.dimensions as number[] | undefined)?.[1] ?? .7) * .25;
        point.project(camera);
        const x = (point.x * .5 + .5) * el.clientWidth;
        const y = (-point.y * .5 + .5) * el.clientHeight;
        const left = THREE.MathUtils.clamp(x + 12, 8, Math.max(8, el.clientWidth - 220));
        const top = THREE.MathUtils.clamp(y - 12, 78, Math.max(78, el.clientHeight - 65));
        label.current.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
        label.current.style.opacity = point.z >= -1 && point.z <= 1 ? '1' : '0';
      } else if (label.current) {
        label.current.style.opacity = '0';
      }
      renderer.render(scene, camera);
    };
    draw();
    state.current = { scene, camera, orbit, objects, root, seatMarkers, wallGroup, ceilingGroup, floorMat, wallMat, ceilingMat };
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener('pointerdown', startPick);
      renderer.domElement.removeEventListener('pointermove', look);
      renderer.domElement.removeEventListener('pointerup', finishPick);
      renderer.domElement.removeEventListener('pointercancel', finishPick);
      orbit.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);
  useEffect(() => { selectedRef.current = selectedId; }, [selectedId]);
  useEffect(() => {
    seatModeRef.current = seatView;
    const s = state.current;
    if (!s.orbit) return;
    const { root, objects } = s;
    const transparentOrbit = !seatView;
    s.floorMat.transparent = transparentOrbit;
    s.floorMat.opacity = transparentOrbit ? .22 : 1;
    s.floorMat.depthWrite = !transparentOrbit;
    s.wallMat.transparent = transparentOrbit;
    s.wallMat.opacity = transparentOrbit ? .12 : 1;
    s.wallMat.depthWrite = !transparentOrbit;
    s.ceilingMat.transparent = transparentOrbit;
    s.ceilingMat.opacity = transparentOrbit ? .12 : 1;
    s.ceilingMat.depthWrite = !transparentOrbit;
    s.floorMat.needsUpdate = true;
    s.wallMat.needsUpdate = true;
    s.ceilingMat.needsUpdate = true;
    s.wallGroup.visible = walls;
    s.ceilingGroup.visible = ceiling;
    for (const child of [...root.children]) {
      if (child.userData.projection) root.remove(child);
    }
    config.equipment.forEach((e: Equipment) => {
      const obj = objects.get(e.id);
      if (!obj) return;
      obj.visible = !seatView || e.type !== 'seat';
      obj.position.set(...e.position);
      obj.rotation.copy(degreesToEuler(e.rotation));
    });
    s.seatMarkers.forEach((marker: THREE.Mesh) => { marker.visible = !seatView; });
    for (const item of config.equipment) {
      const obj = objects.get(item.id);
      if (!obj) continue;
      const previous = obj.userData.dimensions as number[];
      const dimensionsChanged = previous.some((v, i) => v !== item.dimensions[i]);
      if (item.modelUrl && (obj.userData.loadedModel !== item.modelUrl || dimensionsChanged)) {
        void loadModel(item.modelUrl).then(model => {
          fitModel(model, item.dimensions);
          model.traverse(child => {
            if (child instanceof THREE.Mesh) child.userData.equipmentId = item.id;
          });
          obj.clear();
          obj.add(model);
          obj.userData.loadedModel = item.modelUrl;
          obj.userData.dimensions = [...item.dimensions];
        }).catch(console.error);
      }
      else if (!item.modelUrl && dimensionsChanged) {
        obj.scale.set(item.dimensions[0] / previous[0], item.dimensions[1] / previous[1], item.dimensions[2] / previous[2]);
        obj.userData.dimensions = [...item.dimensions];
      }
      if (item.type === 'screen' && item.imageUrl && obj.userData.loadedImage !== item.imageUrl) {
        new THREE.TextureLoader().load(item.imageUrl, texture => {
          texture.colorSpace = THREE.SRGBColorSpace;
          const mesh = obj.children[0];
          if (mesh instanceof THREE.Mesh) mesh.material = new THREE.MeshBasicMaterial({ map: texture });
          obj.userData.loadedImage = item.imageUrl;
        });
      }
    }
    if (showProjection) addProjectionLines(root, config);
  }, [config, showProjection, walls, ceiling, seatView]);
  useEffect(() => {
    const current = state.current;
    if (!current.orbit) return;
    updateCameraView(current, config, seatView, topView, host.current?.querySelector('canvas') ?? null);
  }, [seatView, topView, config]);
  return <div className="viewport" ref={host}><div className="object-callout" ref={label}><b>{selectedName}</b><span>{selectedDescription}</span></div></div>;
}
