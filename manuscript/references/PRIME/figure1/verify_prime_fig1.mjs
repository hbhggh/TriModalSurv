#!/usr/bin/env node
// Structural + text-metric checks for PRIME_Figure1_Editable.excalidraw (run after build_prime_fig1.mjs).
// Exit code 1 if any check fails.
import { readFile } from "node:fs/promises";
import { inflateSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const scene = JSON.parse(await readFile(join(HERE, "PRIME_Figure1_Editable.excalidraw"), "utf8"));
const manifest = JSON.parse(await readFile(join(HERE, "module_manifest.json"), "utf8"));
const svg = await readFile(join(HERE, "PRIME_Figure1_Preview.svg"), "utf8");
const png = await readFile(join(HERE, "PRIME_Figure1_Preview.png"));

const fails = [];
const check = (ok, msg) => { if (!ok) fails.push(msg); };
const els = scene.elements;
const byId = new Map(els.map((e) => [e.id, e]));
const PAD = 5; // Excalidraw BOUND_TEXT_PADDING

// ---- 1. structure
check(scene.type === "excalidraw" && scene.version === 2, "scene type/version");
check(Object.keys(scene.files ?? {}).length === 0, "files must be empty (no embedded bitmaps)");
check(!els.some((e) => e.type === "image" || e.type === "embeddable" || e.type === "iframe"), "no image/embeddable elements");
check(!els.some((e) => e.locked), "no locked elements");
check(byId.size === els.length, "element ids unique");
for (const e of els) {
  if (e.type === "text") check(e.text.trim().length > 0 && e.width > 0 && e.height > 0, `text ${e.id} empty or unmeasured`);
  if (e.containerId) {
    const k = byId.get(e.containerId);
    check(k && (k.boundElements ?? []).some((b) => b.id === e.id && b.type === "text"), `bound text ${e.id} ↔ container`);
  }
  for (const b of e.boundElements ?? []) {
    const t = byId.get(b.id);
    if (b.type === "text") check(t?.containerId === e.id, `container ${e.id} → text ${b.id}`);
    if (b.type === "arrow") check(t?.startBinding?.elementId === e.id || t?.endBinding?.elementId === e.id, `target ${e.id} → arrow ${b.id}`);
  }
  for (const k of ["startBinding", "endBinding"]) if (e[k]) {
    const t = byId.get(e[k].elementId);
    check(t && (t.boundElements ?? []).some((b) => b.id === e.id), `arrow ${e.id} ${k} → ${e[k].elementId}`);
  }
}
// every module's elements carry the module group id; nothing else carries it
const membersOf = (gid) => els.filter((e) => e.groupIds.includes(gid)).map((e) => e.id).sort();
for (const [kind, table] of [["modules", manifest.modules], ["labels", manifest.labels]]) {
  for (const [name, ids] of Object.entries(table)) {
    const got = membersOf(`g.${name}`);
    check(JSON.stringify(got) === JSON.stringify([...ids].sort()), `${kind} ${name}: group members ≠ manifest`);
    check(ids.length >= 2 || kind === "modules", `${kind} ${name} has < 2 elements`);
  }
}
for (const id of manifest.texts) check(byId.get(id)?.groupIds.length === 0, `free text ${id} must be ungrouped`);

// ---- 2. text metrics (V29)
const rotBox = (e) => { // axis-aligned bbox of a rotated rect
  const cx = e.x + e.width / 2, cy = e.y + e.height / 2, c = Math.abs(Math.cos(e.angle)), s = Math.abs(Math.sin(e.angle));
  const hw = (e.width * c + e.height * s) / 2, hh = (e.width * s + e.height * c) / 2;
  return [cx - hw, cy - hh, cx + hw, cy + hh];
};
const lineBox = (e) => {
  const xs = e.points.map((p) => e.x + p[0]), ys = e.points.map((p) => e.y + p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
};
const box = (e) => (e.points ? lineBox(e) : rotBox(e));
const inside = (a, b, tol = 0.5) => a[0] >= b[0] - tol && a[1] >= b[1] - tol && a[2] <= b[2] + tol && a[3] <= b[3] + tol;
const overlap = (a, b) => Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > 0.5 && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > 0.5;

// 2a. bound text fits its container with Excalidraw's padding (else the editor re-wraps it)
for (const t of els.filter((e) => e.containerId)) {
  const k = byId.get(t.containerId);
  check(t.width <= k.width - 2 * PAD + 0.01 && t.height <= k.height - 2 * PAD + 0.01,
    `bound text ${t.id} (${t.width.toFixed(1)}×${t.height.toFixed(1)}) exceeds ${k.id} inner (${(k.width - 2 * PAD).toFixed(1)}×${(k.height - 2 * PAD).toFixed(1)})`);
}
// 2b. no two independent text blocks overlap (a math label counts as one block)
const labelOf = new Map();
for (const [name, ids] of Object.entries(manifest.labels)) for (const id of ids) labelOf.set(id, name);
const blocks = new Map();
for (const t of els.filter((e) => e.type === "text" && !e.containerId)) {
  const key = labelOf.get(t.id) ?? t.id, b = rotBox(t);
  const cur = blocks.get(key);
  blocks.set(key, cur ? [Math.min(cur[0], b[0]), Math.min(cur[1], b[1]), Math.max(cur[2], b[2]), Math.max(cur[3], b[3])] : b);
}
const B = [...blocks.entries()];
for (let i = 0; i < B.length; i++) for (let j = i + 1; j < B.length; j++)
  check(!overlap(B[i][1], B[j][1]), `text blocks overlap: ${B[i][0]} × ${B[j][0]}`);
// 2c. texts that belong inside a shape stay inside it
const within = [
  ["wsi.backbone.text", "wsi.backbone.shape"], ["report.backbone.text", "report.backbone.shape"], ["rna.backbone.text", "rna.backbone.shape"],
  ["mid.memoryBank.title", "mid.memoryBank.box"], ["pre.backbone.text", "pre.backbone.box"],
  ["legend.missing.text", "legend.box"], ["legend.aggregate.text", "legend.box"],
  ["pre.alignIT.viT.label", "pre.alignIT.viT"], ["pre.alignIT.vjT.label", "pre.alignIT.vjT"], ["pre.alignTR.vjT.label", "pre.alignTR.vjT"],
  ["pre.alignIR.viR.label", "pre.alignIR.viR"], ["pre.alignTR.viR.label", "pre.alignTR.viR"], ["pre.alignTR.vjR.label", "pre.alignTR.vjR"],
  ...[0, 1, 3, 4].flatMap((k) => [[`pre.h1row.cell${k}.label`, `pre.h1row.cell${k}`], [`pre.h2col.cell${k}.label`, `pre.h2col.cell${k}`]]),
];
for (const [tid, sid] of within) {
  const tb = blocks.get(tid), s = byId.get(sid);
  check(tb && s && inside(tb, box(s)), `${tid} not inside ${sid}`);
}

// ---- 3. exports
check(svg.includes("svg-source:excalidraw") && svg.includes("payload-start"), "SVG lacks embedded scene");
try {
  const b64 = svg.split("<!-- payload-start -->")[1].split("<!-- payload-end -->")[0].trim();
  const outer = JSON.parse(Buffer.from(b64, "base64").toString("latin1"));
  const inner = outer.compressed ? inflateSync(Buffer.from(outer.encoded, "latin1")).toString("utf8") : outer.encoded;
  const emb = JSON.parse(inner);
  const a = emb.elements.map((e) => e.id).sort().join(), b = els.map((e) => e.id).sort().join();
  check(a === b, `SVG embedded scene ids differ (svg ${emb.elements.length} vs scene ${els.length})`);
} catch (err) { check(false, `SVG payload decode failed: ${err.message}`); }
check(png.subarray(1, 4).toString() === "PNG", "PNG signature");
const pw = png.readUInt32BE(16), ph = png.readUInt32BE(20);
check(pw > 3000 && ph > 1300, `PNG size ${pw}×${ph}`);

const count = (t) => els.filter((e) => e.type === t).length;
console.log(`elements ${els.length} (rect ${count("rectangle")}, ellipse ${count("ellipse")}, line ${count("line")}, arrow ${count("arrow")}, text ${count("text")})`);
console.log(`modules ${Object.keys(manifest.modules).length}, math labels ${Object.keys(manifest.labels).length}, free texts ${manifest.texts.length}, bound texts ${els.filter((e) => e.containerId).length}, bound arrows ${els.filter((e) => e.startBinding || e.endBinding).length}`);
console.log(`PNG ${pw}×${ph}, SVG ${(svg.length / 1024).toFixed(0)} KB`);
if (fails.length) { console.log(`FAIL (${fails.length})`); for (const f of fails) console.log("  - " + f); process.exit(1); }
console.log("PASS");
