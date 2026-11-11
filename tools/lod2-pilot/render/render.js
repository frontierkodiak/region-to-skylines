// One renderer for every arm, so appearance never differs between them: the PL-881 hybrid
// atlas (siding, brick, stone, shingle) tiled at its recorded metre scale, walls by the
// building's recorded wall material, every up-facing face shingle. No windows, doors or
// trim in any arm. Views: "city" (pixel-asheville's default camera: orthographic, azimuth
// -40, elevation 30, 2.8 art pixels per metre, no antialiasing), "close" (same direction,
// building fills the frame) and "top" (straight down, north up).
import * as THREE from "three";

const SCALE = { siding: [1.5, 1.4], brick: [1.6, 0.9], roof: [2.0, 1.2], stone: [1.5, 1.2] };
const WALL_OF = { brick: "brick", stone: "stone", concrete: "stone" };
const DEG = Math.PI / 180;
// Two renderers for the page's life (a browser allows only a few WebGL contexts).
const renderers = {};
function rendererFor(view) {
  const key = view === "city" ? "plain" : "smooth";
  if (!renderers[key]) {
    const canvas = document.createElement("canvas");
    document.body.append(canvas);
    const r = new THREE.WebGLRenderer({ canvas, antialias: key === "smooth", preserveDrawingBuffer: true });
    r.setPixelRatio(1);
    r.shadowMap.enabled = true;
    r.shadowMap.type = key === "plain" ? THREE.BasicShadowMap : THREE.PCFSoftShadowMap;
    renderers[key] = r;
  }
  return renderers[key];
}
const loader = new THREE.TextureLoader();
const textures = {};
async function texture(name, base) {
  if (!textures[name]) {
    const t = await loader.loadAsync(`${base}/${name}.png`);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    t.magFilter = THREE.LinearFilter;
    textures[name] = t;
  }
  return textures[name];
}

function armMesh(arm, material, tex, sharp) {
  const groups = { roof: [], wall: [] };
  const uv = { roof: [], wall: [] };
  const up = new THREE.Vector3(0, 1, 0), a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const n = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
  for (let t = 0; t < arm.kind.length; t++) {
    const k = arm.kind[t] === "roof" ? "roof" : "wall", p = arm.tri, o = t * 9;
    a.set(p[o], p[o + 1], p[o + 2]); b.set(p[o + 3], p[o + 4], p[o + 5]); c.set(p[o + 6], p[o + 7], p[o + 8]);
    n.subVectors(b, a).cross(e1.subVectors(c, a)).normalize();
    const [sx, sy] = SCALE[k === "roof" ? "roof" : material];
    if (k === "roof") {
      e1.crossVectors(up, n);
      if (e1.lengthSq() < 1e-6) e1.set(1, 0, 0);
      e1.normalize();
      e2.crossVectors(n, e1);
    } else {
      e1.crossVectors(up, n);
      if (e1.lengthSq() < 1e-6) e1.set(1, 0, 0);
      e1.normalize();
      e2.copy(up);
    }
    for (const v of [a, b, c]) {
      groups[k].push(v.x, v.y, v.z);
      uv[k].push(v.dot(e1) / sx, v.dot(e2) / sy);
    }
  }
  const out = new THREE.Group();
  for (const k of ["roof", "wall"]) {
    if (!groups[k].length) continue;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(groups[k], 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uv[k], 2));
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ map: tex[k], side: THREE.DoubleSide, flatShading: true }));
    m.castShadow = m.receiveShadow = true;
    out.add(m);
  }
  return out;
}

function fieldMesh(f, half, colourOf) {
  const n = f.n, pos = [], col = [], idx = [];
  const y = (i, j) => f.y[Math.min(n - 1, j) * n + Math.min(n - 1, i)];
  for (let j = 0; j < n; j++)
    for (let i = 0; i < n; i++) {
      pos.push(-half + (i + 0.5) * f.cell, y(i, j), -half + (j + 0.5) * f.cell);
      col.push(...colourOf(j * n + i));
    }
  for (let j = 0; j < n - 1; j++)
    for (let i = 0; i < n - 1; i++) {
      const q = j * n + i;
      idx.push(q, q + n, q + 1, q + 1, q + n, q + n + 1);
    }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }));
  m.receiveShadow = true;
  return m;
}

// what: an arm name, or "ref" for the lidar first-surface reference.
window.renderScene = async (scene, what, view, base, opts = {}) => {
  const material = WALL_OF[scene.wall] ?? "siding";
  const tex = { roof: await texture("roof", base), wall: await texture(material, base) };
  const world = new THREE.Scene();
  world.background = new THREE.Color("#cfd8dc");
  world.add(new THREE.HemisphereLight("#dce3f0", "#8a7f68", 1.5));
  const sun = new THREE.DirectionalLight("#fff1d6", 2.4);
  sun.position.set(-0.55, 0.75, 0.35).multiplyScalar(300);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  const S = scene.half * 1.6;
  Object.assign(sun.shadow.camera, { left: -S, right: S, top: S, bottom: -S, near: 1, far: 800 });
  sun.shadow.bias = -0.0005;
  sun.shadow.normalBias = 0.05;
  world.add(sun, sun.target);
  let top = 0;
  if (what === "ref") {
    const C = [[0.52, 0.56, 0.42], [0.33, 0.5, 0.3], [0.8, 0.79, 0.76]];
    const m = fieldMesh(scene.dsm, scene.half, (q) => C[scene.dsm.cls[q]]);
    m.castShadow = true;
    world.add(m);
  } else {
    world.add(fieldMesh(scene.dtm, scene.half, () => [0.52, 0.56, 0.42]));
    const arm = scene.arms[what];
    if (arm) world.add(armMesh(arm, material, tex, view === "city"));
  }
  // frame on the outline and the tallest arm, the same for every arm of a building
  let r = 0;
  for (const [x, z] of scene.ring) r = Math.max(r, Math.hypot(x, z));
  for (const arm of Object.values(scene.arms)) for (let i = 1; i < arm.tri.length; i += 3) top = Math.max(top, arm.tri[i]);
  top = Math.min(top, opts.maxTop ?? 60);
  const az = (opts.az ?? -40) * DEG, el = (view === "top" ? 90 : opts.el ?? 30) * DEG;
  const target = new THREE.Vector3(0, top * 0.4, 0);
  const cam = new THREE.OrthographicCamera();
  cam.position.set(target.x + Math.sin(az) * Math.cos(el) * 400, target.y + Math.sin(el) * 400, target.z + Math.cos(az) * Math.cos(el) * 400);
  if (view === "top") cam.up.set(0, 0, -1);
  cam.lookAt(target);
  const halfW = view === "top" ? r + 4 : r + 5, halfH = view === "top" ? r + 4 : (r + 5) * Math.sin(el) + top * 0.6 * Math.cos(el) + 2;
  const ppm = view === "city" ? 2.8 : Math.min(40, (view === "top" ? 420 : 860) / (2 * halfW));
  const W = Math.round(2 * halfW * ppm), H = Math.round(2 * halfH * ppm);
  Object.assign(cam, { left: -halfW, right: halfW, top: halfH, bottom: -halfH, near: 1, far: 1200 });
  cam.updateProjectionMatrix();
  const renderer = rendererFor(view);
  renderer.setSize(W, H, false);
  renderer.render(world, cam);
  const url = renderer.domElement.toDataURL("image/png");
  world.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
  sun.shadow.map?.dispose();
  return { url, W, H };
};
window.ready = true;
