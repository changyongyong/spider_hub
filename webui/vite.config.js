import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/ui/",
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/workers": "http://127.0.0.1:8000",
      "/slavers": "http://127.0.0.1:8000",
      "/jobs": "http://127.0.0.1:8000",
      "/fetch": "http://127.0.0.1:8000"
    }
  }
});
