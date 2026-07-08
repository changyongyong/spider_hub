import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  const proxyOptions = {
    target: apiProxyTarget,
  };

  return {
    base: "/ui/",
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        "/auth": proxyOptions,
        "/environments": proxyOptions,
        "/health": proxyOptions,
        "/workers": proxyOptions,
        "/slaves": proxyOptions,
        "/jobs": proxyOptions,
        "/fetch": proxyOptions
      }
    }
  };
});
