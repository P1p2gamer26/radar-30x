// RadarIA — escena 3D "el universo de RadarIA". ES module, Three.js vía importmap.
// Planetas = redes (de donde llegan las señales); estrellas = temas; cerca del centro = producir ya.
// Contrato: export function mountScene(canvas, topics, onOpen, sources)
//   -> { focus(slug), discover(slug, platform), screenPos(slug) }
// Sin WebGL: lanza Error('no-webgl') y el index.js hace fallback 2D.

import * as THREE from "three";

const COLORS = { lima: 0xebff6f, despegando: 0xd4f06a, hueso: 0xf7f5f2, ambar: 0xffcc6e, apagado: 0x6b6b6b };
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
  wiki: ["Wikipedia", 0xb9b9b2],
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
  const [r, g, b] = rgb(hex);
  return radialTexture(
    [
      [0, `rgba(${r},${g},${b},${alpha})`],
      [0.5, `rgba(${r},${g},${b},${alpha * 0.35})`],
      [1, `rgba(${r},${g},${b},0)`],
    ],
    256
  );
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
        vO = aOpacity * (0.55 + 0.45 * sin(uTime * 0.6 + aOpacity * 40.0));
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

function buildNebula() {
  const g = new THREE.Group();
  [
    [COLORS.lima, 0.1, -60, 36, -190, 230],
    [COLORS.ambar, 0.09, 90, -20, -200, 260],
    [COLORS.lima, 0.06, 20, -50, -170, 180],
    [COLORS.ambar, 0.05, -130, -30, -210, 200],
  ].forEach(([c, a, x, y, z, s]) => {
    const sp = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: nebulaTexture(c, a), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false })
    );
    sp.position.set(x, y, z);
    sp.scale.set(s, s * 0.7, 1);
    g.add(sp);
  });
  return g;
}

// Planeta: esfera iluminada desde el núcleo (shader simple) + borde atmosférico.
function planetMaterial(hex) {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(hex).lerp(new THREE.Color(0x777777), 0.25) } },
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
        vec3 c = uColor * (0.14 + 0.9 * l) + vec3(0.92, 1.0, 0.43) * 0.1 * l + uColor * rim * 0.35;
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
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
      fragmentShader: `varying float vA; void main() { gl_FragColor = vec4(0.92, 1.0, 0.43, vA * vA * 0.4); }`,
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
    [ringRadius(0.8), COLORS.lima, 0.6, "Producir ya", "rgba(235,255,111,0.8)"],
    [ringRadius(0.5), COLORS.ambar, 0.45, "Vigilar", "rgba(255,204,110,0.75)"],
    [R_MAX, 0x8a8a8a, 0.22, null, null],
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

export function mountScene(canvas, topics, onOpen, sources) {
  if (!hasWebGL()) throw new Error("no-webgl");

  const reducedMotion = prefersReducedMotion();
  const parent = canvas.parentElement || canvas;
  if (getComputedStyle(parent).position === "static") parent.style.position = "relative";

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x030304, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, (canvas.clientWidth || 1) / (canvas.clientHeight || 1), 0.1, 900);
  const baseCamPos = new THREE.Vector3(0, 18, 34);
  camera.position.copy(baseCamPos);
  const lookAt = new THREE.Vector3(0, 0, 0);
  const camStart = new THREE.Vector3();
  camera.lookAt(lookAt);

  // --- Fondo: estrellas en capas (parallax), vía láctea y nebulosa (~7000 puntos) ---
  const bg = new THREE.Group();
  scene.add(bg);
  const farStars = buildPoints(2600, 1.3, () => onSphere(300, 480), 0xf7f5f2);
  const nearStars = buildPoints(1300, 2.0, () => onSphere(140, 260), 0xffffff);
  const milky = buildPoints(3000, 1.4, milkyPos, 0xf0e6d2);
  bg.add(farStars, nearStars, milky, buildNebula());
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
      color: "rgba(200,200,195,0.8)",
      whiteSpace: "nowrap",
      pointerEvents: "none",
      textShadow: "0 1px 6px rgba(0,0,0,0.9)",
    });
    labelLayer.appendChild(el);
    planets.push({
      name: s.name,
      mesh,
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
      if (!(star.hoverLabel || star.flashing || star.top3 || star.rec)) {
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
        prio: star.hoverLabel ? 3 : star.rec ? 2 : star.top3 ? 1 : 0,
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
      const hide = v.z >= 1 || (v.x < w * 0.5 && v.y > h * 0.55) || (w < 800 && v.y > h * 0.6) || v.x < 20 || v.x > w - 20 || v.y > h - 70 || v.y < 20;
      p.el.style.opacity = hide ? "0" : "1";
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
  canvas.addEventListener("click", () => {
    if (!hovered) return;
    const slug = hovered.topic.slug;
    canvas.dispatchEvent(new CustomEvent("topic:open", { detail: slug, bubbles: true }));
    if (typeof onOpen === "function") onOpen(slug);
    focus(slug);
  });

  // --- Acercamiento de cámara ---
  let dolly = null;
  function focus(slug) {
    const star = findStar(slug);
    if (!star) return;
    const dir = star.sprite.position.clone().normalize();
    dolly = {
      from: camera.position.clone(),
      to: star.sprite.position.clone().add(dir.multiplyScalar(6)).add(new THREE.Vector3(0, 3, 0)),
      lookFrom: lookAt.clone(),
      lookTo: star.sprite.position.clone(),
      start: performance.now(),
      duration: 1100,
    };
  }

  function resize() {
    const w = parent.clientWidth || window.innerWidth;
    const h = parent.clientHeight || window.innerHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    // En ancho empuja la escena a la derecha/arriba: el titular queda libre.
    camStart.set(0, 18, 34).multiplyScalar(w > 800 ? 1.3 : 2.1);
    baseCamPos.copy(camStart);
    if (w > 800) camera.setViewOffset(w, h, -w * 0.1, h * 0.03, w, h);
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
      const s = star.baseScale * tw * flashScale;
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

    planets.forEach((p) => {
      p.mesh.rotation.y = t * 0.1;
    });
    coreGlow.scale.setScalar(3.2 + 0.25 * Math.sin(t * 1.5));
    layoutLabels();

    raycaster.setFromCamera(pointerNdc, camera);
    const hits = raycaster.intersectObjects(stars.map((s) => s.sprite), false);
    const nh = hits.length ? stars.find((s) => s.sprite === hits[0].object) : null;
    if (nh !== hovered) {
      if (hovered) hovered.hoverLabel = false;
      hovered = nh;
      if (hovered) hovered.hoverLabel = true;
      canvas.style.cursor = hovered ? "pointer" : "default";
    }

    renderer.render(scene, camera);
  }

  function animate() {
    requestAnimationFrame(animate);
    if (!visible) return;
    const dt = Math.min(0.1, clock.getDelta());
    const t = clock.elapsedTime;
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
    nearStars.position.x += (mouse.x * -4 - nearStars.position.x) * 0.04;
    if (dolly) {
      const k = Math.min(1, (performance.now() - dolly.start) / dolly.duration);
      const e = 1 - Math.pow(1 - k, 3);
      camera.position.lerpVectors(dolly.from, dolly.to, e);
      lookAt.lerpVectors(dolly.lookFrom, dolly.lookTo, e);
      camera.lookAt(lookAt);
      if (k >= 1) dolly = null;
    } else {
      const sw = Math.sin(t * 0.05) * 0.22;
      camera.position.set(
        baseCamPos.x * Math.cos(sw) - baseCamPos.z * Math.sin(sw) + mouse.x * 1.5,
        baseCamPos.y + mouse.y * 0.8,
        baseCamPos.x * Math.sin(sw) + baseCamPos.z * Math.cos(sw)
      );
      camera.lookAt(lookAt);
    }
    draw();
  }

  if (reducedMotion) draw(); // escena estática: un solo render
  else animate();

  return { focus, discover, screenPos };
}
