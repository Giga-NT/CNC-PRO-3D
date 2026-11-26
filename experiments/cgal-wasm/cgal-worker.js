import createCGALModule from './dist/cgal_boolean.js';

let modulePromise = null;

async function getModule() {
  if (!modulePromise) {
    modulePromise = createCGALModule({
      locateFile: (path) => new URL('./dist/' + path, import.meta.url).href
    });
  }
  return modulePromise;
}

function copyIntoWasm(module, source, heapName, bytesPerElement) {
  if (!source || !source.length) return 0;
  const pointer = module._malloc(source.byteLength);
  if (!pointer) throw new Error('WASM memory allocation failed');
  const heap = module[heapName];
  const offset = pointer / bytesPerElement;
  heap.set(source, offset);
  return pointer;
}

self.onmessage = async (event) => {
  const data = event.data || {};
  if (data.type !== 'difference') return;

  const started = performance.now();
  let module;
  let aPositionPointer = 0;
  let aIndexPointer = 0;
  let bPositionPointer = 0;
  let bIndexPointer = 0;

  try {
    module = await getModule();
    const aPositions = data.a.positions;
    const aIndices = data.a.indices || new Uint32Array(0);
    const bPositions = data.b.positions;
    const bIndices = data.b.indices || new Uint32Array(0);

    aPositionPointer = copyIntoWasm(module, aPositions, 'HEAPF32', 4);
    aIndexPointer = copyIntoWasm(module, aIndices, 'HEAPU32', 4);
    bPositionPointer = copyIntoWasm(module, bPositions, 'HEAPF32', 4);
    bIndexPointer = copyIntoWasm(module, bIndices, 'HEAPU32', 4);

    const status = module._cgal_run_difference(
      aPositionPointer, aPositions.length / 3,
      aIndexPointer, aIndices.length,
      bPositionPointer, bPositions.length / 3,
      bIndexPointer, bIndices.length
    );

    if (status !== 0) {
      throw new Error(module.UTF8ToString(module._cgal_last_error()) || ('CGAL error ' + status));
    }

    const vertexCount = module._cgal_result_vertex_count();
    const indexCount = module._cgal_result_index_count();
    const positionsPointer = module._cgal_result_positions_ptr();
    const indicesPointer = module._cgal_result_indices_ptr();
    const positions = module.HEAPF32.slice(positionsPointer / 4, positionsPointer / 4 + vertexCount * 3);
    const indices = module.HEAPU32.slice(indicesPointer / 4, indicesPointer / 4 + indexCount);

    self.postMessage({
      type: 'result',
      positions,
      indices,
      stats: {
        validationMs: module._cgal_validation_ms(),
        booleanMs: module._cgal_boolean_ms(),
        totalMs: performance.now() - started,
        vertices: vertexCount,
        triangles: indexCount / 3
      }
    }, [positions.buffer, indices.buffer]);
  } catch (error) {
    self.postMessage({ type: 'error', message: error && error.message ? error.message : String(error) });
  } finally {
    if (module) {
      if (aPositionPointer) module._free(aPositionPointer);
      if (aIndexPointer) module._free(aIndexPointer);
      if (bPositionPointer) module._free(bPositionPointer);
      if (bIndexPointer) module._free(bIndexPointer);
    }
  }
};
