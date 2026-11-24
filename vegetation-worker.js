import { vegetationExpectation } from "./vegetation-inputs.js";

self.onmessage = async ({ data: square }) => {
  try {
    const { fromUrl } = await import("https://cdn.jsdelivr.net/npm/geotiff@2.1.3/+esm");
    const base = new URL(".", self.location.href);
    const report = await vegetationExpectation(square, { fromUrl,
      canopyUrl: (key) => new URL(`canopy/${key}.tif`, base).href,
      forestUrl: new URL("forest-types.tif", base).href,
      coverUrl: (key) => new URL(`worldcover/ESA_WorldCover_10m_2021_v200_${key}_Map.tif`, base).href });
    self.postMessage({ report });
  } catch (error) { self.postMessage({ error: String(error.message) }); }
};
