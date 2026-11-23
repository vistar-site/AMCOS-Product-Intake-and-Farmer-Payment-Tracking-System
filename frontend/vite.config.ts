/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// The browser calls /api/... on the Vite dev server; Vite forwards (proxies) it to
// the backend. Same origin for the browser => the httpOnly refresh cookie just works
// and no CORS is needed in development. Inside Docker the target is http://backend:8000.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // PWA: generates the web app manifest (installable app) and a service worker
    // (Workbox) that caches the APPLICATION SHELL — HTML, JS, CSS, icons — so the app
    // opens with no internet. API responses are NOT cached by the service worker:
    // offline data lives in IndexedDB, under our explicit control.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'AMCOS Produce & Payments',
        short_name: 'AMCOS',
        description: 'Produce intake and farmer payment tracking for agricultural cooperatives',
        theme_color: '#0f3420',
        background_color: '#f8fafc',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',        // any page URL opens the cached app offline
        navigateFallbackDenylist: [/^\/api\//], // never answer API calls from the cache
      },
      devOptions: { enabled: false },           // SW only in production builds (see docs)
    }),
  ],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
    proxy: {
      '/api': process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
