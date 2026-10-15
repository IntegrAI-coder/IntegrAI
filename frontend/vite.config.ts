/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/IntegrAI/',
  plugins: [react()],
  publicDir: '../data',
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
