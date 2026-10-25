import * as THREE from 'three';
import type { RoomConfig } from '../config/schema';
import { degreesToEuler } from './coordinates';
import { calculateProjection } from './projection';

export function addProjectionLines(root: THREE.Group, config: RoomConfig) {
  for (const projector of config.equipment.filter(item => item.type === 'projector')) {
    const screen = config.equipment.find(item => item.id === projector.targetScreenId && item.type === 'screen');
    if (!screen) continue;
    const result = calculateProjection(projector, screen);
    if (!result.supported) continue;
    const origin = new THREE.Vector3(...projector.position);
    origin.y += projector.lensOffset ?? 0;
    const center = new THREE.Vector3(...screen.position);
    const right = new THREE.Vector3(1, 0, 0).applyEuler(degreesToEuler(screen.rotation));
    const up = new THREE.Vector3(0, 1, 0).applyEuler(degreesToEuler(screen.rotation));
    const w = result.width / 2;
    const h = result.height / 2;
    const corners = [
      center.clone().addScaledVector(right, -w).addScaledVector(up, h),
      center.clone().addScaledVector(right, w).addScaledVector(up, h),
      center.clone().addScaledVector(right, w).addScaledVector(up, -h),
      center.clone().addScaledVector(right, -w).addScaledVector(up, -h),
    ];
    const pairs = [0, 1, 1, 2, 2, 3, 3, 0, 4, 0, 4, 1, 4, 2, 4, 3];
    const positions: number[] = [];
    for (const i of pairs) {
      const point = i < 4 ? corners[i] : origin;
      positions.push(point.x, point.y, point.z);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#53d8c0', transparent: true, opacity: .8 }));
    lines.userData.projection = true;
    root.add(lines);
  }
}
