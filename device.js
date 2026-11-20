// Decide before capturing inputs or creating the Python worker.
export function desktopBuildPolicy(nav = navigator) {
  const phone = nav.userAgentData?.mobile || /Android|iPhone|iPad|iPod|Windows Phone/i.test(nav.userAgent);
  const limited = typeof nav.deviceMemory === "number" && nav.deviceMemory <= 4;
  return phone || limited ? "Build this map on a computer. It needs about 500 MB of free memory." : null;
}
