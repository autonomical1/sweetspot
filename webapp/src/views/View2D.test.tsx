/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { Room } from '../api/client';
import { useAppStore } from '../store';
import { View2D } from './View2D';

const room: Room = { schema_version:1, units:'ft', room_id:'r_plan', session_id:null, source:'rectangle', dimensions:{width:12,length:15,height:9}, surfaces:[], objects:[], listener:{position:[6,3.6,9],facing:[0,-1]}, budget:1500, warnings:[], frame:null, captured_room:null };

beforeEach(() => useAppStore.setState({ room, layout:null, metrics:null, selected:null, stage:'idle' }));
afterEach(cleanup);

describe('View2D', () => {
  it('renders safely without a layout', () => { render(<View2D />); expect(screen.getByLabelText('Room plan in feet, north at top')).toBeTruthy(); });
  it('uses a neutral color for an unknown role and marks refining work', () => {
    useAppStore.setState({ layout:{ stage:'refining', speakers:[{role:'Custom',position:[2,4,3],aim:[6,3,9]}] }, metrics:{} });
    render(<View2D />);
    expect(screen.getByText('Refining 3D...')).toBeTruthy();
    expect(screen.getByTestId('speaker-Custom').querySelector('rect')?.getAttribute('fill')).toBe('#aeb8c1');
  });
  it('escapes selection and tabs through speakers', () => {
    useAppStore.setState({ layout:{ speakers:[{role:'L',position:[2,3,3],aim:[6,3,9]},{role:'R',position:[9,3,3],aim:[6,3,9]}] }, metrics:{}, selected:'L' });
    render(<View2D />); const plan=screen.getByLabelText('Room plan in feet, north at top');
    fireEvent.keyDown(plan,{key:'Escape'}); expect(useAppStore.getState().selected).toBeNull();
    fireEvent.keyDown(plan,{key:'Tab'}); expect(useAppStore.getState().selected).toBe('L');
  });
});
