import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // « prompt » : la nouvelle version attend l'accord de l'utilisateur (UpdateBanner), pour ne
      // jamais recharger la page au milieu d'une saisie de notes.
      registerType: "prompt",
      injectRegister: false,
      includeAssets: ["icons/icon.svg", "icons/apple-touch-icon.png"],
      manifest: {
        name: "Classio",
        short_name: "Classio",
        description: "Les notes de l'école, sur votre téléphone.",
        lang: "fr",
        id: "/",
        start_url: "/",
        scope: "/",
        categories: ["education"],
        prefer_related_applications: false,
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
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//],
      },
    }),
  ],
  server: {
    // Même origine qu'en production : le cookie de session HttpOnly fonctionne sans CORS.
    host: true,
    // Accès depuis un téléphone du même réseau Wi-Fi (adresse IP du PC).
    allowedHosts: [".classio.localhost", "localhost"],
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/admin": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: { target: "es2019", sourcemap: false },
});
