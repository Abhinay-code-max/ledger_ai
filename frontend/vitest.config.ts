import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: [
      'tests/unit/**/*.{test,spec}.ts',
      'tests/component/**/*.{test,spec}.tsx',
      'tests/security/**/*.{test,spec}.ts',
      'tests/a11y/**/*.{test,spec}.tsx',
      'tests/reproducibility/**/*.{test,spec}.ts',
    ],
    exclude: ['tests/e2e/**'],
  },
})
