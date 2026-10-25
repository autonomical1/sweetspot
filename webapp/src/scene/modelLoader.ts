import { Box3, Group, Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const cache = new Map<string, Promise<Group>>();

export async function loadModel(url: string): Promise<Group> {
  const resolved = url.startsWith('/models/') ? `${import.meta.env.BASE_URL}${url.slice(1)}` : url;
  if (!cache.has(resolved)) {
    cache.set(resolved, new GLTFLoader().loadAsync(resolved).then(gltf => {
      const root = gltf.scene;
      const box = new Box3().setFromObject(root);
      root.position.sub(box.getCenter(new Vector3()));
      return root;
    }));
  }
  return (await cache.get(resolved)!).clone(true);
}

export function fitModel(root: Group, dimensions: readonly number[]) {
  root.updateMatrixWorld(true);
  const size = new Box3().setFromObject(root).getSize(new Vector3());
  root.scale.set(dimensions[0] / (size.x || 1), dimensions[1] / (size.y || 1), dimensions[2] / (size.z || 1));
}
