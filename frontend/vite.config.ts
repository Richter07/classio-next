import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon.svg", "icons/apple-touch-icon.png"],
      manifest: {
        name: "Classio",
        short_name: "Classio",
        description: "Les notes de l'école, sur votre téléphone.",
        lang: "fr",
        start_url: "/",
        display: "standalone",
        background_color: "#FBF7EC",
        theme_color: "#0E5A43",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Seule l'application est précachée. Les réponses de l'API, qui contiennent des données
        // de mineurs, ne passent jamais par le cache du service worker.
        globPatterns: ["**/*.{js,css,html,svg,png}"],
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//],
      },
    }),
  ],
  server: {
    // Même origine qu'en production : le cookie de session HttpOnly fonctionne sans CORS.
    host: true,
    allowedHosts: [".classio.localhost"],
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: { target: "es2019", sourcemap: false },
});
