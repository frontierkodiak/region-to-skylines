// Reads the square's WorldCover overviews off the page's main thread, in a
// worker the capability view terminates on pan or unmount. Nothing here
// decides a level: it returns the same lattice evidence the Node reader does.
import { collectLandcover } from "./capability-evidence.js";

const GEOTIFF_ESM = "https://cdn.jsdelivr.net/npm/geotiff@2.1.3/+esm";
const base = new URL(".", self.location.href);

self.onmessage = async ({ data: { square } }) => {
  try {
    const { fromUrl } = await import(GEOTIFF_ESM);
    const { values, ...landcover } = await collectLandcover(square, {
      fromUrl,
      tileUrl: (tile) => new URL(`worldcover/ESA_WorldCover_10m_2021_v200_${tile}_Map.tif`, base).href,
    });
    const bytes = Uint8Array.from(values).buffer;
    self.postMessage({ landcover, values: bytes }, [bytes]);
  } catch (error) {
    self.postMessage({ error: String(error?.message ?? error) });
  }
};
