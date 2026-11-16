"use strict";

const ROAD_SERIES = [
  ["local roads", ["road (small)"], "--s1"],
  ["highways", ["highway"], "--s2"],
  ["arterials", ["road (medium)", "road (large)"], "--s3"],
  ["rail", ["rail"], "--s4"],
  ["metro", ["metro"], "--s5"],
  ["paths", ["path"], "--s6"],
];
const ZONE_SERIES = [
  ["residential", ["ResidentialLow", "ResidentialHigh"], "--s3"],
  ["commercial", ["CommercialLow", "CommercialHigh"], "--s1"],
  ["industrial", ["Industrial"], "--s4"],
  ["office", ["Office"], "--s7"],
];
const ZONE_CODE = { 2: "residential", 3: "residential", 4: "commercial", 5: "commercial", 6: "industrial", 7: "office" };
const MAP_LEGEND = [
  ["Residential", "#80c460"], ["Commercial", "#6eaae6"], ["Industrial", "#e8c440"], ["Office", "#60c8ce"],
  ["Services", "#9659be"], ["Highway", "#d67834", "line"], ["Road", "#7c7c82", "line"], ["Rail", "#804a8a", "line"],
];
const DIFF_LEGEND = [["Added", "#e63c8c"], ["New zoning", "#e8c440"], ["Removed", "#1e1e1e", "line"], ["Before", "#c9c7c2"]];

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n, d = 0) => (n == null ? "–" : Number(n).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }));
const day = (iso) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
const dayTime = (iso) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const gameDate = (iso) => iso.slice(0, 10);
const ROAD_NAMES = { "road (small)": "local road", "road (medium)": "medium road", "road (large)": "large road" };
const roadName = (k) => ROAD_NAMES[k] || k;
const sum = (obj, keys) => keys.reduce((a, k) => a + (obj && obj[k] ? obj[k] : 0), 0);

let DATA, series, index = 0, showChanges = true, wholeMap = false;

fetch("data.json").then((r) => r.json()).then((d) => {
  DATA = d;
  const tabs = document.getElementById("tabs");
  d.series.forEach((s, i) => {
    const b = document.createElement("button");
    b.textContent = s.name;
    b.onclick = () => select(i);
    tabs.appendChild(b);
  });
  document.getElementById("slider").oninput = (e) => show(+e.target.value);
  document.getElementById("changes").onclick = (e) => {
    showChanges = !showChanges;
    e.target.setAttribute("aria-pressed", showChanges);
    show(index);
  };
  document.getElementById("view").onclick = (e) => {
    wholeMap = !wholeMap;
    e.target.setAttribute("aria-pressed", wholeMap);
    show(index);
  };
  document.getElementById("zoom").onclick = (e) => {
    const w = document.getElementById("mapwrap");
    const on = !w.classList.contains("zoomed");
    w.classList.toggle("zoomed", on);
    e.target.setAttribute("aria-pressed", on);
  };
  document.getElementById("foot").textContent = d.footer || "";
  select(0);
});

function select(i) {
  series = DATA.series[i];
  [...document.getElementById("tabs").children].forEach((b, j) => b.setAttribute("aria-pressed", i === j));
  const saves = series.saves;
  const first = saves[0].saved_at, last = saves[saves.length - 1].saved_at;
  const time = (iso) => new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  const span = day(first) === day(last) ? `${day(first)}, ${time(first)} to ${time(last)}` : `${day(first)} to ${day(last)}`;
  document.getElementById("subtitle").textContent = `${saves.length} saves, ${span} · map: ${series.map}`;
  const slider = document.getElementById("slider");
  slider.max = saves.length - 1;
  charts();
  observations();
  show(saves.length - 1);
}

function show(i) {
  index = i;
  const s = series.saves[i];
  document.getElementById("slider").value = i;
  const diff = showChanges && s.diff_image;
  const img = document.getElementById("map");
  const core = !wholeMap && s.core_image;
  img.src = diff ? (core ? s.core_diff_image : s.diff_image) : (core ? s.core_image : s.image);
  img.alt = `${series.name}, save ${i + 1}`;
  document.getElementById("stamp").innerHTML =
    `<span>Saved <b>${dayTime(s.saved_at)}</b></span><span>Population <b>${fmt(s.population)}</b></span>` +
    `<span>In game <b>${gameDate(s.game_date)}</b></span><span>Save <b>${i + 1}/${series.saves.length}</b></span>`;
  document.getElementById("change").innerHTML = changeText(s, i);
  legend(diff);
  document.querySelectorAll(".chart").forEach((c) => c._mark && c._mark(i));
}

function changeText(s, i) {
  if (i === 0) return "First save in this series.";
  const c = s.change;
  const prev = series.saves[i - 1];
  const km = Object.values(c.road_km_added).reduce((a, b) => a + b, 0);
  const parts = [];
  const byType = Object.entries(c.road_km_added).filter(([, v]) => v >= 0.05).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${fmt(v, 1)} ${roadName(k)}`).join(", ");
  parts.push(`<b>+${fmt(km, 1)} km</b> of network${byType ? ` (${byType})` : ""}`);
  if (c.road_km_removed >= 0.05) parts.push(`${fmt(c.road_km_removed, 1)} km removed`);
  const zones = {};
  for (const [code, n] of Object.entries(c.zone_cells_added)) {
    const z = ZONE_CODE[code];
    if (z) zones[z] = (zones[z] || 0) + n;
  }
  const zTotal = Object.values(zones).reduce((a, b) => a + b, 0);
  if (zTotal) {
    const zs = Object.entries(zones).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${fmt(v * 64e-6, 2)} ${k}`).join(", ");
    parts.push(`<b>+${fmt(zTotal * 64e-6, 2)} km²</b> zoned (${zs})`);
  }
  const placed = Object.entries(c.buildings_added).filter(([k]) => k !== "growable").reduce((a, [, v]) => a + v, 0);
  const grown = c.buildings_added.growable || 0;
  parts.push(`<b>${fmt(grown)}</b> new growables, <b>${fmt(placed)}</b> placed buildings`);
  const hours = (new Date(s.saved_at) - new Date(prev.saved_at)) / 3.6e6;
  return `Since ${dayTime(prev.saved_at)} (${hours < 48 ? fmt(hours, 1) + " h" : fmt(hours / 24, 1) + " days"} later): ` + parts.join("; ") + ".";
}

function legend(diff) {
  const items = diff ? DIFF_LEGEND : MAP_LEGEND;
  document.getElementById("legend").innerHTML = items.map(([n, c, kind]) =>
    `<span><i class="${kind || ""}" style="background:${c}"></i>${n}</span>`).join("");
}

// Charts ---------------------------------------------------------------------

function charts() {
  const saves = series.saves;
  const t = saves.map((s) => new Date(s.saved_at).getTime());
  lineChart(document.getElementById("pop"), t, saves.map((s) => s.population), (i) =>
    `${dayTime(saves[i].saved_at)} · ${fmt(saves[i].population)} people`);
  const roads = ROAD_SERIES.map(([name, keys, color]) => ({ name, color: css(color), values: saves.map((s) => sum(s.road_km, keys)) }))
    .filter((r) => r.values.some((v) => v > 0.05));
  stackChart(document.getElementById("roads"), t, roads, (v) => fmt(v, 1));
  const zones = ZONE_SERIES.map(([name, keys, color]) => ({ name, color: css(color), values: saves.map((s) => sum(s.zone_km2, keys)) }));
  stackChart(document.getElementById("zones"), t, zones, (v) => fmt(v, 2));
  servicesTable();
}

const W = 640, H = 190, M = { l: 44, r: 92, t: 10, b: 24 };

function scaleX(t) {
  const t0 = t[0], t1 = t[t.length - 1];
  return (v) => M.l + ((v - t0) / Math.max(1, t1 - t0)) * (W - M.l - M.r);
}
function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
function axes(t, ymax, yfmt) {
  const x = scaleX(t);
  const y = (v) => H - M.b - (v / ymax) * (H - M.t - M.b);
  let g = `<g class="axis">`;
  for (let k = 0; k <= 4; k++) {
    const v = (ymax * k) / 4;
    g += `<line x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}" stroke-width="1"/>`;
    g += `<text x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${yfmt(v)}</text>`;
  }
  const days = new Set();
  t.forEach((v) => {
    const d = day(new Date(v).toISOString());
    if (days.has(d)) return;
    days.add(d);
  });
  const ticks = [...days];
  const step = Math.ceil(ticks.length / 6);
  ticks.forEach((d, k) => {
    if (k % step) return;
    const v = t.find((tt) => day(new Date(tt).toISOString()) === d);
    g += `<text x="${x(v)}" y="${H - 6}" text-anchor="middle">${d}</text>`;
  });
  return { g: g + "</g>", x, y };
}

function hover(el, svgW, xs, label, markExtra) {
  const tip = document.createElement("div");
  tip.className = "tip";
  el.appendChild(tip);
  const svg = el.querySelector("svg");
  const cursor = svg.querySelector(".cursor");
  const pick = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * svgW;
    let best = 0;
    xs.forEach((v, i) => { if (Math.abs(v - px) < Math.abs(xs[best] - px)) best = i; });
    return best;
  };
  const place = (i) => {
    const r = svg.getBoundingClientRect();
    cursor.setAttribute("x1", xs[i]); cursor.setAttribute("x2", xs[i]); cursor.style.display = "";
    tip.innerHTML = label(i);
    tip.style.display = "block";
    const left = (xs[i] / svgW) * r.width;
    tip.style.left = Math.min(Math.max(left, 70), r.width - 70) + "px";
    tip.style.top = "6px";
  };
  svg.addEventListener("pointermove", (ev) => place(pick(ev)));
  svg.addEventListener("pointerleave", () => { tip.style.display = "none"; cursor.style.display = "none"; });
  svg.addEventListener("click", (ev) => show(pick(ev)));
  el._mark = markExtra;
}

function lineChart(el, t, vals, label) {
  const ymax = niceMax(Math.max(...vals));
  const yfmt = (v) => (ymax >= 10000 ? fmt(v / 1000) + "k" : fmt(v));
  const { g, x, y } = axes(t, ymax, yfmt);
  const xs = t.map(x);
  const pts = vals.map((v, i) => `${xs[i]},${y(v)}`).join(" ");
  const c = css("--s1");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Population by save">${g}
    <line class="cursor" y1="${M.t}" y2="${H - M.b}" stroke="${css("--text-3")}" stroke-dasharray="3 3" style="display:none"/>
    <polyline fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" points="${pts}"/>
    ${vals.map((v, i) => `<circle class="pt" data-i="${i}" cx="${xs[i]}" cy="${y(v)}" r="4" fill="${c}" stroke="${css("--surface")}" stroke-width="2"/>`).join("")}
    <circle class="sel" r="7" fill="none" stroke="${css("--text")}" stroke-width="2"/>
    <text class="label" x="${xs[xs.length - 1] + 8}" y="${y(vals[vals.length - 1]) + 4}">${fmt(vals[vals.length - 1])}</text>
  </svg>${table(["Saved", "Population"], t.map((tt, i) => [dayTime(series.saves[i].saved_at), fmt(vals[i])]))}`;
  const sel = el.querySelector(".sel");
  hover(el, W, xs, label, (i) => { sel.setAttribute("cx", xs[i]); sel.setAttribute("cy", y(vals[i])); });
}

function stackChart(el, t, rows, vfmt) {
  const n = t.length;
  const totals = t.map((_, i) => rows.reduce((a, r) => a + r.values[i], 0));
  const ymax = niceMax(Math.max(...totals));
  const { g, x, y } = axes(t, ymax, (v) => (ymax >= 100 ? fmt(v) : vfmt(v)));
  const xs = t.map(x);
  let base = new Array(n).fill(0);
  let paths = "", labels = "";
  rows.forEach((r) => {
    const top = base.map((b, i) => b + r.values[i]);
    const upper = top.map((v, i) => `${xs[i]},${y(v)}`);
    const lower = base.map((v, i) => `${xs[i]},${y(v)}`).reverse();
    paths += `<polygon points="${upper.concat(lower).join(" ")}" fill="${r.color}" stroke="${css("--surface")}" stroke-width="1.5" stroke-linejoin="round"/>`;
    const last = r.values[n - 1];
    if (last / ymax > 0.05) labels += `<text class="label" x="${xs[n - 1] + 8}" y="${y(base[n - 1] + last / 2) + 4}">${r.name} ${vfmt(last)}</text>`;
    base = top;
  });
  const legendHtml = `<div class="legend">${rows.map((r) => `<span><i style="background:${r.color}"></i>${r.name}</span>`).join("")}</div>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">${g}${paths}
    <line class="cursor" y1="${M.t}" y2="${H - M.b}" stroke="${css("--text")}" stroke-width="1" style="display:none"/>
    <line class="sel" y1="${M.t}" y2="${H - M.b}" stroke="${css("--text")}" stroke-width="2" stroke-opacity="0.55"/>
    ${labels}</svg>${legendHtml}` +
    table(["Saved", ...rows.map((r) => r.name), "total"], t.map((_, i) => [dayTime(series.saves[i].saved_at), ...rows.map((r) => vfmt(r.values[i])), vfmt(totals[i])]));
  const sel = el.querySelector(".sel");
  hover(el, W, xs, (i) => `${dayTime(series.saves[i].saved_at)}<br>` +
    rows.slice().reverse().map((r) => `${r.name}: ${vfmt(r.values[i])}`).join("<br>") + `<br>total ${vfmt(totals[i])}`,
    (i) => { sel.setAttribute("x1", xs[i]); sel.setAttribute("x2", xs[i]); });
}

function table(head, rows) {
  return `<details><summary>Table</summary><table><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>` +
    rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + `</table></details>`;
}

const SERVICE_NAMES = {
  education: "Education", health: "Health", deathcare: "Deathcare", fire: "Fire", police: "Police",
  electricity: "Power", water_service: "Water", garbage: "Garbage", transport: "Transport stops & depots",
  park: "Parks & plazas", monument: "Landmarks & unique", industry: "Industry (specialised)", other: "Other",
};

function servicesTable() {
  const saves = series.saves;
  const keys = Object.keys(SERVICE_NAMES).filter((k) => saves.some((s) => s.services[k]));
  const pick = [0, Math.floor((saves.length - 1) / 2), saves.length - 1].filter((v, i, a) => a.indexOf(v) === i);
  const head = ["", ...pick.map((i) => day(saves[i].saved_at))];
  const rows = keys.map((k) => [SERVICE_NAMES[k], ...pick.map((i) => fmt(saves[i].services[k] || 0))]);
  rows.push(["Growable buildings", ...pick.map((i) => fmt(saves[i].growables))]);
  document.getElementById("services").innerHTML = `<table><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>` +
    rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + `</table>`;
}

function observations() {
  const list = (DATA.observations || {})[series.slug] || [];
  document.getElementById("obs").innerHTML = list.map((o) => `<li>${o}</li>`).join("");
}
