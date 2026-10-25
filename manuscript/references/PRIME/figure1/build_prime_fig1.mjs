#!/usr/bin/env node
// Rebuild Figure 1 of PRIME (arXiv 2604.04999) as native, editable Excalidraw elements.
//
// Geometry is written in the pixel space of the original figure
// (https://arxiv.org/html/2604.04999v1/framework.png, 5064×2273) and scaled by S.
// Pipeline:
//   1. build the element list below (no images, no embedded SVG);
//   2. measure every text in headless Chrome with Excalidraw's own rule
//      (canvas measureText, height = fontSize × lineHeight × lines), using the
//      renderer bundled in @excalidraw/cli (= @excalidraw/excalidraw 0.18.1);
//   3. write PRIME_Figure1_Editable.excalidraw + module_manifest.json;
//   4. exportToSvg (scene embedded, re-importable) → PRIME_Figure1_Preview.svg;
//   5. `excalidraw render` (official CLI) → PRIME_Figure1_Preview.png.
//
// Requires: npm install -g @excalidraw/cli@0.2.0, Google Chrome.
// Run:      node build_prime_fig1.mjs

import { readFile, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = {
  scene: join(HERE, "PRIME_Figure1_Editable.excalidraw"),
  svg: join(HERE, "PRIME_Figure1_Preview.svg"),
  png: join(HERE, "PRIME_Figure1_Preview.png"),
  manifest: join(HERE, "module_manifest.json"),
};
const CHROME = process.env.EXCALIDRAW_BROWSER_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const CLI = join(execFileSync("npm", ["root", "-g"]).toString().trim(), "@excalidraw/cli");

const S = 0.4; // original px → scene px
const FONT = 2; // Helvetica (fontFamily 2); see README note in result for why not Liberation Sans
const FONT_CSS = "Helvetica, sans-serif, Segoe UI Emoji"; // what Excalidraw 0.18.1 builds for fontFamily 2
const LH = 1.15; // Excalidraw line height for Helvetica

// ---------------------------------------------------------------- palette (sampled from the original)
const C = {
  ink: "#1e1e1e", arrow: "#333333", navy: "#34495e", salmon: "#d27a6c", blueArrow: "#2f5d7c",
  panel: "#4a5866", grayLine: "#555555",
  bandWsi: "#edf8fe", bandRep: "#fef5f1", bandRna: "#fbeff9",
  blueBox: "#caeefb", pinkBox: "#f2cfee", peachBox: "#fbe3d6", grayBox: "#f2f2f2",
  trapBlue: "#dceaf7",
  eFront: "#bfbfbf", eLeft: "#9a9a9a", eBottom: "#d6d6d6",
  zI: ["#b3c5e5", "#c9d5ee", "#909eb8"], zR: ["#f2cfee", "#f6dcf2", "#c3a6bf"], zT: ["#f6c6ad", "#f9d6c4", "#d9a88f"],
  olive: "#dddb97", brown: "#be9f95", salmonFill: "#f19e9a", red: "#d77665", yellow: "#f2c454",
  lightBlue: "#b3c5e5", paleBlue: "#b3cdee", teal: "#43978d", orange: "#f09249",
  magenta: "#e59edd", magentaDark: "#d86ecc", blueDark: "#4e95d9", veryPale: "#dde8f3",
  moeBlock: "#f3edc4", moeStroke: "#e3c35a", trf: "#f2e1f0", fusion: "#dddb97",
  h1: "#c8efcb", h2: "#dceaf7", far: "#d9776a", close: "#2e6d8e", skipBlue: "#adc1e6", skipPink: "#f0c2eb",
  tissue: "#e48ab8", tile: "#e699bf", snow: "#7fb3e3", xRed: "#e0302a",
};

// ---------------------------------------------------------------- element factory
const els = [];
const manifest = { modules: {}, labels: {}, texts: [] };
const groupStack = [];
const usedIds = new Set();
let seq = 1;

const sc = (v) => Math.round(v * S * 100) / 100;
const uid = (id) => {
  let k = id;
  for (let n = 2; usedIds.has(k); n++) k = `${id}~${n}`;
  usedIds.add(k);
  return k;
};

function add(type, id, props) {
  const el = {
    id: uid(id), type, x: 0, y: 0, width: 0, height: 0, angle: 0,
    strokeColor: C.ink, backgroundColor: "transparent", fillStyle: "solid",
    strokeWidth: 1, strokeStyle: "solid", roughness: 0, opacity: 100,
    groupIds: groupStack.map((g) => g.gid).reverse(), frameId: null, roundness: null,
    seed: seq, version: 1, versionNonce: (seq * 7919) % 2147483647, isDeleted: false,
    boundElements: null, updated: 1, link: null, locked: false,
    ...props,
  };
  seq++;
  els.push(el);
  for (const g of groupStack) g.ids.push(el.id);
  return el;
}

// kind: "modules" (multi-shape icon / box with its inner text) or "labels" (math label pieces)
function group(kind, name, fn) {
  const g = { gid: `g.${name}`, ids: [] };
  groupStack.push(g);
  try { fn(); } finally { groupStack.pop(); }
  if (manifest[kind][name]) throw new Error(`duplicate ${kind} name ${name}`);
  manifest[kind][name] = g.ids;
}
const mod = (name, fn) => group("modules", name, fn);

const style = (s = {}) => ({
  strokeColor: s.stroke ?? C.ink,
  backgroundColor: s.fill ?? "transparent",
  strokeWidth: s.sw ?? 1,
  strokeStyle: s.dash ? (s.dash === true ? "dashed" : s.dash) : "solid",
  opacity: s.op ?? 100,
});

function rect(id, x, y, w, h, s = {}) {
  return add("rectangle", id, { x: sc(x), y: sc(y), width: sc(w), height: sc(h), roundness: s.round ? { type: 3 } : null, angle: s.angle ?? 0, ...style(s) });
}
function ellipse(id, cx, cy, rx, ry, s = {}) {
  return add("ellipse", id, { x: sc(cx - rx), y: sc(cy - ry), width: sc(2 * rx), height: sc(2 * ry), ...style(s) });
}
function linear(type, id, pts, s, extra) {
  const P = pts.map(([px, py]) => [sc(px), sc(py)]);
  const [x0, y0] = P[0];
  const rel = P.map(([px, py]) => [Math.round((px - x0) * 100) / 100, Math.round((py - y0) * 100) / 100]);
  const xs = rel.map((p) => p[0]), ys = rel.map((p) => p[1]);
  return add(type, id, {
    x: x0, y: y0, width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys),
    points: rel, lastCommittedPoint: null, startBinding: null, endBinding: null,
    startArrowhead: null, endArrowhead: null, roundness: s.curve ? { type: 2 } : null,
    ...style(s), ...extra,
  });
}
const poly = (id, pts, s = {}) => linear("line", id, [...pts, pts[0]], s, {}); // closed → filled
const polyline = (id, pts, s = {}) => linear("line", id, pts, s, {});
function arrow(id, pts, s = {}) {
  return linear("arrow", id, pts, { stroke: C.arrow, sw: 2.5, ...s }, {
    elbowed: false, startArrowhead: s.both ? "triangle" : null, endArrowhead: s.noHead ? null : "triangle",
  });
}

// visual bbox (scene px) of a bindable element, honouring a ±90° rotation
function vbox(el) {
  const q = Math.abs(Math.sin(el.angle || 0)) > 0.5;
  const w = q ? el.height : el.width, h = q ? el.width : el.height;
  const cx = el.x + el.width / 2, cy = el.y + el.height / 2;
  return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
}
function bind(ar, end, target) {
  const pt = end === "start" ? ar.points[0] : ar.points[ar.points.length - 1];
  const px = ar.x + pt[0], py = ar.y + pt[1];
  const [x0, y0, x1, y1] = vbox(target);
  const dx = Math.max(x0 - px, 0, px - x1), dy = Math.max(y0 - py, 0, py - y1);
  ar[end === "start" ? "startBinding" : "endBinding"] = { elementId: target.id, focus: 0, gap: Math.max(1, Math.round(Math.hypot(dx, dy) * 100) / 100) };
  target.boundElements = [...(target.boundElements || []), { id: ar.id, type: "arrow" }];
}
function arrowBetween(id, pts, from, to, s) {
  const a = arrow(id, pts, s);
  if (from) bind(a, "start", from);
  if (to) bind(a, "end", to);
  return a;
}

// Text: position is resolved after measurement. anchor: "c" centre, "lt" left-top, "lc" left-centre, "rc".
function text(id, str, x, y, s = {}) {
  const el = add("text", id, {
    x: 0, y: 0, width: 0, height: 0, text: str, originalText: str,
    fontSize: s.size ?? 16, fontFamily: FONT, textAlign: s.align ?? "center", verticalAlign: "top",
    containerId: null, autoResize: true, lineHeight: LH, angle: s.angle ?? 0,
    strokeColor: s.color ?? C.ink, backgroundColor: "transparent", strokeWidth: 1, opacity: s.op ?? 100,
  });
  el._lay = { x: sc(x), y: sc(y), anchor: s.anchor ?? "c", fit: s.fit ? sc(s.fit) : null };
  if (!groupStack.length) manifest.texts.push(el.id);
  return el;
}
// Bound label (moves with its container; double-click edits it).
function label(container, str, s = {}) {
  const el = add("text", `${container.id}.label`, {
    x: 0, y: 0, width: 0, height: 0, text: str, originalText: str,
    fontSize: s.size ?? 16, fontFamily: FONT, textAlign: "center", verticalAlign: "middle",
    containerId: container.id, autoResize: true, lineHeight: LH, angle: container.angle,
    strokeColor: s.color ?? C.ink, backgroundColor: "transparent", strokeWidth: 1, opacity: 100,
  });
  el._lay = { bound: container, dx: s.dx ? sc(s.dx) : 0 };
  container.boundElements = [...(container.boundElements || []), { id: el.id, type: "text" }];
  return el;
}
// Math label  base_sub^sup  as three small texts in one group (stacked like LaTeX).
function math(name, baseStr, sub, sup, cx, cy, size = 22) {
  group("labels", name, () => {
    const small = Math.round(size * 0.68 * 10) / 10;
    const b = text(`${name}.base`, baseStr, cx, cy, { size });
    const lo = sub ? text(`${name}.sub`, sub, cx, cy, { size: small, align: "left" }) : null;
    const hi = sup ? text(`${name}.sup`, sup, cx, cy, { size: small, align: "left" }) : null;
    b._math = { lo, hi };
    for (const t of [lo, hi]) if (t) t._lay = { skip: true };
  });
}
const fire = (id, x, y, size = 18) => text(id, "🔥", x, y, { size });
const snow = (id, x, y, size = 18) => text(id, "❄", x, y, { size, color: C.snow });

// ---------------------------------------------------------------- composite shapes
const hex2rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const rgb2hex = (r) => "#" + r.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
const mix = (a, b, t) => rgb2hex(hex2rgb(a).map((v, i) => v + (hex2rgb(b)[i] - v) * t));
const lighten = (h, t) => mix(h, "#ffffff", t);
const darken = (h, t) => mix(h, "#000000", t);

// Feature-embedding bar seen from lower-left (grey E bars): front + left face + bottom face.
function barE(id, fx, fy, w, h, s = {}) {
  const dx = -20, dy = 18;
  const st = { stroke: s.dash ? "#2f3e4c" : "#6b6b6b", sw: s.dash ? 1.5 : 1, dash: s.dash };
  const front = rect(`${id}.front`, fx, fy, w, h, { ...st, fill: s.dash ? "#ffffff" : C.eFront }); // white, not transparent: keeps the interior clickable
  poly(`${id}.left`, [[fx, fy], [fx + dx, fy + dy], [fx + dx, fy + h + dy], [fx, fy + h]], { ...st, fill: s.dash ? "#d9d9d9" : C.eLeft });
  poly(`${id}.bottom`, [[fx, fy + h], [fx + w, fy + h], [fx + w + dx, fy + h + dy], [fx + dx, fy + h + dy]], { ...st, fill: s.dash ? "#ffffff" : C.eBottom });
  return front;
}
// Token bar seen from upper-left (coloured Z bars): front + left face + top face.
function barZ(id, fx, fy, w, h, [front, left, top], s = {}) {
  const dx = -30, dy = -31;
  const st = { stroke: s.dash ? "#3a3a3a" : darken(front, 0.45), sw: s.dash ? 1.5 : 1, dash: s.dash };
  poly(`${id}.left`, [[fx, fy], [fx + dx, fy + dy], [fx + dx, fy + h + dy], [fx, fy + h]], { ...st, fill: left });
  poly(`${id}.top`, [[fx, fy], [fx + dx, fy + dy], [fx + w + dx, fy + dy], [fx + w, fy]], { ...st, fill: top });
  return rect(`${id}.front`, fx, fy, w, h, { ...st, fill: front });
}
// Oblique prototype prism of the memory bank.
function prism(id, fx, fy, w, h, color) {
  const ex = 150, ey = -156;
  const st = { stroke: darken(color, 0.45), sw: 1 };
  poly(`${id}.top`, [[fx, fy], [fx + ex, fy + ey], [fx + w + ex, fy + ey], [fx + w, fy]], { ...st, fill: lighten(color, 0.3) });
  poly(`${id}.side`, [[fx + w, fy], [fx + w + ex, fy + ey], [fx + w + ex, fy + h + ey], [fx + w, fy + h]], { ...st, fill: darken(color, 0.18) });
  rect(`${id}.front`, fx, fy, w, h, { ...st, fill: color });
}
function trapezoid(id, xl, ytl, ybl, xr, ytr, ybr, fill) {
  return poly(id, [[xl, ytl], [xr, ytr], [xr, ybr], [xl, ybl]], { fill, stroke: "#222222", sw: 1.5 });
}
const tri = (id, x0, x1, yb, yt, fill, stroke = "#4a5a78") =>
  poly(id, [[x0, yb], [(x0 + x1) / 2, yt], [x1, yb]], { fill, stroke, sw: 1 });
function hollowArrow(id, x0, x1, cy, h) {
  const w = x1 - x0, t = h * 0.24, hx = x0 + w * 0.45;
  return poly(id, [[x0, cy - t], [hx, cy - t], [hx, cy - h / 2], [x1, cy], [hx, cy + h / 2], [hx, cy + t], [x0, cy + t]], { fill: "#ffffff", stroke: "#111111", sw: 2 });
}
const otimes = (id, cx, cy, r) => mod(id, () => {
  ellipse(`${id}.ring`, cx, cy, r, r, { fill: "#ffffff", stroke: "#222222", sw: 2 });
  const d = r * 0.7071;
  polyline(`${id}.d1`, [[cx - d, cy - d], [cx + d, cy + d]], { stroke: "#222222", sw: 2 });
  polyline(`${id}.d2`, [[cx - d, cy + d], [cx + d, cy - d]], { stroke: "#222222", sw: 2 });
});
const sheetStack = (id, x, y, w, h, fill = "#ffffff") => {
  rect(`${id}.back`, x + 13, y + 13, w, h, { fill: "#ffffff", stroke: "#111111", sw: 2 });
  return rect(`${id}.front`, x, y, w, h, { fill, stroke: "#111111", sw: 2 });
};
const blueArrow = (id, x0, x1, y) => arrow(id, [[x0, y], [x1, y]], { stroke: C.blueArrow, sw: 4 });

// deterministic pseudo-random for textures
let rs = 7;
const rnd = () => ((rs = (rs * 16807) % 2147483647) / 2147483647);

// ================================================================= LAYOUT
// ---------- frames of the three stages + legend
rect("panel.preprocess", 10, 205, 1388, 2060, { round: true, dash: true, stroke: C.panel, sw: 2 });
rect("panel.imputation", 1447, 208, 1780, 2058, { round: true, dash: true, stroke: C.panel, sw: 2 });
rect("panel.pretraining", 3354, 208, 1705, 2058, { round: true, dash: true, stroke: C.panel, sw: 2 });
text("title.preprocess", "Sample Pre-processing", 702, 2182, { fit: 704 });
text("title.imputation", "Missing Modality Imputation", 2337, 2182, { fit: 848 });
text("title.pretraining", "Missing-aware Pretraining", 4205, 2182, { fit: 792 });

mod("legend", () => {
  rect("legend.box", 1454, 6, 1990, 156, { dash: true, stroke: "#555555", sw: 1.2, fill: "#ffffff" });
  const st = { dash: true, stroke: "#2f3e4c", sw: 1.5, fill: "#ffffff" };
  rect("legend.missing.front", 1494, 62, 170, 65, st);
  poly("legend.missing.top", [[1494, 62], [1524, 41], [1694, 41], [1664, 62]], st);
  poly("legend.missing.side", [[1664, 62], [1694, 41], [1694, 106], [1664, 127]], st);
  text("legend.missing.text", "Missing", 1808, 86, { size: 17 });
  fire("legend.fire", 2019, 86, 24);
  text("legend.trainable.text", "Trainable", 2218, 86, { size: 17 });
  snow("legend.snow", 2456, 86, 26);
  text("legend.frozen.text", "Frozen", 2626, 86, { size: 17 });
  otimes("legend.otimes", 2837, 86, 24);
  text("legend.aggregate.text", "Weighted Aggregate", 3146, 86, { size: 17 });
});

// ---------- Sample Pre-processing
rect("band.wsi", 49, 336, 1296, 441, { round: true, fill: C.bandWsi, stroke: "transparent", sw: 1 });
rect("band.report", 49, 962, 1296, 434, { round: true, fill: C.bandRep, stroke: "transparent", sw: 1 });
rect("band.rna", 49, 1595, 1296, 437, { round: true, fill: C.bandRna, stroke: "transparent", sw: 1 });

mod("wsi.slide", () => {
  sheetStack("wsi.slide.sheet", 104, 357, 392, 333, "#f4f3f1");
  const blob = [[150, 410], [185, 392], [230, 388], [265, 380], [300, 385], [330, 378], [370, 382], [405, 375], [430, 386], [447, 401], [470, 405], [481, 425], [470, 446], [478, 472], [470, 502], [473, 540], [478, 580], [470, 620], [462, 650], [440, 666], [400, 668], [350, 664], [300, 670], [250, 666], [200, 668], [160, 662], [142, 640], [140, 600], [146, 560], [138, 520], [142, 480], [136, 440]];
  poly("wsi.slide.tissue", blob, { fill: C.tissue, stroke: "#cf6f9f", sw: 0.5 });
  poly("wsi.slide.purple", [[143, 612], [190, 598], [240, 615], [290, 603], [340, 618], [390, 604], [440, 614], [468, 606], [470, 650], [440, 666], [400, 668], [350, 664], [300, 670], [250, 666], [200, 668], [160, 662]], { fill: "#b88ac6", stroke: "transparent", sw: 0.5, op: 65 });
  poly("wsi.slide.light", [[290, 400], [330, 393], [350, 452], [342, 560], [322, 598], [298, 520]], { fill: "#f3bdd7", stroke: "transparent", sw: 0.5, op: 45 });
  for (let i = 0; i < 26; i++) {
    const cx = 165 + rnd() * 285, cy = 410 + rnd() * 190, r = 6 + rnd() * 12;
    ellipse(`wsi.slide.speck${i}`, cx, cy, r * 1.5, r, { fill: ["#d06aa0", "#f2aed0", "#c47cbf", "#ea9cc5"][i % 4], stroke: "transparent", sw: 0.5, op: 50 });
  }
  poly("wsi.slide.edge", [[440, 470], [462, 468], [468, 590], [452, 600]], { fill: "#d4609a", stroke: "transparent", sw: 0.5, op: 70 });
});
text("wsi.caption", "Whole Slide Image", 309, 745, { size: 17 });
blueArrow("wsi.arrow1", 523, 577, 536);

mod("wsi.tiles", () => {
  const x0 = 598, y0 = 393, cw = 63.4, ch = 57.2;
  const cut = new Set(["0,3", "0,4", "1,4", "2,4"]);
  const xs = new Set(["0,3", "0,4", "1,4", "2,4", "3,0", "4,3"]);
  for (let r = 0; r < 5; r++) for (let c = 0; c < 5; c++) {
    const k = `${r},${c}`;
    const fill = cut.has(k) ? "#f8f1f4" : [C.tile, "#e08db6", "#eaa3c8", "#e494bc"][Math.floor(rnd() * 4)];
    rect(`wsi.tiles.r${r}c${c}`, x0 + c * cw, y0 + r * ch, cw, ch, { fill, stroke: "#111111", sw: 1 });
  }
  for (const k of xs) {
    const [r, c] = k.split(",").map(Number);
    const cx = x0 + (c + 0.5) * cw, cy = y0 + (r + 0.5) * ch, d = 17;
    polyline(`wsi.tiles.x${r}${c}a`, [[cx - d, cy - d], [cx + d, cy + d]], { stroke: C.xRed, sw: 2 });
    polyline(`wsi.tiles.x${r}${c}b`, [[cx - d, cy + d], [cx + d, cy - d]], { stroke: C.xRed, sw: 2 });
  }
});
text("wsi.tiles.caption", "Tiling & Filtering", 756, 745, { size: 17 });
blueArrow("wsi.arrow2", 938, 991, 536);
mod("wsi.backbone", () => {
  trapezoid("wsi.backbone.shape", 1006, 434, 642, 1186, 479, 593, C.trapBlue);
  snow("wsi.backbone.snow", 1044, 474, 20);
  text("wsi.backbone.text", "Frozen\nBackbone", 1098, 548, { size: 15 });
});
blueArrow("wsi.arrow3", 1202, 1256, 536);
mod("wsi.E", () => barE("wsi.E", 1297, 439, 43, 157));
math("wsi.E.label", "E", "i", "(I)", 1306, 668, 20);

mod("report.pages", () => {
  sheetStack("report.pages.sheet", 97, 984, 387, 342);
  for (let i = 0; i < 20; i++) {
    const y = 1004 + i * 15.5;
    if (i === 12) { polyline("report.pages.rule", [[118, y], [462, y]], { stroke: "#666666", sw: 0.8 }); continue; }
    const len = 120 + rnd() * 220;
    polyline(`report.pages.l${i}`, [[118, y], [118 + len, y]], { stroke: "#a3a3a3", sw: 0.6 });
  }
  for (let i = 0; i < 4; i++) {
    const y = 1118 + i * 16, x = 330 + rnd() * 20;
    const pts = []; for (let k = 0; k < 9; k++) pts.push([x + k * 11, y + (k % 2 ? -3 : 3)]);
    polyline(`report.pages.hw${i}`, pts, { stroke: "#7a7a7a", sw: 0.6, curve: true });
  }
});
text("report.caption", "Pathology Reports", 309, 1372, { size: 17 });
blueArrow("report.arrow1", 517, 569, 1168);
mod("report.ocr", () => {
  const b = rect("report.ocr.box", 578, 1087, 337, 159, { round: true, fill: C.peachBox, stroke: C.navy, sw: 2 });
  label(b, "OCR & Standard\nCleaning", { size: 16 });
});
blueArrow("report.arrow2", 934, 983, 1168);
mod("report.backbone", () => {
  trapezoid("report.backbone.shape", 999, 1059, 1270, 1176, 1103, 1225, C.peachBox);
  snow("report.backbone.snow", 1040, 1106, 20);
  text("report.backbone.text", "Frozen\nBackbone", 1090, 1180, { size: 15 });
});
blueArrow("report.arrow3", 1194, 1248, 1168);
mod("report.E", () => barE("report.E", 1297, 1087, 43, 150));
math("report.E.label", "E", "i", "(T)", 1306, 1310, 20);

mod("rna.heatmap", () => {
  sheetStack("rna.heatmap.sheet", 97, 1607, 387, 333);
  const V = [
    [0.9, 0.5, 0.6, -0.3, -0.7, -0.2], [0.4, 0.3, 0.8, -0.5, -0.4, -0.6], [0.6, 0.7, 0.9, -0.2, -0.3, -0.4],
    [0.2, 0.4, 0.3, -0.6, -0.5, -0.3], [-0.5, -0.4, -0.6, 0.9, 0.4, 0.3], [-0.3, -0.6, -0.4, 0.8, 0.6, 0.5],
    [-0.6, -0.3, -0.5, 0.5, 0.9, 0.2], [-0.4, -0.5, -0.2, 0.6, 0.3, 0.8], [-0.2, -0.4, -0.3, 0.3, 0.5, 0.9],
    [-0.5, -0.3, -0.6, 0.4, 0.7, 0.6],
  ];
  const col = (v) => (v < 0 ? mix("#e3ebf5", "#4f7fbf", -v) : v < 0.45 ? mix("#e3ebf5", "#f2b79a", v / 0.45) : mix("#f2b79a", "#b3262d", (v - 0.45) / 0.55));
  const x0 = 171, y0 = 1664, cw = 313 / 6, ch = 276 / 10;
  V.forEach((row, r) => row.forEach((v, c) => rect(`rna.heatmap.r${r}c${c}`, x0 + c * cw, y0 + r * ch, cw, ch, { fill: col(v), stroke: col(v), sw: 0.5 })));
  // dendrograms
  const dl = (id, a, b, x) => polyline(id, [[171, a], [x, a], [x, b], [171, b]], { stroke: "#444444", sw: 0.8 });
  dl("rna.heatmap.dl1", y0 + ch * 0.5, y0 + ch * 1.5, 158); dl("rna.heatmap.dl2", y0 + ch * 2.5, y0 + ch * 3.5, 160);
  dl("rna.heatmap.dl3", y0 + ch * 1, y0 + ch * 3, 140); dl("rna.heatmap.dl4", y0 + ch * 4.5, y0 + ch * 5.5, 156);
  dl("rna.heatmap.dl5", y0 + ch * 6.5, y0 + ch * 8.5, 150); dl("rna.heatmap.dl6", y0 + ch * 5, y0 + ch * 7.5, 128);
  dl("rna.heatmap.dl7", y0 + ch * 2, y0 + ch * 6.2, 108);
  const dt = (id, a, b, y) => polyline(id, [[a, y0], [a, y], [b, y], [b, y0]], { stroke: "#444444", sw: 0.8 });
  dt("rna.heatmap.dt1", x0 + cw * 0.5, x0 + cw * 1.5, 1650); dt("rna.heatmap.dt2", x0 + cw * 1, x0 + cw * 2.5, 1636);
  dt("rna.heatmap.dt3", x0 + cw * 3.5, x0 + cw * 4.5, 1648); dt("rna.heatmap.dt4", x0 + cw * 4, x0 + cw * 5.5, 1632);
  dt("rna.heatmap.dt5", x0 + cw * 1.8, x0 + cw * 4.8, 1618);
});
text("rna.caption", "Bulk RNA-seq", 297, 2001, { size: 17 });
blueArrow("rna.arrow1", 517, 569, 1792);
mod("rna.backbone", () => {
  trapezoid("rna.backbone.shape", 582, 1688, 1896, 760, 1733, 1850, C.pinkBox);
  snow("rna.backbone.snow", 621, 1730, 18);
  text("rna.backbone.text", "Frozen\nBackbone", 672, 1803, { size: 15 });
});
blueArrow("rna.arrow2", 780, 834, 1792);
mod("rna.seq", () => {
  const b = rect("rna.seq.box", 853, 1704, 320, 166, { round: true, fill: C.pinkBox, stroke: C.navy, sw: 2 });
  label(b, "Sequence\nStandardization", { size: 16 });
});
blueArrow("rna.arrow3", 1194, 1248, 1792);
mod("rna.E", () => barE("rna.E", 1297, 1712, 43, 152));
math("rna.E.label", "E", "i", "(R)", 1302, 1928, 20);

// ---------- Missing Modality Imputation
// skip connections first so that bars and boxes are drawn on top of them
arrow("mid.skipI.down", [[1719, 1016], [1719, 1137]], { stroke: C.skipBlue, sw: 3 });
arrow("mid.skipI.branch", [[1719, 1045], [2451, 1045], [2451, 544], [2569, 544]], { stroke: C.skipBlue, sw: 3 });
arrow("mid.skipR.down", [[2204, 1016], [2204, 1137]], { stroke: C.skipPink, sw: 3 });
arrow("mid.skipR.branch", [[2204, 1083], [2393, 1083], [2393, 1177], [2569, 1177]], { stroke: C.skipPink, sw: 3 });

let eI, eR, tokI, tokR;
mod("mid.E_I", () => { eI = barE("mid.E_I", 1698, 263, 43, 155); });
mod("mid.E_T", () => barE("mid.E_T", 1949, 263, 43, 155, { dash: true }));
mod("mid.E_R", () => { eR = barE("mid.E_R", 2183, 263, 43, 155); });
math("mid.E_I.label", "E", "i", "(I)", 1612, 300, 22);
math("mid.E_T.label", "E", "i", "(T)", 1858, 300, 22);
math("mid.E_R.label", "E", "i", "(R)", 2100, 300, 22);

mod("mid.tokenizerI", () => {
  tokI = rect("mid.tokenizerI.box", 1503, 523, 432, 156, { round: true, fill: C.blueBox, stroke: C.salmon, sw: 2 });
  label(tokI, "Modality-Specific\nTokenizer", { size: 16 });
  fire("mid.tokenizerI.fire", 1548, 640);
});
mod("mid.tokenizerR", () => {
  tokR = rect("mid.tokenizerR.box", 1987, 523, 434, 156, { round: true, fill: C.pinkBox, stroke: C.salmon, sw: 2 });
  label(tokR, "Modality-Specific\nTokenizer", { size: 16 });
  fire("mid.tokenizerR.fire", 2032, 640);
});
arrowBetween("mid.arrow.EI_tok", [[1719, 440], [1719, 519]], null, tokI);
arrowBetween("mid.arrow.ER_tok", [[2204, 440], [2204, 519]], null, tokR);
arrow("mid.arrow.tokI_Z", [[1719, 683], [1719, 762]]);
arrow("mid.arrow.tokR_Z", [[2204, 683], [2204, 762]]);

mod("mid.Z_I", () => barZ("mid.Z_I", 1702, 800, 64, 216, C.zI));
mod("mid.Z_R", () => barZ("mid.Z_R", 2188, 800, 64, 216, C.zR));
math("mid.Z_I.label", "Z", "i", "(I)", 1607, 798, 22);
math("mid.Z_R.label", "Z", "i", "(R)", 2092, 798, 22);

let bank, qbox;
mod("mid.memoryBank", () => {
  bank = rect("mid.memoryBank.box", 1597, 1140, 710, 333, { dash: true, stroke: C.grayLine, sw: 1.2, fill: "#ffffff" });
  fire("mid.memoryBank.fire", 1637, 1190);
  const cols = [C.olive, C.brown, C.salmonFill, C.red, C.yellow];
  cols.forEach((c, i) => prism(`mid.memoryBank.p${i}`, 1624 + i * 65.5, 1336, 47, 49, c));
  text("mid.memoryBank.dots", "…", 2068, 1300, { size: 22 });
  prism("mid.memoryBank.p5", 2083, 1336, 47, 49, C.paleBlue);
  text("mid.memoryBank.title", "Shared Prototype Memory Bank", 1952, 1433, { fit: 655 });
});
arrow("mid.arrow.bank_qI", [[1719, 1473], [1719, 1562]]);
arrow("mid.arrow.bank_qR", [[2203, 1473], [2203, 1562]]);

mod("mid.weights", () => {
  qbox = rect("mid.weights.box", 1662, 1566, 630, 296, { dash: true, stroke: C.grayLine, sw: 1.2, fill: "#ffffff" });
  const chart = (id, ax, tops, xs) => {
    polyline(`${id}.axes`, [[ax, 1619], [ax, 1827], [ax + 247, 1827]], { stroke: "#222222", sw: 2 });
    [C.olive, C.brown, C.salmonFill, C.red, C.lightBlue].forEach((c, i) =>
      rect(`${id}.bar${i}`, xs[i], tops[i], 36, 1827 - tops[i], { fill: c, stroke: darken(c, 0.4), sw: 1 }));
  };
  chart("mid.weights.qI", 1699, [1668, 1801, 1692, 1746, 1718], [1711, 1754, 1797, 1839, 1884]);
  chart("mid.weights.qR", 2008, [1722, 1738, 1793, 1689, 1788], [2023, 2063, 2105, 2148, 2192]);
});
math("mid.qI.label", "q", "i", "(I)", 1797, 1650, 19);
math("mid.qR.label", "q", "i", "(R)", 2106, 1650, 19);
arrow("mid.arrow.q_agg", [[1976, 1862], [1976, 1968]]);
otimes("mid.aggregate", 1976, 2002, 28);
arrow("mid.arrow.bank_agg", [[1597, 1306], [1512, 1306], [1512, 2002], [1944, 2002]], { stroke: "#222222", sw: 2.5 });
arrow("mid.arrow.agg_ZT", [[2008, 2002], [2448, 2002], [2448, 1791], [2570, 1791]], { stroke: "#222222", sw: 2.5 });

// three refinement branches
const branch = (k, zColors, zDash, zy, zh, boxY, fill, stroke, tokens) => {
  let box;
  mod(`mid.branch${k}.Z`, () => barZ(`mid.branch${k}.Z`, 2608, zy, 64, zh, zColors, { dash: zDash }));
  mod(`mid.branch${k}.refine`, () => {
    box = rect(`mid.branch${k}.refine.box`, 2750, boxY, 432, 156, { round: true, fill, stroke, sw: 2 });
    label(box, "Modality-Specific\nRefinement", { size: 16 });
    fire(`mid.branch${k}.refine.fire`, 2800, boxY + 112);
  });
  const cy = boxY + 78;
  arrowBetween(`mid.branch${k}.arrow.Z_refine`, [[2676, cy], [2746, cy]], null, box);
  arrowBetween(`mid.branch${k}.arrow.refine_tokens`, [[2966, boxY + 156 + 3], [2966, boxY + 226]], box, null);
  mod(`mid.branch${k}.tokens`, () => tokens(boxY + 230));
};
branch("I", C.zI, false, 466, 220, 419, C.blueBox, C.salmon, (y) => {
  for (let i = 0; i < 5; i++) tri(`mid.branchI.tokens.t${i}`, 2753 + i * 82.6, 2753 + (i + 1) * 82.6, y + 82, y, C.lightBlue);
});
branch("R", C.zR, false, 1104, 211, 1042, C.pinkBox, C.salmon, (y) => {
  for (let i = 0; i < 5; i++) ellipse(`mid.branchR.tokens.c${i}`, 2800 + i * 83, y + 47, 41, 41, { fill: C.magenta, stroke: "#7a4a78", sw: 1 });
});
branch("T", C.zT, true, 1710, 219, 1664, C.peachBox, C.peachBox, (y) => {
  [C.yellow, C.salmonFill, C.brown, C.olive, C.teal].forEach((c, i) =>
    rect(`mid.branchT.tokens.s${i}`, 2761 + i * 82, y + 4, 82, 81, { fill: c, stroke: "#333333", sw: 1 }));
});
math("mid.branchI.Z.label", "Z", "i", "(I)", 2513, 465, 22);
math("mid.branchR.Z.label", "Z", "i", "(R)", 2513, 1108, 22);
math("mid.branchT.Z.label", "Z", "i", "(T)", 2521, 1706, 22);
math("mid.branchI.Zt.label", "Z̃", "i", "(I)", 2968, 783, 22);
math("mid.branchR.Zt.label", "Z̃", "i", "(R)", 2968, 1415, 22);
math("mid.branchT.Zt.label", "Z̃", "i", "(T)", 2968, 2030, 22);

hollowArrow("flow.toPretrain1", 3249, 3341, 581, 106);
hollowArrow("flow.toPretrain2", 3249, 3341, 1616, 106);

// ---------- Missing-aware Pretraining
const plot = (id, ox, x1, build) => mod(id, () => {
  arrow(`${id}.axes`, [[ox, 282], [ox, 648], [x1, 648]], { stroke: "#222222", sw: 2.5, both: true });
  build();
});
const pair = (id, a, b, color) => arrow(id, [a, b], { stroke: color, sw: 1.8, both: true });
const sq = (id, x, y, fill) => rect(id, x, y, 130, 130, { fill, stroke: "#555555", sw: 1 });
const circ = (id, cx, cy, fill) => ellipse(id, cx, cy, 65, 65, { fill, stroke: darken(fill, 0.45), sw: 1 });

plot("pre.alignIT", 3416, 3884, () => {
  sq("pre.alignIT.viT", 3441, 474, C.peachBox);
  tri("pre.alignIT.vjI", 3580, 3712, 400, 271, C.lightBlue);
  sq("pre.alignIT.vjT", 3689, 510, C.zT[0]);
  pair("pre.alignIT.far1", [3501, 466], [3571, 402], C.far);
  pair("pre.alignIT.close", [3725, 388], [3777, 497], C.close);
  pair("pre.alignIT.far2", [3576, 578], [3684, 597], C.far);
});
math("pre.alignIT.viT.label", "v", "i", "(T)", 3504, 541, 20);
math("pre.alignIT.vjI.label", "v", "j", "(I)", 3648, 358, 20);
math("pre.alignIT.vjT.label", "v", "j", "(T)", 3752, 577, 20);
text("pre.alignIT.far1.text", "far", 3516, 410, { size: 16, angle: -0.6 });
text("pre.alignIT.close.text", "close", 3787, 425, { size: 16, angle: 1.05 });
text("pre.alignIT.far2.text", "far", 3634, 559, { size: 16, angle: 0.12 });
text("pre.alignIT.caption", "Align Img & Text", 3636, 694, { size: 16 });

plot("pre.alignIR", 3972, 4440, () => {
  circ("pre.alignIR.viR", 4221, 339, C.magenta);
  tri("pre.alignIR.viI", 3993, 4126, 603, 469, C.lightBlue);
  tri("pre.alignIR.vjI", 4237, 4369, 632, 499, C.blueDark, "#2c4f7a");
  pair("pre.alignIR.close", [4063, 462], [4153, 362], C.close);
  pair("pre.alignIR.far1", [4253, 406], [4292, 497], C.far);
  pair("pre.alignIR.far2", [4114, 556], [4250, 579], C.far);
});
math("pre.alignIR.viR.label", "v", "i", "(R)", 4219, 341, 20);
math("pre.alignIR.viI.label", "v", "i", "(I)", 4058, 563, 20);
math("pre.alignIR.vjI.label", "v", "j", "(I)", 4303, 592, 20);
text("pre.alignIR.close.text", "close", 4080, 381, { size: 16, angle: -1.0 });
text("pre.alignIR.far1.text", "far", 4318, 437, { size: 16, angle: 1.05 });
text("pre.alignIR.far2.text", "far", 4186, 538, { size: 16, angle: 0.12 });
text("pre.alignIR.caption", "Align Img & RNA", 4193, 694, { size: 16 });

plot("pre.alignTR", 4526, 4994, () => {
  sq("pre.alignTR.vjT", 4551, 481, C.zT[0]);
  circ("pre.alignTR.viR", 4775, 339, C.magenta);
  circ("pre.alignTR.vjR", 4868, 572, C.magentaDark);
  pair("pre.alignTR.far1", [4600, 456], [4713, 380], C.far);
  pair("pre.alignTR.far2", [4812, 406], [4848, 497], C.far);
  pair("pre.alignTR.close", [4689, 553], [4800, 578], C.close);
});
math("pre.alignTR.vjT.label", "v", "j", "(T)", 4614, 548, 20);
math("pre.alignTR.viR.label", "v", "i", "(R)", 4773, 341, 20);
math("pre.alignTR.vjR.label", "v", "j", "(R)", 4866, 574, 20);
text("pre.alignTR.far1.text", "far", 4627, 396, { size: 16, angle: -0.6 });
text("pre.alignTR.far2.text", "far", 4872, 432, { size: 16, angle: 1.05 });
text("pre.alignTR.close.text", "close", 4745, 528, { size: 16, angle: 0.12 });
text("pre.alignTR.caption", "Align Text & RNA", 4754, 694, { size: 16 });
text("pre.interModality.title", "Inter-modality Contrastive Learning", 4204, 775, { fit: 775 });

// views
const view = (k, yTop, yTri, ySq, yCirc, triC, sqC, circC) => mod(`pre.view${k}`, () => {
  const yb = yTop + 366, ym = (yTop + yb) / 2;
  const br = (id, xo, xi) => polyline(id, [[xi, yTop], [xo + (xi - xo) * 0.3, yTop + 9], [xo, yTop + 42], [xo, yb - 42], [xo + (xi - xo) * 0.3, yb - 9], [xi, yb]], { stroke: "#222222", sw: 2.5, curve: true });
  br(`pre.view${k}.bracketL`, 3427, 3475);
  br(`pre.view${k}.bracketR`, 3776, 3728);
  triC.forEach((c, i) => tri(`pre.view${k}.t${i}`, 3447 + i * 66.4, 3447 + (i + 1) * 66.4, yTri + 64, yTri, c));
  sqC.forEach((c, i) => rect(`pre.view${k}.s${i}`, 3447 + i * 66.4, ySq, 66.4, 64, { fill: c, stroke: "#333333", sw: 1 }));
  circC.forEach((c, i) => ellipse(`pre.view${k}.c${i}`, 3480 + i * 66.4, yCirc, 33, 33, { fill: c, stroke: "#444444", sw: 1 }));
});
view("1", 904, 962, 1062, 1197,
  [C.lightBlue, C.brown, C.lightBlue, C.yellow, C.lightBlue],
  [C.lightBlue, C.paleBlue, C.salmonFill, C.olive, C.teal],
  [C.magenta, C.veryPale, C.orange, C.magenta, C.red]);
view("2", 1684, 1725, 1826, 1961,
  [C.teal, C.lightBlue, C.brown, C.lightBlue, C.lightBlue],
  [C.brown, C.salmonFill, C.lightBlue, C.olive, C.teal],
  [C.magenta, C.teal, C.magenta, C.lightBlue, C.olive]);
text("pre.view1.caption", "View 1", 3614, 1283, { size: 17 });
text("pre.view2.caption", "View 2", 3614, 2051, { size: 17 });

let vaug;
mod("pre.viewAug", () => {
  vaug = rect("pre.viewAug.box", 3453, 1429, 322, 145, { round: true, fill: C.grayBox, stroke: "#333333", sw: 2 });
  label(vaug, "View\nAugmentation", { size: 17 });
});
arrowBetween("pre.arrow.aug_view1", [[3614, 1425], [3614, 1310]], vaug, null);
arrowBetween("pre.arrow.aug_view2", [[3614, 1578], [3614, 1680]], vaug, null);

let moe1, trf, moe2, fus;
mod("pre.backbone", () => {
  rect("pre.backbone.box", 3900, 835, 304, 1284, { round: true, fill: C.grayBox, stroke: "#2f3e4c", sw: 2 });
  fire("pre.backbone.fire", 3938, 884);
  text("pre.backbone.text", "Modality-Aware MoE Fusion Backbone", 3943, 1480, { fit: 840, angle: Math.PI / 2 });
  // rotated containers: unrotated size is (height × width) of the visual box
  const block = (id, cy, h, fill, stroke, str) => {
    const b = rect(id, 4075 - h / 2, cy - 161 / 2, h, 161, { round: true, fill, stroke, sw: 2, angle: Math.PI / 2 });
    label(b, str, { size: 16 });
    return b;
  };
  moe1 = block("pre.backbone.moe1", 1118, 282, C.moeBlock, C.moeStroke, "MoE\nBlock");
  trf = block("pre.backbone.transformer", 1520, 344, C.trf, C.salmon, "Transformer\nBlock");
  moe2 = block("pre.backbone.moe2", 1913, 288, C.moeBlock, C.moeStroke, "MoE\nBlock");
});
arrowBetween("pre.arrow.in_moe1", [[4075, 904], [4075, 973]], null, moe1);
arrowBetween("pre.arrow.moe1_trf", [[4075, 1263], [4075, 1344]], moe1, trf);
arrowBetween("pre.arrow.trf_moe2", [[4075, 1696], [4075, 1765]], trf, moe2);
arrow("pre.arrow.view1_backbone", [[3806, 1088], [3896, 1088]]);
arrow("pre.arrow.view2_backbone", [[3806, 1859], [3896, 1859]]);

mod("pre.fusion", () => {
  fus = rect("pre.fusion.box", 4282, 1018, 279, 159, { round: true, fill: C.fusion, stroke: C.salmon, sw: 2 });
  label(fus, "Fusion\nProjector", { size: 18 });
  fire("pre.fusion.fire", 4312, 1064, 19);
});
arrowBetween("pre.arrow.backbone_fusion", [[4208, 1097], [4278, 1097]], null, fus);
arrow("pre.arrow.h1", [[4561, 1097], [4702, 1097], [4702, 1262]], { stroke: "#111111", sw: 3.5 });
arrow("pre.arrow.h2", [[4613, 1097], [4613, 1214], [4253, 1214], [4253, 1625], [4362, 1625]], { stroke: "#111111", sw: 3.5 });
math("pre.h1.label", "h", "i", "(1)", 4772, 1206, 22);
math("pre.h2.label", "h", "i", "(2)", 4310, 1556, 22);

mod("pre.h1row", () => {
  const subs = ["i,0", "i,1", null, "i,d−1", "i,d"];
  subs.forEach((s, k) => {
    const x = 4488 + k * 87.6;
    rect(`pre.h1row.cell${k}`, x, 1265, 87.6, 90, { fill: C.h1, stroke: "#6f8f72", sw: 1 });
    if (s) math(`pre.h1row.cell${k}.label`, "h", s, "(1)", x + 37, 1310, 13.5);
    else text(`pre.h1row.cell${k}.dots`, "…", x + 43.8, 1306, { size: 14 });
  });
});
mod("pre.h2col", () => {
  const subs = ["i,0", "i,1", null, "i,d−1", "i,d"];
  subs.forEach((s, k) => {
    const y = 1393 + k * 91.4;
    rect(`pre.h2col.cell${k}`, 4366, y, 90, 91.4, { fill: C.h2, stroke: "#6f7f92", sw: 1 });
    if (s) math(`pre.h2col.cell${k}.label`, "h", s, "(2)", 4404, y + 47, 13.5);
    else text(`pre.h2col.cell${k}.dots`, "⋮", 4411, y + 46, { size: 14 });
  });
});
mod("pre.simMatrix", () => {
  const M = [
    ["#b3c5e5", "#dceaf7", "#a6caec", "#dceaf7", "#b3cdee"],
    ["#dceaf7", "#b3c5e5", "#dceaf7", "#a6caec", "#dceaf7"],
    ["#a6caec", "#dceaf7", "#b3c5e5", "#dceaf7", "#a6caec"],
    ["#dceaf7", "#a6caec", "#dceaf7", "#b3c5e5", "#dceaf7"],
    ["#b3cdee", "#dceaf7", "#a6caec", "#dceaf7", "#b3c5e5"],
  ];
  M.forEach((row, i) => row.forEach((c, j) =>
    rect(`pre.simMatrix.r${i}c${j}`, 4488 + j * 88.4, 1393 + i * 91.4, 88.4, 91.4, { fill: c, stroke: "#5a6878", sw: 1 })));
});
text("pre.interView.title", "Inter-view Contrastive Learning", 4630, 1912, { fit: 660 });

// ================================================================= MEASURE + EXPORT
const { chromium } = await import(pathToFileURL(join(CLI, "node_modules/playwright-core/index.mjs")).href);
const ORIGIN = "http://excalidraw-renderer.local";
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  const page = await browser.newPage({ serviceWorkers: "block" });
  const rendererJs = await readFile(join(CLI, "dist/renderer.js"));
  await page.route("**/*", async (r) => {
    const u = new URL(r.request().url());
    if (u.origin !== ORIGIN) return r.abort();
    if (u.pathname === "/") return r.fulfill({ contentType: "text/html", body: '<!doctype html><meta charset="utf-8">' });
    if (u.pathname === "/renderer.js") return r.fulfill({ contentType: "text/javascript", body: rendererJs });
    const m = /^\/fonts\/([0-9a-f]{64})\.woff2$/.exec(u.pathname);
    if (m) return readFile(join(CLI, "dist/fonts", `${m[1]}.woff2`)).then((b) => r.fulfill({ contentType: "font/woff2", body: b }), () => r.abort());
    return r.abort();
  });
  await page.goto(`${ORIGIN}/`);

  const texts = els.filter((e) => e.type === "text");
  const measure = async () => {
    const res = await page.evaluate(({ items, css }) => {
      const c = document.createElement("canvas").getContext("2d");
      return items.map(({ id, text, size }) => {
        c.font = `${size}px ${css}`;
        const lines = text.split("\n");
        return { id, w: Math.max(...lines.map((l) => c.measureText(l).width)), n: lines.length };
      });
    }, { items: texts.map((t) => ({ id: t.id, text: t.text, size: t.fontSize })), css: FONT_CSS });
    const byId = new Map(res.map((r) => [r.id, r]));
    for (const t of texts) { const r = byId.get(t.id); t.width = r.w; t.height = t.fontSize * LH * r.n; }
  };
  await measure();
  for (const t of texts) if (t._lay?.fit) t.fontSize = Math.round((t.fontSize * t._lay.fit) / t.width * 10) / 10;
  await measure();

  // resolve positions
  for (const t of texts) {
    const L = t._lay;
    if (!L || L.skip) continue;
    if (L.bound) {
      const k = L.bound;
      t.x = k.x + (k.width - t.width) / 2 + L.dx;
      t.y = k.y + (k.height - t.height) / 2;
    } else if (t._math) {
      const { lo, hi } = t._math;
      const wSmall = Math.max(lo?.width ?? 0, hi?.width ?? 0);
      const W = t.width + 1 + wSmall;
      t.x = L.x - W / 2; t.y = L.y - t.height / 2;
      if (lo) { lo.x = t.x + t.width + 1; lo.y = t.y + t.height * 0.5; }
      if (hi) { hi.x = t.x + t.width + 1; hi.y = t.y - t.height * 0.16; }
    } else {
      const a = L.anchor;
      t.x = a.startsWith("l") ? L.x : L.x - t.width / 2;
      t.y = a === "lt" ? L.y : L.y - t.height / 2;
    }
  }
  for (const e of els) { delete e._lay; delete e._math; }
  for (const e of els) for (const k of ["x", "y", "width", "height"]) e[k] = Math.round(e[k] * 100) / 100;

  const appState = { viewBackgroundColor: "#ffffff", exportBackground: true, exportWithDarkMode: false, gridSize: 20, gridModeEnabled: false };
  const scene = { type: "excalidraw", version: 2, source: "https://excalidraw.com", elements: els, appState, files: {} };
  await writeFile(OUT.scene, JSON.stringify(scene, null, 2) + "\n");
  await writeFile(OUT.manifest, JSON.stringify(manifest, null, 2) + "\n");

  const svg = await page.evaluate(async ({ elements, appState }) => {
    const lib = await import("/renderer.js");
    const node = await lib.exportToSvg({ data: { elements, appState: { ...appState, exportEmbedScene: true }, files: {} }, config: { padding: 20 } });
    return node.outerHTML;
  }, { elements: els, appState });
  await writeFile(OUT.svg, svg + "\n");
} finally {
  await browser.close();
}

execFileSync("excalidraw", ["render", OUT.scene, "--out", OUT.png, "--scale", "2", "--max-width", "8192", "--max-height", "8192", "--padding", "20"], { stdio: "inherit" });
console.log(`elements: ${els.length}  modules: ${Object.keys(manifest.modules).length}  labels: ${Object.keys(manifest.labels).length}  free texts: ${manifest.texts.length}`);
