import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev: 前端 :5173 代理 REST(/api) 与 WebSocket(/ws) 到后端 :8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist" },
});
