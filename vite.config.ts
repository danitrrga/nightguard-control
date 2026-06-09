import { defineConfig } from "vite";

// Tauri-aware Vite config (vanilla-TS template).
// The dev server port is FIXED to match tauri.conf.json -> build.devUrl.
export default defineConfig({
  // Frontend sources live in src/ (index.html + main.ts); build output goes to
  // the repo-root dist/ that tauri.conf.json references as ../dist.
  root: "src",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    target: "esnext",
  },
  // Prevent Vite from clearing the screen so Rust compiler errors stay visible.
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
});
