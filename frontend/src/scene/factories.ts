import { BoxGeometry, CylinderGeometry, Group, Mesh, MeshStandardMaterial } from 'three';
import type { Equipment } from '../config/schema';
import { degreesToEuler, toVector3 } from './coordinates';
export function makeDevice(item:Equipment):Group{
  const g=new Group(); g.name=item.id; const dims=item.dimensions; const mat=(color:string,roughness=.7)=>new MeshStandardMaterial({color,roughness});
  const add=(geometry:any,material:any,y=0)=>{const m=new Mesh(geometry,material);m.position.y=y;g.add(m);return m;};
  const color=item.color??({speaker:'#313943',projector:'#f0f1ed',screen:'#f5f4ed',seat:'#d28b58'}[item.type]);
  if(item.type==='speaker'){add(new BoxGeometry(...dims),mat(color)); add(new CylinderGeometry(dims[0]*.19,dims[0]*.19,.025,24),mat('#11161c'),dims[1]*.27);add(new CylinderGeometry(dims[0]*.3,dims[0]*.3,.03,24),mat('#151b21'),-dims[1]*.19);}
  else if(item.type==='projector'){add(new BoxGeometry(...dims),mat(color));const lens=new Mesh(new CylinderGeometry(.035,.035,.035,24),mat('#18232d'));lens.rotation.x=Math.PI/2;lens.position.set(0,0,-dims[2]/2-.012);g.add(lens);}
  else if(item.type==='screen'){add(new BoxGeometry(...dims),mat(color,.2));}
  else {add(new BoxGeometry(dims[0],dims[1]*.56,dims[2]*.72),mat(color),dims[1]*.26);const back=add(new BoxGeometry(dims[0],dims[1]*.4,dims[2]*.13),mat(color),dims[1]*.77); back.position.z=dims[2]*.28;}
  g.position.copy(toVector3(item.position));g.rotation.copy(degreesToEuler(item.rotation));g.userData.equipmentId=item.id;g.userData.dimensions=[...dims]; return g;
}
