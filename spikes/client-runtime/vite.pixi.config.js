import { defineConfig } from "vite";

export default defineConfig({
  build: {
    emptyOutDir: true,
    lib: {
      entry: new URL("./src/pixi-candidate.ts", import.meta.url).pathname,
      fileName: "pixi-candidate",
      formats: ["es"],
    },
    outDir: "dist/pixi",
  },
});
