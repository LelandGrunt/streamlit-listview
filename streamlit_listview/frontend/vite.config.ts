import react from "@vitejs/plugin-react";
import process from "node:process";
import { defineConfig, UserConfig } from "vite";

/**
 * Vite configuration for the listview Streamlit Components V2 build.
 *
 * Library mode emits one hashed JS entry (index-[hash].js). With
 * cssCodeSplit:false, all imported CSS is extracted into ONE asset, renamed
 * to index-[hash].css below, so the Python js="index-*.js" / css="index-*.css"
 * globs each resolve to exactly one file (zero or multiple files error at
 * registration).
 *
 * NOTE: this is rolldown-vite — output overrides go under
 * build.rolldownOptions.output, not rollupOptions.
 *
 * @see https://vitejs.dev/config/ for complete Vite configuration options.
 */
export default defineConfig(() => {
  const isProd = process.env.NODE_ENV === "production";
  const isDev = !isProd;

  return {
    base: "./",
    plugins: [react()],
    define: {
      // We are building in library mode, we need to define the NODE_ENV
      // variable to prevent issues when executing the JS.
      "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV),
    },
    build: {
      minify: isDev ? false : "oxc",
      outDir: "build",
      sourcemap: isDev,
      // Collapse all imported CSS into a single extracted asset so the
      // css="index-*.css" glob resolves to exactly one file.
      cssCodeSplit: false,
      lib: {
        entry: "./src/index.tsx",
        name: "Listview",
        formats: ["es"],
        fileName: "index-[hash]",
      },
      rolldownOptions: {
        output: {
          // Hashed name for the single extracted stylesheet -> index-[hash].css.
          assetFileNames: "index-[hash][extname]",
          ...(!isDev && {
            minify: {
              compress: {
                dropConsole: true,
                dropDebugger: true,
              },
            },
          }),
        },
      },
    },
  } satisfies UserConfig;
});
