// EstelarIA — escena 3D "el universo de EstelarIA". ES module, Three.js vía importmap.
// Planetas = redes (de donde llegan las señales); estrellas = temas; cerca del centro = producir ya.
// Contrato: export function mountScene(canvas, topics, onOpen, sources)
//   -> { focus(slug), discover(slug, platform), screenPos(slug), setExplore(on), release(), isExplore() }
// opts.onPlanet(name) se llama al tocar un planeta.
// Sin WebGL: lanza Error('no-webgl') y el index.js hace fallback 2D.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

// Paleta galaxia: lima = acento azul eléctrico, despegando = violeta.
const COLORS = { lima: 0x6f94ff, despegando: 0xa77dff, hueso: 0xe9e6ff, ambar: 0xffc07a, apagado: 0x6b68a0 };
// Por early_label (lenguaje simple); si falta, por stage.
const KIND_BY_LABEL = { temprano: "early", despegando: "rising", estable: "stable", pico: "peak", saturado: "peak", cayendo: "fading" };
const KIND_BY_STAGE = { temprana: "early", creciendo: "rising", estable: "stable", saturada: "peak", bajando: "fading" };
const KIND_COLOR = { early: COLORS.lima, rising: COLORS.despegando, stable: COLORS.hueso, peak: COLORS.ambar, fading: COLORS.apagado };

// Planetas: color propio sutil.
const PLATFORMS = {
  youtube: ["YouTube", 0xe0645a],
  linkedin: ["LinkedIn", 0x5e9bd0],
  instagram: ["Instagram", 0xd0699f],
  tiktok: ["TikTok", 0x5fcfc8],
  hn: ["Hacker News", 0xe58a44],
  gnews: ["Google News", 0x9fb4c8],
  wiki: ["Wikipedia", 0xb9b6d6],
};
const DEFAULT_SOURCES = ["youtube", "linkedin", "instagram", "tiktok", "hn", "gnews"].map((name) => ({ name, signals: 100 }));

// Órbitas = umbrales de decisión.
const R_MIN = 3.5;
const R_MAX = 17;
const R_PLANETS = 23;
const ringRadius = (p) => R_MIN + (R_MAX - R_MIN) * (1 - p);

const clamp01 = (v) => Math.max(0, Math.min(1, v == null ? 0 : v));
const rgb = (hex) => [(hex >> 16) & 255, (hex >> 8) & 255, hex & 255];

function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")));
  } catch (e) {
    return false;
  }
}

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Sprite radial (canvas 2D, sin assets). stops: [[pos, "rgba"], ...]
function radialTexture(stops, size = 128) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const ctx = cv.getContext("2d");
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  stops.forEach(([p, c]) => g.addColorStop(p, c));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(cv);
}

function starTexture(hex) {
  const [r, g, b] = rgb(hex);
  return radialTexture([
    [0, "rgba(255,255,255,0.85)"],
    [0.16, `rgba(${r},${g},${b},0.95)`],
    [0.5, `rgba(${r},${g},${b},0.3)`],
    [1, "rgba(0,0,0,0)"],
  ]);
}

// Anillo blanco suave (se tiñe con material.color): halo de pico y anillo de nacimiento.
function ringTexture() {
  return radialTexture([
    [0, "rgba(255,255,255,0)"],
    [0.6, "rgba(255,255,255,0)"],
    [0.78, "rgba(255,255,255,0.9)"],
    [0.86, "rgba(255,255,255,0.35)"],
    [1, "rgba(255,255,255,0)"],
  ]);
}

function nebulaTexture(hex, alpha) {
  // Nube irregular: varias manchas radiales superpuestas.
  const [r, g, b] = rgb(hex);
  const size = 256;
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const ctx = cv.getContext("2d");
  for (let i = 0; i < 7; i++) {
    const x = size / 2 + (Math.random() - 0.5) * size * 0.4;
    const y = size / 2 + (Math.random() - 0.5) * size * 0.4;
    const rad = size * (0.18 + Math.random() * 0.22);
    const g2 = ctx.createRadialGradient(x, y, 0, x, y, rad);
    g2.addColorStop(0, `rgba(${r},${g},${b},${alpha * 0.55})`);
    g2.addColorStop(0.5, `rgba(${r},${g},${b},${alpha * 0.2})`);
    g2.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.fillStyle = g2;
    ctx.fillRect(0, 0, size, size);
  }
  return new THREE.CanvasTexture(cv);
}

function makeTextSprite(text, color) {
  const cv = document.createElement("canvas");
  cv.width = 512;
  cv.height = 96;
  const ctx = cv.getContext("2d");
  ctx.font = "500 40px Geist, 'Helvetica Neue', Arial, sans-serif";
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false }));
  sp.scale.set(5, 0.94, 1);
  return sp;
}

// Campo de estrellas de fondo (Points con titileo en shader). posFn: () -> [x,y,z]
function buildPoints(count, size, posFn, tint) {
  const geo = new THREE.BufferGeometry();
  const p = new Float32Array(count * 3);
  const a = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    p.set(posFn(), i * 3);
    a[i] = Math.random();
  }
  geo.setAttribute("position", new THREE.BufferAttribute(p, 3));
  geo.setAttribute("aOpacity", new THREE.BufferAttribute(a, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(tint) }, uSize: { value: size } },
    vertexShader: `
      attribute float aOpacity; varying float vO; uniform float uTime; uniform float uSize;
      void main() {
        vO = aOpacity * (0.4 + 0.6 * sin(uTime * (0.5 + aOpacity * 1.6) + aOpacity * 40.0));
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = uSize * (160.0 / -mv.z);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      varying float vO; uniform vec3 uColor;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        gl_FragColor = vec4(uColor, vO * (1.0 - d * 2.0));
      }`,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

function onSphere(rMin, rMax) {
  const r = rMin + Math.random() * (rMax - rMin);
  const th = Math.random() * Math.PI * 2;
  const ph = Math.acos(2 * Math.random() - 1);
  return [r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th)];
}

// Vía Láctea: banda inclinada de puntos tras el disco.
function milkyPos() {
  const t = (Math.random() - 0.5) * 2;
  const across = (Math.random() + Math.random() - 1) * (10 + 26 * (1 - Math.abs(t)));
  const a = 0.5;
  const along = t * 260;
  return [along * Math.cos(a) - across * Math.sin(a), along * Math.sin(a) * 0.6 + across * Math.cos(a) + 10, -170 + across * 0.3];
}

// Nebulosa volumétrica falsa: nubes aditivas grandes azul/violeta que derivan y rotan despacio (ver animate).
function buildNebula() {
  const g = new THREE.Group();
  [
    [0x2f55ff, 0.34, -70, 30, -190, 300],
    [0x7a3cff, 0.3, 100, -20, -200, 320],
    [0x1a0f6a, 0.4, 10, -60, -170, 260],
    [0xb04bff, 0.16, -140, -30, -210, 240],
    [0x2a7bff, 0.18, 150, 60, -230, 280],
    [0x3b1a9a, 0.34, -30, 90, -180, 260],
    [0xff5fd2, 0.07, 40, 10, -220, 200],
  ].forEach(([c, a, x, y, z, s], i) => {
    const sp = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: nebulaTexture(c, Math.min(1, a * 1.5)), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false })
    );
    sp.position.set(x, y, z);
    sp.scale.set(s, s * 0.7, 1);
    sp.userData = { x, y, ph: i * 1.7, rot: (i % 2 ? 1 : -1) * (0.004 + 0.003 * i) };
    g.add(sp);
  });
  return g;
}

// Planeta: esfera iluminada desde el núcleo (shader simple) + borde atmosférico.
function planetMaterial(hex) {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(hex).lerp(new THREE.Color(0x7a78a8), 0.25) } },
    vertexShader: `
      varying vec3 vN; varying vec3 vW; varying vec3 vV;
      void main() {
        vec4 w = modelMatrix * vec4(position, 1.0);
        vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
        vV = normalize(cameraPosition - w.xyz);
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      varying vec3 vN; varying vec3 vW; varying vec3 vV; uniform vec3 uColor;
      void main() {
        float l = max(dot(vN, normalize(-vW)), 0.0);
        float rim = pow(1.0 - max(dot(vN, vV), 0.0), 3.0);
        vec3 c = uColor * (0.14 + 0.9 * l) + vec3(0.45, 0.55, 1.0) * 0.12 * l + uColor * rim * 0.35;
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
}

// Atmósfera: fresnel aditivo del color del planeta (uAmt la enciende al seleccionarlo).
function atmosphereMaterial(hex) {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(hex) }, uAmt: { value: 0 } },
    vertexShader: `
      varying vec3 vN; varying vec3 vV;
      void main() {
        vec4 w = modelMatrix * vec4(position, 1.0);
        vN = normalize(mat3(modelMatrix) * normal); vV = normalize(cameraPosition - w.xyz);
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      varying vec3 vN; varying vec3 vV; uniform vec3 uColor; uniform float uAmt;
      void main() {
        float f = pow(1.0 - max(dot(vN, vV), 0.0), 2.2);
        gl_FragColor = vec4(uColor * 1.4, f * uAmt);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
}

// Estelas de velocidad: líneas radiales pegadas a la cámara; uAmt (0..1) las estira desde el punto de fuga.
function buildWarp(count) {
  const p = new Float32Array(count * 6);
  const e = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2;
    const r = 1.5 + Math.random() * 14;
    const z = -(6 + Math.random() * 60);
    p.set([Math.cos(a) * r, Math.sin(a) * r, z, Math.cos(a) * r, Math.sin(a) * r, z], i * 6);
    e[i * 2 + 1] = 1;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(p, 3));
  geo.setAttribute("aEnd", new THREE.BufferAttribute(e, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uAmt: { value: 0 } },
    vertexShader: `
      attribute float aEnd; uniform float uAmt; varying float vA;
      void main() {
        vec3 q = position;
        q.xy *= 1.0 + aEnd * uAmt * 1.6;
        q.z *= 1.0 - aEnd * uAmt * 0.55;
        vA = (1.0 - aEnd * 0.8) * uAmt;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(q, 1.0);
      }`,
    fragmentShader: "varying float vA; void main() { gl_FragColor = vec4(0.62, 0.7, 1.0, vA * 0.85); }",
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const lines = new THREE.LineSegments(geo, mat);
  lines.frustumCulled = false;
  lines.visible = false;
  return lines;
}

// Haz del faro: cuña lima con degradado hacia atrás + línea brillante en el borde de ataque.
// Con rotation.y = -s, el borde de ataque apunta al azimut s (x=cos, z=sin).
function buildSweep(radius) {
  const group = new THREE.Group();
  const span = 0.5;
  const wedge = new THREE.Mesh(
    new THREE.CircleGeometry(radius, 48, 0, span),
    new THREE.ShaderMaterial({
      uniforms: { uSpan: { value: span } },
      vertexShader: `
        varying float vA; uniform float uSpan;
        void main() {
          vA = 1.0 - clamp(atan(position.y, position.x) / uSpan, 0.0, 1.0);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `varying float vA; void main() { gl_FragColor = vec4(0.45, 0.58, 1.0, vA * vA * 0.4); }`,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    })
  );
  wedge.rotation.x = -Math.PI / 2;
  wedge.position.y = 0.05;
  group.add(wedge);
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0.07, 0), new THREE.Vector3(radius, 0.07, 0)]),
    new THREE.LineBasicMaterial({ color: COLORS.lima, transparent: true, opacity: 0.9 })
  );
  group.add(line);
  return group;
}

function buildRings() {
  const group = new THREE.Group();
  // Producir ya = Recomendar p>=0.80; Vigilar = Aprender p>=0.50; borde = p 0.
  [
    [ringRadius(0.8), COLORS.lima, 0.6, "Producir ya", "rgba(143,171,255,0.9)"],
    [ringRadius(0.5), COLORS.ambar, 0.45, "Vigilar", "rgba(255,192,122,0.8)"],
    [R_MAX, 0x8a86c8, 0.22, null, null],
  ].forEach(([r, color, opacity, label, textColor]) => {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(r - 0.045, r + 0.045, 160),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false })
    );
    ring.rotation.x = -Math.PI / 2;
    group.add(ring);
    if (label) {
      const sp = makeTextSprite(label, textColor);
      sp.position.set(Math.cos(1.2) * r, 0.5, Math.sin(1.2) * r);
      group.add(sp);
    }
  });
  return group;
}

// Piezas por fuente de un tema: topic.by_source si existe; si no, cuenta top_signals por source.
export function sourceCounts(topic) {
  if (topic.by_source && typeof topic.by_source === "object") return { ...topic.by_source };
  const out = {};
  (topic.top_signals || []).forEach((s) => {
    out[s.source] = (out[s.source] || 0) + 1;
  });
  return out;
}

// Rayo de luz: cilindro fino (eje Y, de la estrella al planeta) con pulsos que fluyen y se desvanecen.
function makeRay(color, weight) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(color) }, uW: { value: weight }, uFade: { value: 0 }, uHead: { value: 1 } },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
    fragmentShader: `varying vec2 vUv; uniform float uTime; uniform float uW; uniform float uFade; uniform float uHead; uniform vec3 uColor;
      void main(){
        float flow = 0.5 + 0.5 * sin(vUv.y * 40.0 - uTime * 4.0);
        float a = (0.28 + 0.72 * flow) * (0.35 + 0.65 * uW) * uFade;
        a *= step(vUv.y, uHead);
        float hd = exp(-abs(vUv.y - uHead) * 28.0) * step(uHead, 0.999) * uFade;
        gl_FragColor = vec4(mix(uColor, vec3(1.0), 0.25 * flow + hd), a + hd * 0.9);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 6, 1, true), mat);
  mesh.frustumCulled = false;
  return mesh;
}

export function mountScene(canvas, topics, onOpen, sources, opts = {}) {
  if (!hasWebGL()) throw new Error("no-webgl");

  const reducedMotion = prefersReducedMotion();
  const parent = canvas.parentElement || canvas;
  if (getComputedStyle(parent).position === "static") parent.style.position = "relative";

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x05040d, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, (canvas.clientWidth || 1) / (canvas.clientHeight || 1), 0.1, 900);
  const baseCamPos = new THREE.Vector3(0, 18, 34);
  camera.position.copy(baseCamPos);
  const lookAt = new THREE.Vector3(0, 0, 0);
  const camStart = new THREE.Vector3();
  camera.lookAt(lookAt);
  scene.add(camera);
  canvas.__cam = camera; // inspección en pruebas
  const warp = buildWarp(520);
  camera.add(warp);
  const FOV_REST = 50;
  const flash = document.createElement("div");
  flash.className = "fly-flash";
  parent.appendChild(flash);

  // --- Fondo: estrellas en capas (parallax), vía láctea y nebulosa (~7000 puntos) ---
  const bg = new THREE.Group();
  scene.add(bg);
  const farStars = buildPoints(2600, 1.3, () => onSphere(300, 480), 0xcfd6ff);
  const nearStars = buildPoints(1300, 2.0, () => onSphere(140, 260), 0xffffff);
  const milky = buildPoints(3000, 1.4, milkyPos, 0xb9a8ff);
  const nebula = buildNebula();
  bg.add(farStars, nearStars, milky, nebula);
  const bgPoints = [farStars, nearStars, milky];

  // --- Observatorio: núcleo, órbitas-umbral y haz ---
  scene.add(buildRings());
  const sweep = buildSweep(R_MAX);
  scene.add(sweep);
  const coreGlow = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: starTexture(COLORS.lima), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
  );
  coreGlow.scale.set(3.2, 3.2, 1);
  scene.add(coreGlow);
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(0.28, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffffff })));

  // --- Capa de etiquetas DOM (textContent) ---
  const labelLayer = document.createElement("div");
  labelLayer.className = "star-label-layer";
  Object.assign(labelLayer.style, { position: "absolute", inset: "0", pointerEvents: "none", overflow: "hidden" });
  parent.appendChild(labelLayer);

  // --- Planetas = plataformas ---
  const list = (Array.isArray(sources) && sources.length ? sources : DEFAULT_SOURCES).filter((s) => PLATFORMS[s.name]);
  const maxSig = Math.max(1, ...list.map((s) => s.signals || 0));
  const planets = [];
  list.forEach((s, i) => {
    const [label, color] = PLATFORMS[s.name];
    const radius = 0.5 + 0.8 * Math.sqrt((s.signals || 0) / maxSig);
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 28, 20), planetMaterial(color));
    scene.add(mesh);
    const glow = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: starTexture(color), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.22 })
    );
    glow.scale.set(radius * 4, radius * 4, 1);
    mesh.add(glow);
    const el = document.createElement("div");
    el.textContent = label;
    Object.assign(el.style, {
      position: "absolute",
      transform: "translateX(-50%)",
      fontFamily: "Geist, 'Helvetica Neue', Arial, sans-serif",
      fontSize: "11px",
      letterSpacing: "0.04em",
      color: "rgba(200,198,235,0.85)",
      whiteSpace: "nowrap",
      pointerEvents: "none",
      textShadow: "0 1px 6px rgba(0,0,0,0.9)",
    });
    labelLayer.appendChild(el);
    const atmo = new THREE.Mesh(new THREE.SphereGeometry(radius * 1.16, 32, 20), atmosphereMaterial(color));
    atmo.visible = false;
    mesh.add(atmo);
    const orbitRing = new THREE.Mesh(
      new THREE.RingGeometry(radius * 2.1, radius * 2.14, 96),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending })
    );
    orbitRing.rotation.set(Math.PI / 2 - 0.35, 0, 0.3);
    orbitRing.visible = false;
    scene.add(orbitRing);
    planets.push({
      name: s.name,
      mesh,
      atmo,
      orbitRing,
      sel: 0,
      rot: 0,
      el,
      radius,
      angle: (i / list.length) * Math.PI * 2 + 0.4,
      speed: 0.045 + 0.012 * (i % 3), // rad/s, lento
      r: R_PLANETS + (i % 2) * 1.6,
    });
  });
  const placePlanet = (p) => p.mesh.position.set(Math.cos(p.angle) * p.r, 0, Math.sin(p.angle) * p.r);
  planets.forEach(placePlanet);

  // --- Estrellas = temas ---
  const ringTex = ringTexture();
  const texCache = {};
  const top3 = new Set([...topics].sort((a, b) => (b.p || 0) - (a.p || 0)).slice(0, 3).map((t) => t.slug));
  const rRec = ringRadius(0.8);
  const rApr = ringRadius(0.5);
  const catRank = { Recomendar: 0, Aprender: 1 };
  const order = [...topics].sort(
    (a, b) => (catRank[a.decision] ?? 2) - (catRank[b.decision] ?? 2) || String(a.slug).localeCompare(String(b.slug))
  );
  const n = Math.max(1, topics.length);
  const stars = [];

  topics.forEach((topic) => {
    const kind =
      KIND_BY_LABEL[String(topic.early_label || "").toLowerCase().split(/[\s/]/)[0]] || KIND_BY_STAGE[topic.stage] || "stable";
    const color = KIND_COLOR[kind];
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: (texCache[color] ??= starTexture(color)),
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    // Azimut en arco que deja libre el cuadrante cercano-izquierdo (titular).
    const k = order.indexOf(topic);
    const azimuth = -Math.PI * 0.8 + ((k + 0.5) / n) * Math.PI * 1.25;
    let d = ringRadius(clamp01(topic.p));
    if (topic.decision === "Recomendar") d = Math.min(d, rRec - 1.2);
    else if (topic.decision === "Aprender") d = THREE.MathUtils.clamp(d, rRec + 0.7, rApr - 0.7);
    else d = THREE.MathUtils.clamp(d, rApr + 0.7, R_MAX - 1);
    let baseScale = THREE.MathUtils.lerp(0.9, 2.2, Math.min(1, Math.max(0, topic.volume || 0) / 60));
    if (kind === "peak") baseScale *= 1.5;
    if (kind === "fading") baseScale *= 0.8;
    sprite.position.set(Math.cos(azimuth) * d, 0.3, Math.sin(azimuth) * d);
    scene.add(sprite);

    // Aro: estrella naciente (aro que se expande) o gigante ámbar (halo fijo).
    let aro = null;
    if (kind === "early" || kind === "peak") {
      aro = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: ringTex, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
      );
      aro.position.copy(sprite.position);
      scene.add(aro);
    }

    const label = document.createElement("div");
    label.className = "star-label";
    label.textContent = topic.name || topic.slug || "";
    Object.assign(label.style, {
      position: "absolute",
      transform: "translateX(-50%)",
      fontFamily: "'EB Garamond', Georgia, serif",
      color: topic.decision === "Recomendar" ? "var(--lima)" : "var(--hueso)",
      textShadow: "0 1px 6px rgba(0,0,0,0.85), 0 0 14px rgba(0,0,0,0.6)",
      fontSize: topic.decision === "Recomendar" ? "17px" : top3.has(topic.slug) ? "13px" : "16px",
      fontWeight: topic.decision === "Recomendar" ? "500" : "400",
      letterSpacing: "0.01em",
      whiteSpace: "nowrap",
      opacity: "0",
      transition: "opacity 0.35s ease",
      pointerEvents: "none",
    });
    labelLayer.appendChild(label);

    stars.push({
      topic,
      kind,
      sprite,
      aro,
      label,
      baseScale,
      growth: Math.max(0, topic.growth || 1),
      phase: Math.random() * 6.28,
      azimuth: ((azimuth % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2),
      top3: top3.has(topic.slug),
      rec: topic.decision === "Recomendar", // las estrellas Recomendar siempre llevan su nombre
      flashUntil: 0,
      flashing: false,
      sel: 0,
      hoverLabel: false,
      burstStart: null,
    });
  });

  const findStar = (slug) => stars.find((s) => s.topic.slug === slug);

  function project(v) {
    const p = v.clone().project(camera);
    return { x: (p.x * 0.5 + 0.5) * (canvas.clientWidth || 1), y: (-p.y * 0.5 + 0.5) * (canvas.clientHeight || 1), z: p.z };
  }

  // Etiquetas de estrellas: hover, destellos y top 3; recorta al viewport y evita solapes.
  function layoutLabels() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const edge = 12;
    const cand = [];
    stars.forEach((star) => {
      if (star === selected && heroOn) {
        star.label.style.opacity = "0";
        return;
      }
      const near = exploring && camera.position.distanceTo(star.sprite.position) < 16;
      if (!(star.hoverLabel || star.flashing || star.top3 || star.rec || near || star === selected)) {
        star.label.style.opacity = "0";
        return;
      }
      const v = project(star.sprite.position);
      const lw = star.label.offsetWidth || 80;
      const lh = star.label.offsetHeight || 20;
      const sy = v.y - 14;
      if (!(v.z < 1 && v.x > 0 && v.x < w && sy > edge && sy < h - edge)) {
        star.label.style.opacity = "0";
        return;
      }
      cand.push({
        star,
        lw,
        prio: star.hoverLabel || star === selected ? 3 : star.rec ? 2 : star.top3 ? 1 : 0,
        x: Math.max(edge + lw / 2, Math.min(w - edge - lw / 2, v.x)),
        y: Math.max(edge, Math.min(h - edge - lh, sy - lh)),
      });
    });
    cand.sort((a, b) => b.prio - a.prio || (b.star.topic.p || 0) - (a.star.topic.p || 0));
    const placed = [];
    cand.forEach((c) => {
      if (placed.some((o) => Math.abs(o.y - c.y) < 24 && Math.abs(o.x - c.x) < (o.lw + c.lw) / 2)) {
        c.star.label.style.opacity = "0";
        return;
      }
      placed.push(c);
      c.star.label.style.left = `${c.x}px`;
      c.star.label.style.top = `${c.y}px`;
      c.star.label.style.opacity = "1";
    });
    // Nombres de planetas bajo cada uno; se ocultan en el rincón del titular (abajo-izquierda).
    planets.forEach((p) => {
      const v = project(p.mesh.position);
      const hide = v.z >= 1 || (!exploring && ((v.x < w * 0.5 && v.y > h * 0.55) || (w < 800 && v.y > h * 0.6))) || v.x < 20 || v.x > w - 20 || v.y > h - 70 || v.y < 20;
      p.el.style.opacity = hide || (p === selectedPlanet && heroOn) ? "0" : "1";
      p.el.style.left = `${v.x}px`;
      p.el.style.top = `${v.y + 8 + p.radius * 9}px`;
    });
  }

  // --- Interacción ---
  const raycaster = new THREE.Raycaster();
  raycaster.params.Sprite = { threshold: 0.6 };
  const pointerNdc = new THREE.Vector2(-10, -10);
  let hovered = null;
  let mouse = { x: 0, y: 0 };

  canvas.addEventListener("pointermove", (ev) => {
    const r = canvas.getBoundingClientRect();
    pointerNdc.x = mouse.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointerNdc.y = mouse.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  });
  canvas.addEventListener("pointerleave", () => {
    pointerNdc.set(-10, -10);
    mouse = { x: 0, y: 0 };
  });
  // Toque/clic: la estrella o planeta más cercano al puntero en pantalla (cómodo en táctil).
  let down = null;
  canvas.addEventListener("pointerdown", (ev) => (down = { x: ev.clientX, y: ev.clientY }));
  function pick(ev) {
    const r = canvas.getBoundingClientRect();
    const px = ev.clientX - r.left;
    const py = ev.clientY - r.top;
    const lim = ev.pointerType === "touch" ? 34 : 26;
    let best = null;
    let bd = lim;
    const test = (v, item) => {
      const q = project(v);
      if (q.z >= 1) return;
      const d = Math.hypot(q.x - px, q.y - py);
      if (d < bd) {
        bd = d;
        best = item;
      }
    };
    stars.forEach((s) => test(s.sprite.position, { star: s }));
    planets.forEach((p) => test(p.mesh.position, { planet: p }));
    return best;
  }
  // El panel espera a que termine el vuelo y salgan los rayos: primero se ve la animación, luego el texto.
  let panelTimer = null;
  function select(hit, fly) {
    clearTimeout(panelTimer);
    const wait = fly && !reducedMotion ? 2300 : 0;
    if (hit.star) {
      if (fly) flyToStar(hit.star);
      showRays(hit.star.topic);
      panelTimer = setTimeout(() => {
        canvas.dispatchEvent(new CustomEvent("topic:open", { detail: hit.star.topic.slug, bubbles: true }));
        if (typeof onOpen === "function") onOpen(hit.star.topic.slug);
      }, wait);
    } else {
      if (fly) flyToPlanet(hit.planet);
      showPlanetRays(hit.planet);
      panelTimer = setTimeout(() => {
        if (typeof opts.onPlanet === "function") opts.onPlanet(hit.planet.name);
      }, wait);
    }
  }
  canvas.addEventListener("click", (ev) => {
    if (down && Math.hypot(ev.clientX - down.x, ev.clientY - down.y) > 6) return; // fue un arrastre
    const hit = pick(ev);
    if (hit) select(hit, !exploring);
  });
  canvas.addEventListener("dblclick", (ev) => {
    const hit = exploring && pick(ev);
    if (!hit) return;
    if (hit.star) {
      flyToStar(hit.star);
      showRays(hit.star.topic);
    } else {
      flyToPlanet(hit.planet);
      showPlanetRays(hit.planet);
    }
  });

  // --- Cámara: auto (vaivén) | held (fija sobre lo tocado) | explore (OrbitControls) ---
  let exploring = false;
  let controls = null;
  let dolly = null;
  let held = false;
  let selected = null;
  const MAX_TARGET = 32;
  const swayPos = (t, out) => {
    const sw = Math.sin(t * 0.05) * 0.22;
    return out.set(
      baseCamPos.x * Math.cos(sw) - baseCamPos.z * Math.sin(sw) + mouse.x * 1.5,
      baseCamPos.y + mouse.y * 0.8,
      baseCamPos.x * Math.sin(sw) + baseCamPos.z * Math.cos(sw)
    );
  };
  function requestDraw() {
    if (reducedMotion) draw();
  }

  // Vuelo cinematográfico: arco Bézier que rodea el objetivo, expo in-out, FOV 50→70→40 y estelas por velocidad.
  // toFn/lookFn se evalúan cada cuadro (los planetas se mueven). Con movimiento reducido: salto directo.
  const easeExpo = (k) => (k <= 0 ? 0 : k >= 1 ? 1 : k < 0.5 ? Math.pow(2, 20 * k - 10) / 2 : (2 - Math.pow(2, -20 * k + 10)) / 2);
  let hold = null; // órbita lenta tras llegar
  let flyEnd = 0;
  let idle = false; // deriva automática solo sin interacción ni vuelo
  let heroOn = false;
  let warpAmt = 0;
  let frameDt = 0;
  const lastPos = camera.position.clone();
  const setFov = (v) => {
    if (Math.abs(camera.fov - v) > 0.01) {
      camera.fov = v;
      camera.updateProjectionMatrix();
    }
  };
  function flyTo(toFn, lookFn, o = {}) {
    held = true;
    hold = null;
    if (reducedMotion) {
      camera.position.copy(toFn());
      lookAt.copy(lookFn());
      setFov(FOV_REST);
      flyEnd = 0;
      applyCamera();
      return;
    }
    const from = camera.position.clone();
    const to0 = toFn();
    const dir = to0.clone().sub(from);
    const len = dir.length();
    const side = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
    const ctrl = from.clone().lerp(to0, 0.5).addScaledVector(side, len * (o.arc ?? 0.38)).add(new THREE.Vector3(0, len * 0.12, 0));
    const duration = o.duration || 1900;
    dolly = { from, ctrl, lookFrom: lookAt.clone(), toFn, lookFn, start: performance.now(), duration, len, o };
    flyEnd = dolly.start + duration;
  }
  function applyCamera() {
    if (controls) {
      controls.target.copy(lookAt);
      controls.update();
    } else camera.lookAt(lookAt);
    requestDraw();
  }
  function flyToStar(star) {
    const p = star.sprite.position;
    const to = p.clone().add(p.clone().normalize().multiplyScalar(7)).add(new THREE.Vector3(0, 3, 0));
    flyTo(() => to, () => p);
  }
  function flyToPlanet(pl) {
    // ~35% de la altura de pantalla (FOV ~43). Elige el lado (adentro/afuera, ±tangente) con más aire hasta otros planetas.
    const d = pl.radius * 7.7;
    const offs = (sIn, sTan) => {
      const p = pl.mesh.position;
      const out = new THREE.Vector3(p.x, 0, p.z).normalize();
      const tan = new THREE.Vector3(-p.z, 0, p.x).normalize();
      return p.clone().addScaledVector(out, -sIn * d * 0.78).addScaledVector(tan, sTan * d * 0.5).add(new THREE.Vector3(0, d * 0.18, 0));
    };
    let best = [1, 1];
    let bs = -1;
    [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([i, t]) => {
      const c = offs(i, t);
      const sc = Math.min(...planets.filter((o) => o !== pl).map((o) => c.distanceTo(o.mesh.position)));
      if (sc > bs) {
        bs = sc;
        best = [i, t];
      }
    });
    flyTo(() => offs(best[0], best[1]), () => pl.mesh.position);
  }
  function focus(slug) {
    const star = findStar(slug);
    if (!star) return;
    flyToStar(star);
    showRays(star.topic);
  }
  // Vuelve a la vista general y borra los rayos (en explorar, solo borra rayos).
  function release() {
    clearRays();
    if (exploring || !held) return;
    hold = null;
    const zero = new THREE.Vector3();
    flyTo(() => swayPos(clock.elapsedTime + 1, new THREE.Vector3()), () => zero, { duration: 1200, arc: 0.22, release: true });
    held = false;
    flyEnd = 0;
  }
  function setExplore(on) {
    if (on === exploring) return;
    exploring = on;
    if (on) {
      dolly = null;
      held = true;
      controls = new OrbitControls(camera, canvas);
      // Órbita esférica: arrastre horizontal = azimut, vertical = elevación (polar acotado para no voltearse).
      controls.enableDamping = true;
      controls.dampingFactor = 0.04;
      controls.rotateSpeed = 0.7;
      controls.zoomSpeed = 0.8;
      controls.minPolarAngle = 0.1;
      controls.maxPolarAngle = Math.PI - 0.1;
      controls.minDistance = 2.5;
      controls.maxDistance = 90;
      controls.autoRotateSpeed = 0.25; // deriva muy lenta en reposo
      controls.target.copy(lookAt);
      let idleTimer = 0;
      controls.addEventListener("start", () => {
        dolly = null;
        hold = null;
        idle = false;
        clearTimeout(idleTimer);
      });
      controls.addEventListener("end", () => {
        idleTimer = setTimeout(() => (idle = !reducedMotion), 3000);
      });
      idle = !reducedMotion;
      controls.addEventListener("change", requestDraw);
      resize();
    } else {
      controls.dispose();
      controls = null;
      canvas.style.touchAction = "";
      resize();
      release();
    }
    requestDraw();
  }

  // --- Llegada: corona + anillos concéntricos (estrella) y título grande ---
  const glowTex = radialTexture([[0, "rgba(255,255,255,0.8)"], [0.3, "rgba(255,255,255,0.25)"], [1, "rgba(255,255,255,0)"]]);
  const fxSprite = (map) => {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    sp.visible = false;
    scene.add(sp);
    return sp;
  };
  const corona = fxSprite(glowTex);
  const fxRings = [fxSprite(ringTex), fxSprite(ringTex), fxSprite(ringTex)];
  let selectedPlanet = null;
  const hero = document.createElement("div");
  hero.className = "hero-label";
  labelLayer.appendChild(hero);
  let heroAnchor = null;
  function showHero(text, anchorFn, planetRadius) {
    hero.textContent = text;
    hero.classList.remove("hero-in");
    void hero.offsetWidth;
    hero.style.animationDelay = reducedMotion ? "0ms" : `${Math.max(0, flyEnd - performance.now() - 250)}ms`;
    hero.classList.add("hero-in");
    heroOn = true;
    heroAnchor = { fn: anchorFn, planetRadius };
  }
  function hideHero() {
    hero.classList.remove("hero-in");
    heroOn = false;
    heroAnchor = null;
  }
  function layoutHero() {
    if (!heroOn) return;
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const pos = heroAnchor.fn();
    const v = project(pos);
    let y = v.y - 64;
    let tf = "translate(-50%,-100%)";
    if (heroAnchor.planetRadius) {
      const R = (h / (2 * Math.tan((camera.fov * Math.PI) / 360))) * (heroAnchor.planetRadius / Math.max(0.1, camera.position.distanceTo(pos)));
      y = v.y - R - 14;
    }
    hero.style.visibility = v.z < 1 ? "visible" : "hidden";
    hero.style.left = `${Math.max(140, Math.min(w - 140, v.x))}px`;
    hero.style.top = `${Math.max(70, Math.min(h - 80, y))}px`;
    hero.style.transform = tf;
  }

  // --- Rayos de luz: de una estrella a las redes de donde vienen sus piezas (o de un planeta a sus temas) ---
  const rays = [];
  const UP = new THREE.Vector3(0, 1, 0);
  function clearRays() {
    rays.forEach((r) => {
      scene.remove(r.mesh);
      r.mesh.geometry.dispose();
      r.mesh.material.dispose();
    });
    rays.length = 0;
    selected = null;
    selectedPlanet = null;
    hideHero();
    requestDraw();
  }
  function addRays(origin, targets, color) {
    clearRays();
    const max = Math.max(1, ...targets.map((t) => t.count));
    const base = Math.max(performance.now(), flyEnd);
    targets.forEach((t, i) => {
      const w = t.count / max;
      const mesh = makeRay(color(t), w);
      mesh.userData.radius = 0.025 + 0.07 * w;
      scene.add(mesh);
      rays.push({ mesh, origin, target: t.pos, t0: base + i * 120 });
    });
    updateRays(0);
  }
  function showRays(topic) {
    const counts = sourceCounts(topic);
    const targets = planets.filter((p) => counts[p.name] > 0).map((p) => ({ pos: p.mesh.position, count: counts[p.name], hex: PLATFORMS[p.name][1] }));
    const star = findStar(topic.slug);
    addRays(star.sprite.position, targets, (t) => t.hex);
    selected = star;
    showHero(star.topic.name || star.topic.slug || "", () => star.sprite.position, 0);
  }
  function showPlanetRays(pl) {
    const ranked = stars
      .map((s) => ({ s, c: sourceCounts(s.topic)[pl.name] || 0 }))
      .filter((x) => x.c > 0)
      .sort((a, b) => b.c - a.c || (b.s.topic.p || 0) - (a.s.topic.p || 0))
      .slice(0, 3);
    const hex = PLATFORMS[pl.name][1];
    addRays(pl.mesh.position, ranked.map((x) => ({ pos: x.s.sprite.position, count: x.c })), () => hex);
    selectedPlanet = pl;
    showHero(PLATFORMS[pl.name][0], () => pl.mesh.position, pl.radius);
  }
  function updateRays(t) {
    const now = performance.now();
    rays.forEach((r) => {
      const a = r.origin;
      const b = r.target;
      r.mesh.position.copy(a).add(b).multiplyScalar(0.5);
      r.mesh.quaternion.setFromUnitVectors(UP, b.clone().sub(a).normalize());
      const rad = r.mesh.userData.radius;
      r.mesh.scale.set(rad, a.distanceTo(b), rad);
      r.mesh.material.uniforms.uTime.value = t;
      const u = clamp01((now - r.t0) / 700);
      r.mesh.material.uniforms.uFade.value = reducedMotion ? 1 : Math.min(1, Math.max(0, now - r.t0) / 400);
      r.mesh.material.uniforms.uHead.value = reducedMotion ? 1 : 1 - Math.pow(1 - u, 3);
    });
  }

  let vx = -0.1; // desplazamiento horizontal de la vista (fracción del ancho); con panel abierto centra el objetivo a la izquierda
  function resize() {
    const w = parent.clientWidth || window.innerWidth;
    const h = parent.clientHeight || window.innerHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    // En ancho empuja la escena a la derecha/arriba: el titular queda libre.
    camStart.set(0, 18, 34).multiplyScalar(w > 800 ? 1.3 : 2.1);
    baseCamPos.copy(camStart);
    if (exploring) camera.clearViewOffset();
    else if (w > 800) camera.setViewOffset(w, h, w * vx, h * 0.03, w, h);
    else camera.setViewOffset(w, h, 0, h * 0.03, w, h);
    camera.updateProjectionMatrix();
  }
  resize();
  const resizeObserver =
    typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(() => {
          resize();
          if (reducedMotion) draw();
        })
      : null;
  if (resizeObserver) resizeObserver.observe(parent);
  else window.addEventListener("resize", resize);

  let visible = !document.hidden;
  document.addEventListener("visibilitychange", () => {
    visible = !document.hidden;
  });

  // --- Descubrimiento: el haz gira hacia la estrella, un rayo sale del planeta y la enciende ---
  const TAU = Math.PI * 2;
  const COMET_MS = 1100;
  const BURST_MS = 900;
  const RING_MS = 1500;
  const burstRings = [];
  const ringGeo = new THREE.RingGeometry(0.88, 1, 64);
  const TRAIL = 14;
  const cometLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(Array.from({ length: TRAIL }, () => new THREE.Vector3())),
    new THREE.LineBasicMaterial({ color: COLORS.lima, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  cometLine.visible = false;
  cometLine.frustumCulled = false;
  scene.add(cometLine);
  const cometHead = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: starTexture(COLORS.lima), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
  );
  cometHead.scale.set(1.3, 1.3, 1);
  cometHead.visible = false;
  scene.add(cometHead);
  let pending = null; // { star, resolve, t0, from }
  let speedMul = 1;

  function screenPos(slug) {
    const star = findStar(slug);
    if (!star) return null;
    const v = project(star.sprite.position);
    return v.z >= 1 ? null : { x: v.x, y: v.y };
  }

  function startBurst(star, nowMs) {
    star.burstStart = nowMs;
    star.flashUntil = Math.max(star.flashUntil, nowMs + 2500);
    const ring = new THREE.Mesh(
      ringGeo,
      new THREE.MeshBasicMaterial({
        color: KIND_COLOR[star.kind],
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(star.sprite.position.x, 0.2, star.sprite.position.z);
    ring.scale.setScalar(0.1);
    scene.add(ring);
    burstRings.push({ ring, t0: nowMs });
  }

  // platform: clave de la red de la señal descubierta (youtube, linkedin, hn, gnews...).
  function discover(slug, platform) {
    const star = findStar(slug);
    if (!star) return Promise.resolve(null);
    if (pending) pending.resolve(null);
    return new Promise((resolve) => {
      if (reducedMotion) return resolve(screenPos(slug));
      const planet = planets.find((p) => p.name === platform);
      const from = planet
        ? planet.mesh.position.clone()
        : new THREE.Vector3(Math.cos(star.azimuth) * R_PLANETS, 0, Math.sin(star.azimuth) * R_PLANETS);
      pending = { star, resolve, t0: performance.now(), from };
    });
  }

  let sweepAngle = 0;
  const clock = new THREE.Clock();

  // Devuelve true cuando el rayo ya llegó a la estrella.
  function updateComet(nowMs) {
    if (!pending) {
      cometLine.visible = cometHead.visible = false;
      return false;
    }
    const k = Math.min(1, (nowMs - pending.t0) / COMET_MS);
    const to = pending.star.sprite.position;
    const at = (u) => {
      const v = pending.from.clone().lerp(to, u);
      v.y += Math.sin(u * Math.PI) * 4; // arco
      return v;
    };
    const arr = cometLine.geometry.attributes.position;
    for (let i = 0; i < TRAIL; i++) {
      const v = at(Math.max(0, k - (i / TRAIL) * 0.3));
      arr.setXYZ(i, v.x, v.y, v.z);
    }
    arr.needsUpdate = true;
    cometHead.position.copy(at(k));
    cometLine.visible = cometHead.visible = k < 1;
    return k >= 1;
  }

  function draw() {
    const t = clock.elapsedTime;
    const nowMs = t * 1000;
    bgPoints.forEach((p) => (p.material.uniforms.uTime.value = t));
    const normSweep = ((sweepAngle % TAU) + TAU) % TAU;

    if (pending && updateComet(performance.now())) {
      const ahead = (((pending.star.azimuth - normSweep) % TAU) + TAU) % TAU;
      if (ahead < 0.12 || ahead > TAU - 0.08 || performance.now() - pending.t0 > 3500) {
        startBurst(pending.star, nowMs);
        const done = pending;
        pending = null;
        updateComet(0);
        done.resolve(screenPos(done.star.topic.slug));
      }
    }
    for (let i = burstRings.length - 1; i >= 0; i--) {
      const b = burstRings[i];
      const k = (nowMs - b.t0) / RING_MS;
      if (k >= 1) {
        scene.remove(b.ring);
        b.ring.material.dispose();
        burstRings.splice(i, 1);
      } else {
        b.ring.scale.setScalar(0.5 + 8 * (1 - Math.pow(1 - k, 3)));
        b.ring.material.opacity = 0.9 * (1 - k);
      }
    }

    const nowP = performance.now();
    const arrived = reducedMotion ? 1 : clamp01((nowP - flyEnd) / 700);
    let active = stars.filter((s) => nowMs < s.flashUntil).length;
    stars.forEach((star) => {
      const diff = Math.abs(Math.atan2(Math.sin(normSweep - star.azimuth), Math.cos(normSweep - star.azimuth)));
      if (!reducedMotion && active < 2 && diff < 0.12 && nowMs - star.flashUntil > 500) {
        star.flashUntil = nowMs + 1500;
        active++;
      }
      const flashing = nowMs < star.flashUntil;
      star.flashing = flashing;

      // Titileo por crecimiento; la estrella que cae parpadea débil.
      const tw = 1 + 0.2 * Math.sin(t * (1.4 + star.growth * 0.8) + star.phase) * clamp01(star.growth / 2.5);
      let flashScale = flashing ? 1.3 : 1;
      if (star.burstStart != null) {
        const bk = (nowMs - star.burstStart) / BURST_MS;
        if (bk < 1) flashScale = Math.max(flashScale, 1 + 1.5 * Math.pow(1 - bk, 2));
      }
      star.sel = reducedMotion ? (star === selected ? 1 : 0) : star.sel + ((star === selected ? arrived : 0) - star.sel) * Math.min(1, frameDt * 6);
      const s = star.baseScale * tw * flashScale * (1 + 0.9 * star.sel + 0.08 * star.sel * Math.sin(t * 3));
      star.sprite.scale.set(s, s, 1);
      star.sprite.material.opacity = flashing ? 1 : star.kind === "fading" ? 0.4 + 0.15 * Math.sin(t * 0.9 + star.phase) : 0.92;

      if (star.aro) {
        if (star.kind === "early") {
          // Estrella naciente: aro de nacimiento que se expande y se desvanece.
          const u = (t * 0.45 + star.phase) % 1;
          const as = star.baseScale * (1.2 + 2 * u);
          star.aro.scale.set(as, as, 1);
          star.aro.material.opacity = 0.6 * (1 - u);
        } else {
          // Pico: halo ámbar amplio y estable.
          const as = star.baseScale * 1.9 * (1 + 0.04 * Math.sin(t * 1.6 + star.phase));
          star.aro.scale.set(as, as, 1);
          star.aro.material.opacity = 0.28;
        }
      }
    });

    const ss = selected && selected.sel > 0.01 ? selected : null;
    corona.visible = !!ss;
    fxRings.forEach((r) => (r.visible = !!ss));
    if (ss) {
      const col = KIND_COLOR[ss.kind];
      corona.position.copy(ss.sprite.position);
      corona.material.color.setHex(col);
      const cs = ss.baseScale * (5 + 0.7 * Math.sin(t * 3)) * ss.sel;
      corona.scale.set(cs, cs, 1);
      corona.material.opacity = 0.6 * ss.sel;
      fxRings.forEach((r, i) => {
        const u = (t * 0.55 + i / 3) % 1;
        const sc = ss.baseScale * (2 + 11 * u);
        r.position.copy(ss.sprite.position);
        r.material.color.setHex(col);
        r.scale.set(sc, sc, 1);
        r.material.opacity = 0.75 * (1 - u) * (1 - u) * ss.sel;
      });
    }
    planets.forEach((p) => {
      p.sel = reducedMotion ? (p === selectedPlanet ? 1 : 0) : p.sel + ((p === selectedPlanet ? arrived : 0) - p.sel) * Math.min(1, frameDt * 5);
      p.rot += frameDt * (0.1 + 0.6 * p.sel);
      p.mesh.rotation.y = reducedMotion ? t * 0.1 : p.rot;
      const on = p.sel > 0.01;
      p.atmo.visible = p.orbitRing.visible = on;
      if (on) {
        p.atmo.material.uniforms.uAmt.value = p.sel * (0.95 + 0.15 * Math.sin(t * 2));
        p.orbitRing.position.copy(p.mesh.position);
        p.orbitRing.rotation.z += frameDt * 0.4;
        p.orbitRing.material.opacity = 0.55 * p.sel;
      }
    });
    coreGlow.scale.setScalar(3.2 + 0.25 * Math.sin(t * 1.5));
    layoutLabels();
    layoutHero();

    raycaster.setFromCamera(pointerNdc, camera);
    const hits = raycaster.intersectObjects(stars.map((s) => s.sprite), false);
    const nh = hits.length ? stars.find((s) => s.sprite === hits[0].object) : null;
    if (nh !== hovered) {
      if (hovered) hovered.hoverLabel = false;
      hovered = nh;
      if (hovered) hovered.hoverLabel = true;
      canvas.style.cursor = hovered ? "pointer" : "default";
    }

    updateRays(t);
    renderer.render(scene, camera);
  }

  function animate() {
    requestAnimationFrame(animate);
    if (!visible) return;
    const dt = Math.min(0.1, clock.getDelta());
    const t = clock.elapsedTime;
    frameDt = dt;
    speedMul += ((pending ? 3.2 : 1) - speedMul) * Math.min(1, dt * 4);
    sweepAngle += (dt / 7) * TAU * speedMul;
    sweep.rotation.y = -sweepAngle;
    planets.forEach((p) => {
      p.angle += p.speed * dt;
      placePlanet(p);
    });

    // Parallax con el mouse (capas) y vaivén suave de cámara.
    bg.rotation.y += (mouse.x * 0.05 - bg.rotation.y) * 0.04;
    bg.rotation.x += (-mouse.y * 0.03 - bg.rotation.x) * 0.04;
    if (!reducedMotion) {
      // Galaxia viva: capas giran lento, nubes derivan.
      farStars.rotation.y += dt * 0.004;
      nearStars.rotation.y -= dt * 0.006;
      milky.rotation.z += dt * 0.008;
      nebula.children.forEach((sp) => {
        const u = sp.userData;
        sp.material.rotation += dt * u.rot;
        sp.position.x = u.x + Math.sin(t * 0.03 + u.ph) * 14;
        sp.position.y = u.y + Math.cos(t * 0.025 + u.ph) * 8;
        sp.material.opacity = 0.8 + 0.2 * Math.sin(t * 0.2 + u.ph);
      });
    }
    nearStars.position.x += (mouse.x * -4 - nearStars.position.x) * 0.04;
    const nowP = performance.now();
    const place = () => {
      if (controls) {
        controls.autoRotate = false;
        controls.target.copy(lookAt);
        controls.update();
      } else camera.lookAt(lookAt);
    };
    if (dolly) {
      const k = Math.min(1, (nowP - dolly.start) / dolly.duration);
      const e = easeExpo(k);
      const u = 1 - e;
      const to = dolly.toFn();
      camera.position.set(0, 0, 0).addScaledVector(dolly.from, u * u).addScaledVector(dolly.ctrl, 2 * u * e).addScaledVector(to, e * e);
      lookAt.lerpVectors(dolly.lookFrom, dolly.lookFn(), e);
      const rel = !!dolly.o.release;
      const peak = rel ? 62 : 70;
      const end = rel ? FOV_REST : 40;
      setFov(k < 0.5 ? THREE.MathUtils.lerp(FOV_REST, peak, Math.sin(k * Math.PI)) : THREE.MathUtils.lerp(peak, end, 0.5 - 0.5 * Math.cos((k - 0.5) * 2 * Math.PI)));
      if (k >= 1) {
        if (!rel) hold = { lookFn: dolly.lookFn, off: camera.position.clone().sub(lookAt), t0: nowP };
        dolly = null;
      }
      place();
    } else if (hold) {
      // Llegada: órbita lenta de ~9° y el FOV se relaja 40→43.
      const th = Math.min(1, (nowP - hold.t0) / 9000);
      lookAt.copy(hold.lookFn());
      camera.position.copy(lookAt).add(hold.off.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(9) * (1 - (1 - th) * (1 - th))));
      setFov(THREE.MathUtils.lerp(40, 43, clamp01((nowP - hold.t0) / 2000)));
      place();
    } else {
      setFov(THREE.MathUtils.lerp(camera.fov, FOV_REST, Math.min(1, dt * 3)));
      if (controls) {
        controls.autoRotate = idle;
        controls.update();
        if (controls.target.length() > MAX_TARGET) controls.target.setLength(MAX_TARGET);
        lookAt.copy(controls.target);
      } else if (held) camera.lookAt(lookAt);
      else {
        camera.position.copy(swayPos(t, new THREE.Vector3()));
        camera.lookAt(lookAt);
      }
    }

    if (!exploring && (parent.clientWidth || 0) > 800) {
      const tx = selected || selectedPlanet ? 0.15 : -0.1;
      if (Math.abs(tx - vx) > 0.0005) {
        vx += (tx - vx) * Math.min(1, dt * 3);
        resize();
      }
    }

    // Estelas proporcionales a la velocidad de la cámara durante el vuelo; flash lima al llegar.
    let target = 0;
    if (dolly && dt > 0) {
      const mean = dolly.len / (dolly.duration / 1000);
      target = clamp01(camera.position.distanceTo(lastPos) / dt / (mean * 5)) * clamp01(dolly.len / 12 + 0.3);
    }
    lastPos.copy(camera.position);
    warpAmt += (target - warpAmt) * Math.min(1, dt * 14);
    warp.visible = warpAmt > 0.01;
    warp.material.uniforms.uAmt.value = warpAmt;
    const d = nowP - (flyEnd - 120);
    const f = flyEnd && d > 0 ? 0.6 * (d < 120 ? d / 120 : Math.exp(-(d - 120) / 350)) : 0;
    flash.style.opacity = f > 0.004 ? f.toFixed(3) : "0";
    draw();
  }

  if (reducedMotion) draw(); // escena estática: un solo render
  else animate();

  return { focus, discover, screenPos, setExplore, release, isExplore: () => exploring };
}
