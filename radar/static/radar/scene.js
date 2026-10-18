// RadarIA — escena 3D "el cielo de temas". ES module, Three.js vía importmap.
// Contrato: export function mountScene(canvas, topics, onOpen) -> { focus(slug), discover(slug), screenPos(slug) }
// Sin WebGL: lanza Error('no-webgl') y el index.js hace fallback 2D.

import * as THREE from "three";

// Color por ETAPA (casi todo es Descartar); la decision se lee por la distancia al centro.
const STAGE_COLOR = {
  temprana: 0xebff6f,
  creciendo: 0xd4f06a,
  estable: 0xf7f5f2,
  saturada: 0xffcc6e,
  bajando: 0x6b6b6b,
};

// Distancia de una estrella segun p (coincide con los anillos de umbral).
const R_MIN = 4;
const R_MAX = 21;
const ringRadius = (p) => R_MIN + (R_MAX - R_MIN) * (1 - p);
// ponytail: intensidad alta porque el albedo es casi negro (luces fisicas de three r160).
const LIME_LIGHT = 16;

function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch (e) {
    return false;
  }
}

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Textura radial generada en canvas 2D para sprites de estrella (sin assets externos).
function makeStarTexture(colorHex) {
  const size = 128;
  const cv = document.createElement("canvas");
  cv.width = size;
  cv.height = size;
  const ctx = cv.getContext("2d");
  const r = Math.floor((colorHex >> 16) & 255);
  const g = Math.floor((colorHex >> 8) & 255);
  const b = Math.floor(colorHex & 255);
  const grad = ctx.createRadialGradient(
    size / 2,
    size / 2,
    0,
    size / 2,
    size / 2,
    size / 2
  );
  grad.addColorStop(0, `rgba(255,255,255,0.8)`);
  grad.addColorStop(0.18, `rgba(${r},${g},${b},0.95)`);
  grad.addColorStop(0.5, `rgba(${r},${g},${b},0.35)`);
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(cv);
  tex.needsUpdate = true;
  return tex;
}

// Anillo suave para el halo de "Recomendar".
function makeHaloTexture() {
  const cv = document.createElement("canvas");
  cv.width = 128;
  cv.height = 128;
  const ctx = cv.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 20, 64, 64, 64);
  g.addColorStop(0, "rgba(235,255,111,0)");
  g.addColorStop(0.72, "rgba(235,255,111,0.9)");
  g.addColorStop(0.8, "rgba(235,255,111,0.5)");
  g.addColorStop(1, "rgba(235,255,111,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(cv);
}

// Etiqueta de texto en canvas, para los anillos de umbral.
function makeTextSprite(text) {
  const cv = document.createElement("canvas");
  cv.width = 512;
  cv.height = 96;
  const ctx = cv.getContext("2d");
  ctx.font = "500 40px Geist, 'Helvetica Neue', Arial, sans-serif";
  ctx.fillStyle = "rgba(190,190,185,0.85)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const sp = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false })
  );
  sp.scale.set(6.4, 1.2, 1);
  return sp;
}

// Textura de banda de vía láctea: ruido suave en gradiente.
function makeMilkyBandTexture() {
  const w = 1024;
  const h = 128;
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(247,245,242,0)");
  grad.addColorStop(0.5, "rgba(247,245,242,0.12)");
  grad.addColorStop(1, "rgba(247,245,242,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 2200; i++) {
    const x = Math.random() * w;
    const yc = h / 2 + (Math.random() - 0.5) * h * 0.85;
    const r = Math.random() * 1.1 + 0.2;
    const a = Math.random() * 0.5 + 0.05;
    ctx.beginPath();
    ctx.fillStyle = `rgba(247,245,242,${a})`;
    ctx.arc(x, yc, r, 0, Math.PI * 2);
    ctx.fill();
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.needsUpdate = true;
  return tex;
}

function duneHeight(x, z, t) {
  // Combinación de senos para dunas suaves, sin librerías de ruido.
  return (
    Math.sin(x * 0.045 + t * 0.02) * 3.2 +
    Math.sin(z * 0.03 - t * 0.015) * 2.4 +
    Math.sin((x + z) * 0.018) * 1.6 +
    Math.sin(x * 0.11 + z * 0.07) * 0.6
  );
}

function buildDunes() {
  const size = 260;
  const seg = 110;
  const geo = new THREE.PlaneGeometry(size, size, seg, seg);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const z = pos.getZ(i);
    // Centro plano (donde gira el radar) y crestas hacia afuera.
    const k = THREE.MathUtils.smoothstep(Math.hypot(x, z), 20, 60);
    pos.setY(i, (duneHeight(x, z, 0) + 3) * k - 0.2);
  }
  geo.computeVertexNormals();

  const mat = new THREE.MeshStandardMaterial({
    color: 0x0d0d0b,
    roughness: 1,
    metalness: 0,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.receiveShadow = false;
  return mesh;
}

function buildStarfield() {
  const count = 3200;
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const opacities = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const r = 180 + Math.random() * 260;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(THREE.MathUtils.randFloat(-0.1, 1));
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = Math.abs(r * Math.cos(phi)) * 0.7 + 20;
    positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    opacities[i] = Math.random();
  }
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("aOpacity", new THREE.BufferAttribute(opacities, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(0xf7f5f2) } },
    vertexShader: `
      attribute float aOpacity;
      varying float vOpacity;
      uniform float uTime;
      void main() {
        vOpacity = aOpacity * (0.55 + 0.45 * sin(uTime * 0.6 + aOpacity * 40.0));
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = 1.6 * (160.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying float vOpacity;
      uniform vec3 uColor;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        gl_FragColor = vec4(uColor, vOpacity * (1.0 - d * 2.0));
      }
    `,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

function buildMilkyWay() {
  const count = 9000;
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const opacities = new Float32Array(count);
  const warm = new Float32Array(count);
  const bandAngle = 0.55; // inclinación de la banda
  for (let i = 0; i < count; i++) {
    // Más densidad en el centro de la banda, tinte cálido en el núcleo.
    const t = Math.sign(Math.random() - 0.5) * Math.pow(Math.random(), 1.6);
    const spread = Math.random();
    const along = t * 240;
    const core = 1 - Math.abs(t);
    const across = (Math.random() - 0.5) * (14 + 40 * core) * Math.pow(spread, 1.6);
    const x = along * Math.cos(bandAngle) - across * Math.sin(bandAngle);
    const y = along * Math.sin(bandAngle) * 0.75 + across * Math.sin(bandAngle) + 38 + Math.abs(across) * 0.3;
    const z = along * Math.sin(bandAngle) + across * Math.cos(bandAngle) - 120;
    positions[i * 3] = x;
    positions[i * 3 + 1] = Math.max(10, y);
    positions[i * 3 + 2] = z;
    opacities[i] = 0.2 + Math.random() * 0.8;
    warm[i] = core * 0.5;
  }
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("aOpacity", new THREE.BufferAttribute(opacities, 1));
  geo.setAttribute("aWarm", new THREE.BufferAttribute(warm, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(0xf7f5f2) } },
    vertexShader: `
      attribute float aOpacity;
      attribute float aWarm;
      varying float vOpacity;
      varying float vWarm;
      uniform float uTime;
      void main() {
        vWarm = aWarm;
        vOpacity = aOpacity * (0.5 + 0.5 * sin(uTime * 0.35 + aOpacity * 60.0));
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = 1.5 * (160.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying float vOpacity;
      varying float vWarm;
      uniform vec3 uColor;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        vec3 c = mix(uColor, vec3(1.0, 0.86, 0.66), vWarm);
        gl_FragColor = vec4(c, vOpacity * 0.75 * (1.0 - d * 2.0));
      }
    `,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

// Resplandor del horizonte: cilindro abierto con gradiente vertical lima.
function buildHorizonGlow() {
  const cv = document.createElement("canvas");
  cv.width = 4;
  cv.height = 128;
  const ctx = cv.getContext("2d");
  const g = ctx.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, "rgba(235,255,111,0)");
  g.addColorStop(0.72, "rgba(235,255,111,0.10)");
  g.addColorStop(0.9, "rgba(235,255,111,0.22)");
  g.addColorStop(1, "rgba(235,255,111,0.05)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 4, 128);
  const mat = new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(cv),
    transparent: true,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    blending: THREE.AdditiveBlending,
  });
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(300, 300, 70, 48, 1, true), mat);
  mesh.position.y = 28;
  return mesh;
}

function buildRadarRings() {
  const group = new THREE.Group();
  // Umbrales p=0.80 (Recomendar), p=0.50 (Aprender) y borde p=0.
  const defs = [
    [ringRadius(0.8), 0xebff6f, 0.55, "Recomendar"],
    [ringRadius(0.5), 0xffcc6e, 0.45, "Aprender"],
    [R_MAX, 0x8a8a8a, 0.3, null],
  ];
  defs.forEach(([r, color, opacity, label]) => {
    const geo = new THREE.RingGeometry(r - 0.07, r + 0.07, 128);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(geo, mat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.05;
    group.add(ring);
    if (label) {
      const sp = makeTextSprite(label);
      sp.position.set(Math.cos(1.6) * r, 0.7, Math.sin(1.6) * r);
      group.add(sp);
    }
  });
  return group;
}

// Barrido: cuña lima con degradado hacia atrás + línea brillante en el borde de ataque.
// Con rotation.y = -s, el borde de ataque apunta al azimut s (x=cos, z=sin).
function buildSweep(radius) {
  const group = new THREE.Group();
  const span = 0.5;
  const wedge = new THREE.Mesh(
    new THREE.CircleGeometry(radius, 48, 0, span),
    new THREE.ShaderMaterial({
      uniforms: { uSpan: { value: span } },
      vertexShader: `
        varying float vA;
        uniform float uSpan;
        void main() {
          vA = 1.0 - clamp(atan(position.y, position.x) / uSpan, 0.0, 1.0);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying float vA;
        void main() { gl_FragColor = vec4(0.92, 1.0, 0.43, vA * vA * 0.55); }
      `,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    })
  );
  wedge.rotation.x = -Math.PI / 2;
  wedge.position.y = 0.12;
  group.add(wedge);
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0.14, 0), new THREE.Vector3(radius, 0.14, 0)]),
    new THREE.LineBasicMaterial({ color: 0xebff6f, transparent: true, opacity: 0.95 })
  );
  group.add(line);
  return group;
}

export function mountScene(canvas, topics, onOpen) {
  if (!hasWebGL()) {
    throw new Error("no-webgl");
  }

  const reducedMotion = prefersReducedMotion();
  const parent = canvas.parentElement || canvas;
  if (getComputedStyle(parent).position === "static") {
    parent.style.position = "relative";
  }

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x050506, 1);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x050506, 0.0115);

  const camera = new THREE.PerspectiveCamera(
    52,
    (canvas.clientWidth || canvas.width || 1) / (canvas.clientHeight || canvas.height || 1),
    0.1,
    900
  );
  const baseCamPos = new THREE.Vector3(0, 15, 31);
  camera.position.copy(baseCamPos);
  camera.lookAt(0, 2, 0);

  // Luz rasante lima desde un lado y bajo: dibuja las crestas.
  const rim = new THREE.DirectionalLight(0xebff6f, LIME_LIGHT);
  rim.position.set(-60, 1.5, -25);
  scene.add(rim);
  scene.add(new THREE.AmbientLight(0x101010, 0.4));

  const dunes = buildDunes();
  scene.add(dunes);
  scene.add(buildHorizonGlow());

  const starfield = buildStarfield();
  scene.add(starfield);

  const milkyWay = buildMilkyWay();
  scene.add(milkyWay);

  const rings = buildRadarRings();
  scene.add(rings);

  const sweep = buildSweep(R_MAX);
  scene.add(sweep);

  // --- Estrellas de los temas ---
  const starGroup = new THREE.Group();
  scene.add(starGroup);

  const labelLayer = document.createElement("div");
  labelLayer.className = "star-label-layer";
  labelLayer.style.position = "absolute";
  labelLayer.style.inset = "0";
  labelLayer.style.pointerEvents = "none";
  labelLayer.style.overflow = "hidden";
  parent.appendChild(labelLayer);

  const stars = [];
  const texCache = {};
  const haloTex = makeHaloTexture();
  const top3 = new Set(
    [...topics].sort((a, b) => (b.p || 0) - (a.p || 0)).slice(0, 3).map((t) => t.slug)
  );
  const n = Math.max(1, topics.length);
  // Blips sobre el disco: orden por categoria y slug, azimut repartido en un arco que deja libre
  // el cuadrante cercano-izquierdo (titular). ponytail: reparto uniforme, sin relajacion de colisiones.
  const catRank = { Recomendar: 0, Aprender: 1 };
  const order = [...topics].sort(
    (a, b) =>
      (catRank[a.decision] ?? 2) - (catRank[b.decision] ?? 2) || String(a.slug).localeCompare(String(b.slug))
  );
  const rRec = ringRadius(0.8);
  const rApr = ringRadius(0.5);
  topics.forEach((topic, i) => {
    const color = STAGE_COLOR[topic.stage] ?? STAGE_COLOR.estable;
    const tex = (texCache[color] ??= makeStarTexture(color));
    const mat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const sprite = new THREE.Sprite(mat);

    const k = order.indexOf(topic);
    const azimuth = -Math.PI * 0.8 + ((k + 0.5) / n) * Math.PI * 1.2;
    const momentum = clamp01(topic.momentum);
    const p = clamp01(topic.p);
    const volume = Math.max(0, topic.volume || 0);
    const growth = Math.max(0, topic.growth || 1);

    // Mismo mapeo que los anillos, ajustado para que la decision caiga en su zona.
    let distance = ringRadius(p);
    if (topic.decision === "Recomendar") distance = Math.min(distance, rRec - 1.6);
    else if (topic.decision === "Aprender") distance = THREE.MathUtils.clamp(distance, rRec + 0.8, rApr - 0.8);
    else distance = THREE.MathUtils.clamp(distance, rApr + 0.8, R_MAX - 1.2);
    const height = THREE.MathUtils.lerp(0.25, 1.1, momentum); // bajo: en perspectiva, más alto parece más lejos del centro
    const baseScale = THREE.MathUtils.lerp(0.9, 2.2, Math.min(1, volume / 60));

    const x = Math.cos(azimuth) * distance;
    const z = Math.sin(azimuth) * distance;
    sprite.position.set(x, height, z);
    sprite.scale.set(baseScale, baseScale, 1);

    const pin = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0.1, z), new THREE.Vector3(x, height, z)]),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.35 })
    );
    starGroup.add(pin);

    const label = document.createElement("div");
    label.className = "star-label";
    label.textContent = topic.name || topic.slug || "";
    label.style.position = "absolute";
    label.style.transform = "translateX(-50%)";
    label.style.fontFamily = "'EB Garamond', Georgia, serif";
    label.style.color = "var(--hueso)";
    label.style.textShadow = "0 1px 6px rgba(0,0,0,0.85), 0 0 14px rgba(0,0,0,0.6)";
    label.style.fontSize = top3.has(topic.slug) ? "13px" : "16px";
    label.style.letterSpacing = "0.01em";
    label.style.whiteSpace = "nowrap";
    label.style.opacity = "0";
    label.style.transition = "opacity 0.35s ease";
    label.style.pointerEvents = "none";
    labelLayer.appendChild(label);

    starGroup.add(sprite);

    let halo = null;
    if (topic.decision === "Recomendar") {
      halo = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: haloTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
      );
      halo.position.copy(sprite.position);
      starGroup.add(halo);
    }

    stars.push({
      halo,
      top3: top3.has(topic.slug),
      topic,
      sprite,
      label,
      azimuth: ((azimuth % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2),
      baseScale,
      growth,
      flashUntil: 0,
      flashing: false,
      hoverLabel: false,
    });
  });

  function clamp01(v) {
    return Math.max(0, Math.min(1, v == null ? 0 : v));
  }

  // Etiquetas: hover, destellos del barrido (máx 2) y top 3 por p. Se recortan al
  // viewport y se oculta la de menor p si dos se solapan.
  function layoutLabels() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const edge = 12;
    const cand = [];
    stars.forEach((star) => {
      const want = star.hoverLabel || star.flashing || star.top3;
      if (!want) {
        star.label.style.opacity = "0";
        return;
      }
      const v = star.sprite.position.clone().project(camera);
      const sx = (v.x * 0.5 + 0.5) * w;
      const sy = (-v.y * 0.5 + 0.5) * h - 14;
      const lw = star.label.offsetWidth || 80;
      const lh = star.label.offsetHeight || 20;
      const ok = v.z < 1 && sx > 0 && sx < w && sy > edge && sy < h - edge;
      if (!ok) {
        star.label.style.opacity = "0";
        return;
      }
      const x = Math.max(edge + lw / 2, Math.min(w - edge - lw / 2, sx));
      const y = Math.max(edge, Math.min(h - edge - lh, sy - lh));
      cand.push({ star, x, y, lw, prio: star.hoverLabel ? 2 : star.top3 ? 1 : 0 });
    });
    cand.sort((a, b) => b.prio - a.prio || (b.star.topic.p || 0) - (a.star.topic.p || 0));
    const placed = [];
    cand.forEach((c) => {
      const clash = placed.some(
        (o) => Math.abs(o.y - c.y) < 24 && Math.abs(o.x - c.x) < (o.lw + c.lw) / 2
      );
      if (clash) {
        c.star.label.style.opacity = "0";
        return;
      }
      placed.push(c);
      c.star.label.style.left = `${c.x}px`;
      c.star.label.style.top = `${c.y}px`;
      c.star.label.style.opacity = "1";
    });
  }

  // --- Interacción: hover y clic ---
  const raycaster = new THREE.Raycaster();
  raycaster.params.Sprite = { threshold: 0.6 };
  const pointerNdc = new THREE.Vector2(-10, -10);
  let hovered = null;
  let mouseNorm = { x: 0, y: 0 };

  function onPointerMove(ev) {
    const rect = canvas.getBoundingClientRect();
    pointerNdc.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointerNdc.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    mouseNorm.x = pointerNdc.x;
    mouseNorm.y = pointerNdc.y;
  }
  function onPointerLeave() {
    pointerNdc.set(-10, -10);
    mouseNorm = { x: 0, y: 0 };
  }
  function onClick() {
    if (hovered) {
      const slug = hovered.topic.slug;
      try {
        canvas.dispatchEvent(
          new CustomEvent("topic:open", { detail: slug, bubbles: true })
        );
      } catch (e) {
        /* noop */
      }
      if (typeof onOpen === "function") onOpen(slug);
      focus(slug);
    }
  }

  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerleave", onPointerLeave);
  canvas.addEventListener("click", onClick);

  // --- Dolly de cámara ---
  let dolly = null; // { target: Vector3, lookAt: Vector3, start, duration }
  function focus(slug) {
    const star = stars.find((s) => s.topic.slug === slug);
    if (!star) return { focus };
    const dir = star.sprite.position.clone().normalize();
    const target = star.sprite.position
      .clone()
      .add(dir.multiplyScalar(6))
      .add(new THREE.Vector3(0, 2.5, 0));
    dolly = {
      from: camera.position.clone(),
      to: target,
      lookFrom: controlsLookAt.clone(),
      lookTo: star.sprite.position.clone(),
      start: performance.now(),
      duration: 1100,
    };
    return { focus };
  }

  const controlsLookAt = new THREE.Vector3(0, 3, 0);

  // --- Resize ---
  function resize() {
    const w = parent.clientWidth || window.innerWidth;
    const h = parent.clientHeight || window.innerHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    // En pantallas anchas empuja la escena a la derecha/arriba: el titular queda libre.
    if (w > 800) camera.setViewOffset(w, h, -w * 0.2, h * 0.08, w, h);
    else camera.setViewOffset(w, h, -w * 0.04, h * 0.14, w, h);
    camera.updateProjectionMatrix();
  }
  resize();
  const resizeObserver =
    typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
  if (resizeObserver) resizeObserver.observe(parent);
  else window.addEventListener("resize", resize);

  let visible = !document.hidden;
  function onVisibility() {
    visible = !document.hidden;
  }
  document.addEventListener("visibilitychange", onVisibility);

  const clock = new THREE.Clock();
  let sweepAngle = 0;
  const SWEEP_PERIOD = 6; // segundos por vuelta
  let rafId = null;

  // --- Descubrimiento: el barrido acelera hasta el blip, que destella con una onda en el suelo ---
  const TAU = Math.PI * 2;
  const BURST_MS = 900;
  const RING_MS = 1500;
  let pending = null; // { star, resolve, t0 }
  let speedMul = 1;
  const burstRings = [];
  const ringGeo = new THREE.RingGeometry(0.88, 1, 64);

  function screenPos(slug) {
    const star = stars.find((s) => s.topic.slug === slug);
    if (!star) return null;
    const v = star.sprite.position.clone().project(camera);
    if (v.z >= 1) return null;
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    return { x: (v.x * 0.5 + 0.5) * w, y: (-v.y * 0.5 + 0.5) * h };
  }

  function startBurst(star, nowMs) {
    star.burstStart = nowMs;
    star.flashUntil = Math.max(star.flashUntil, nowMs + 2500);
    const color = STAGE_COLOR[star.topic.stage] ?? STAGE_COLOR.estable;
    const ring = new THREE.Mesh(
      ringGeo,
      new THREE.MeshBasicMaterial({
        color,
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

  // Resuelve con la posicion en pantalla del blip cuando el barrido lo alcanza.
  function discover(slug) {
    const star = stars.find((s) => s.topic.slug === slug);
    if (!star) return Promise.resolve(null);
    if (pending) pending.resolve(null);
    return new Promise((resolve) => {
      if (reducedMotion) {
        resolve(screenPos(slug));
        return;
      }
      pending = { star, resolve, t0: performance.now() };
    });
  }

  function animate() {
    rafId = requestAnimationFrame(animate);
    if (!visible) return;
    const dt = Math.min(0.1, clock.getDelta());
    const t = clock.elapsedTime;

    starfield.material.uniforms.uTime.value = t;
    milkyWay.material.uniforms.uTime.value = t;

    if (!reducedMotion) {
      speedMul += ((pending ? 3.5 : 1) - speedMul) * Math.min(1, dt * 4);
      sweepAngle += (dt / SWEEP_PERIOD) * Math.PI * 2 * speedMul;
      sweep.rotation.y = -sweepAngle;

      // Órbita lentísima de la cámara + parallax de mouse.
      const orbit = t * 0.015;
      const parallaxX = mouseNorm.x * 1.4;
      const parallaxY = mouseNorm.y * 0.7;
      if (!dolly) {
        camera.position.x = baseCamPos.x * Math.cos(orbit) - baseCamPos.z * Math.sin(orbit) + parallaxX;
        camera.position.z = baseCamPos.x * Math.sin(orbit) + baseCamPos.z * Math.cos(orbit);
        camera.position.y = baseCamPos.y + parallaxY;
        camera.lookAt(controlsLookAt);
      }
    }

    // Detectar paso del barrido por el azimut de cada estrella + pulso de growth.
    const normalizedSweep = ((sweepAngle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
    if (pending) {
      const ahead = (((pending.star.azimuth - normalizedSweep) % TAU) + TAU) % TAU;
      if (ahead < 0.1 || ahead > TAU - 0.06 || performance.now() - pending.t0 > 5000) {
        startBurst(pending.star, t * 1000);
        const done = pending;
        pending = null;
        done.resolve(screenPos(done.star.topic.slug));
      }
    }
    for (let i = burstRings.length - 1; i >= 0; i--) {
      const b = burstRings[i];
      const k = (t * 1000 - b.t0) / RING_MS;
      if (k >= 1) {
        scene.remove(b.ring);
        b.ring.material.dispose();
        burstRings.splice(i, 1);
      } else {
        b.ring.scale.setScalar(0.5 + 7 * (1 - Math.pow(1 - k, 3)));
        b.ring.material.opacity = 0.9 * (1 - k);
      }
    }
    let active = stars.filter((s) => t * 1000 < s.flashUntil).length;
    stars.forEach((star) => {
      const diff = Math.abs(
        Math.atan2(Math.sin(normalizedSweep - star.azimuth), Math.cos(normalizedSweep - star.azimuth))
      );
      if (!reducedMotion && active < 2 && diff < 0.12 && t * 1000 - star.flashUntil > 500) {
        star.flashUntil = t * 1000 + 1500;
        active++;
      }
      const flashing = t * 1000 < star.flashUntil;
      star.flashing = flashing;
      if (star.halo) {
        const hs = star.baseScale * 2.1 * (1 + 0.08 * Math.sin(t * 2.4));
        star.halo.scale.set(hs, hs, 1);
        star.halo.material.opacity = 0.4 + 0.15 * Math.sin(t * 2.4);
      }

      const pulse = 1 + 0.18 * Math.sin(t * (1.5 + star.growth * 0.6)) * clamp01(star.growth / 3);
      let flashScale = flashing ? 1.35 : 1;
      if (star.burstStart != null) {
        const bk = (t * 1000 - star.burstStart) / BURST_MS;
        if (bk < 1) flashScale = Math.max(flashScale, 1 + 1.2 * Math.pow(1 - bk, 2));
      }
      const scale = star.baseScale * pulse * flashScale;
      star.sprite.scale.set(scale, scale, 1);
      star.sprite.material.opacity = flashing ? 1 : 0.9;
    });
    layoutLabels();

    // Raycaster hover.
    raycaster.setFromCamera(pointerNdc, camera);
    const hits = raycaster.intersectObjects(
      stars.map((s) => s.sprite),
      false
    );
    const newHovered = hits.length ? stars.find((s) => s.sprite === hits[0].object) : null;
    if (newHovered !== hovered) {
      if (hovered) hovered.hoverLabel = false;
      hovered = newHovered;
      if (hovered) hovered.hoverLabel = true;
      canvas.style.cursor = hovered ? "pointer" : "default";
    }

    // Dolly de cámara animado.
    if (dolly) {
      const elapsed = performance.now() - dolly.start;
      const k = Math.min(1, elapsed / dolly.duration);
      const eased = 1 - Math.pow(1 - k, 3);
      camera.position.lerpVectors(dolly.from, dolly.to, eased);
      controlsLookAt.lerpVectors(dolly.lookFrom, dolly.lookTo, eased);
      camera.lookAt(controlsLookAt);
      if (k >= 1) dolly = null;
    }

    renderer.render(scene, camera);
  }

  if (reducedMotion) {
    // Escena estática: un solo render, sin barrido ni órbita.
    layoutLabels();
    renderer.render(scene, camera);
  } else {
    animate();
  }

  return { focus, discover, screenPos };
}
