// One export decision for the page and CLI; absent/invalid checks never download silently.
export function waterRiskDecision(risk) {
  if (!risk || risk.schema !== 1 || !["lower", "warning", "declined"].includes(risk.status) || !Array.isArray(risk.reasons))
    return { action: "decline", title: "Water check unavailable", reasons: ["Choose another square or export a heightmap for the Map Editor."] };
  if (risk.status === "declined") return { action: "decline", title: "Water check unavailable", reasons: risk.reasons };
  if (!risk.calibration?.squares || !risk.features || !Array.isArray(risk.outside_calibration) ||
      !["flood", "drying"].every((key) => ["flagged", "not_flagged"].includes(risk.risks?.[key]?.level)) ||
      (risk.status === "lower" && (risk.reasons.length || risk.outside_calibration.length ||
        Object.values(risk.risks).some((r) => r.level !== "not_flagged"))))
    return { action: "decline", title: "Water check unavailable", reasons: ["The water-check result is incomplete or inconsistent."] };
  if (risk.status === "warning") return { action: "review", title: "Review this square's water risk", reasons: risk.reasons };
  return { action: "download", title: "No screened water-risk flags", reasons: [] };
}

export function calibrationText(risk) {
  const c = risk?.calibration, r = c?.results;
  if (!r) return "Calibration is unavailable.";
  const percent = (n) => n === null ? "not measurable" : `${Math.round(n * 100)}%`;
  const unscored = c.unscored_complete_60_positive_outcomes;
  const gaps = unscored ? ` ${unscored.flood} flooding and ${unscored.drying} water-loss outcomes could not be scored.` : "";
  const dryingLimit = r.drying.negative_runs === 0 ? " Every scored complete run lost monitored water; drying false alarms cannot be measured." : "";
  return `${c.squares} landscapes; ${c.complete_60_runs} of ${c.complete_60_registry_runs ?? c.complete_60_runs} complete sixty-minute runs have bound inputs. Retrospective flooding precision ${percent(r.flood.precision)}, recall ${percent(r.flood.recall)}; monitored-water-loss precision ${percent(r.drying.precision)}, recall ${percent(r.drying.recall)}.${dryingLimit}${gaps} Unscored outcomes are not passes. These are calibration results, not independent geographic validation. Not every minor stream is monitored.`;
}
