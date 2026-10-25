import * as THREE from 'three';
import type { RoomConfig } from '../config/schema';

export function createRoomShell(root: THREE.Group, room: RoomConfig['room'], walls: boolean, ceiling: boolean) {
  const floorMat = new THREE.MeshStandardMaterial({ color: room.floorColor, roughness: .88, transparent: true, opacity: .3, depthWrite: false });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(room.width, room.length), floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -.015;
  floor.receiveShadow = true;
  root.add(floor);

  const wallMat = new THREE.MeshStandardMaterial({ color: room.wallColor, roughness: .9, side: THREE.DoubleSide, transparent: true, opacity: .12, depthWrite: false });
  const wallGroup = new THREE.Group();
  root.add(wallGroup);
  const wall = (width: number, height: number, x: number, y: number, z: number, ry = 0) => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMat);
    mesh.position.set(x, y, z);
    mesh.rotation.y = ry;
    wallGroup.add(mesh);
  };
  if (walls) {
    wall(room.width, room.height, 0, room.height / 2, -room.length / 2);
    wall(room.width, room.height, 0, room.height / 2, room.length / 2, Math.PI);
    wall(room.length, room.height, -room.width / 2, room.height / 2, 0, Math.PI / 2);
    wall(room.length, room.height, room.width / 2, room.height / 2, 0, -Math.PI / 2);
  }

  const ceilingMat = new THREE.MeshStandardMaterial({ color: room.ceilingColor, side: THREE.DoubleSide, transparent: true, opacity: .12, depthWrite: false });
  const ceilingGroup = new THREE.Group();
  const panel = new THREE.Mesh(new THREE.PlaneGeometry(room.width, room.length), ceilingMat);
  panel.rotation.x = Math.PI / 2;
  panel.position.y = room.height;
  ceilingGroup.add(panel);
  ceilingGroup.visible = ceiling;
  root.add(ceilingGroup);
  return { floorMat, wallMat, wallGroup, ceilingMat, ceilingGroup };
}
