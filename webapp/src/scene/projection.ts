import { Euler, Vector3 } from 'three';
import type { Equipment } from '../config/schema';
export type ProjectionResult = { supported:boolean; reason?:string; distance:number; width:number; height:number; fits:boolean };
export function calculateProjection(projector: Equipment, screen: Equipment): ProjectionResult {
  const direction=new Vector3(0,0,-1).applyEuler(new Euler(...projector.rotation.map((n)=>n*Math.PI/180) as [number,number,number]));
  const lens=new Vector3(...projector.position); lens.y += projector.lensOffset??0;
  const toScreen=new Vector3(...screen.position).sub(lens);
  const distance=toScreen.length();
  if(Math.abs(direction.x)>.015 || Math.abs(direction.y)>.015 || direction.dot(toScreen.clone().normalize())<.995) return {supported:false,reason:'Angled projection is not supported yet.',distance,width:0,height:0,fits:false};
  const screenNormal=new Vector3(0,0,1).applyEuler(new Euler(...screen.rotation.map((n)=>n*Math.PI/180) as [number,number,number]));
  if(direction.dot(screenNormal)>-.995) return {supported:false,reason:'Angled screen configurations are not supported yet.',distance,width:0,height:0,fits:false};
  if(!projector.throwRatio||!projector.aspectRatio) return {supported:false,reason:'Set throw ratio and aspect ratio to preview.',distance,width:0,height:0,fits:false};
  const width=distance/projector.throwRatio, height=width/projector.aspectRatio;
  const screenWidth=screen.dimensions[0],screenHeight=screen.dimensions[1];
  return {supported:true,distance,width,height,fits:width<=screenWidth&&height<=screenHeight};
}
