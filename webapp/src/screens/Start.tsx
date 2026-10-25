import { Viewer } from './Viewer';

export function Start({ navigate }: { navigate: (search: string) => void }) {
  return <Viewer roomId={null} navigate={navigate} />;
}
