import { defineConfig } from 'vite';

// `npm run build`        -> dist/ (copies public/, i.e. public/data from `make export`)
// `npm run build:single` -> dist-single/ (no public dir; scripts/inline-single.mjs inlines JS, CSS and data)
// base './' keeps every URL relative so the site works under a GitHub Pages project subpath and from file://.
export default defineConfig(({ mode }) => {
  const single = mode === 'single';
  return {
    base: './',
    publicDir: single ? false : 'public',
    server: { fs: { strict: true } },
    build: {
      outDir: single ? (process.env.SINGLE_OUT ?? 'dist-single') : 'dist',
      emptyOutDir: true,
      target: 'es2020',
      assetsInlineLimit: single ? 100_000_000 : 4096,
      cssCodeSplit: false,
      modulePreload: single ? false : { polyfill: true },
      rollupOptions: single ? { output: { inlineDynamicImports: true } } : {},
    },
  };
});
