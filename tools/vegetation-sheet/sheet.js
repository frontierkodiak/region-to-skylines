const response = await fetch("sheet-data.json");
if (!response.ok) throw new Error("Sheet data unavailable");
const data = await response.json(), root = document.querySelector("#squares"), percent = (v) => Number.isFinite(v) ? `${Math.round(v * 100)}%` : "—";
document.querySelector("#date").textContent = data.generated_at.slice(0, 10);
let mode = "canopy";
function render() {
  root.replaceChildren();
  for (const square of data.squares) {
    const s = square.summary, article = document.createElement("article"), h = s.canopy.height_m;
    const title = document.createElement("h2"); title.textContent = square.name;
    const canvas = document.createElement("canvas"); canvas.width = canvas.height = square.grid.size;
    canvas.setAttribute("aria-label", `${square.name} ${mode === "height" ? "canopy height" : "canopy cover"}`);
    const context = canvas.getContext("2d"), pixels = context.createImageData(canvas.width, canvas.height);
    for (let i = 0; i < square.canopy.length; i++) {
      const raw = square[mode][i], v = mode === "height" ? Math.min(1, raw / 40) : raw;
      pixels.data.set(Number.isFinite(raw) ? [232 - v * 183, 238 - v * 125, 229 - v * 170, 255] : [180,179,176,255], 4 * i);
    }
    context.putImageData(pixels, 0, 0);
    const measure = document.createElement("p"); measure.className = "measure";
    measure.textContent = `${percent(s.canopy.cover)} canopy · ${Math.round(h.p50)} m median`;
    const genera = document.createElement("p"); genera.className = "genera";
    genera.textContent = s.composition.genus.slice(0,3).map((g) => `${g.genus} ${percent(g.share)}`).join(" · ") || "No local genus evidence";
    const detail = document.createElement("p"); detail.textContent = `Canopy p10–p90: ${Math.round(h.p10)}–${Math.round(h.p90)} m. Shrub ${percent(s.landcover.shrub_share)} · grass ${percent(s.landcover.grass_share)}.`;
    const forms = document.createElement("p"); forms.className = "coverage";
    const mix = s.tree_forms.growth_forms;
    forms.textContent = `Tree forms: needles ${percent(mix.needleleaf_evergreen)} · deciduous ${percent(mix.broadleaf_deciduous)} · evergreen broadleaf ${percent(mix.broadleaf_evergreen)} · palm ${percent(mix.palm)} · unknown ${percent(mix.unknown)}.`;
    const coverage = document.createElement("p"); coverage.className = "coverage";
    coverage.textContent = `${percent(s.canopy.coverage.fraction)} imagery · ${percent(s.composition.coverage.fraction)} local genus coverage`;
    const link = document.createElement("a"); link.href = `${square.slug}.json.gz`; link.textContent = "Cell expectations (.json.gz)";
    article.append(title,canvas,measure,genera,detail,forms,coverage,link); root.append(article);
  }
}
document.querySelectorAll('[name="view"]').forEach((input) => input.addEventListener("change", () => { mode = input.value; render(); }));
render();
const benchmark = await (await fetch("final_source_pool_benchmark.json")).json();
const rejected = await (await fetch("production_benchmark.json")).json();
const table = document.createElement("table");
table.innerHTML = "<thead><tr><th>City</th><th>Blocks</th><th>Regional</th><th>Rejected local</th><th>Final fallback</th></tr></thead>";
const body = document.createElement("tbody");
for (const [city, result] of Object.entries(benchmark.sources)) {
  const row = document.createElement("tr");
  for (const value of [city === "boston" ? "Boston" : "Asheville", result.heldout_blocks, result.regional.tvd.toFixed(3), rejected.sources[city].local.tvd.toFixed(3), result.local.tvd.toFixed(3)]) {
    const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
  }
  body.append(row);
}
table.append(body); document.querySelector("#accuracy").append(table);
document.querySelector("#verdict").textContent = "The first nearest-neighbour model lost to the regional inventory baseline in both cities. Inventory gaps now use the source-wide mix; observed local inventory counts are kept where available.";
window.vegetationSheet = { data, benchmark };
