import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  publicDir: false,
  build: {
    outDir: "../web/spa",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/media": "http://127.0.0.1:8765",
      "/overview.html": "http://127.0.0.1:8765",
      "/claims.html": "http://127.0.0.1:8765",
      "/backtest.html": "http://127.0.0.1:8765",
      "/claim-": "http://127.0.0.1:8765",
    },
  },
});
