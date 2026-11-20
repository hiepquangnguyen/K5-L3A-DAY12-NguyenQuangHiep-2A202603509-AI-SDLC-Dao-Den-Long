import * as THREE from './vendor/three.module.min.js';

const params = new URLSearchParams(window.location.search);
const DURATION_S = Math.max(1, Number(params.get('duration') || '30'));
const WARMUP_S = Math.max(0, Number(params.get('warmup') || '3'));

const PALETTE = {
  sky: 0x0e1430,
  fog: 0x1b2350,
  grass: 0x2f5d50,
  sand: 0xc9b48a,
  wood: 0x6b4a2f,
  cloudSea: 0x12384a,
  lanternLit: 0xffb347,
  lanternCore: 0xffe9b0,
  lanternUnlit: 0x5b5f6e,
  moteCore: 0xfff6c2,
  moteHalo: 0xffe58a,
  shadeBody: 0x120a1a,
  shadeAura: 0x7a3cff,
  mayCloak: 0xe8e2d0,
  mayCrimson: 0xc8102e,
  gold: 0xf2c14e,
};

const canvas = document.getElementById('bench-canvas');
const elStatus = document.getElementById('bench-status');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

function detectRendererName() {
  try {
    const gl = renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    if (dbg) {
      const gpu = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
      if (gpu) return `Three.js r170 / ${gpu}`;
    }
    const fallback = gl.getParameter(gl.RENDERER);
    if (fallback) return `Three.js r170 / ${fallback}`;
  } catch (_) {}
  return 'Three.js r170 (WebGL2)';
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(PALETTE.sky);
scene.fog = new THREE.FogExp2(PALETTE.fog, 0.011);

const camera = new THREE.PerspectiveCamera(54, window.innerWidth / window.innerHeight, 0.1, 320);
camera.position.set(30, 15, 0);
camera.lookAt(0, 0, 0);

// Full Night 1 lighting matching active play with 3/5 lit lanterns (0.15 + 0.55 * 0.6 = 0.48)
const ambientLight = new THREE.AmbientLight(0x8899cc, 0.48);
scene.add(ambientLight);

const hemiLight = new THREE.HemisphereLight(0x3a4d8f, 0x122230, 0.55);
scene.add(hemiLight);

const moonLight = new THREE.DirectionalLight(0xd9e4ff, 0.95);
moonLight.position.set(22, 42, 18);
moonLight.castShadow = true;
moonLight.shadow.mapSize.set(512, 512);
moonLight.shadow.camera.near = 5;
moonLight.shadow.camera.far = 120;
const dCam = 48;
moonLight.shadow.camera.left = -dCam;
moonLight.shadow.camera.right = dCam;
moonLight.shadow.camera.top = dCam;
moonLight.shadow.camera.bottom = -dCam;
scene.add(moonLight);

// Cloud sea base (static, no extra particle/creative FX)
const seaFloor = new THREE.Mesh(
  new THREE.CircleGeometry(220, 48),
  new THREE.MeshBasicMaterial({ color: PALETTE.cloudSea })
);
seaFloor.rotation.x = -Math.PI / 2;
seaFloor.position.y = -11.5;
scene.add(seaFloor);

// Night 1 Island (r=40m)
const grassMat = new THREE.MeshStandardMaterial({ color: PALETTE.grass, roughness: 0.9 });
const sandMat = new THREE.MeshStandardMaterial({ color: PALETTE.sand, roughness: 0.85 });
const woodMat = new THREE.MeshStandardMaterial({ color: PALETTE.wood, roughness: 0.82 });

const islandBody = new THREE.Mesh(new THREE.CylinderGeometry(40, 38.4, 3.0, 48), grassMat);
islandBody.position.set(0, -1.5, 0);
islandBody.receiveShadow = true;
scene.add(islandBody);

const rim = new THREE.Mesh(new THREE.TorusGeometry(39.7, 0.38, 8, 48), sandMat);
rim.rotation.x = Math.PI / 2;
rim.position.set(0, 0.04, 0);
scene.add(rim);

for (let i = 0; i < 4; i++) {
  const plank = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.16, 0.9), woodMat);
  plank.position.set(0, 0.08, 38.5 + i * 1.1);
  scene.add(plank);
}

// Stationary Mây at (0, 0, 0) without extra creative Halo/trails
const playerGroup = new THREE.Group();
const cloak = new THREE.Mesh(new THREE.ConeGeometry(0.54, 1.25, 14), new THREE.MeshStandardMaterial({ color: PALETTE.mayCloak, roughness: 0.75 }));
cloak.position.y = 0.68;
cloak.castShadow = true;
const scarf = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.09, 8, 16), new THREE.MeshStandardMaterial({ color: PALETTE.mayCrimson, roughness: 0.6 }));
scarf.rotation.x = Math.PI / 2;
scarf.position.y = 1.25;
const head = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 12), new THREE.MeshStandardMaterial({ color: 0xf6d9c3, roughness: 0.65 }));
head.position.y = 1.44;
const hat = new THREE.Mesh(new THREE.ConeGeometry(0.68, 0.38, 16), new THREE.MeshStandardMaterial({ color: PALETTE.sand, roughness: 0.85, side: THREE.DoubleSide }));
hat.position.y = 1.7;
const miniLantern = new THREE.Mesh(
  new THREE.SphereGeometry(0.11, 8, 8),
  new THREE.MeshStandardMaterial({ color: PALETTE.lanternCore, emissive: PALETTE.lanternLit, emissiveIntensity: 2.0 })
);
miniLantern.position.set(0, 1.32, 0.56);
const playerLight = new THREE.PointLight(PALETTE.lanternLit, 3.6, 15, 1.6);
playerLight.position.set(0, 1.5, 0.56);
playerGroup.add(cloak, scarf, head, hat, miniLantern, playerLight);
scene.add(playerGroup);

// Build Lanterns L1..L5 (L1-L3 lit with full lights + safe rings; L4-L5 unlit)
function addLantern(lData) {
  const g = new THREE.Group();
  g.position.set(lData.pos[0], lData.pos[1], lData.pos[2]);

  const stoneBase = new THREE.Mesh(
    new THREE.CylinderGeometry(0.7, 0.88, 0.42, 8),
    new THREE.MeshStandardMaterial({ color: PALETTE.lanternUnlit, roughness: 0.9 })
  );
  stoneBase.position.y = 0.21;
  stoneBase.castShadow = true;

  const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.24, 2.5, 8), woodMat);
  pillar.position.y = 1.65;
  pillar.castShadow = true;

  const housing = new THREE.Mesh(
    new THREE.SphereGeometry(0.62, 14, 12),
    new THREE.MeshStandardMaterial({
      color: lData.lit ? PALETTE.lanternCore : PALETTE.lanternUnlit,
      emissive: lData.lit ? PALETTE.lanternLit : PALETTE.lanternUnlit,
      emissiveIntensity: lData.lit ? 2.4 : 0.25,
      roughness: 0.4,
    })
  );
  housing.scale.set(lData.lit ? 1.0 : 1.06, lData.lit ? 1.25 : 1.0, lData.lit ? 1.0 : 1.06);
  housing.position.y = 3.2;

  const cap = new THREE.Mesh(new THREE.ConeGeometry(0.85, 0.5, 8), woodMat);
  cap.position.y = 4.0;
  g.add(stoneBase, pillar, housing, cap);

  if (lData.lit) {
    const light = new THREE.PointLight(PALETTE.lanternLit, 10.0, 26, 1.5);
    light.position.y = 3.2;
    const safeRing = new THREE.Mesh(
      new THREE.RingGeometry(5.86, 6.0, 40),
      new THREE.MeshBasicMaterial({ color: PALETTE.gold, side: THREE.DoubleSide, transparent: true, opacity: 0.36 })
    );
    safeRing.rotation.x = -Math.PI / 2;
    safeRing.position.y = 0.08;
    g.add(light, safeRing);
  }
  scene.add(g);
}

// Instanced meshes for exact 200 Shades + 100 Motes (zero per-frame GC allocation)
let shadeBodiesMesh = null;
let shadeEyesMesh = null;
let moteCoreMesh = null;
let moteHaloMesh = null;
let shadeCount = 0;
const latestSx = new Float32Array(256);
const latestSy = new Float32Array(256);
const latestSz = new Float32Array(256);
const dummy = new THREE.Object3D();

function initEntities(msg) {
  for (const lan of msg.lanterns) addLantern(lan);

  // Motes (static in bench mode because pickup/spawn disabled)
  const motes = msg.motes || [];
  if (motes.length > 0 && !moteCoreMesh) {
    moteCoreMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.24, 8, 8),
      new THREE.MeshStandardMaterial({
        color: PALETTE.moteCore,
        emissive: PALETTE.moteHalo,
        emissiveIntensity: 2.3,
      }),
      motes.length
    );
    moteHaloMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.42, 8, 8),
      new THREE.MeshBasicMaterial({ color: PALETTE.moteHalo, transparent: true, opacity: 0.28 }),
      motes.length
    );
    for (let i = 0; i < motes.length; i++) {
      const m = motes[i];
      dummy.position.set(m[0], m[1] + 0.72, m[2]);
      dummy.scale.set(1, 1, 1);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      moteCoreMesh.setMatrixAt(i, dummy.matrix);
      moteHaloMesh.setMatrixAt(i, dummy.matrix);
    }
    moteCoreMesh.instanceMatrix.needsUpdate = true;
    moteHaloMesh.instanceMatrix.needsUpdate = true;
    scene.add(moteCoreMesh, moteHaloMesh);
  }

  // Shades (200 wandering Shades)
  const shades = msg.shades || [];
  shadeCount = shades.length;
  if (shadeCount > 0 && !shadeBodiesMesh) {
    shadeBodiesMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.62, 10, 10),
      new THREE.MeshStandardMaterial({
        color: PALETTE.shadeBody,
        emissive: PALETTE.shadeAura,
        emissiveIntensity: 0.9,
        roughness: 0.5,
      }),
      shadeCount
    );
    shadeBodiesMesh.castShadow = true;
    shadeEyesMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.09, 6, 6),
      new THREE.MeshBasicMaterial({ color: PALETTE.shadeAura }),
      shadeCount * 2
    );
    for (let i = 0; i < shadeCount; i++) {
      latestSx[i] = shades[i][0];
      latestSy[i] = shades[i][1];
      latestSz[i] = shades[i][2];
    }
    updateShadeMatrices();
    scene.add(shadeBodiesMesh, shadeEyesMesh);
  }
}

function updateShadeMatrices() {
  if (!shadeBodiesMesh || shadeCount === 0) return;
  for (let i = 0; i < shadeCount; i++) {
    const x = latestSx[i];
    const y = latestSy[i];
    const z = latestSz[i];
    dummy.position.set(x, y, z);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(1, 1.35, 1);
    dummy.updateMatrix();
    shadeBodiesMesh.setMatrixAt(i, dummy.matrix);

    dummy.scale.set(1, 1, 1);
    dummy.position.set(x - 0.2, y + 0.25, z + 0.52);
    dummy.updateMatrix();
    shadeEyesMesh.setMatrixAt(i * 2, dummy.matrix);

    dummy.position.set(x + 0.2, y + 0.25, z + 0.52);
    dummy.updateMatrix();
    shadeEyesMesh.setMatrixAt(i * 2 + 1, dummy.matrix);
  }
  shadeBodiesMesh.instanceMatrix.needsUpdate = true;
  shadeEyesMesh.instanceMatrix.needsUpdate = true;
}

let sceneReady = false;
function connectBenchWS() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${window.location.host}/ws`);
  ws.binaryType = 'arraybuffer';
  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      const f32 = new Float32Array(ev.data);
      const n = Math.min(shadeCount, Math.floor(f32.length / 3));
      for (let i = 0; i < n; i++) {
        const base = i * 3;
        latestSx[i] = f32[base];
        latestSy[i] = f32[base + 1];
        latestSz[i] = f32[base + 2];
      }
      return;
    }
    const msg = JSON.parse(ev.data);
    if (msg.type === 'bench_init') {
      initEntities(msg);
      sceneReady = true;
    }
  };
}
connectBenchWS();

// Orbit: center (0,0,0), radius 30m, Y=15m, start angle 0 deg (30,15,0), CCW from above, 15s/rev
const ORBIT_RADIUS = 30.0;
const ORBIT_Y = 15.0;
const PERIOD_S = 15.0;

let firstFrameSent = false;
let measuringStarted = false;
let benchDoneSent = false;
let startMs = 0;
let measureStartMs = 0;
let prevFrameMs = 0;
const dtSamples = [];

function tickBench(now) {
  if (!benchDoneSent) {
    requestAnimationFrame(tickBench);
  }

  if (!sceneReady) {
    renderer.render(scene, camera);
    return;
  }

  if (!firstFrameSent) {
    firstFrameSent = true;
    startMs = now;
    measureStartMs = now + WARMUP_S * 1000.0;
    prevFrameMs = now;
    elStatus.textContent = `Khởi động Benchmark (${WARMUP_S}s warm-up, sau đó đo ${DURATION_S}s)...`;
    fetch('/api/bench/first_frame', { method: 'POST', body: '{}' }).catch(() => {});
  }

  const elapsedSec = (now - startMs) / 1000.0;
  const theta = (elapsedSec / PERIOD_S) * Math.PI * 2.0;
  camera.position.set(Math.cos(theta) * ORBIT_RADIUS, ORBIT_Y, -Math.sin(theta) * ORBIT_RADIUS);
  camera.lookAt(0, 0, 0);

  updateShadeMatrices();
  renderer.render(scene, camera);

  const dtMs = now - prevFrameMs;
  prevFrameMs = now;

  if (now >= measureStartMs) {
    if (!measuringStarted) {
      measuringStarted = true;
      elStatus.textContent = `Đang đo hiệu năng (${DURATION_S}s)...`;
    }
    if (dtMs > 0.0) {
      dtSamples.push(dtMs);
    }
    const measuredSec = (now - measureStartMs) / 1000.0;
    if (measuredSec >= DURATION_S && !benchDoneSent) {
      benchDoneSent = true;
      elStatus.textContent = `Hoàn tất đo ${dtSamples.length} khung hình — đang lưu bench.json...`;
      fetch('/api/bench/done', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dt_ms: dtSamples,
          renderer: detectRendererName(),
        }),
      }).catch(() => {});
    }
  }
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

requestAnimationFrame(tickBench);
