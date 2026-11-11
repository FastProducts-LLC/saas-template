/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// All API calls go through the dev-server proxy so the app and API share an
// origin (cookies just work). In Docker, VITE_PROXY_TARGET=http://backend:8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Loopback by default so `npm run dev` on a laptop isn't served to the
    // whole Wi-Fi. Docker passes `--host` (frontend/Dockerfile) and device
    // testing can opt in with `npm run dev -- --host`.
    port: 5173,
    proxy: {
      // Trailing slash so SPA routes like /api-keys don't get proxied.
      "/api/": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:21428",
        changeOrigin: true,
        // Forward X-Forwarded-For so the backend audit trail sees the
        // browser's IP, not the Vite container's.
        xfwd: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
