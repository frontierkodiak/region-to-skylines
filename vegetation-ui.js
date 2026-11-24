const percent = (v) => Number.isFinite(v) ? `${Math.round(v * 100)}%` : "—";
export const genusText = (composition) => composition?.genus?.slice(0, 3).map((g) => `${g.genus} ${percent(g.share)}`).join(" · ") || "Genera not recorded nearby";

export function paintCanopy(canvas, report) {
  const n = report.grid.size;
  canvas.width = n; canvas.height = n;
  const context = canvas.getContext("2d"), pixels = context.createImageData(n, n);
  for (let i = 0; i < report.cells.length; i++) {
    const value = report.cells[i].canopy.cover, valid = Number.isFinite(value);
    pixels.data.set(valid ? [232 - value * 183, 238 - value * 125, 229 - value * 170, 255] : [180, 179, 176, 255], i * 4);
  }
  context.putImageData(pixels, 0, 0);
}

export function mountVegetation(root) {
  const readout = root.querySelector(".vegetation-summary"), genera = root.querySelector(".vegetation-genera"),
    canvas = root.querySelector("canvas"), coverage = root.querySelector(".vegetation-coverage"),
    detail = root.querySelector(".vegetation-cell"), download = root.querySelector(".vegetation-download"), forms = root.querySelector(".vegetation-forms");
  let worker = null, report = null, sequence = 0;
  function reset() {
    worker?.terminate(); worker = null; sequence++; report = null;
    readout.textContent = "Checking vegetation…";
    genera.textContent = ""; coverage.textContent = ""; detail.textContent = ""; download.disabled = true;
    forms.textContent = "";
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    root.dataset.state = "loading";
  }
  function unavailable() {
    reset(); root.dataset.state = "unavailable";
    readout.textContent = "Vegetation unavailable";
    coverage.textContent = "Move the square to retry.";
  }
  function render(value) {
    report = value; worker?.terminate(); worker = null;
    const canopy = value.summary.canopy, composition = value.summary.composition;
    root.dataset.state = canopy.status === "available" ? "available" : "partial";
    const height = canopy.height_m;
    readout.textContent = `${percent(canopy.cover)} canopy${Number.isFinite(height?.p50) ? ` · ${Math.round(height.p50)} m median height` : ""}`;
    genera.textContent = genusText(composition);
    const mix = value.summary.tree_forms.growth_forms;
    forms.textContent = `Tree-form estimate: ${percent(mix.needleleaf_evergreen)} evergreen needles · ${percent(mix.broadleaf_deciduous)} deciduous broadleaf · ${percent(mix.broadleaf_evergreen)} evergreen broadleaf · ${percent(mix.palm)} palms · ${percent(mix.unknown)} unclassified. Land cover: ${percent(value.summary.landcover.shrub_share)} shrubs · ${percent(value.summary.landcover.grass_share)} grass.`;
    coverage.textContent = `${percent(canopy.coverage.fraction)} imagery coverage · ${percent(composition.coverage.fraction)} with local genus records`;
    paintCanopy(canvas, value); download.disabled = false;
    detail.textContent = "";
  }
  canvas.addEventListener("pointermove", (event) => {
    if (!report) return;
    const rect = canvas.getBoundingClientRect(), n = report.grid.size;
    const col = Math.min(n - 1, Math.max(0, Math.floor((event.clientX - rect.left) / rect.width * n)));
    const row = Math.min(n - 1, Math.max(0, Math.floor((event.clientY - rect.top) / rect.height * n)));
    const cell = report.cells[row * n + col];
    detail.textContent = `${Math.round(report.grid.cell_m)} m cell · ${percent(cell.canopy.cover)} canopy · ${genusText(cell.composition)}`;
  });
  download.addEventListener("click", () => {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "vegetation.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  function update(square) {
    reset(); const current = sequence;
    worker = new Worker(new URL("./vegetation-worker.js", import.meta.url), { type: "module" });
    worker.onmessage = ({ data }) => { if (current !== sequence) return; data.report ? render(data.report) : unavailable(); };
    worker.onerror = () => { if (current === sequence) unavailable(); };
    worker.postMessage(square);
  }
  return { reset, update, unavailable, render };
}
