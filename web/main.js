import * as THREE from './vendor/three.module.min.js';

// ---------- Procedural Fairy-Tale Web Audio Synth (Creative, UI-only) ----------
class SoundFX {
  constructor() {
    this.ctx = null;
    this.muted = false;
  }
  unlock() {
    if (this.muted) return;
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) this.ctx = new AC();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
  }
  toggleMute() {
    this.muted = !this.muted;
    return this.muted;
  }
  tone(freq, dur, type = 'sine', gainPeak = 0.08, delay = 0) {
    if (this.muted || !this.ctx) return;
    const t0 = this.ctx.currentTime + delay;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(gainPeak, t0 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }
  motePicked(carried) {
    const scale = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5];
    const f = scale[(carried - 1) % scale.length];
    this.tone(f, 0.22, 'sine', 0.08);
  }
  deposit() {
    this.tone(440, 0.18, 'triangle', 0.07, 0);
    this.tone(659.25, 0.24, 'triangle', 0.07, 0.07);
  }
  lanternLit() {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => this.tone(f, 0.45, 'sine', 0.08, i * 0.07));
  }
  pulse() {
    this.tone(330, 0.28, 'triangle', 0.1, 0);
    this.tone(660, 0.35, 'sine', 0.08, 0.05);
  }
  playerHit() {
    this.tone(150, 0.25, 'sawtooth', 0.09, 0);
    this.tone(110, 0.3, 'sine', 0.09, 0.05);
  }
  gameOver(won) {
    if (won) {
      [523.25, 659.25, 783.99, 1046.5, 1318.5].forEach((f, i) =>
        this.tone(f, 0.5, 'sine', 0.09, i * 0.1)
      );
    } else {
      [330, 293.66, 246.94, 196].forEach((f, i) => this.tone(f, 0.4, 'triangle', 0.07, i * 0.12));
    }
  }
}

const sfx = new SoundFX();

// ---------- Three.js Scene Setup ----------
const canvas = document.getElementById('game-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

const scene = new THREE.Scene();
const NIGHT_SKY = new THREE.Color(0x0d0b1f);
const WARM_SKY = new THREE.Color(0x281e42);
scene.background = NIGHT_SKY.clone();
scene.fog = new THREE.FogExp2(0x0d0b1f, 0.015);

const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.2, 320);

const hemiLight = new THREE.HemisphereLight(0x524b8a, 0x161428, 0.65);
scene.add(hemiLight);

const moonLight = new THREE.DirectionalLight(0xa7b7ff, 0.65);
moonLight.position.set(-28, 42, -24);
moonLight.castShadow = true;
moonLight.shadow.mapSize.set(1024, 1024);
moonLight.shadow.camera.near = 5;
moonLight.shadow.camera.far = 130;
moonLight.shadow.camera.left = -52;
moonLight.shadow.camera.right = 52;
moonLight.shadow.camera.top = 52;
moonLight.shadow.camera.bottom = -52;
scene.add(moonLight);

// Sky stars & moon
{
  const starGeo = new THREE.BufferGeometry();
  const count = 420;
  const pos = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.random() * Math.PI * 0.45;
    const r = 140 + Math.random() * 40;
    pos[i * 3] = Math.cos(theta) * Math.cos(phi) * r;
    pos[i * 3 + 1] = Math.sin(phi) * r + 15;
    pos[i * 3 + 2] = Math.sin(theta) * Math.cos(phi) * r;
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const starMat = new THREE.PointsMaterial({ color: 0xffe4b5, size: 0.7, transparent: true, opacity: 0.85 });
  scene.add(new THREE.Points(starGeo, starMat));

  const moon = new THREE.Mesh(
    new THREE.SphereGeometry(5.5, 20, 20),
    new THREE.MeshBasicMaterial({ color: 0xfff1c9 })
  );
  moon.position.set(-60, 72, -55);
  scene.add(moon);
}

// Island Đảo Bến (circular, radius 45m, top at Y = 0)
const ISLAND_RADIUS = 45;
const islandGroup = new THREE.Group();
scene.add(islandGroup);

const islandTop = new THREE.Mesh(
  new THREE.CylinderGeometry(ISLAND_RADIUS, ISLAND_RADIUS * 0.92, 3.2, 64),
  new THREE.MeshStandardMaterial({ color: 0x20303b, roughness: 0.92, metalness: 0.04 })
);
islandTop.position.y = -1.6;
islandTop.receiveShadow = true;
islandGroup.add(islandTop);

// Central plaza stone disc
const plaza = new THREE.Mesh(
  new THREE.CylinderGeometry(5.5, 5.8, 0.08, 32),
  new THREE.MeshStandardMaterial({ color: 0x3b4454, roughness: 0.85 })
);
plaza.position.y = 0.02;
plaza.receiveShadow = true;
islandGroup.add(plaza);

// Outer cliff rim & wooden pier dock at +Z
const rimRing = new THREE.Mesh(
  new THREE.TorusGeometry(ISLAND_RADIUS - 0.3, 0.35, 8, 64),
  new THREE.MeshStandardMaterial({ color: 0x394b57, roughness: 0.9 })
);
rimRing.rotation.x = Math.PI / 2;
rimRing.position.y = 0.05;
islandGroup.add(rimRing);

const pierGroup = new THREE.Group();
for (let i = 0; i < 6; i++) {
  const plank = new THREE.Mesh(
    new THREE.BoxGeometry(3.2, 0.18, 0.9),
    new THREE.MeshStandardMaterial({ color: 0x5d402a, roughness: 0.85 })
  );
  plank.position.set(0, 0.09, ISLAND_RADIUS - 1.5 + i * 1.15);
  plank.receiveShadow = true;
  pierGroup.add(plank);
}
islandGroup.add(pierGroup);

// Decorative stylized trees & rocks around island perimeter
function addSceneryProps() {
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x4b3526, roughness: 0.9 });
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x1e4042, roughness: 0.85 });
  const rockMat = new THREE.MeshStandardMaterial({ color: 0x3a4052, roughness: 0.92 });
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * Math.PI * 2 + 0.18;
    const r = 34 + (i % 3) * 3.2;
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    if (Math.abs(x) < 4 && z > 35) continue; // keep pier clear

    if (i % 3 === 0) {
      const rock = new THREE.Mesh(new THREE.DodecahedronGeometry(1.1 + (i % 2) * 0.4, 0), rockMat);
      rock.position.set(x, 0.45, z);
      rock.scale.y = 0.7;
      rock.castShadow = true;
      rock.receiveShadow = true;
      islandGroup.add(rock);
    } else {
      const tree = new THREE.Group();
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.34, 1.8, 7), trunkMat);
      trunk.position.y = 0.9;
      trunk.castShadow = true;
      const crown1 = new THREE.Mesh(new THREE.ConeGeometry(1.4, 2.5, 8), leafMat);
      crown1.position.y = 2.6;
      crown1.castShadow = true;
      const crown2 = new THREE.Mesh(new THREE.ConeGeometry(1.0, 2.0, 8), leafMat);
      crown2.position.y = 3.8;
      crown2.castShadow = true;
      tree.add(trunk, crown1, crown2);
      tree.position.set(x, 0, z);
      islandGroup.add(tree);
    }
  }
}
addSceneryProps();

// Drifting sea of clouds below island
const cloudSea = new THREE.Group();
const cloudMat = new THREE.MeshStandardMaterial({
  color: 0x2a2448,
  emissive: 0x16122c,
  roughness: 1.0,
  transparent: true,
  opacity: 0.85,
});
for (let i = 0; i < 28; i++) {
  const a = (i / 28) * Math.PI * 2;
  const r = 52 + (i % 4) * 14;
  const puff = new THREE.Mesh(new THREE.SphereGeometry(7 + (i % 3) * 2.5, 12, 10), cloudMat);
  puff.scale.set(1.6, 0.42, 1.3);
  puff.position.set(Math.cos(a) * r, -3.5 - (i % 3) * 1.2, Math.sin(a) * r);
  cloudSea.add(puff);
}
scene.add(cloudSea);

// ---------- Character: Mây (conical hat nón lá + hanging mini lantern + Orbiting Firefly Halo) ----------
const playerGroup = new THREE.Group();
scene.add(playerGroup);

const playerBodyGroup = new THREE.Group();
playerGroup.add(playerBodyGroup);

const cloakMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.55, 1.25, 12),
  new THREE.MeshStandardMaterial({ color: 0x3b6078, roughness: 0.75 })
);
cloakMesh.position.y = 0.68;
cloakMesh.castShadow = true;
playerBodyGroup.add(cloakMesh);

const headMesh = new THREE.Mesh(
  new THREE.SphereGeometry(0.29, 14, 14),
  new THREE.MeshStandardMaterial({ color: 0xf6d9c3, roughness: 0.65 })
);
headMesh.position.y = 1.42;
headMesh.castShadow = true;
playerBodyGroup.add(headMesh);

// Nón lá (conical hat)
const hatMesh = new THREE.Mesh(
  new THREE.ConeGeometry(0.68, 0.38, 18),
  new THREE.MeshStandardMaterial({ color: 0xd9b36c, roughness: 0.85, side: THREE.DoubleSide })
);
hatMesh.position.y = 1.68;
hatMesh.castShadow = true;
playerBodyGroup.add(hatMesh);

// Hanging miniature golden lantern on hat brim
const miniCord = new THREE.Mesh(
  new THREE.CylinderGeometry(0.015, 0.015, 0.24, 6),
  new THREE.MeshBasicMaterial({ color: 0x5c3c20 })
);
miniCord.position.set(0, 1.45, 0.56);
playerBodyGroup.add(miniCord);

const miniLantern = new THREE.Mesh(
  new THREE.SphereGeometry(0.11, 10, 10),
  new THREE.MeshStandardMaterial({
    color: 0xffd27a,
    emissive: 0xff9f2e,
    emissiveIntensity: 2.2,
    roughness: 0.3,
  })
);
miniLantern.position.set(0, 1.32, 0.56);
playerBodyGroup.add(miniLantern);

const playerLight = new THREE.PointLight(0xffb558, 4.0, 15, 1.6);
playerLight.position.set(0, 1.5, 0.56);
playerGroup.add(playerLight);

// Creative Feature 1: Orbiting Firefly Halo matching carried count
const haloGroup = new THREE.Group();
haloGroup.position.y = 1.85;
playerGroup.add(haloGroup);
const haloOrbs = [];
for (let i = 0; i < 10; i++) {
  const orb = new THREE.Mesh(
    new THREE.SphereGeometry(0.075, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0xffd56b })
  );
  orb.visible = false;
  haloGroup.add(orb);
  haloOrbs.push(orb);
}

// Expanding Pulse Shockwave Ring
const pulseRing = new THREE.Mesh(
  new THREE.RingGeometry(0.7, 1.0, 48),
  new THREE.MeshBasicMaterial({
    color: 0xffc857,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.0,
  })
);
pulseRing.rotation.x = -Math.PI / 2;
pulseRing.position.y = 0.15;
pulseRing.visible = false;
scene.add(pulseRing);
let pulseFxTime = -1;

// ---------- Dynamic Entity Pools ----------
const lanternObjects = new Map();
const moteObjects = new Map();
const shadeObjects = new Map();
const sparks = [];

function createLanternVisual(lData, lanternCost, safeRadius) {
  const group = new THREE.Group();
  group.position.set(lData.pos[0], 0, lData.pos[2]);

  const stoneBase = new THREE.Mesh(
    new THREE.CylinderGeometry(0.7, 0.9, 0.45, 8),
    new THREE.MeshStandardMaterial({ color: 0x454a5c, roughness: 0.9 })
  );
  stoneBase.position.y = 0.22;
  stoneBase.castShadow = true;
  stoneBase.receiveShadow = true;
  group.add(stoneBase);

  const pillar = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18, 0.24, 2.5, 8),
    new THREE.MeshStandardMaterial({ color: 0x3b2d26, roughness: 0.85 })
  );
  pillar.position.y = 1.65;
  pillar.castShadow = true;
  group.add(pillar);

  const housingMat = new THREE.MeshStandardMaterial({
    color: 0x4c4866,
    emissive: 0x261d3a,
    emissiveIntensity: 0.4,
    roughness: 0.45,
  });
  const housing = new THREE.Mesh(new THREE.SphereGeometry(0.62, 16, 14), housingMat);
  housing.scale.y = 1.25;
  housing.position.y = 3.2;
  group.add(housing);

  const cap = new THREE.Mesh(
    new THREE.ConeGeometry(0.85, 0.5, 8),
    new THREE.MeshStandardMaterial({ color: 0x2c2438, roughness: 0.8 })
  );
  cap.position.y = 4.0;
  group.add(cap);

  const light = new THREE.PointLight(0xffa947, 0, 28, 1.5);
  light.position.y = 3.2;
  group.add(light);

  // Ground safe_radius aura ring
  const safeRingMat = new THREE.MeshBasicMaterial({
    color: 0xffbe55,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.0,
  });
  const safeRing = new THREE.Mesh(
    new THREE.RingGeometry(safeRadius - 0.14, safeRadius, 48),
    safeRingMat
  );
  safeRing.rotation.x = -Math.PI / 2;
  safeRing.position.y = 0.06;
  group.add(safeRing);

  // Floating progress pips (5 pips)
  const pips = [];
  for (let i = 0; i < lanternCost; i++) {
    const pipMat = new THREE.MeshBasicMaterial({ color: 0x5c5875 });
    const pip = new THREE.Mesh(new THREE.SphereGeometry(0.1, 8, 8), pipMat);
    const a = (i / lanternCost) * Math.PI * 2;
    pip.position.set(Math.cos(a) * 1.05, 1.65, Math.sin(a) * 1.05);
    group.add(pip);
    pips.push(pip);
  }

  scene.add(group);
  return { group, housingMat, light, safeRingMat, pips };
}

function createMoteVisual(pos) {
  const group = new THREE.Group();
  group.position.set(pos[0], 0, pos[2]);

  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.24, 12, 12),
    new THREE.MeshStandardMaterial({
      color: 0xffe484,
      emissive: 0xffa62b,
      emissiveIntensity: 2.5,
      roughness: 0.2,
    })
  );
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 12, 12),
    new THREE.MeshBasicMaterial({ color: 0xffc65c, transparent: true, opacity: 0.25 })
  );
  group.add(core, halo);
  scene.add(group);
  return { group, phase: Math.random() * Math.PI * 2 };
}

function createShadeVisual(pos) {
  const group = new THREE.Group();
  group.position.set(pos[0], pos[1], pos[2]);

  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x0e081a,
    emissive: 0x4b187a,
    emissiveIntensity: 1.0,
    roughness: 0.5,
  });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.62, 14, 14), bodyMat);
  body.scale.set(1, 1.35, 1);
  body.castShadow = true;
  group.add(body);

  const eyeL = new THREE.Mesh(
    new THREE.SphereGeometry(0.09, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0xd980ff })
  );
  eyeL.position.set(-0.2, 0.25, 0.52);
  const eyeR = eyeL.clone();
  eyeR.position.x = 0.2;
  group.add(eyeL, eyeR);

  const stunRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.5, 0.05, 6, 20),
    new THREE.MeshBasicMaterial({ color: 0xe6a8ff })
  );
  stunRing.rotation.x = Math.PI / 2;
  stunRing.position.y = 1.05;
  stunRing.visible = false;
  group.add(stunRing);

  scene.add(group);
  return { group, bodyMat, stunRing, phase: Math.random() * Math.PI * 2 };
}

function spawnBurst(x, y, z, color, count = 12) {
  const mat = new THREE.MeshBasicMaterial({ color });
  const geo = new THREE.SphereGeometry(0.09, 6, 6);
  for (let i = 0; i < count; i++) {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    scene.add(m);
    const a = Math.random() * Math.PI * 2;
    const sp = 1.5 + Math.random() * 3.5;
    sparks.push({
      mesh: m,
      vx: Math.cos(a) * sp,
      vy: 2.0 + Math.random() * 3.5,
      vz: Math.sin(a) * sp,
      life: 0.65,
    });
  }
}

// ---------- HUD Refs ----------
const elConn = document.getElementById('conn-dot');
const elFlames = document.getElementById('hud-flames');
const elCarried = document.getElementById('hud-carried');
const elLanterns = document.getElementById('hud-lanterns');
const elScore = document.getElementById('hud-score');
const elTimer = document.getElementById('hud-timer');
const elPulse = document.getElementById('hud-pulse');
const elToast = document.getElementById('event-toast');
const elPrompt = document.getElementById('context-prompt');
const elWelcome = document.getElementById('welcome-banner');
const elOverlay = document.getElementById('gameover-overlay');
const elModalTitle = document.getElementById('modal-title');
const elModalSub = document.getElementById('modal-subtitle');
const elModalScore = document.getElementById('modal-score');
const elModalLanterns = document.getElementById('modal-lanterns');
const elModalFlames = document.getElementById('modal-flames');
const elModalTime = document.getElementById('modal-time');

let toastTimeout = null;
function showToast(text) {
  elToast.textContent = text;
  elToast.classList.remove('hidden');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => elToast.classList.add('hidden'), 2000);
}

// ---------- Controls & WebSocket Sync ----------
const keys = new Set();
let camYawDeg = 0;
let isDragging = false;
let lastMouseX = 0;
let latestState = null;

window.addEventListener('keydown', (e) => {
  sfx.unlock();
  const code = e.code;
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(code)) {
    e.preventDefault();
  }
  keys.add(code);
  if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(code)) {
    elWelcome.classList.add('hidden');
  }
  if (code === 'KeyR') {
    sendRestart();
  } else if (code === 'KeyM') {
    const muted = sfx.toggleMute();
    document.getElementById('btn-mute').textContent = muted ? '🔇 Tắt tiếng [M]' : '🔊 Âm thanh [M]';
  }
});

window.addEventListener('keyup', (e) => {
  keys.delete(e.code);
});

canvas.addEventListener('mousedown', (e) => {
  sfx.unlock();
  isDragging = true;
  lastMouseX = e.clientX;
});
window.addEventListener('mouseup', () => { isDragging = false; });
window.addEventListener('mousemove', (e) => {
  if (!isDragging) return;
  const dx = e.clientX - lastMouseX;
  lastMouseX = e.clientX;
  camYawDeg = (camYawDeg - dx * 0.35) % 360;
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

function sendRestart() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    elOverlay.classList.add('hidden');
    const nextSeed = Math.floor(Math.random() * 900000) + 1000;
    ws.send(JSON.stringify({ type: 'restart', seed: nextSeed }));
  }
}

document.getElementById('btn-play-again').addEventListener('click', sendRestart);
document.getElementById('btn-restart-hud').addEventListener('click', sendRestart);
document.getElementById('btn-mute').addEventListener('click', () => {
  const muted = sfx.toggleMute();
  document.getElementById('btn-mute').textContent = muted ? '🔇 Tắt tiếng [M]' : '🔊 Âm thanh [M]';
});

function handleEvents(events, state) {
  for (const ev of events) {
    if (ev.name === 'mote_picked') {
      sfx.motePicked(ev.data.carried);
      spawnBurst(state.player.pos[0], state.player.pos[1] + 0.8, state.player.pos[2], 0xffd56b, 8);
    } else if (ev.name === 'deposit') {
      sfx.deposit();
      showToast(`Đã nạp +${ev.data.amount} ánh sáng vào ${ev.data.lantern_id}`);
      const lan = state.lanterns.find((l) => l.id === ev.data.lantern_id);
      if (lan) spawnBurst(lan.pos[0], 2.5, lan.pos[2], 0xffbe55, 14);
    } else if (ev.name === 'lantern_lit') {
      sfx.lanternLit();
      showToast(`✨ ${ev.data.lantern_id} đã bừng sáng!`);
      const lan = state.lanterns.find((l) => l.id === ev.data.lantern_id);
      if (lan) spawnBurst(lan.pos[0], 3.2, lan.pos[2], 0xffe484, 24);
    } else if (ev.name === 'pulse') {
      sfx.pulse();
      pulseFxTime = 0;
      pulseRing.position.set(state.player.pos[0], 0.15, state.player.pos[2]);
      pulseRing.visible = true;
      const cnt = (ev.data.stunned_ids || []).length;
      showToast(cnt > 0 ? `🌟 Tỏa sáng làm choáng ${cnt} Bóng Mực!` : '🌟 Tỏa sáng!');
    } else if (ev.name === 'player_hit') {
      sfx.playerHit();
      showToast(`💥 Bị Bóng Mực chạm! Rơi ${ev.data.dropped} đom đóm`);
      spawnBurst(state.player.pos[0], 1.0, state.player.pos[2], 0xc678ff, 14);
    } else if (ev.name === 'game_over') {
      sfx.gameOver(ev.data.result === 'won');
    }
  }
}

function syncVisualsFromState(st) {
  const tuning = st.tuning;
  const cost = tuning.lantern_cost;
  const safeR = tuning.safe_radius;

  // Player position & yaw
  playerGroup.position.set(st.player.pos[0], st.player.pos[1], st.player.pos[2]);
  playerBodyGroup.rotation.y = THREE.MathUtils.degToRad(st.player_yaw_deg || 0);
  playerBodyGroup.visible = st.invuln_s <= 0 || Math.floor(st.tick / 4) % 2 === 0;

  // Orbiting firefly halo
  for (let i = 0; i < haloOrbs.length; i++) {
    haloOrbs[i].visible = i < st.player.carried;
  }

  // Lanterns & progressive island lighting
  for (const lData of st.lanterns) {
    let vis = lanternObjects.get(lData.id);
    if (!vis) {
      vis = createLanternVisual(lData, cost, safeR);
      lanternObjects.set(lData.id, vis);
    }
    vis.group.position.set(lData.pos[0], 0, lData.pos[2]);
    if (lData.lit) {
      vis.housingMat.color.setHex(0xffe08a);
      vis.housingMat.emissive.setHex(0xff9d2e);
      vis.housingMat.emissiveIntensity = 2.6;
      vis.light.intensity = 10.0;
      vis.safeRingMat.opacity = 0.35;
    } else {
      const ratio = lData.deposited / cost;
      vis.housingMat.color.setHex(0x4c4866);
      vis.housingMat.emissive.setHex(ratio > 0 ? 0xa36420 : 0x261d3a);
      vis.housingMat.emissiveIntensity = 0.4 + ratio * 1.1;
      vis.light.intensity = ratio * 2.5;
      vis.safeRingMat.opacity = 0.0;
    }
    vis.pips.forEach((pip, idx) => {
      pip.material.color.setHex(idx < lData.deposited ? 0xffc65c : 0x45405c);
    });
  }

  // Motes sync
  const activeMoteIds = new Set();
  for (const mData of st.motes || []) {
    activeMoteIds.add(mData.id);
    let vis = moteObjects.get(mData.id);
    if (!vis) {
      vis = createMoteVisual(mData.pos);
      moteObjects.set(mData.id, vis);
    }
    vis.group.position.x = mData.pos[0];
    vis.group.position.z = mData.pos[2];
  }
  for (const [id, vis] of moteObjects.entries()) {
    if (!activeMoteIds.has(id)) {
      scene.remove(vis.group);
      moteObjects.delete(id);
    }
  }

  // Shades sync
  const activeShadeIds = new Set();
  for (const sData of st.shades || []) {
    activeShadeIds.add(sData.id);
    let vis = shadeObjects.get(sData.id);
    if (!vis) {
      vis = createShadeVisual(sData.pos);
      shadeObjects.set(sData.id, vis);
    }
    vis.group.position.set(sData.pos[0], sData.pos[1], sData.pos[2]);
    const stunned = sData.state === 'stunned';
    vis.stunRing.visible = stunned;
    vis.bodyMat.emissive.setHex(stunned ? 0xb47cff : 0x4b187a);
    vis.bodyMat.emissiveIntensity = stunned ? 1.8 : 1.0;
  }
  for (const [id, vis] of shadeObjects.entries()) {
    if (!activeShadeIds.has(id)) {
      scene.remove(vis.group);
      shadeObjects.delete(id);
    }
  }

  // HUD updates
  const maxFlames = tuning.flames;
  elFlames.textContent = '🔥'.repeat(st.player.flames) + '🖤'.repeat(Math.max(0, maxFlames - st.player.flames));
  elCarried.textContent = `✨ ${st.player.carried} / ${tuning.carry_capacity}`;
  elLanterns.textContent = `🏮 ${st.lit_count} / ${st.lantern_total}`;
  elScore.textContent = String(st.score);

  const secs = Math.max(0, Math.ceil(st.time_left_s));
  const mm = String(Math.floor(secs / 60)).padStart(2, '0');
  const ss = String(secs % 60).padStart(2, '0');
  elTimer.textContent = `${mm}:${ss}`;

  if (st.pulse_cooldown_s > 0) {
    elPulse.textContent = `Hồi ${st.pulse_cooldown_s.toFixed(1)}s`;
    elPulse.className = 'value cooldown';
  } else if (st.player.carried < tuning.pulse_cost) {
    elPulse.textContent = `Thiếu sáng (cần ${tuning.pulse_cost})`;
    elPulse.className = 'value cooldown';
  } else {
    elPulse.textContent = `Sẵn sàng (tốn ${tuning.pulse_cost})`;
    elPulse.className = 'value ready';
  }

  // Context prompt near unlit lantern
  let nearUnlit = null;
  for (const lData of st.lanterns) {
    if (lData.lit) continue;
    const d = Math.hypot(st.player.pos[0] - lData.pos[0], st.player.pos[2] - lData.pos[2]);
    if (d <= tuning.interact_radius) {
      nearUnlit = lData;
      break;
    }
  }
  if (nearUnlit && st.state === 'playing') {
    elPrompt.textContent =
      st.player.carried > 0
        ? `Nhấn [E] nạp ánh sáng vào ${nearUnlit.id} (${nearUnlit.deposited}/${cost})`
        : `${nearUnlit.id} (${nearUnlit.deposited}/${cost}) — Hãy nhặt thêm đom đóm ✨`;
    elPrompt.classList.remove('hidden');
  } else {
    elPrompt.classList.add('hidden');
  }

  // Island lighting brightens progressively as lanterns are lit
  const litFrac = st.lit_count / Math.max(1, st.lantern_total);
  hemiLight.intensity = 0.65 + litFrac * 0.85;
  scene.background.lerpColors(NIGHT_SKY, WARM_SKY, litFrac);
  scene.fog.color.copy(scene.background);
  scene.fog.density = 0.015 - litFrac * 0.007;

  // Game Over modal
  if (st.state === 'won' || st.state === 'lost') {
    elOverlay.classList.remove('hidden');
    if (st.state === 'won') {
      elModalTitle.textContent = 'Đảo Bến Đã Bừng Sáng!';
      elModalSub.textContent = 'Mây đã thắp sáng cả 5 Đèn Lồng Lớn và đẩy lùi màn sương đen.';
    } else {
      elModalTitle.textContent = 'Màn Đêm Phủ Kín';
      elModalSub.textContent =
        st.game_over_reason === 'dawn'
          ? 'Thời gian đêm đã hết trước khi thắp đủ 5 Đèn Lồng Lớn.'
          : 'Bóng Mực đã dập tắt hết ngọn lửa của Mây.';
    }
    elModalScore.textContent = String(st.score);
    elModalLanterns.textContent = `${st.lit_count} / ${st.lantern_total}`;
    elModalFlames.textContent = String(st.player.flames);
    elModalTime.textContent = `${Math.floor(st.time_left_s)}s`;
  } else {
    elOverlay.classList.add('hidden');
  }
}

// ---------- Animation & Input Loop ----------
let lastFrameTime = performance.now();
function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min(0.05, (now - lastFrameTime) / 1000);
  lastFrameTime = now;
  const t = now * 0.001;

  // Keyboard camera rotation
  if (keys.has('KeyQ')) camYawDeg = (camYawDeg + 95 * dt) % 360;
  if (keys.has('KeyC')) camYawDeg = (camYawDeg - 95 * dt) % 360;

  // Send input packet matching Test Contract v1.0 handedness:
  // forward vector = (sin θ, cos θ), right vector = (-cos θ, sin θ) => move_x: A=+1, D=-1; move_z: W=+1, S=-1
  if (ws && ws.readyState === WebSocket.OPEN) {
    const mz = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
    const mx = (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0) - (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0);
    ws.send(
      JSON.stringify({
        type: 'input',
        move: [mx, mz],
        cam_yaw_deg: camYawDeg,
        jump: keys.has('Space'),
        interact: keys.has('KeyE') || keys.has('KeyF'),
        pulse: keys.has('ShiftLeft') || keys.has('ShiftRight') || keys.has('KeyJ'),
      })
    );
  }

  // Orbiting fireflies around Mây's hat
  haloGroup.rotation.y = t * 1.9;
  haloOrbs.forEach((orb, idx) => {
    if (!orb.visible) return;
    const a = (idx / Math.max(1, haloOrbs.filter((o) => o.visible).length)) * Math.PI * 2;
    orb.position.set(Math.cos(a) * 0.95, Math.sin(t * 4 + idx) * 0.14, Math.sin(a) * 0.95);
  });

  // Bobbing motes & floating shades
  for (const vis of moteObjects.values()) {
    vis.group.position.y = 0.72 + Math.sin(t * 3.1 + vis.phase) * 0.22;
  }
  for (const vis of shadeObjects.values()) {
    vis.group.rotation.y = t * 1.4 + vis.phase;
    vis.stunRing.rotation.z = t * 5.0;
  }

  // Pulse shockwave animation
  if (pulseFxTime >= 0) {
    pulseFxTime += dt;
    const dur = 0.45;
    if (pulseFxTime >= dur) {
      pulseFxTime = -1;
      pulseRing.visible = false;
    } else {
      const p = pulseFxTime / dur;
      const scale = 1 + p * 7.5;
      pulseRing.scale.set(scale, scale, 1);
      pulseRing.material.opacity = (1 - p) * 0.75;
    }
  }

  // Burst sparks
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
    const sc = Math.max(0.1, s.life / 0.65);
    s.mesh.scale.setScalar(sc);
  }

  cloudSea.rotation.y = t * 0.012;

  // Third-person camera follow
  const px = playerGroup.position.x;
  const py = playerGroup.position.y;
  const pz = playerGroup.position.z;
  const rad = THREE.MathUtils.degToRad(camYawDeg);
  const camDist = 14.5;
  const camHeight = 8.8;
  camera.position.set(px - Math.sin(rad) * camDist, py + camHeight, pz - Math.cos(rad) * camDist);
  camera.lookAt(px, py + 1.6, pz);

  renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

requestAnimationFrame(animate);
