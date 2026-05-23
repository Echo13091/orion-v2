export function getBackendUrl() {
  const configured = process.env.NEXT_PUBLIC_BACKEND_URL;

  if (
    configured &&
    !configured.includes("localhost") &&
    !configured.includes("127.0.0.1")
  ) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol || "http:";
    const hostname = window.location.hostname;

    return `${protocol}//${hostname}:5001`;
  }

  return configured?.replace(/\/$/, "") || "http://localhost:5001";
}
