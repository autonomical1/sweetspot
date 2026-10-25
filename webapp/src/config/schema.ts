import { z } from 'zod';

const vector3 = z.tuple([z.number(), z.number(), z.number()]);
const equipment = z.object({
  id: z.string().min(1), name: z.string().min(1), description: z.string().optional(), type: z.enum(['speaker','projector','screen','seat']),
  dimensions: vector3, position: vector3, rotation: vector3.default([0,0,0]), color: z.string().optional(),
  modelUrl: z.string().optional(), imageUrl: z.string().optional(), lensOffset: z.number().optional(), throwRatio: z.number().positive().optional(),
  aspectRatio: z.number().positive().optional(), targetScreenId: z.string().optional()
});
export const RoomConfigSchema = z.object({
  version: z.literal(1), units: z.literal('m').default('m'), coordinateSystem: z.literal('Y-up').default('Y-up'),
  room: z.object({ width: z.number().positive(), length: z.number().positive(), height: z.number().positive(), floorColor: z.string().default('#343b43'), wallColor: z.string().default('#e1e5e7'), ceilingColor: z.string().default('#f1f1ec'), showCeiling: z.boolean().default(true) }),
  equipment: z.array(equipment),
  seats: z.array(z.object({ id:z.string(), name:z.string(), position:vector3, target:vector3.optional() })).default([])
}).superRefine((c,ctx)=>{
  const ids=new Set<string>(); c.equipment.forEach((e,i)=>{ if(ids.has(e.id)) ctx.addIssue({code:'custom',path:['equipment',i,'id'],message:`Duplicate equipment id: ${e.id}`}); ids.add(e.id); });
  c.equipment.forEach((e,i)=>{ if(e.type==='projector' && e.targetScreenId && !c.equipment.some(x=>x.id===e.targetScreenId&&x.type==='screen')) ctx.addIssue({code:'custom',path:['equipment',i,'targetScreenId'],message:'Projector targetScreenId must reference a screen.'}); });
});
export type RoomConfig = z.infer<typeof RoomConfigSchema>;
export type Equipment = RoomConfig['equipment'][number];
export function parseRoomConfig(input: unknown): RoomConfig { return RoomConfigSchema.parse(input); }
