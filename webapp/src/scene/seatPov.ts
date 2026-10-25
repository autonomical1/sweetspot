import * as THREE from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { RoomConfig } from '../config/schema';

interface Pose { position: THREE.Vector3; target: THREE.Vector3 }

export interface ViewState {
  camera: THREE.PerspectiveCamera;
  orbit: OrbitControls;
  objects: Map<string, THREE.Group>;
  seatMarkers: THREE.Mesh[];
  seatActive?: boolean;
  isTop?: boolean;
  orbitPose?: Pose;
  normalPose?: Pose;
  lookYaw?: number;
  lookPitch?: number;
}

export function updateCameraView(state: ViewState, config: RoomConfig, seatView: boolean, topView: boolean, canvas: HTMLCanvasElement | null) {
  if (seatView) {
    if (!state.seatActive) {
      const pose = state.isTop && state.orbitPose ? state.orbitPose : { position: state.camera.position, target: state.orbit.target };
      state.normalPose = { position: pose.position.clone(), target: pose.target.clone() };
      if (!state.isTop) state.orbitPose = { position: pose.position.clone(), target: pose.target.clone() };
      state.seatActive = true;
      state.isTop = false;
    }
    state.orbit.enabled = false;
    state.camera.position.set(...(config.seats[0]?.position ?? [0, 1.1, 1]));
    const seat = config.seats[0];
    const target = new THREE.Vector3(...(seat?.target ?? [0, 1.4, -2]));
    const direction = target.sub(state.camera.position).normalize();
    const yaw = Math.atan2(-direction.x, -direction.z);
    const pitch = Math.asin(THREE.MathUtils.clamp(direction.y, -1, 1));
    state.lookYaw = yaw;
    state.lookPitch = pitch;
    state.camera.rotation.order = 'YXZ';
    state.camera.rotation.set(pitch, yaw, 0, 'YXZ');
    if (canvas) canvas.style.cursor = 'grab';
  } else {
    state.orbit.enabled = true;
    if (topView) {
      if (!state.isTop && !state.seatActive) state.orbitPose = { position: state.camera.position.clone(), target: state.orbit.target.clone() };
      state.seatActive = false;
      state.camera.position.set(0, Math.max(config.room.width, config.room.length) * 1.25, .001);
      state.orbit.target.set(0, 0, 0);
      state.isTop = true;
    } else {
      const shouldRestore = state.seatActive || state.isTop;
      state.seatActive = false;
      state.isTop = false;
      const pose = state.orbitPose ?? state.normalPose;
      if (shouldRestore && pose) {
        state.camera.position.copy(pose.position);
        state.orbit.target.copy(pose.target);
        state.camera.rotation.set(0, 0, 0);
      }
    }
    state.camera.up.set(0, 1, 0);
    state.orbit.update();
    if (canvas) canvas.style.cursor = '';
  }
  for (const item of config.equipment.filter(item => item.type === 'seat')) {
    const chair = state.objects.get(item.id);
    if (chair) chair.visible = !seatView;
  }
  for (const marker of state.seatMarkers) marker.visible = !seatView;
}
