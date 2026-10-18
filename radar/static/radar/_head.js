// EstelarIA — escena 3D "el cielo de temas". ES module, Three.js vía importmap.
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

