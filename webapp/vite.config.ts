import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: { outDir: '../web', emptyOutDir: false },
  server: {
    proxy: Object.fromEntries(
      ['/rooms', '/health', '/products', '/materials', '/sessions'].map(path => [path, 'http://127.0.0.1:8000']),
    ),
  },
});
