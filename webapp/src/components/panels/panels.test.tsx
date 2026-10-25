// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Layout, Metrics, Room } from '../../api/client';
import { AcousticsPanel } from './AcousticsPanel';
import { LayoutPanel } from './LayoutPanel';
import { ShopPanel } from './ShopPanel';

const room = { room_id: 'r_demo', budget: 1500, dimensions: { width: 18, length: 13, height: 9 }, listener: { position: [9, 3.6, 11.5], facing: [0, -1] }, surfaces: [{ id: 'wall_n', kind: 'wall', material: 'drywall', polygon: [], absorption: { '500': .08, '1000': .09 } }], warnings: [] } as unknown as Room;
const layout: Layout = { stage: 'quick', speakers: [{ role: 'L', position: [2, 3.6, 0], aim: [9, 3.6, 11] }, { role: 'mystery', position: [3, 3, 1], aim: [9, 3, 11] }] };
const metrics: Metrics = { score: .5262, reflections: [{ speaker: 'L', surface_id: 'wall_n', delay_ms: 4.2, level_db: -8.1, point: [1, 2, 3] }], treatment_patches: [], sub_modes: { schroeder_hz: 85, axial_modes_hz: [30, 60], sub_position: [1, 1, 1] } };

describe('panels', () => {
  it('shows staged layout, unknown roles, and selects a speaker', () => {
    const select = vi.fn(); render(<LayoutPanel room={room} layout={layout} metrics={metrics} onSelect={select} />);
    expect(screen.getByText(/Showing the quick layout/)).toBeTruthy();
    expect(screen.getByText('mystery')).toBeTruthy();
    fireEvent.click(screen.getByText('L')); expect(select).toHaveBeenCalledWith('L');
  });

  it('recomputes with the chosen layout and height speakers', () => {
    const recompute = vi.fn(); render(<LayoutPanel room={room} layout={{ ...layout, preset: '5.1' }} metrics={metrics} onSelect={vi.fn()} onRecompute={recompute} />);
    fireEvent.click(screen.getByRole('button', { name: '7.1' })); fireEvent.click(screen.getByRole('button', { name: '.4' }));
    fireEvent.click(screen.getByRole('button', { name: 'Recompute as 7.1.4' })); expect(recompute).toHaveBeenCalledWith('7.1.4');
  });

  it('renders strong reflections and empty-shop placement hint', () => {
    render(<><AcousticsPanel room={room} metrics={metrics} onSelect={vi.fn()} /><ShopPanel room={room} hasLayout={false} /></>);
    expect(screen.getByText('strong')).toBeTruthy();
    expect(screen.getByText('Place the speakers first.')).toBeTruthy();
  });
});
