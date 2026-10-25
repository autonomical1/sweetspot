export const FT_TO_M = 0.3048;

export function ftToM(feet: number): number {
  return feet * FT_TO_M;
}

export function mToFt(meters: number): number {
  return meters / FT_TO_M;
}
