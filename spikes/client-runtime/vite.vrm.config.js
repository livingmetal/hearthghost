import { defineConfig } from "vite";

export default defineConfig({
  build: {
    emptyOutDir: true,
    lib: {
      entry: new URL("./src/vrm-candidate.ts", import.meta.url).pathname,
      fileName: "vrm-candidate",
      formats: ["es"],
    },
    outDir: "dist/vrm",
  },
});
