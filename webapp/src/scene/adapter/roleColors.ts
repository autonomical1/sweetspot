export const roleColors = {
  front: '#4cc9f0',
  centre: '#f4d35e',
  lfe: '#f28f3b',
  surround: '#a78bfa',
  overhead: '#65d6a2',
  unknown: '#c4ccd4',
} as const;

export type RoleFamily = keyof typeof roleColors;

export function roleFamily(role: string): RoleFamily {
  if (role === 'L' || role === 'R') return 'front';
  if (role === 'C') return 'centre';
  if (role === 'LFE' || role === 'LFE2') return 'lfe';
  if (['Ls', 'Rs', 'Lss', 'Rss', 'Lrs', 'Rrs'].includes(role)) return 'surround';
  if (['Ltf', 'Rtf', 'Ltr', 'Rtr', 'Ltm', 'Rtm'].includes(role)) return 'overhead';
  return 'unknown';
}
