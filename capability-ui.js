import { captureEstimate } from "./capability-inputs.js";
import { checkCapabilities, stockComparison, STOCK_MEASURES } from "./capability-model.js";

const ICONS = {
  road: "M6 3 3 21M18 3l3 18M12 3v4m0 3v4m0 3v4",
  rail: "M7 3h10v14H7zM7 7h10M7 13h10M9 17l-4 4m10-4 4 4M7 20h10",
  ship: "M5 12V6h6v6m0-4h6v4M3 12l3 7h12l3-7-9-3-9 3m0 9q3-2 6 0t6 0 6 0",
  air: "m3 12 7-2 1-7h2l1 7 7 2v2l-7-1-1 6 3 2H8l3-2-1-6-7 1z",
  water: "M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12z",
  buildable: "m3 10 9-7 9 7M6 8v13h12V8M10 21v-7h4v7",
  resources: "m4 20 5-15 7-2 5 9-8 9-9-1zM9 5l4 16m3-18-3 18M4 20l17-8",
  trees: "m12 3-6 8h3l-5 7h6v3h4v-3h6l-5-7h3z",
};
const LABELS = { road: "Road", rail: "Rail", ship: "Ship", air: "Air", water: "Water", buildable: "Land", resources: "Resources", trees: "Trees" };
const LEVELS = { promised: ["✓", "Verified"], likely: ["≈", "Maybe"], not_possible_here: ["×", "No in this plan"], unknown: ["?", "Unknown"], loading: ["…", "Checking"] };
const REASONS = {
  initial_deep_corridor: "The initial water estimate has a broad deep corridor reaching two map-edge points and the central 25 tiles. The game's ship path and stable water still need checking.",
  no_corridor_in_estimate: "No broad deep corridor was found in the initial water estimate. This estimate cannot rule out another route or establish what remains wet in the game.",
  mapped_candidate_not_routed: "Mapped transport supplies a candidate. An outside route, legal grades and native pathfinding have not been established.",
  transport_not_established: "No transport candidate was established from the captured data. A synthetic route may still be possible.",
  not_evaluated: "This capability is not yet modeled for live checks.",
  dry_low_slope_samples: "Dry samples with local slope below 15%. This is not the game's buildable-area bar or a legal start-site check.",
};
const BANDS = { below_p25: "Below p25", typical: "Typical", above_p75: "Above p75", not_comparable: "Not comparable" };

// Place evidence reasons state the measured values and their scope. "Land
// cover", "recorded" and "suitability" are deliberate: none of these is the
// export's planted trees, resource bytes or a native check.
const pct = (value) => !Number.isFinite(value) ? "—" : value > 0 && value < 0.005 ? "<1%" : `${Math.round(value * 100)}%`;
const score = (value) => (Number.isFinite(value) ? String(Number(value.toFixed(2))) : "—");
const sampling = (evidence) => evidence.landcover.sample_m ? `${Math.round(evidence.landcover.sample_m)} m WorldCover sampling` : "WorldCover sampling";
const PLACE_DETAIL = {
  vegetation_suitability_candidate: (e) => `Tree cover on ${pct(e.vegetation.tree_cover_share_of_central_land)} of the central tiles' land, weighted suitability ${score(e.vegetation.tree_suitability)} at ${sampling(e)}. Land cover, not the export's planted trees.`,
  tree_support_below_candidate_threshold: (e) => `Tree cover on ${pct(e.vegetation.tree_cover_share_of_central_land)} of the central tiles' land, weighted suitability ${score(e.vegetation.tree_suitability)} at ${sampling(e)} — below the ${score(e.vegetation.candidate_min)} candidate level, so this stays unknown. Land cover, not the export's planted trees.`,
  no_tree_support_in_sampled_landcover: (e) => `No tree-supporting cover in this ${sampling(e)}, so trees stay unknown. The player can still plant them.`,
  no_landcover_evidence: () => "Land cover could not be loaded, so trees are unknown. Move the square to retry.",
  landcover_coverage_incomplete: (e) => `Land cover covers ${pct(e.landcover.coverage_of_central_land)} of the central tiles' land, too little to judge.`,
  no_central_land: () => "The central tiles have no dry land to judge trees on.",
  recorded_deposit_in_central_tiles: (e) => `${[
    e.deposits.ore.central ? `${e.deposits.ore.central} ore` : "",
    e.deposits.oil.central ? `${e.deposits.oil.central} oil` : "",
  ].filter(Boolean).join(" and ")} deposit${e.deposits.ore.central + e.deposits.oil.central === 1 ? "" : "s"} recorded in the central tiles (USGS MRDS). Records, not measured reserves.`,
  fertile_land_suitability_candidate: (e) => `Fertile-land suitability ${score(e.fertility.suitability)} from crop, grass, wetland and shrub cover; cropland ${pct(e.fertility.crop_share_of_central_land)} of the central tiles' land. Ore and oil are not established.`,
  fertile_cover_below_candidate_threshold: (e) => `Fertile-land suitability ${score(e.fertility.suitability)} and cropland ${pct(e.fertility.crop_share_of_central_land)} — below the ${score(e.fertility.candidate_min)} candidate level, too little support for a Maybe. Ore and oil are not established.`,
  recorded_deposit_outside_central_tiles: (e) => `${e.deposits.records} deposit${e.deposits.records === 1 ? "" : "s"} recorded in this square, none in the central tiles.`,
  no_recorded_deposit_or_fertile_cover: () => "No deposit recorded and no crop or pasture cover in this land-cover sample. A missing record is not absence.",
  deposit_evidence_unavailable: () => "No fertile cover found, and deposits could not be loaded. Unknown, not absent.",
  landcover_evidence_unavailable: () => "Deposits were checked; land cover could not be loaded, so fertile land is unknown.",
  no_place_evidence: () => "Neither land cover nor deposits could be loaded. Move the square to retry.",
};
/** The exact text a capability detail shows; exported so tests read the copy itself. */
export const placeDetail = (result) => (result?.evidence && PLACE_DETAIL[result.reason] ? PLACE_DETAIL[result.reason](result.evidence) : null);

export function mountCapabilities(root) {
  const row = root.querySelector(".capability-row"), detail = root.querySelector(".capability-detail"), status = root.querySelector(".capability-status");
  const stockNote = root.querySelector(".stock-basis"), stockList = root.querySelector(".stock-list");
  const ledger = fetch("./capabilities.json").then((r) => { if (!r.ok) throw new Error("Ledger unavailable"); return r.json(); });
  // Attach a rejection handler immediately, even if the first terrain build fails.
  ledger.catch(() => {});
  let controller = null, sequence = 0, active = null, catalog = null;
  const buttons = new Map(), stockRows = new Map();
  const show = (button) => { active = button; detail.textContent = button.title; detail.hidden = false; };
  const hide = () => { active = null; detail.hidden = true; };
  for (const [id, name] of Object.entries(LABELS)) {
    const button = document.createElement("button");
    button.type = "button"; button.dataset.capability = id; button.dataset.level = "loading";
    button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[id]}"/></svg><span class="capability-name">${name}</span><span class="capability-mark" aria-hidden="true">…</span>`;
    button.addEventListener("pointerenter", () => show(button)); button.addEventListener("focus", () => show(button));
    button.addEventListener("click", () => show(button));
    buttons.set(id, button); row.append(button);
  }
  for (const [id, measure] of Object.entries(STOCK_MEASURES)) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "stock-row"; button.dataset.metric = id; button.dataset.state = "checking";
    button.innerHTML = `<span class="stock-name">${measure.label}</span><span class="stock-value">…</span><span class="stock-band">Checking</span>`;
    button.addEventListener("pointerenter", () => show(button)); button.addEventListener("focus", () => show(button));
    button.addEventListener("click", () => show(button));
    stockRows.set(id, button); stockList.append(button);
  }
  root.addEventListener("pointerleave", () => { if (!root.contains(document.activeElement)) hide(); });
  root.addEventListener("focusout", (event) => { if (!root.contains(event.relatedTarget)) hide(); });
  root.addEventListener("keydown", (event) => { if (event.key === "Escape") hide(); });
  function resetStock(state = "checking") {
    for (const button of stockRows.values()) {
      button.dataset.state = state;
      button.querySelector(".stock-value").textContent = state === "unknown" ? "—" : "…";
      button.querySelector(".stock-band").textContent = state === "unknown" ? "Unknown" : "Checking";
      button.title = state === "unknown"
        ? "Against stock maps: this square's data could not be loaded."
        : "Against stock maps: checking this square.";
      button.setAttribute("aria-label", button.title);
    }
  }
  function reset(message = "Checking this square…") {
    controller?.abort(); sequence++;
    status.textContent = message;
    for (const [id, button] of buttons) {
      button.dataset.level = "loading";
      button.querySelector(".capability-mark").textContent = "…";
      button.title = `${LABELS[id]}: checking this square.`;
      button.setAttribute("aria-label", button.title);
    }
    resetStock();
    hide();
  }
  function unavailable() {
    controller?.abort(); sequence++;
    status.textContent = "Square check unavailable · move the square to retry.";
    for (const [id, button] of buttons) {
      button.dataset.level = "unknown"; button.querySelector(".capability-mark").textContent = "?";
      button.title = `${LABELS[id]}: unknown. This square's data could not be loaded.`;
      button.setAttribute("aria-label", button.title);
    }
    resetStock("unknown");
    detail.textContent = "";
    detail.hidden = true;
  }
  // Bounds come from the ledger with float noise (761.5999999999999); show them at display precision.
  const format = (value, unit) => unit === "%" ? `${Number(value.toFixed(1))}%`
    : unit === "fraction" ? `${Number((value * 100).toFixed(1))}%` : `${Number(value.toFixed(1))} m`;
  function renderStock(stock) {
    if (!catalog) return;
    const reference = catalog.stock_reference;
    stockNote.textContent = `${reference.maps} shipped maps · p25–p75 is typical`;
    const comparison = stockComparison(stock?.measures, reference, stock?.comparability);
    for (const [id, button] of stockRows) {
      const row = comparison[id], metric = reference.metrics[id], policy = stock?.comparability?.[id];
      const value = button.querySelector(".stock-value"), band = button.querySelector(".stock-band");
      if (!stock) {
        button.dataset.state = "unknown"; delete button.dataset.band;
        value.textContent = "—"; band.textContent = "Unknown";
        button.title = `${metric.name}: unknown. This square's data could not be loaded.`;
      } else if (!row.comparable) {
        button.dataset.state = "not_comparable"; delete button.dataset.band;
        value.textContent = "—"; band.textContent = BANDS.not_comparable;
        button.title = `${metric.name}: not comparable from this square's map-time capture. ${policy?.detail ?? ""} The ${reference.maps}-map comparison is made on the prepared map.`;
      } else if (row.value == null || row.band === "not_comparable") {
        button.dataset.state = "unknown"; delete button.dataset.band;
        value.textContent = "—"; band.textContent = "Unknown";
        button.title = `${metric.name}: unknown for this square.`;
      } else {
        const screening = policy?.basis?.includes("water_screening") ? " The dry mask uses capture-time water screening." : "";
        button.dataset.state = "measured"; button.dataset.band = row.band;
        value.textContent = format(row.value, row.unit); band.textContent = BANDS[row.band];
        button.title = `${metric.name}: ${format(row.value, row.unit)}, ${BANDS[row.band].toLowerCase()}. p25 ${format(row.p25, row.unit)}, median ${format(row.median, row.unit)}, p75 ${format(row.p75, row.unit)} across ${reference.maps} shipped maps. Capture estimate, not the finished map.${screening}`;
      }
      button.setAttribute("aria-label", button.title);
    }
    if (active) { detail.textContent = active.title; detail.hidden = false; }
  }
  async function update(square) {
    controller?.abort(); controller = new AbortController();
    const signal = controller.signal, current = ++sequence;
    try {
      const [ledgerData, capture] = await Promise.all([ledger, captureEstimate(square, { signal })]);
      if (signal.aborted || sequence !== current) return;
      catalog = ledgerData;
      const report = checkCapabilities(capture.input, catalog);
      for (const [id, button] of buttons) {
        const cap = catalog.capabilities.find((c) => c.id === id), result = report.capabilities[id];
        const [mark, name] = LEVELS[result.level];
        button.dataset.level = result.level; button.querySelector(".capability-mark").textContent = mark;
        const area = id === "buildable" && result.fraction != null ? ` ${Math.round(result.fraction * 100)}% of sampled central land qualifies.` : "";
        button.title = `${cap.name}: ${name}. ${placeDetail(result) ?? REASONS[result.reason] ?? cap.limits}${area}`;
        button.setAttribute("aria-label", button.title);
      }
      status.textContent = `${square.lat.toFixed(3)}, ${square.lon.toFixed(3)} · estimate`;
      renderStock(capture.stock);
      const focused = [...buttons.values(), ...stockRows.values()].find((button) => button === document.activeElement);
      if (focused ?? active) { detail.textContent = (focused ?? active).title; detail.hidden = false; }
    } catch {
      if (signal.aborted || sequence !== current) return;
      unavailable();
    }
  }
  reset();
  return { reset, update, unavailable };
}
