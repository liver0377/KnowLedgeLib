import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    proxy: {
      "/auth": "http://localhost:8080",
      "/info": "http://localhost:8080",
      "/invoke": "http://localhost:8080",
      "/stream": "http://localhost:8080",
      "/history": "http://localhost:8080",
      "/feedback": "http://localhost:8080",
      "/health": "http://localhost:8080",
    },
  },
});
