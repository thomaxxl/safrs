import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const fsPromisesShim = fileURLToPath(
  new URL("./src/shims/fs-promises.ts", import.meta.url),
);
const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? "/admin-app/",
  plugins: [react()],
  resolve: {
    alias: {
      "fs/promises": fsPromisesShim,
      "node:fs/promises": fsPromisesShim,
    },
    preserveSymlinks: true,
  },
  server: {
    host: process.env.VITE_DEV_HOST ?? "127.0.0.1",
    port: Number(process.env.VITE_DEV_PORT ?? "5173"),
    strictPort: true,
    hmr: {
      clientPort: Number(process.env.VITE_HMR_CLIENT_PORT ?? "8000"),
      path: process.env.VITE_HMR_PATH ?? "/admin-app/__vite_hmr",
    },
    fs: {
      allow: [projectRoot],
    },
  },
});
