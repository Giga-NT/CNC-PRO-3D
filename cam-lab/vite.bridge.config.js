export default {
  configFile: false,
  root: __dirname,
  build: {
    target: 'es2020',
    outDir: 'dist',
    emptyOutDir: true,
    lib: {
      entry: 'bridge.ts',
      name: 'CNCVectorCAMBundle',
      formats: ['iife'],
      fileName: () => 'cnc-vector-cam.js'
    }
  }
};
