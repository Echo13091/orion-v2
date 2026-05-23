export function getBackendUrl() {
  /*
   * Browser-safe default:
   * Use the Next.js frontend as a same-origin proxy.
   *
   * Browser:
   *   http://<jetson>:3001/orion-api/system
   *
   * Frontend container:
   *   http://backend:5001/v1/system
   */
  if (typeof window !== "undefined") {
    return "/orion-api";
  }

  return process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") || "http://localhost:5001";
}
