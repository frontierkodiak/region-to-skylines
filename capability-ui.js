import { captureEstimate } from "./capability-inputs.js";
import { checkCapabilities } from "./capability-model.js";

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

export function mountCapabilities(root) {
  const row = root.querySelector(".capability-row"), detail = root.querySelector(".capability-detail"), status = root.querySelector(".capability-status");
  const ledger = fetch("./capabilities.json").then((r) => { if (!r.ok) throw new Error("Ledger unavailable"); return r.json(); });
  // Attach a rejection handler immediately, even if the first terrain build fails.
  ledger.catch(() => {});
  let controller = null, sequence = 0;
  let activeId = null;
  const buttons = new Map();
  for (const [id, name] of Object.entries(LABELS)) {
    const button = document.createElement("button");
    button.type = "button"; button.dataset.capability = id; button.dataset.level = "loading";
    button.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[id]}"/></svg><span class="capability-name">${name}</span><span class="capability-mark" aria-hidden="true">…</span>`;
    const show = () => { activeId = id; detail.textContent = button.title; detail.hidden = false; };
    button.addEventListener("pointerenter", show); button.addEventListener("focus", show); button.addEventListener("click", show);
    buttons.set(id, button); row.append(button);
  }
  const hide = () => { activeId = null; detail.hidden = true; };
  root.addEventListener("pointerleave", () => { if (!root.contains(document.activeElement)) hide(); });
  root.addEventListener("focusout", (event) => { if (!root.contains(event.relatedTarget)) hide(); });
  root.addEventListener("keydown", (event) => { if (event.key === "Escape") hide(); });
  function reset(message = "Checking this square…") {
    controller?.abort(); sequence++;
    status.textContent = message;
    for (const [id, button] of buttons) {
      button.dataset.level = "loading";
      button.querySelector(".capability-mark").textContent = "…";
      button.title = `${LABELS[id]}: checking this square.`;
      button.setAttribute("aria-label", button.title);
    }
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
    detail.textContent = "";
    detail.hidden = true;
  }
  async function update(square) {
    controller?.abort(); controller = new AbortController();
    const signal = controller.signal, current = ++sequence;
    try {
      const [catalog, capture] = await Promise.all([ledger, captureEstimate(square, { signal })]);
      if (signal.aborted || sequence !== current) return;
      const report = checkCapabilities(capture.input, catalog);
      for (const [id, button] of buttons) {
        const cap = catalog.capabilities.find((c) => c.id === id), result = report.capabilities[id];
        const [mark, name] = LEVELS[result.level];
        button.dataset.level = result.level; button.querySelector(".capability-mark").textContent = mark;
        const area = id === "buildable" && result.fraction != null ? ` ${Math.round(result.fraction * 100)}% of sampled central land qualifies.` : "";
        button.title = `${cap.name}: ${name}. ${REASONS[result.reason] ?? cap.limits}${area}`;
        button.setAttribute("aria-label", button.title);
      }
      status.textContent = `${square.lat.toFixed(3)}, ${square.lon.toFixed(3)} · estimate`;
      const active = [...buttons].find(([id, b]) => id === activeId || b === document.activeElement)?.[1];
      if (active) { detail.textContent = active.title; detail.hidden = false; }
    } catch {
      if (signal.aborted || sequence !== current) return;
      unavailable();
    }
  }
  reset();
  return { reset, update, unavailable };
}
