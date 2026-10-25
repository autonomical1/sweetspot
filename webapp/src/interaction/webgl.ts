let available: boolean | null = null;

export function hasWebGL(): boolean {
  if (available !== null) return available;
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2') || canvas.getContext('webgl');
    available = Boolean(context);
    context?.getExtension('WEBGL_lose_context')?.loseContext();
    return available;
  } catch { available = false; return false; }
}
