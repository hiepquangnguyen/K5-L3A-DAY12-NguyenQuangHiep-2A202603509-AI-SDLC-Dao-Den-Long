import * as THREE from './vendor/three.module.min.js';

// ---------- Standard Palette (Ticket-02) ----------
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
  shadeStun: 0x3a3450,
  mayCloak: 0xe8e2d0,
  mayCrimson: 0xc8102e,
  gold: 0xf2c14e,
  drifter: 0x8fa3b8,
};

// ---------- Settings Persistence ----------
const SETTINGS_KEY = 'ddl_settings_v1';
function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      return {
        volume: typeof p.volume === 'number' ? Math.max(0, Math.min(100, p.volume)) : 70,
        sensitivity: typeof p.sensitivity === 'number' ? Math.max(0.2, Math.min(2.5, p.sensitivity)) : 1.0,
      };
    }
  } catch (_) {}
  return { volume: 70, sensitivity: 1.0 };
}
function saveSettings(cfg) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(cfg));
  } catch (_) {}
}
const settings = loadSettings();

// ---------- Procedural Web Audio Engine (Night Ambience + All SFX) ----------
class SoundFX {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.muted = false;
    this.ambienceStarted = false;
  }
  unlock() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        this.ctx = new AC();
        this.masterGain = this.ctx.createGain();
        this.masterGain.connect(this.ctx.destination);
        this.applyVolume();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    if (this.ctx && !this.ambienceStarted) {
      this.startNightAmbience();
    }
  }
  applyVolume() {
    if (!this.masterGain || !this.ctx) return;
    const gain = this.muted ? 0.0 : (settings.volume / 100) * 0.9;
    this.masterGain.gain.setTargetAtTime(gain, this.ctx.currentTime, 0.02);
  }
  toggleMute() {
    this.muted = !this.muted;
    this.applyVolume();
    return this.muted;
  }
  startNightAmbience() {
    if (!this.ctx || !this.masterGain) return;
    this.ambienceStarted = true;
    // Soft low fairy-tale night drone (D3 + A3 gentle sine harmonics)
    [146.83, 220.0].forEach((freq) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.value = 0.022;
      osc.connect(gain);
      gain.connect(this.masterGain);
      osc.start();
    });
  }
  tone(freq, dur, type = 'sine', peak = 0.08, delay = 0) {
    if (this.muted || !this.ctx || !this.masterGain) return;
    const t0 = this.ctx.currentTime + delay;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(peak, t0 + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain);
    gain.connect(this.masterGain);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }
  motePicked(carried) {
    const scale = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5];
    this.tone(scale[(carried - 1) % scale.length], 0.2, 'sine', 0.09);
  }
  charmPicked() {
    [659.25, 880, 1174.66].forEach((f, i) => this.tone(f, 0.25, 'triangle', 0.09, i * 0.05));
  }
  deposit() {
    this.tone(440, 0.15, 'triangle', 0.07, 0);
    this.tone(587.33, 0.2, 'triangle', 0.07, 0.06);
  }
  lanternLit() {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => this.tone(f, 0.42, 'sine', 0.09, i * 0.06));
  }
  pulse() {
    this.tone(330, 0.24, 'triangle', 0.1, 0);
    this.tone(660, 0.3, 'sine', 0.08, 0.05);
  }
  jump() {
    this.tone(280, 0.14, 'sine', 0.06, 0);
    this.tone(410, 0.14, 'sine', 0.05, 0.04);
  }
  dash() {
    this.tone(420, 0.12, 'triangle', 0.08, 0);
    this.tone(720, 0.12, 'sine', 0.06, 0.03);
  }
  shadeSpawned() {
    this.tone(130, 0.35, 'sawtooth', 0.05, 0);
    this.tone(98, 0.4, 'sine', 0.06, 0.1);
  }
  playerHit() {
    this.tone(160, 0.25, 'sawtooth', 0.1, 0);
    this.tone(105, 0.3, 'sine', 0.1, 0.05);
  }
  windWarn() {
    this.tone(310, 0.4, 'sine', 0.05, 0);
  }
  countdownTick() {
    this.tone(880, 0.09, 'triangle', 0.07, 0);
  }
  gameOver(won) {
    if (won) {
      [523.25, 659.25, 783.99, 1046.5, 1318.5].forEach((f, i) =>
        this.tone(f, 0.48, 'sine', 0.09, i * 0.09)
      );
    } else {
      [330, 293.66, 246.94, 196].forEach((f, i) => this.tone(f, 0.38, 'triangle', 0.07, i * 0.11));
    }
  }
}
const sfx = new SoundFX();

// ---------- Three.js Renderer, Sky, Ambient Light ----------
const canvas = document.getElementById('game-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;

const scene = new THREE.Scene();
scene.background = new THREE.Color(PALETTE.sky);
scene.fog = new THREE.FogExp2(PALETTE.fog, 0.011);

const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.2, 360);

// Ambient intensity strictly follows Ticket-02: 0.15 + 0.55 * (lit / total)
const ambientLight = new THREE.AmbientLight(0xdbe3ff, 0.15);
scene.add(ambientLight);

const moonLight = new THREE.DirectionalLight(0xb2c3ff, 0.72);
moonLight.position.set(-28, 48, -26);
moonLight.castShadow = true;
moonLight.shadow.mapSize.set(1024, 1024);
moonLight.shadow.camera.near = 5;
moonLight.shadow.camera.far = 160;
moonLight.shadow.camera.left = -60;
moonLight.shadow.camera.right = 60;
moonLight.shadow.camera.top = 60;
moonLight.shadow.camera.bottom = -60;
scene.add(moonLight);

// Stars & crescent moon
{
  const starGeo = new THREE.BufferGeometry();
  const count = 420;
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI * 0.45;
    const r = 160 + Math.random() * 45;
    pos[i * 3] = Math.cos(theta) * Math.cos(phi) * r;
    pos[i * 3 + 1] = Math.sin(phi) * r + 15;
    pos[i * 3 + 2] = Math.sin(theta) * Math.cos(phi) * r;
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: PALETTE.moteCore, size: 0.7 })));

  const moon = new THREE.Mesh(
    new THREE.SphereGeometry(5.5, 18, 18),
    new THREE.MeshBasicMaterial({ color: PALETTE.lanternCore })
  );
  moon.position.set(-65, 78, -60);
  scene.add(moon);
}

// ---------- Dynamic 3-Night Map Geometry Builder ----------
const worldGroup = new THREE.Group();
scene.add(worldGroup);

const cloudSea = new THREE.Group();
const cloudMat = new THREE.MeshStandardMaterial({
  color: PALETTE.cloudSea,
  emissive: 0x0a202c,
  roughness: 1.0,
  transparent: true,
  opacity: 0.88,
});
scene.add(cloudSea);

function addCloudRing(cx, cz, radius) {
  for (let i = 0; i < 24; i++) {
    const a = (i / 24) * Math.PI * 2;
    const r = radius + (i % 3) * 12;
    const puff = new THREE.Mesh(new THREE.SphereGeometry(7 + (i % 3) * 2, 10, 8), cloudMat);
    puff.scale.set(1.7, 0.4, 1.3);
    puff.position.set(cx + Math.cos(a) * r, -4.0 - (i % 3) * 1.1, cz + Math.sin(a) * r);
    cloudSea.add(puff);
  }
}

function addCircularIsland(cx, yTop, cz, radius, grassMat, sandMat) {
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius * 0.9, 3.0, 48),
    grassMat
  );
  body.position.set(cx, yTop - 1.5, cz);
  body.receiveShadow = true;
  worldGroup.add(body);

  const rim = new THREE.Mesh(new THREE.TorusGeometry(radius - 0.3, 0.38, 8, 48), sandMat);
  rim.rotation.x = Math.PI / 2;
  rim.position.set(cx, yTop + 0.04, cz);
  worldGroup.add(rim);
}

function addLaunchPadVisual(x, y, z) {
  const g = new THREE.Group();
  g.position.set(x, y + 0.06, z);
  const disc = new THREE.Mesh(
    new THREE.CylinderGeometry(1.0, 1.1, 0.14, 24),
    new THREE.MeshStandardMaterial({
      color: PALETTE.gold,
      emissive: PALETTE.lanternLit,
      emissiveIntensity: 0.9,
      roughness: 0.4,
    })
  );
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.75, 1.0, 24),
    new THREE.MeshBasicMaterial({ color: PALETTE.lanternCore, side: THREE.DoubleSide })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.09;
  g.add(disc, ring);
  worldGroup.add(g);
}

function createTier1HalfAnnulusMesh(grassMat, sandMat) {
  // Exact Tier 1: r in [12, 24], z > 0 (angle 0..180 deg in x=r cos a, z=r sin a), height Y=3
  // Shape uses (x, -z) because rotateX(-PI/2) maps (sx, sy, sz) -> (sx, sz, -sy)
  const shape = new THREE.Shape();
  const segs = 36;
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * Math.PI;
    const x = 24 * Math.cos(a);
    const z = 24 * Math.sin(a);
    if (i === 0) shape.moveTo(x, -z);
    else shape.lineTo(x, -z);
  }
  for (let i = segs; i >= 0; i--) {
    const a = (i / segs) * Math.PI;
    const x = 12 * Math.cos(a);
    const z = 12 * Math.sin(a);
    shape.lineTo(x, -z);
  }
  shape.closePath();

  const geo = new THREE.ExtrudeGeometry(shape, { depth: 3.0, bevelEnabled: false });
  geo.rotateX(-Math.PI / 2);
  const mesh = new THREE.Mesh(geo, grassMat);
  mesh.position.y = 0.0;
  mesh.receiveShadow = true;
  mesh.castShadow = true;
  worldGroup.add(mesh);

  // Sand border hint on Tier 1 top (z > 0 -> theta in [PI, 2*PI] before rotateX(-PI/2))
  const rimGeo = new THREE.RingGeometry(23.5, 24.0, 36, 1, Math.PI, Math.PI);
  rimGeo.rotateX(-Math.PI / 2);
  const rim = new THREE.Mesh(rimGeo, new THREE.MeshStandardMaterial({ color: PALETTE.sand, side: THREE.DoubleSide }));
  rim.position.y = 3.02;
  worldGroup.add(rim);
}

function addRampMesh(deg, woodMat) {
  // Ramp from r=30 (Y=0) to r=24 (Y=3), width 3m along radial angle deg
  const rad = THREE.MathUtils.degToRad(deg);
  const length = Math.hypot(6.0, 3.0);
  const slopeAngle = Math.atan2(3.0, 6.0);
  const midR = 27.0;
  const mx = Math.cos(rad) * midR;
  const mz = Math.sin(rad) * midR;

  const holder = new THREE.Group();
  holder.position.set(mx, 1.5, mz);
  holder.rotation.y = Math.atan2(-Math.sin(rad), Math.cos(rad));
  const ramp = new THREE.Mesh(new THREE.BoxGeometry(length, 0.25, 3.0), woodMat);
  ramp.rotation.z = slopeAngle;
  ramp.receiveShadow = true;
  ramp.castShadow = true;
  holder.add(ramp);
  worldGroup.add(holder);
}

let builtNight = -1;
function buildWorldForNight(night) {
  if (builtNight === night) return;
  builtNight = night;
  while (worldGroup.children.length > 0) worldGroup.remove(worldGroup.children[0]);
  while (cloudSea.children.length > 0) cloudSea.remove(cloudSea.children[0]);

  const grassMat = new THREE.MeshStandardMaterial({ color: PALETTE.grass, roughness: 0.9 });
  const sandMat = new THREE.MeshStandardMaterial({ color: PALETTE.sand, roughness: 0.85 });
  const woodMat = new THREE.MeshStandardMaterial({ color: PALETTE.wood, roughness: 0.82 });

  if (night === 1) {
    addCircularIsland(0, 0, 0, 40, grassMat, sandMat);
    // Decorative pier
    for (let i = 0; i < 4; i++) {
      const plank = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.16, 0.9), woodMat);
      plank.position.set(0, 0.08, 38.5 + i * 1.1);
      worldGroup.add(plank);
    }
    addCloudRing(0, 0, 48);
  } else if (night === 2) {
    addCircularIsland(0, 0, 0, 28, grassMat, sandMat);
    addCircularIsland(70, 0, 0, 28, grassMat, sandMat);
    // Bamboo bridge x in [26, 44], z in [-2, 2]
    const bridge = new THREE.Mesh(new THREE.BoxGeometry(18.0, 0.24, 4.0), woodMat);
    bridge.position.set(35, -0.08, 0);
    bridge.receiveShadow = true;
    worldGroup.add(bridge);
    for (let x = 27; x <= 43; x += 2) {
      const slat = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.28, 4.1), sandMat);
      slat.position.set(x, -0.05, 0);
      worldGroup.add(slat);
    }
    addLaunchPadVisual(20, 0, 18);
    addLaunchPadVisual(50, 0, -18);
    addCloudRing(35, 0, 68);
  } else if (night === 3) {
    addCircularIsland(0, 0, 0, 45, grassMat, sandMat);
    createTier1HalfAnnulusMesh(grassMat, sandMat);
    addRampMesh(30, woodMat);
    addRampMesh(150, woodMat);

    // Tier 2 solid cylinder from Y=0 to Y=6 (r=8)
    const tier2 = new THREE.Mesh(new THREE.CylinderGeometry(8.0, 8.0, 6.0, 36), grassMat);
    tier2.position.set(0, 3.0, 0);
    tier2.receiveShadow = true;
    tier2.castShadow = true;
    worldGroup.add(tier2);
    const tier2Rim = new THREE.Mesh(new THREE.TorusGeometry(7.9, 0.22, 8, 36), sandMat);
    tier2Rim.rotation.x = Math.PI / 2;
    tier2Rim.position.y = 6.02;
    worldGroup.add(tier2Rim);

    addLaunchPadVisual(0, 3, 13);

    // Bell Tower: r=2, height=8m on Tier 2 (Y=6..14)
    const tower = new THREE.Mesh(new THREE.CylinderGeometry(2.0, 2.0, 8.0, 24), woodMat);
    tower.position.set(0, 10.0, 0);
    tower.castShadow = true;
    const roof = new THREE.Mesh(new THREE.ConeGeometry(2.8, 1.8, 12), new THREE.MeshStandardMaterial({ color: PALETTE.mayCrimson, roughness: 0.7 }));
    roof.position.set(0, 14.8, 0);
    const bell = new THREE.Mesh(
      new THREE.CylinderGeometry(0.55, 0.8, 1.1, 12),
      new THREE.MeshStandardMaterial({ color: PALETTE.gold, emissive: PALETTE.lanternLit, emissiveIntensity: 0.5, metalness: 0.6, roughness: 0.3 })
    );
    bell.position.set(0, 13.0, 0);
    worldGroup.add(tower, roof, bell);
    addCloudRing(0, 0, 54);
  }
}

// ---------- Player Visual: Mây (Áo #E8E2D0, Khăn #C8102E, Nón lá + Mini Lantern + Orbiting Halo) ----------
const playerGroup = new THREE.Group();
scene.add(playerGroup);
const playerBodyGroup = new THREE.Group();
playerGroup.add(playerBodyGroup);

const cloakMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.54, 1.25, 14),
  new THREE.MeshStandardMaterial({ color: PALETTE.mayCloak, roughness: 0.75 })
);
cloakMesh.position.y = 0.68;
cloakMesh.castShadow = true;
playerBodyGroup.add(cloakMesh);

const scarfMesh = new THREE.Mesh(
  new THREE.TorusGeometry(0.3, 0.09, 8, 16),
  new THREE.MeshStandardMaterial({ color: PALETTE.mayCrimson, roughness: 0.6 })
);
scarfMesh.rotation.x = Math.PI / 2;
scarfMesh.position.y = 1.25;
playerBodyGroup.add(scarfMesh);

const headMesh = new THREE.Mesh(
  new THREE.SphereGeometry(0.28, 14, 14),
  new THREE.MeshStandardMaterial({ color: 0xf6d9c3, roughness: 0.65 })
);
headMesh.position.y = 1.44;
headMesh.castShadow = true;
playerBodyGroup.add(headMesh);

const hatMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.68, 0.38, 18),
  new THREE.MeshStandardMaterial({ color: PALETTE.sand, roughness: 0.85, side: THREE.DoubleSide })
);
hatMesh.position.y = 1.7;
hatMesh.castShadow = true;
playerBodyGroup.add(hatMesh);

const miniCord = new THREE.Mesh(
  new THREE.CylinderGeometry(0.015, 0.015, 0.24, 6),
  new THREE.MeshBasicMaterial({ color: PALETTE.wood })
);
miniCord.position.set(0, 1.45, 0.56);
playerBodyGroup.add(miniCord);

const miniLantern = new THREE.Mesh(
  new THREE.SphereGeometry(0.11, 10, 10),
  new THREE.MeshStandardMaterial({ color: PALETTE.lanternCore, emissive: PALETTE.lanternLit, emissiveIntensity: 2.0 })
);
miniLantern.position.set(0, 1.32, 0.56);
playerBodyGroup.add(miniLantern);

const playerLight = new THREE.PointLight(PALETTE.lanternLit, 3.6, 15, 1.6);
playerLight.position.set(0, 1.5, 0.56);
playerGroup.add(playerLight);

// Creative Feature 1: Orbiting Firefly Halo
const haloGroup = new THREE.Group();
haloGroup.position.y = 1.88;
playerGroup.add(haloGroup);
const haloOrbs = [];
for (let i = 0; i < 10; i++) {
  const orb = new THREE.Mesh(new THREE.SphereGeometry(0.075, 8, 8), new THREE.MeshBasicMaterial({ color: PALETTE.moteCore }));
  orb.visible = false;
  haloGroup.add(orb);
  haloOrbs.push(orb);
}

const pulseRing = new THREE.Mesh(
  new THREE.RingGeometry(0.7, 1.0, 48),
  new THREE.MeshBasicMaterial({ color: PALETTE.gold, side: THREE.DoubleSide, transparent: true, opacity: 0 })
);
pulseRing.rotation.x = -Math.PI / 2;
pulseRing.visible = false;
scene.add(pulseRing);
let pulseFxTime = -1;

// ---------- Entity Visual Pools ----------
const lanternObjects = new Map();
const moteObjects = new Map();
const shadeObjects = new Map();
const drifterObjects = new Map();
const charmObjects = new Map();
const sparks = [];
const windLeaves = [];

let camInitialized = false;
const camCurrentPos = new THREE.Vector3();
const camTargetPos = new THREE.Vector3();
const desiredCamPos = new THREE.Vector3();
const desiredTargetPos = new THREE.Vector3();

function clearEntityPools() {
  camInitialized = false;
  for (const v of lanternObjects.values()) scene.remove(v.group);
  for (const v of moteObjects.values()) scene.remove(v.group);
  for (const v of shadeObjects.values()) scene.remove(v.group);
  for (const v of drifterObjects.values()) scene.remove(v.group);
  for (const v of charmObjects.values()) scene.remove(v.group);
  lanternObjects.clear();
  moteObjects.clear();
  shadeObjects.clear();
  drifterObjects.clear();
  charmObjects.clear();
}

function createLanternVisual(lData, lanternCost, safeRadius) {
  const group = new THREE.Group();
  group.position.set(lData.pos[0], lData.pos[1], lData.pos[2]);

  const stoneBase = new THREE.Mesh(
    new THREE.CylinderGeometry(0.7, 0.88, 0.42, 8),
    new THREE.MeshStandardMaterial({ color: PALETTE.lanternUnlit, roughness: 0.9 })
  );
  stoneBase.position.y = 0.21;
  stoneBase.castShadow = true;
  group.add(stoneBase);

  const pillar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18, 0.24, 2.5, 8),
    new THREE.MeshStandardMaterial({ color: PALETTE.wood, roughness: 0.85 })
  );
  pillar.position.y = 1.65;
  pillar.castShadow = true;
  group.add(pillar);

  const housingMat = new THREE.MeshStandardMaterial({
    color: PALETTE.lanternUnlit,
    emissive: PALETTE.lanternUnlit,
    emissiveIntensity: 0.2,
    roughness: 0.4,
  });
  const housing = new THREE.Mesh(new THREE.SphereGeometry(0.62, 16, 14), housingMat);
  housing.scale.y = 1.25;
  housing.position.y = 3.2;
  group.add(housing);

  const cap = new THREE.Mesh(
    new THREE.ConeGeometry(0.85, 0.5, 8),
    new THREE.MeshStandardMaterial({ color: PALETTE.wood, roughness: 0.8 })
  );
  cap.position.y = 4.0;
  group.add(cap);

  const light = new THREE.PointLight(PALETTE.lanternLit, 0, 26, 1.5);
  light.position.y = 3.2;
  group.add(light);

  const safeRingMat = new THREE.MeshBasicMaterial({
    color: PALETTE.gold,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.0,
  });
  const safeRing = new THREE.Mesh(new THREE.RingGeometry(safeRadius - 0.14, safeRadius, 48), safeRingMat);
  safeRing.rotation.x = -Math.PI / 2;
  safeRing.position.y = 0.08;
  group.add(safeRing);

  // 10-pip ring (matching lantern_cost=10)
  const pips = [];
  for (let i = 0; i < lanternCost; i++) {
    const pipMat = new THREE.MeshBasicMaterial({ color: PALETTE.lanternUnlit });
    const pip = new THREE.Mesh(new THREE.SphereGeometry(0.08, 6, 6), pipMat);
    const a = (i / lanternCost) * Math.PI * 2;
    pip.position.set(Math.cos(a) * 1.05, 1.65, Math.sin(a) * 1.05);
    group.add(pip);
    pips.push(pip);
  }

  scene.add(group);
  return { group, housingMat, light, safeRingMat, pips };
}

function createMoteVisual(mData) {
  const group = new THREE.Group();
  group.position.set(mData.pos[0], mData.pos[1], mData.pos[2]);
  const isDropped = mData.kind === 'dropped';
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(isDropped ? 0.18 : 0.24, 10, 10),
    new THREE.MeshStandardMaterial({
      color: PALETTE.moteCore,
      emissive: isDropped ? PALETTE.lanternLit : PALETTE.moteHalo,
      emissiveIntensity: 2.3,
    })
  );
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(isDropped ? 0.32 : 0.42, 10, 10),
    new THREE.MeshBasicMaterial({ color: PALETTE.moteHalo, transparent: true, opacity: 0.28 })
  );
  group.add(core, halo);
  scene.add(group);
  return { group, baseY: mData.pos[1], phase: Math.random() * Math.PI * 2, isDropped };
}

function createShadeVisual(sData) {
  const group = new THREE.Group();
  group.position.set(sData.pos[0], sData.pos[1], sData.pos[2]);

  const bodyMat = new THREE.MeshStandardMaterial({
    color: PALETTE.shadeBody,
    emissive: PALETTE.shadeAura,
    emissiveIntensity: 0.9,
    roughness: 0.5,
    transparent: true,
    opacity: 1.0,
  });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.62, 14, 14), bodyMat);
  body.scale.set(1, 1.35, 1);
  body.castShadow = true;
  group.add(body);

  const eyeGeo = new THREE.SphereGeometry(0.09, 8, 8);
  const eyeMat = new THREE.MeshBasicMaterial({ color: PALETTE.shadeAura });
  const eyeL = new THREE.Mesh(eyeGeo, eyeMat);
  eyeL.position.set(-0.2, 0.25, 0.52);
  const eyeR = eyeL.clone();
  eyeR.position.x = 0.2;
  group.add(eyeL, eyeR);

  const stunRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.05, 6, 20),
    new THREE.MeshBasicMaterial({ color: PALETTE.gold })
  );
  stunRing.rotation.x = Math.PI / 2;
  stunRing.position.y = 1.05;
  stunRing.visible = false;
  group.add(stunRing);

  scene.add(group);
  return { group, bodyMat, stunRing, phase: Math.random() * Math.PI * 2 };
}

function createDrifterVisual(dData) {
  const group = new THREE.Group();
  group.position.set(dData.pos[0], dData.pos[1], dData.pos[2]);
  const mat = new THREE.MeshStandardMaterial({
    color: PALETTE.drifter,
    emissive: 0x3b536b,
    emissiveIntensity: 0.7,
    roughness: 0.4,
    side: THREE.DoubleSide,
  });
  const ribbon = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.14, 1.9), mat);
  group.add(ribbon);
  const stolenOrb = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 8, 8),
    new THREE.MeshBasicMaterial({ color: PALETTE.moteCore })
  );
  stolenOrb.position.y = 0.35;
  stolenOrb.visible = false;
  group.add(stolenOrb);
  scene.add(group);
  return { group, ribbon, stolenOrb, phase: Math.random() * Math.PI * 2 };
}

function createCharmVisual(pos) {
  const group = new THREE.Group();
  group.position.set(pos[0], pos[1] + 0.9, pos[2]);
  const card = new THREE.Mesh(
    new THREE.BoxGeometry(0.5, 0.85, 0.08),
    new THREE.MeshStandardMaterial({ color: PALETTE.mayCrimson, emissive: 0x550613, roughness: 0.4 })
  );
  const border = new THREE.Mesh(
    new THREE.BoxGeometry(0.58, 0.93, 0.04),
    new THREE.MeshBasicMaterial({ color: PALETTE.gold })
  );
  group.add(border, card);
  scene.add(group);
  return { group, baseY: pos[1] + 0.9 };
}

function spawnBurst(x, y, z, color, count = 10) {
  const mat = new THREE.MeshBasicMaterial({ color });
  const geo = new THREE.SphereGeometry(0.08, 6, 6);
  for (let i = 0; i < count; i++) {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    scene.add(m);
    const a = Math.random() * Math.PI * 2;
    const sp = 1.5 + Math.random() * 3.5;
    sparks.push({ mesh: m, vx: Math.cos(a) * sp, vy: 2 + Math.random() * 3, vz: Math.sin(a) * sp, life: 0.6 });
  }
}

// ---------- HUD & Overlay Refs ----------
const elConn = document.getElementById('conn-dot');
const elNightBadge = document.getElementById('hud-night-badge');
const elFlames = document.getElementById('hud-flames');
const elCharmPill = document.getElementById('hud-charm-pill');
const elCharmSec = document.getElementById('hud-charm-sec');
const elWindPill = document.getElementById('hud-wind-pill');
const elTimer = document.getElementById('hud-timer');
const elLanterns = document.getElementById('hud-lanterns');
const elScore = document.getElementById('hud-score');
const elCampaignScore = document.getElementById('hud-campaign-score');
const elCarriedCount = document.getElementById('hud-carried-count');
const elMoteSlots = document.getElementById('mote-slots');
const elDashCd = document.getElementById('hud-dash-cd');
const elPulseCd = document.getElementById('hud-pulse-cd');
const elToast = document.getElementById('event-toast');
const elPrompt = document.getElementById('context-prompt');
const elArrow = document.getElementById('offscreen-arrow');
const elArrowTri = elArrow.querySelector('.arrow-triangle');
const elArrowLabel = document.getElementById('offscreen-label');

// Build 10 firefly slots
const moteSlotEls = [];
for (let i = 0; i < 10; i++) {
  const s = document.createElement('div');
  s.className = 'mote-slot';
  elMoteSlots.appendChild(s);
  moteSlotEls.push(s);
}

const ovMenu = document.getElementById('menu-overlay');
const ovIntro = document.getElementById('intro-overlay');
const ovPause = document.getElementById('pause-overlay');
const ovSettings = document.getElementById('settings-overlay');
const ovGameOver = document.getElementById('gameover-overlay');

let activeScreen = 'menu'; // menu | intro | play | pause | settings | gameover
let settingsReturnTo = 'menu';
let pendingNight = 1;
let pendingResetCampaign = true;
let lastCountdownSec = -1;
let wasWindWarn = false;

let toastTimeout = null;
function showToast(text) {
  elToast.textContent = text;
  elToast.classList.remove('hidden');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => elToast.classList.add('hidden'), 2000);
}

function setScreen(scr) {
  activeScreen = scr;
  if (scr !== 'play') {
    exitPointerLockSafe();
  }
  ovMenu.classList.toggle('hidden', scr !== 'menu');
  ovIntro.classList.toggle('hidden', scr !== 'intro');
  ovPause.classList.toggle('hidden', scr !== 'pause');
  ovSettings.classList.toggle('hidden', scr !== 'settings');
  ovGameOver.classList.toggle('hidden', scr !== 'gameover');
}

const NIGHT_INTROS = {
  1: {
    eyebrow: 'Đêm 1 / 3',
    title: 'Đảo Bến',
    quote: 'Ông Đăng: "Đêm đầu tiên sương đen vừa kéo về Đảo Bến. Mây hãy gom đom đóm thắp lại 5 ngọn đèn cổ."',
    meta: '5 Đèn Lồng Lớn · Thời gian: 05:00 · Cẩn thận mép đảo 40m!',
  },
  2: {
    eyebrow: 'Đêm 2 / 3',
    title: 'Đảo Cau',
    quote: 'Ông Đăng: "Cầu tre nối hai bờ Đảo Cau giữa biển mây. Coi chừng Gió Lạc rình rập và tận dụng Bùa Gió!"',
    meta: '6 Đèn Lồng Lớn · Thời gian: 05:30 · Cầu tre & Bục gió · Gió Lạc & Bùa Gió',
  },
  3: {
    eyebrow: 'Đêm 3 / 3',
    title: 'Đảo Chuông',
    quote: 'Ông Đăng: "Đêm cuối trên Đảo Chuông ba tầng! Hãy giữ vững ngọn lửa qua cơn gió mạnh tới bình minh!"',
    meta: '7 Đèn Lồng Lớn · Thời gian: 06:00 · 3 Tầng đảo, Dốc 30°/150° & Gió mạnh',
  },
};

function openIntroForNight(night, resetCampaign) {
  pendingNight = night;
  pendingResetCampaign = resetCampaign;
  const info = NIGHT_INTROS[night];
  document.getElementById('intro-eyebrow').textContent = info.eyebrow;
  document.getElementById('intro-title').textContent = info.title;
  document.getElementById('intro-quote').textContent = info.quote;
  document.getElementById('intro-meta').textContent = info.meta;
  // Preview night terrain right behind modal
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'start_night', night, reset_campaign: resetCampaign, started: false }));
  }
  clearEntityPools();
  setScreen('intro');
}

// ---------- Controls, PointerLock & WebSocket Sync ----------
const keys = new Set();
let camYawDeg = 0;
let isDragging = false;
let lastMouseX = 0;
let pointerLocked = false;
let suppressPauseOnUnlock = false;
let lastLockPauseMs = 0;
let latestState = null;

function requestPointerLockSafe() {
  if (activeScreen !== 'play' || pointerLocked || !canvas.requestPointerLock) return;
  try {
    const res = canvas.requestPointerLock();
    if (res && typeof res.catch === 'function') res.catch(() => {});
  } catch (_) {}
}

function exitPointerLockSafe() {
  if (document.pointerLockElement && document.exitPointerLock) {
    suppressPauseOnUnlock = true;
    try {
      document.exitPointerLock();
    } catch (_) {
      suppressPauseOnUnlock = false;
    }
  }
}

document.addEventListener('pointerlockchange', () => {
  const lockedNow = document.pointerLockElement === canvas;
  pointerLocked = lockedNow;
  isDragging = false;
  if (!lockedNow) {
    if (suppressPauseOnUnlock) {
      suppressPauseOnUnlock = false;
    } else if (activeScreen === 'play' && ws && ws.readyState === WebSocket.OPEN) {
      lastLockPauseMs = performance.now();
      ws.send(JSON.stringify({ type: 'toggle_pause' }));
    }
  }
});

window.addEventListener('keydown', (e) => {
  sfx.unlock();
  const code = e.code;
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(code)) {
    e.preventDefault();
  }
  if (!keys.has(code) && activeScreen === 'play') {
    if (code === 'Space') sfx.jump();
  }
  keys.add(code);

  if (code === 'KeyM') {
    const muted = sfx.toggleMute();
    document.getElementById('btn-mute-hud').textContent = muted ? '🔇' : '🔊';
  } else if ((code === 'Escape' || code === 'KeyP') && !e.repeat) {
    const recentlyUnlocked = performance.now() - lastLockPauseMs < 150;
    if ((activeScreen === 'play' || activeScreen === 'pause') && !(code === 'Escape' && (pointerLocked || recentlyUnlocked))) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'toggle_pause' }));
      }
    }
  }
});

window.addEventListener('keyup', (e) => keys.delete(e.code));
canvas.addEventListener('click', () => {
  sfx.unlock();
  if (activeScreen === 'play' && !pointerLocked) {
    requestPointerLockSafe();
  }
});
canvas.addEventListener('mousedown', (e) => {
  sfx.unlock();
  if (!pointerLocked) {
    isDragging = true;
    lastMouseX = e.clientX;
  }
});
window.addEventListener('mouseup', () => { isDragging = false; });
window.addEventListener('mousemove', (e) => {
  if (activeScreen !== 'play') return;
  if (pointerLocked) {
    camYawDeg = (camYawDeg - (e.movementX || 0) * 0.22 * settings.sensitivity) % 360;
  } else if (isDragging) {
    const dx = e.clientX - lastMouseX;
    lastMouseX = e.clientX;
    camYawDeg = (camYawDeg - dx * 0.35 * settings.sensitivity) % 360;
  }
});

let ws = null;
function connectWS() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${window.location.host}/ws`);
  ws.onopen = () => {
    elConn.classList.remove('offline');
    elConn.classList.add('online');
  };
  ws.onclose = () => {
    elConn.classList.remove('online');
    elConn.classList.add('offline');
    setTimeout(connectWS, 1000);
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'frame') {
      latestState = msg.state;
      handleEvents(msg.events || [], msg.state);
      syncVisualsFromState(msg.state);
    }
  };
}
connectWS();

// UI Button Bindings
document.getElementById('btn-play-campaign').addEventListener('click', () => {
  sfx.unlock();
  openIntroForNight(1, true);
});
document.querySelectorAll('.night-pick').forEach((btn) => {
  btn.addEventListener('click', () => {
    sfx.unlock();
    openIntroForNight(Number(btn.dataset.night), true);
  });
});
document.getElementById('btn-start-night').addEventListener('click', () => {
  sfx.unlock();
  clearEntityPools();
  setScreen('play');
  requestPointerLockSafe();
  if (ws && ws.readyState === WebSocket.OPEN) {
    const nextSeed = Math.floor(Math.random() * 900000) + 1000;
    ws.send(JSON.stringify({
      type: 'start_night',
      night: pendingNight,
      seed: nextSeed,
      reset_campaign: pendingResetCampaign,
      started: true,
    }));
  }
});

document.getElementById('btn-pause-hud').addEventListener('click', () => {
  if (activeScreen === 'play' && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'toggle_pause' }));
  }
});
document.getElementById('btn-resume').addEventListener('click', () => {
  if (activeScreen === 'pause' && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'toggle_pause' }));
    requestPointerLockSafe();
  }
});
document.getElementById('btn-pause-restart').addEventListener('click', () => {
  clearEntityPools();
  setScreen('play');
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'restart', seed: Math.floor(Math.random() * 900000) + 1000 }));
  }
});
document.getElementById('btn-pause-menu').addEventListener('click', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'start_night', night: 1, reset_campaign: true, started: false }));
  }
  clearEntityPools();
  setScreen('menu');
});

const inputVol = document.getElementById('input-volume');
const inputSens = document.getElementById('input-sens');
const valVol = document.getElementById('val-volume');
const valSens = document.getElementById('val-sens');
inputVol.value = String(settings.volume);
inputSens.value = String(settings.sensitivity);
valVol.textContent = `${settings.volume}%`;
valSens.textContent = `${settings.sensitivity.toFixed(1)}x`;

inputVol.addEventListener('input', () => {
  settings.volume = Number(inputVol.value);
  valVol.textContent = `${settings.volume}%`;
  sfx.applyVolume();
  saveSettings(settings);
});
inputSens.addEventListener('input', () => {
  settings.sensitivity = Number(inputSens.value);
  valSens.textContent = `${settings.sensitivity.toFixed(1)}x`;
  saveSettings(settings);
});

document.getElementById('btn-menu-settings').addEventListener('click', () => {
  settingsReturnTo = 'menu';
  setScreen('settings');
});
document.getElementById('btn-pause-settings').addEventListener('click', () => {
  settingsReturnTo = 'pause';
  setScreen('settings');
});
document.getElementById('btn-settings-close').addEventListener('click', () => {
  saveSettings(settings);
  setScreen(settingsReturnTo);
});

document.getElementById('btn-mute-hud').addEventListener('click', () => {
  sfx.unlock();
  const muted = sfx.toggleMute();
  document.getElementById('btn-mute-hud').textContent = muted ? '🔇' : '🔊';
});

document.getElementById('btn-next-night').addEventListener('click', () => {
  const nextN = Math.min(3, (latestState ? latestState.night : 1) + 1);
  openIntroForNight(nextN, false);
});
document.getElementById('btn-play-again').addEventListener('click', () => {
  clearEntityPools();
  setScreen('play');
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'restart', seed: Math.floor(Math.random() * 900000) + 1000 }));
  }
});
document.getElementById('btn-result-menu').addEventListener('click', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'start_night', night: 1, reset_campaign: true, started: false }));
  }
  clearEntityPools();
  setScreen('menu');
});

function handleEvents(events, st) {
  for (const ev of events) {
    if (ev.name === 'dash') {
      sfx.dash();
      spawnBurst(st.player.pos[0], st.player.pos[1] + 0.6, st.player.pos[2], PALETTE.mayCloak, 6);
    } else if (ev.name === 'mote_picked') {
      sfx.motePicked(ev.data.carried);
      spawnBurst(st.player.pos[0], st.player.pos[1] + 0.8, st.player.pos[2], PALETTE.moteCore, 8);
    } else if (ev.name === 'charm_picked') {
      sfx.charmPicked();
      showToast('⚡ Đã nhặt Bùa Gió! Chạy nhanh & Lướt không hồi chiêu');
      spawnBurst(st.player.pos[0], st.player.pos[1] + 0.8, st.player.pos[2], PALETTE.mayCrimson, 14);
    } else if (ev.name === 'deposit') {
      sfx.deposit();
      showToast(`Đã nạp +${ev.data.amount} đom đóm vào ${ev.data.lantern_id}`);
      const lan = st.lanterns.find((l) => l.id === ev.data.lantern_id);
      if (lan) spawnBurst(lan.pos[0], lan.pos[1] + 2.2, lan.pos[2], PALETTE.lanternLit, 14);
    } else if (ev.name === 'lantern_lit') {
      sfx.lanternLit();
      showToast(`🏮 ${ev.data.lantern_id} đã bừng sáng!`);
      const lan = st.lanterns.find((l) => l.id === ev.data.lantern_id);
      if (lan) spawnBurst(lan.pos[0], lan.pos[1] + 3.2, lan.pos[2], PALETTE.lanternCore, 24);
    } else if (ev.name === 'pulse') {
      sfx.pulse();
      pulseFxTime = 0;
      pulseRing.position.set(st.player.pos[0], st.player.pos[1] + 0.15, st.player.pos[2]);
      pulseRing.visible = true;
      const cnt = (ev.data.stunned_ids || []).length;
      showToast(cnt > 0 ? `✨ Tỏa Sáng làm choáng ${cnt} Bóng Mực!` : '✨ Tỏa Sáng!');
    } else if (ev.name === 'drifter_steal') {
      sfx.playerHit();
      showToast(`💨 Gió Lạc ${ev.data.drifter_id} cướp ${ev.data.amount} đom đóm!`);
    } else if (ev.name === 'drifter_drop') {
      sfx.motePicked(4);
      showToast(`✨ Gió Lạc ${ev.data.drifter_id} làm rơi ${ev.data.amount} đom đóm!`);
    } else if (ev.name === 'player_hit') {
      sfx.playerHit();
      showToast(
        ev.data.by === 'fall'
          ? `🌊 Rơi khỏi đảo! Mất 1 Ngọn Lửa & ${ev.data.lost} đom đóm`
          : `💥 Bị Bóng Mực chạm! Rơi ${ev.data.dropped} đom đóm`
      );
      spawnBurst(st.player.pos[0], st.player.pos[1] + 1.0, st.player.pos[2], PALETTE.shadeAura, 14);
    } else if (ev.name === 'shade_spawned') {
      sfx.shadeSpawned();
    } else if (ev.name === 'paused') {
      if (activeScreen === 'play') setScreen('pause');
    } else if (ev.name === 'resumed') {
      if (activeScreen === 'pause') setScreen('play');
    } else if (ev.name === 'game_over') {
      sfx.gameOver(ev.data.result === 'won');
    }
  }
}

function syncVisualsFromState(st) {
  buildWorldForNight(st.night);
  const tuning = st.tuning;
  const cost = tuning.lantern_cost;
  const safeR = tuning.safe_radius;

  // Player
  playerGroup.position.set(st.player.pos[0], st.player.pos[1], st.player.pos[2]);
  playerBodyGroup.rotation.y = THREE.MathUtils.degToRad(st.player_yaw_deg || 0);
  const respawning = st.respawn_s > 0;
  playerBodyGroup.visible = !respawning && (!st.player.invuln || Math.floor(st.tick / 4) % 2 === 0);

  for (let i = 0; i < haloOrbs.length; i++) {
    haloOrbs[i].visible = !respawning && i < st.player.carried;
  }

  // Lanterns & Ambient Light Formula: 0.15 + 0.55 * (lit / total)
  for (const lData of st.lanterns) {
    let vis = lanternObjects.get(lData.id);
    if (!vis) {
      vis = createLanternVisual(lData, cost, safeR);
      lanternObjects.set(lData.id, vis);
    }
    vis.group.position.set(lData.pos[0], lData.pos[1], lData.pos[2]);
    if (lData.lit) {
      vis.housingMat.color.setHex(PALETTE.lanternCore);
      vis.housingMat.emissive.setHex(PALETTE.lanternLit);
      vis.housingMat.emissiveIntensity = 2.4;
      vis.light.intensity = 10.0;
      vis.safeRingMat.opacity = 0.36;
    } else {
      const ratio = lData.deposited / cost;
      vis.housingMat.color.setHex(PALETTE.lanternUnlit);
      vis.housingMat.emissive.setHex(ratio > 0 ? PALETTE.lanternLit : PALETTE.lanternUnlit);
      vis.housingMat.emissiveIntensity = 0.25 + ratio * 1.1;
      vis.light.intensity = ratio * 2.5;
      vis.safeRingMat.opacity = 0.0;
    }
    vis.pips.forEach((pip, idx) => {
      pip.material.color.setHex(idx < lData.deposited ? PALETTE.gold : PALETTE.lanternUnlit);
    });
  }

  const litFrac = st.lit_count / Math.max(1, st.lantern_total);
  ambientLight.intensity = 0.15 + 0.55 * litFrac;

  // Motes
  const activeMotes = new Set();
  for (const mData of st.motes || []) {
    activeMotes.add(mData.id);
    let vis = moteObjects.get(mData.id);
    if (!vis) {
      vis = createMoteVisual(mData);
      moteObjects.set(mData.id, vis);
    }
    vis.group.position.x = mData.pos[0];
    vis.group.position.z = mData.pos[2];
    vis.baseY = mData.pos[1];
  }
  for (const [id, vis] of moteObjects.entries()) {
    if (!activeMotes.has(id)) {
      scene.remove(vis.group);
      moteObjects.delete(id);
    }
  }

  // Shades (spawning | wander | chase | recoil | stunned)
  const activeShades = new Set();
  for (const sData of st.shades || []) {
    activeShades.add(sData.id);
    let vis = shadeObjects.get(sData.id);
    if (!vis) {
      vis = createShadeVisual(sData);
      shadeObjects.set(sData.id, vis);
    }
    vis.group.position.set(sData.pos[0], sData.pos[1], sData.pos[2]);
    vis.stunRing.visible = sData.state === 'stunned';
    if (sData.state === 'stunned') {
      vis.bodyMat.color.setHex(PALETTE.shadeStun);
      vis.bodyMat.emissive.setHex(PALETTE.shadeStun);
      vis.bodyMat.opacity = 0.9;
    } else if (sData.state === 'spawning') {
      vis.bodyMat.color.setHex(PALETTE.shadeBody);
      vis.bodyMat.emissive.setHex(PALETTE.shadeAura);
      vis.bodyMat.opacity = 0.45;
    } else {
      vis.bodyMat.color.setHex(PALETTE.shadeBody);
      vis.bodyMat.emissive.setHex(PALETTE.shadeAura);
      vis.bodyMat.opacity = 1.0;
    }
  }
  for (const [id, vis] of shadeObjects.entries()) {
    if (!activeShades.has(id)) {
      scene.remove(vis.group);
      shadeObjects.delete(id);
    }
  }

  // Drifters
  const activeDrifters = new Set();
  for (const dData of st.drifters || []) {
    activeDrifters.add(dData.id);
    let vis = drifterObjects.get(dData.id);
    if (!vis) {
      vis = createDrifterVisual(dData);
      drifterObjects.set(dData.id, vis);
    }
    vis.group.position.set(dData.pos[0], dData.pos[1], dData.pos[2]);
    vis.stolenOrb.visible = dData.stolen > 0;
  }
  for (const [id, vis] of drifterObjects.entries()) {
    if (!activeDrifters.has(id)) {
      scene.remove(vis.group);
      drifterObjects.delete(id);
    }
  }

  // Charms
  for (const cData of st.charms || []) {
    let vis = charmObjects.get(cData.id);
    if (!vis && st.charm_positions && st.charm_positions[cData.id]) {
      vis = createCharmVisual(st.charm_positions[cData.id]);
      charmObjects.set(cData.id, vis);
    }
    if (vis) vis.group.visible = cData.available;
  }

  // Wind SFX & Banner
  if (st.wind_warning && !wasWindWarn) {
    sfx.windWarn();
  }
  wasWindWarn = Boolean(st.wind_warning);
  if (st.wind && st.wind.active) {
    elWindPill.textContent = '🌪 Đang có gió mạnh! (2 m/s)';
    elWindPill.classList.remove('hidden');
  } else if (st.wind_warning) {
    elWindPill.textContent = '🍃 Gió mạnh sắp thổi (2s)!';
    elWindPill.classList.remove('hidden');
  } else {
    elWindPill.classList.add('hidden');
  }

  // HUD Numbers
  elNightBadge.textContent = `Đêm ${st.night} · ${st.island_name}`;
  elFlames.textContent = '🔥'.repeat(st.player.flames) + '🖤'.repeat(Math.max(0, tuning.flames - st.player.flames));
  elLanterns.textContent = `🏮 ${st.lit_count} / ${st.lantern_total}`;
  elScore.textContent = String(st.score);
  elCampaignScore.textContent = String(st.campaign_score || 0);
  elCarriedCount.textContent = `${st.player.carried} / ${tuning.carry_capacity}`;
  moteSlotEls.forEach((slot, idx) => slot.classList.toggle('filled', idx < st.player.carried));

  if (st.player.charm_s > 0) {
    elCharmSec.textContent = `${st.player.charm_s.toFixed(1)}s`;
    elCharmPill.classList.remove('hidden');
  } else {
    elCharmPill.classList.add('hidden');
  }

  const secs = Math.max(0, Math.ceil(st.time_left_s));
  const mm = String(Math.floor(secs / 60)).padStart(2, '0');
  const ss = String(secs % 60).padStart(2, '0');
  elTimer.textContent = `${mm}:${ss}`;
  elTimer.classList.toggle('timer-danger', secs <= 30);

  if (st.session_started && st.state === 'playing' && secs <= 10 && secs > 0 && secs !== lastCountdownSec) {
    lastCountdownSec = secs;
    sfx.countdownTick();
  }

  // Dash & Pulse cooldown HUD
  if (st.player.charm_s > 0) {
    elDashCd.textContent = 'Không hồi chiêu!';
    elDashCd.className = 'skill-state ready';
  } else if (st.player.dash_cd_s > 0) {
    elDashCd.textContent = `Hồi ${st.player.dash_cd_s.toFixed(1)}s`;
    elDashCd.className = 'skill-state cooldown';
  } else {
    elDashCd.textContent = 'Sẵn sàng';
    elDashCd.className = 'skill-state ready';
  }

  if (st.player.pulse_cd_s > 0) {
    elPulseCd.textContent = `Hồi ${st.player.pulse_cd_s.toFixed(1)}s`;
    elPulseCd.className = 'skill-state cooldown';
  } else if (st.player.carried < tuning.pulse_cost) {
    elPulseCd.textContent = `Cần ${tuning.pulse_cost} đom đóm`;
    elPulseCd.className = 'skill-state cooldown';
  } else {
    elPulseCd.textContent = `Sẵn sàng (tốn ${tuning.pulse_cost})`;
    elPulseCd.className = 'skill-state ready';
  }

  // Context prompt near unlit lantern (radius 2.0m)
  let nearUnlit = null;
  for (const lData of st.lanterns) {
    if (lData.lit) continue;
    const d = Math.hypot(st.player.pos[0] - lData.pos[0], st.player.pos[2] - lData.pos[2]);
    if (d <= tuning.interact_radius) {
      nearUnlit = lData;
      break;
    }
  }
  if (nearUnlit && st.state === 'playing' && activeScreen === 'play') {
    elPrompt.textContent = `E — Nạp ánh sáng (${nearUnlit.deposited}/${cost})`;
    elPrompt.classList.remove('hidden');
  } else {
    elPrompt.classList.add('hidden');
  }

  // Game Over / Next Night / Dawn Screen
  if ((st.state === 'won' || st.state === 'lost') && activeScreen === 'play') {
    setScreen('gameover');
    const btnNext = document.getElementById('btn-next-night');
    const isFinalDawn = st.state === 'won' && st.night === 3;
    document.getElementById('modal-eyebrow').textContent = isFinalDawn
      ? 'Bình Minh Đã Lên'
      : `Đêm ${st.night} · ${st.island_name}`;
    document.getElementById('modal-title').textContent = isFinalDawn
      ? 'Chiến Thắng Trọn Vẹn — Bình Minh!'
      : st.state === 'won'
        ? `Đêm ${st.night} Hoàn Thành!`
        : 'Đèn Chưa Kịp Sáng';
    document.getElementById('modal-subtitle').textContent = isFinalDawn
      ? 'Ánh đèn đã rực sáng cả ba hòn đảo giữa biển mây!'
      : st.state === 'won'
        ? `${st.island_name} đã bừng sáng. Chuẩn bị tiến tới hòn đảo kế tiếp.`
        : st.game_over_reason === 'dawn'
          ? 'Đã hết thời gian trước bình minh.'
          : 'Mây đã mất hết Ngọn Lửa.';
    document.getElementById('modal-score').textContent = String(st.score);
    document.getElementById('modal-campaign-score').textContent = String(st.campaign_score || 0);
    document.getElementById('modal-lanterns').textContent = `${st.lit_count} / ${st.lantern_total}`;
    document.getElementById('modal-flames').textContent = String(st.player.flames);
    btnNext.classList.toggle('hidden', !(st.state === 'won' && st.night < 3));
  }
}

// ---------- Off-Screen Nearest Unlit Lantern Arrow ----------
const projVec = new THREE.Vector3();
function updateOffscreenArrow(st) {
  if (!st || st.state !== 'playing' || activeScreen !== 'play') {
    elArrow.classList.add('hidden');
    return;
  }
  let nearest = null;
  let bestD = Infinity;
  for (const lData of st.lanterns) {
    if (lData.lit) continue;
    const d = Math.hypot(lData.pos[0] - st.player.pos[0], lData.pos[2] - st.player.pos[2]);
    if (d < bestD) {
      bestD = d;
      nearest = lData;
    }
  }
  if (!nearest) {
    elArrow.classList.add('hidden');
    return;
  }
  projVec.set(nearest.pos[0], nearest.pos[1] + 2.5, nearest.pos[2]).project(camera);
  const behind = projVec.z > 1.0;
  let sx = projVec.x;
  let sy = projVec.y;
  if (behind) {
    sx = -sx;
    sy = -sy;
  }
  if (!behind && Math.abs(sx) <= 0.9 && Math.abs(sy) <= 0.85) {
    elArrow.classList.add('hidden');
    return;
  }
  const len = Math.max(0.001, Math.hypot(sx, sy));
  const nx = sx / len;
  const ny = sy / len;
  const edgeScale = 0.78 / Math.max(Math.abs(nx), Math.abs(ny));
  const rawCx = (nx * edgeScale * 0.5 + 0.5) * window.innerWidth;
  const rawCy = (-ny * edgeScale * 0.5 + 0.5) * window.innerHeight;
  const cx = Math.max(220, Math.min(window.innerWidth - 250, rawCx));
  const cy = Math.max(125, Math.min(window.innerHeight - 155, rawCy));
  elArrow.style.left = `${cx}px`;
  elArrow.style.top = `${cy}px`;
  const deg = (Math.atan2(nx, ny) * 180) / Math.PI;
  elArrowTri.style.transform = `rotate(${deg}deg)`;
  elArrowLabel.textContent = `${nearest.id} (${Math.round(bestD)}m)`;
  elArrow.classList.remove('hidden');
}

// ---------- FPS Perf Tracking & Render Loop ----------
const elHudFps = document.getElementById('hud-fps');
const perfSamples = [];
window.__gamePerf = { fps: 60, avgFps: 60, samples: 0 };
let fpsUiTick = 0;

let lastFrameTime = performance.now();
function animate(now) {
  requestAnimationFrame(animate);
  const rawDt = (now - lastFrameTime) / 1000;
  const dt = Math.min(0.05, rawDt);
  lastFrameTime = now;
  const t = now * 0.001;

  if (rawDt > 0.001) {
    const instFps = 1.0 / rawDt;
    perfSamples.push(instFps);
    if (perfSamples.length > 60) perfSamples.shift();
    const avg = perfSamples.reduce((a, b) => a + b, 0) / perfSamples.length;
    window.__gamePerf = {
      fps: Number(instFps.toFixed(1)),
      avgFps: Number(avg.toFixed(1)),
      samples: perfSamples.length,
    };
    fpsUiTick++;
    if (elHudFps && fpsUiTick % 15 === 0) {
      elHudFps.textContent = `FPS: ${Math.round(instFps)} (avg ${avg.toFixed(1)})`;
    }
  }

  if (activeScreen === 'play') {
    if (keys.has('KeyQ')) camYawDeg = (camYawDeg + 95 * dt * settings.sensitivity) % 360;
    if (keys.has('KeyC')) camYawDeg = (camYawDeg - 95 * dt * settings.sensitivity) % 360;
  }

  if (ws && ws.readyState === WebSocket.OPEN) {
    const mz =
      activeScreen === 'play'
        ? (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0)
        : 0;
    const mx =
      activeScreen === 'play'
        ? (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0) - (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0)
        : 0;
    ws.send(
      JSON.stringify({
        type: 'input',
        move: [mx, mz],
        cam_yaw_deg: camYawDeg,
        jump: activeScreen === 'play' && keys.has('Space'),
        interact: activeScreen === 'play' && keys.has('KeyE'),
        pulse: activeScreen === 'play' && (keys.has('KeyF') || keys.has('KeyJ')),
        dash: activeScreen === 'play' && (keys.has('ShiftLeft') || keys.has('ShiftRight')),
        pause: false,
      })
    );
  }

  // Wind leaf FX (Night 3)
  if (latestState && (latestState.wind_warning || (latestState.wind && latestState.wind.active))) {
    if (windLeaves.length < 25 && Math.random() < 0.4) {
      const leaf = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, 0.04, 0.12),
        new THREE.MeshBasicMaterial({ color: PALETTE.sand })
      );
      leaf.position.set(
        playerGroup.position.x + (Math.random() - 0.5) * 24,
        playerGroup.position.y + 1 + Math.random() * 4,
        playerGroup.position.z + (Math.random() - 0.5) * 24
      );
      scene.add(leaf);
      windLeaves.push({ mesh: leaf, life: 1.5 });
    }
  }
  const wRad = latestState && latestState.wind ? THREE.MathUtils.degToRad(latestState.wind.dir_deg) : 0;
  for (let i = windLeaves.length - 1; i >= 0; i--) {
    const lf = windLeaves[i];
    lf.life -= dt;
    if (lf.life <= 0) {
      scene.remove(lf.mesh);
      windLeaves.splice(i, 1);
      continue;
    }
    lf.mesh.position.x += Math.cos(wRad) * 8 * dt;
    lf.mesh.position.z += Math.sin(wRad) * 8 * dt;
    lf.mesh.rotation.x += 4 * dt;
    lf.mesh.rotation.y += 5 * dt;
  }

  // Animations
  haloGroup.rotation.y = t * 1.9;
  const activeOrbs = haloOrbs.filter((o) => o.visible).length;
  let orbIdx = 0;
  haloOrbs.forEach((orb) => {
    if (!orb.visible) return;
    const a = (orbIdx / Math.max(1, activeOrbs)) * Math.PI * 2;
    orb.position.set(Math.cos(a) * 0.95, Math.sin(t * 4 + orbIdx) * 0.14, Math.sin(a) * 0.95);
    orbIdx++;
  });

  for (const vis of moteObjects.values()) {
    vis.group.position.y = vis.baseY + (vis.isDropped ? 0.55 : 0.72) + Math.sin(t * 3.1 + vis.phase) * 0.2;
  }
  for (const vis of shadeObjects.values()) {
    vis.group.rotation.y = t * 1.4 + vis.phase;
    vis.stunRing.rotation.z = t * 5.0;
  }
  for (const vis of drifterObjects.values()) {
    vis.ribbon.rotation.z = Math.sin(t * 4 + vis.phase) * 0.25;
    vis.ribbon.rotation.y = t * 1.6;
  }
  for (const vis of charmObjects.values()) {
    vis.group.rotation.y = t * 1.8;
    vis.group.position.y = vis.baseY + Math.sin(t * 2.5) * 0.15;
  }

  if (pulseFxTime >= 0) {
    pulseFxTime += dt;
    if (pulseFxTime >= 0.4) {
      pulseFxTime = -1;
      pulseRing.visible = false;
    } else {
      const p = pulseFxTime / 0.4;
      const sc = 1 + p * 4.2;
      pulseRing.scale.set(sc, sc, 1);
      pulseRing.material.opacity = (1 - p) * 0.8;
    }
  }

  for (let i = sparks.length - 1; i >= 0; i--) {
    const s = sparks[i];
    s.life -= dt;
    if (s.life <= 0) {
      scene.remove(s.mesh);
      sparks.splice(i, 1);
      continue;
    }
    s.vy -= 7.5 * dt;
    s.mesh.position.x += s.vx * dt;
    s.mesh.position.y += s.vy * dt;
    s.mesh.position.z += s.vz * dt;
    s.mesh.scale.setScalar(Math.max(0.1, s.life / 0.6));
  }

  cloudSea.rotation.y = t * 0.01;

  // Smooth third-person camera follow (frame-rate independent damping)
  const px = playerGroup.position.x;
  const py = playerGroup.position.y;
  const pz = playerGroup.position.z;
  const rad = THREE.MathUtils.degToRad(camYawDeg);
  desiredTargetPos.set(px, py + 1.6, pz);
  desiredCamPos.set(px - Math.sin(rad) * 14.5, py + 8.8, pz - Math.cos(rad) * 14.5);
  if (!camInitialized || desiredTargetPos.distanceTo(camTargetPos) > 12.0) {
    camCurrentPos.copy(desiredCamPos);
    camTargetPos.copy(desiredTargetPos);
    camInitialized = true;
  } else {
    const alpha = 1.0 - Math.exp(-10.0 * dt);
    camCurrentPos.lerp(desiredCamPos, alpha);
    camTargetPos.lerp(desiredTargetPos, alpha);
  }
  camera.position.copy(camCurrentPos);
  camera.lookAt(camTargetPos);

  updateOffscreenArrow(latestState);
  renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

requestAnimationFrame(animate);
