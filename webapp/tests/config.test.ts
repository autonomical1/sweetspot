import { describe, expect, it } from 'vitest';
import { parseRoomConfig } from '../src/config/schema';
import { exampleConfig } from '../src/config/example';
import { degreesToEuler, eulerToDegrees } from '../src/scene/coordinates';
import { calculateProjection } from '../src/scene/projection';

describe('room configuration',()=>{
 it('accepts the example and rejects a broken schema',()=>{expect(parseRoomConfig(exampleConfig).version).toBe(1);expect(()=>parseRoomConfig({...exampleConfig,version:2})).toThrow();});
 it('preserves optional object descriptions from the room file',()=>{const config=parseRoomConfig({...exampleConfig,equipment:[{...exampleConfig.equipment[0],description:'Front wall projection surface'}]});expect(config.equipment[0].description).toBe('Front wall projection surface');});
 it('converts degree rotations to and from Three.js radians',()=>{const e=degreesToEuler([0,90,0]);expect(e.y).toBeCloseTo(Math.PI/2);expect(eulerToDegrees(e)[1]).toBeCloseTo(90);});
 it('calculates a perpendicular projection and identifies angled projection',()=>{const p=exampleConfig.equipment.find(e=>e.type==='projector')!,s=exampleConfig.equipment.find(e=>e.type==='screen')!;expect(calculateProjection(p,s).supported).toBe(true);expect(calculateProjection(p,s).width).toBeCloseTo(3.022);expect(calculateProjection({...p,rotation:[12,0,0]},s).supported).toBe(false);expect(calculateProjection(p,{...s,rotation:[0,12,0]}).supported).toBe(false);});
});
