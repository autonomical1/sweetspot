import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Box3, Group, Vector3 } from 'three';
const cache=new Map<string,Promise<Group>>();
export async function loadModel(url:string):Promise<Group>{
  if(!cache.has(url)) cache.set(url,new GLTFLoader().loadAsync(url).then(g=>{
    const root=g.scene; const box=new Box3().setFromObject(root); const center=box.getCenter(new Vector3());
    root.position.sub(center); return root;
  }));
  return (await cache.get(url)!).clone(true);
}
export function fitModel(root:Group, dimensions:readonly number[]){
  root.updateMatrixWorld(true); const box=new Box3().setFromObject(root); const size=box.getSize(new Vector3());
  root.scale.set(dimensions[0]/(size.x||1),dimensions[1]/(size.y||1),dimensions[2]/(size.z||1));
}
