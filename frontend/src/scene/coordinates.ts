import { Euler, Vector3 } from 'three';
export const toVector3 = (v: readonly number[]) => new Vector3(v[0],v[1],v[2]);
export const degreesToEuler = (v: readonly number[]) => new Euler(v[0]*Math.PI/180,v[1]*Math.PI/180,v[2]*Math.PI/180,'XYZ');
export const eulerToDegrees = (e: Euler): [number,number,number] => [e.x*180/Math.PI,e.y*180/Math.PI,e.z*180/Math.PI];
