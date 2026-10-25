import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  base: "./",
  publicDir: "public",
  build: {
    outDir: "../gerald/home/webui",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(root, "index.html"),
        td: resolve(root, "td.html"),
        board: resolve(root, "board.html")
      },
      output: {
        assetFileNames: assetInfo =>
          assetInfo.name?.endsWith(".ttf") ? "fonts/[name][extname]" : "assets/[name]-[hash][extname]"
      }
    }
  }
});
