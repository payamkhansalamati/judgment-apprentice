import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
const backendUrl = process.env.JA_BACKEND_URL ?? "http://127.0.0.1:8000";
const apiProxy = {
  target: backendUrl,
  ws: true,
  headers: { host: "127.0.0.1:8000" },
};
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    proxy: { "/api": apiProxy, "/ready": apiProxy },
  },
  preview: { host: "127.0.0.1", proxy: { "/api": apiProxy } },
});
