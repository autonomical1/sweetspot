import { Viewer } from './Viewer';

export function Start({ navigate, initialView }: { navigate: (search: string) => void; initialView: '3d' | '2d' }) {
  return <Viewer roomId={null} initialView={initialView} navigate={navigate} />;
}
