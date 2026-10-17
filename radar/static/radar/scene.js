// Radar 30X — escena 3D "el cielo de temas". ES module, Three.js vía importmap.
// Contrato: export function mountScene(canvas, topics, onOpen) -> { focus(slug) }
// Sin WebGL: lanza Error('no-webgl') y el index.js hace fallback 2D.

import * as THREE from "three";

const DECISION_COLOR = {
  Recomendar: 0xebff6f,
  Aprender: 0xffcc6e,
  Descartar: 0x8a8a8a,
};

const DECISION_RING_RADIUS = {
  Recomendar: 6,
  Aprender: 11,
  Descartar: 17,
};

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
  grad.addColorStop(0, `rgba(255,255,255,0.95)`);
  grad.addColorStop(0.18, `rgba(${r},${g},${b},0.95)`);
  grad.addColorStop(0.5, `rgba(${r},${g},${b},0.35)`);
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(cv);
  tex.needsUpdate = true;
  return tex;
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
    pos.setY(i, duneHeight(x, z, 0));
  }
  geo.computeVertexNormals();

  const mat = new THREE.MeshStandardMaterial({
    color: 0x0b0b0c,
    roughness: 0.95,
    metalness: 0.05,
    flatShading: false,
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
  const count = 6000;
  const geo = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3);
  const opacities = new Float32Array(count);
  const bandAngle = 0.55; // inclinación de la banda
  for (let i = 0; i < count; i++) {
    const t = (Math.random() - 0.5) * 2;
    const spread = Math.random();
    const along = t * 240;
    const across = (Math.random() - 0.5) * 50 * Math.pow(spread, 1.6);
    const x = along * Math.cos(bandAngle) - across * Math.sin(bandAngle);
    const y = along * Math.sin(bandAngle) * 0.25 + across * Math.sin(bandAngle) + 60 + Math.abs(across) * 0.3;
    const z = along * Math.sin(bandAngle) + across * Math.cos(bandAngle) - 120;
    positions[i * 3] = x;
    positions[i * 3 + 1] = Math.max(10, y);
    positions[i * 3 + 2] = z;
    opacities[i] = 0.2 + Math.random() * 0.8;
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
        vOpacity = aOpacity * (0.5 + 0.5 * sin(uTime * 0.35 + aOpacity * 60.0));
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = 1.3 * (160.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying float vOpacity;
      uniform vec3 uColor;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) discard;
        gl_FragColor = vec4(uColor, vOpacity * 0.6 * (1.0 - d * 2.0));
      }
    `,
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

function buildRadarRings() {
  const group = new THREE.Group();
  const radii = [
    DECISION_RING_RADIUS.Recomendar,
    DECISION_RING_RADIUS.Aprender,
    DECISION_RING_RADIUS.Descartar,
  ];
  const colors = [0xebff6f, 0xffcc6e, 0x525252];
  radii.forEach((r, i) => {
    const geo = new THREE.RingGeometry(r - 0.06, r + 0.06, 96);
    const mat = new THREE.MeshBasicMaterial({
      color: colors[i],
      transparent: true,
      opacity: 0.28,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.05;
    group.add(ring);
  });
  return group;
}

function buildSweepCone(radius) {
  const geo = new THREE.ConeGeometry(radius, 0.001, 32, 1, true, 0, Math.PI / 7);
  geo.rotateX(Math.PI / 2);
  geo.translate(0, 0.08, 0);
  const mat = new THREE.MeshBasicMaterial({
    color: 0xebff6f,
    transparent: true,
    opacity: 0.16,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(geo, mat);
  return mesh;
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
  const baseCamPos = new THREE.Vector3(0, 9, 26);
  camera.position.copy(baseCamPos);
  camera.lookAt(0, 3, 0);

  // Luz rasante lima tenue sobre las crestas de las dunas.
  const rim = new THREE.DirectionalLight(0xebff6f, 0.35);
  rim.position.set(-40, 6, -10);
  scene.add(rim);
  const ambient = new THREE.AmbientLight(0x3a3a3a, 0.5);
  scene.add(ambient);
  const fill = new THREE.DirectionalLight(0x8899aa, 0.12);
  fill.position.set(20, 15, 20);
  scene.add(fill);

  const dunes = buildDunes();
  scene.add(dunes);

  const starfield = buildStarfield();
  scene.add(starfield);

  const milkyWay = buildMilkyWay();
  scene.add(milkyWay);

  const rings = buildRadarRings();
  scene.add(rings);

  const maxRingRadius = DECISION_RING_RADIUS.Descartar;
  const sweep = buildSweepCone(maxRingRadius);
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
  const n = Math.max(1, topics.length);
  topics.forEach((topic, i) => {
    const color = DECISION_COLOR[topic.decision] ?? DECISION_COLOR.Descartar;
    const tex = makeStarTexture(color);
    const mat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const sprite = new THREE.Sprite(mat);

    const azimuth = (i / n) * Math.PI * 2;
    const momentum = clamp01(topic.momentum);
    const p = clamp01(topic.p);
    const volume = Math.max(0, topic.volume || 0);
    const growth = Math.max(0, topic.growth || 1);

    const distance = THREE.MathUtils.lerp(4, maxRingRadius + 4, 1 - p);
    const height = THREE.MathUtils.lerp(2, 14, momentum);
    const baseScale = THREE.MathUtils.lerp(1.1, 3.4, Math.min(1, volume / 60));

    const x = Math.cos(azimuth) * distance;
    const z = Math.sin(azimuth) * distance;
    sprite.position.set(x, height, z);
    sprite.scale.set(baseScale, baseScale, 1);

    const label = document.createElement("div");
    label.className = "star-label";
    label.textContent = topic.name || topic.slug || "";
    label.style.position = "absolute";
    label.style.transform = "translate(-50%, -100%)";
    label.style.fontFamily = "'EB Garamond', Georgia, serif";
    label.style.color = "var(--hueso)";
    label.style.textShadow = "0 1px 6px rgba(0,0,0,0.85), 0 0 14px rgba(0,0,0,0.6)";
    label.style.fontSize = "16px";
    label.style.letterSpacing = "0.01em";
    label.style.whiteSpace = "nowrap";
    label.style.opacity = "0";
    label.style.transition = "opacity 0.35s ease";
    label.style.pointerEvents = "none";
    labelLayer.appendChild(label);

    starGroup.add(sprite);

    stars.push({
      topic,
      sprite,
      label,
      azimuth: ((azimuth % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2),
      baseScale,
      growth,
      flashUntil: 0,
      hoverLabel: false,
    });
  });

  function clamp01(v) {
    return Math.max(0, Math.min(1, v == null ? 0 : v));
  }

  function setLabelPosition(star, visible) {
    const v = star.sprite.position.clone().project(camera);
    const w = canvas.clientWidth || renderer.domElement.clientWidth || 1;
    const h = canvas.clientHeight || renderer.domElement.clientHeight || 1;
    const sx = (v.x * 0.5 + 0.5) * w;
    const sy = (-v.y * 0.5 + 0.5) * h;
    const onscreen = v.z < 1 && sx >= -40 && sx <= w + 40 && sy >= -40 && sy <= h + 40;
    star.label.style.left = `${sx}px`;
    star.label.style.top = `${sy - 10}px`;
    star.label.style.opacity = visible && onscreen ? "1" : "0";
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
  const SWEEP_PERIOD = 8; // segundos por vuelta
  let rafId = null;

  function animate() {
    rafId = requestAnimationFrame(animate);
    if (!visible) return;
    const dt = clock.getDelta();
    const t = clock.elapsedTime;

    starfield.material.uniforms.uTime.value = t;
    milkyWay.material.uniforms.uTime.value = t;

    if (!reducedMotion) {
      sweepAngle += (dt / SWEEP_PERIOD) * Math.PI * 2;
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
    stars.forEach((star) => {
      const diff = Math.abs(
        Math.atan2(Math.sin(normalizedSweep - star.azimuth), Math.cos(normalizedSweep - star.azimuth))
      );
      if (!reducedMotion && diff < 0.12 && t * 1000 - star.flashUntil > 500) {
        star.flashUntil = t * 1000 + 1500;
      }
      const flashing = t * 1000 < star.flashUntil;

      const pulse = 1 + 0.18 * Math.sin(t * (1.5 + star.growth * 0.6)) * clamp01(star.growth / 3);
      const flashScale = flashing ? 1.35 : 1;
      const scale = star.baseScale * pulse * flashScale;
      star.sprite.scale.set(scale, scale, 1);
      star.sprite.material.opacity = flashing ? 1 : 0.9;

      setLabelPosition(star, flashing || star.hoverLabel);
    });

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
    stars.forEach((star) => setLabelPosition(star, false));
    renderer.render(scene, camera);
  } else {
    animate();
  }

  return { focus };
}
