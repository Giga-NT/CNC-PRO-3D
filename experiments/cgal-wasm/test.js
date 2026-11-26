import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.getElementById('view');
const status = document.getElementById('status');
const button = document.getElementById('run');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x17191d);
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);
camera.position.set(3.2, 2.5, 3.5);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x4b5360, 2));
const key = new THREE.DirectionalLight(0xffffff, 2.5);
key.position.set(4, 6, 5);
key.castShadow = true;
scene.add(key);
const grid = new THREE.GridHelper(4, 20, 0x596273, 0x343a44);
grid.position.y = -1.02;
scene.add(grid);

let resultMesh = null;
const worker = new Worker('./cgal-worker.js', { type: 'module' });

function makeBox(center, half) {
  const vertices = [
    [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
    [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]
  ];
  const indices = [
    0,2,1, 0,3,2, 4,5,6, 4,6,7,
    0,1,5, 0,5,4, 3,7,6, 3,6,2,
    0,4,7, 0,7,3, 1,2,6, 1,6,5
  ];
  const positions = new Float32Array(vertices.length * 3);
  vertices.forEach((v, i) => {
    positions[i*3] = center[0] + v[0] * half[0];
    positions[i*3+1] = center[1] + v[1] * half[1];
    positions[i*3+2] = center[2] + v[2] * half[2];
  });
  return { positions, indices: new Uint32Array(indices) };
}

function render() {
  requestAnimationFrame(render);
  controls.update();
  renderer.render(scene, camera);
}
render();

function resize() {
  const width = canvas.clientWidth || 1;
  const height = canvas.clientHeight || 1;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

button.addEventListener('click', () => {
  button.disabled = true;
  status.textContent = 'Загрузка CGAL WASM и выполнение Difference…';
  worker.postMessage({
    type: 'difference',
    a: makeBox([0,0,0], [1,1,1]),
    b: makeBox([0.75,0,0], [0.5,0.5,0.5])
  });
});

worker.onmessage = (event) => {
  button.disabled = false;
  const data = event.data || {};
  if (data.type === 'error') {
    status.textContent = 'ОШИБКА: ' + data.message;
    return;
  }
  if (data.type !== 'result') return;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(data.positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(data.indices, 1));
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  if (resultMesh) {
    scene.remove(resultMesh);
    resultMesh.geometry.dispose();
    resultMesh.material.dispose();
  }
  resultMesh = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({ color: 0x9caec8, metalness: 0.18, roughness: 0.48, side: THREE.DoubleSide })
  );
  resultMesh.castShadow = true;
  resultMesh.receiveShadow = true;
  scene.add(resultMesh);

  const s = data.stats;
  status.textContent =
    'УСПЕХ: Difference вернул замкнутую сетку.\n' +
    'Проверка входов: ' + s.validationMs.toFixed(1) + ' ms; ' +
    'булева операция: ' + s.booleanMs.toFixed(1) + ' ms; ' +
    'всего в Worker: ' + s.totalMs.toFixed(1) + ' ms.\n' +
    'Вершин: ' + s.vertices.toLocaleString('ru-RU') +
    '; треугольников: ' + s.triangles.toLocaleString('ru-RU') + '.';
};
