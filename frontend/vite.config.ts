import { defineConfig } from "vite";

export default defineConfig(({ mode }) => {
  const target =
    mode === "test" ? "http://127.0.0.1:8001" : "http://127.0.0.1:8000";
  return {
    server: {
      port: 5173,
      strictPort: true,
      proxy: { "/v1": target, "/health": target },
    },
  };
});
