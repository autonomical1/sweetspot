import type { CSSProperties, ReactNode } from 'react';
import { formatFtIn } from '../../lib/format';

export const roleColors: Record<string, string> = {
  L: '#64c7ff', R: '#64c7ff', C: '#f4bd61', LFE: '#d98cff', Ls: '#77d79a', Rs: '#77d79a',
  Lss: '#77d79a', Rss: '#77d79a', Lrs: '#77d79a', Rrs: '#77d79a', Ltf: '#f28b82', Rtf: '#f28b82',
  Ltr: '#f28b82', Rtr: '#f28b82', Ltm: '#f28b82', Rtm: '#f28b82', LFE2: '#d98cff',
};

export function RoleChip({ role }: { role: string }) {
  return <span className="role-chip" style={{ '--role-color': roleColors[role] ?? '#8e9aa5' } as CSSProperties}>{role}</span>;
}

export const money = (value: number, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value);
export const position = ([x, y, z]: number[]) => `${formatFtIn(x)}, ${formatFtIn(z)} (${formatFtIn(y)})`;
export const section = (title: string, children: ReactNode) => <section className="panel-section"><h3>{title}</h3>{children}</section>;
