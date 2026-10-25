import { useEffect, useState } from 'react';
import { Pair } from './screens/Pair';
import { Start } from './screens/Start';
import { Viewer } from './screens/Viewer';

export default function App() {
  const [query, setQuery] = useState(() => window.location.search);
  useEffect(() => {
    const update = () => setQuery(window.location.search);
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);
  const navigate = (search: string) => {
    window.history.pushState({}, '', `/app/${search}`);
    setQuery(window.location.search);
  };
  const params = new URLSearchParams(query);
  if (params.has('pair')) return <Pair onBack={() => navigate('')} />;
  const roomId = params.get('room');
  if (roomId) return <Viewer roomId={roomId} initialView={params.get('view') === '2d' ? '2d' : '3d'} navigate={navigate} />;
  return <Start navigate={navigate} initialView={params.get('view') === '2d' ? '2d' : '3d'} />;
}
