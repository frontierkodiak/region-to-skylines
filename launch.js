// Launch presentation only. Keep the complete preset/input catalog in terrain.js
// unchanged so older links, CLI names and all five fixture cases still work.
import { PRESETS } from "./terrain.js";

export const LAUNCH_EXAMPLES = ["asheville", "innsbruck", "pittsburgh", "rio"]
  .map((slug) => PRESETS.find((preset) => preset.slug === slug));

export function mapWarning(preset) {
  if (preset?.slug === "rio")
    return "Rio has localized flooding and some dry minor-stream beds in the tested map.";
  if (preset?.slug === "charleston")
    return "Charleston's terrain accuracy check failed. It is not a launch example; its real elevations remain unverified.";
  return preset?.check ?? null;
}
