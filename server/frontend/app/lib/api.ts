export type ApiFetchOptions = RequestInit & {
  timeoutMs?: number;
};

function requestLabel(input: RequestInfo | URL) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();

  try {
    return input.url;
  } catch {
    return "request";
  }
}

export async function apiFetch(
  input: RequestInfo | URL,
  options: ApiFetchOptions = {},
): Promise<Response> {
  const { timeoutMs = 8000, signal, ...init } = options;

  if (signal) {
    return fetch(input, { ...init, signal });
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        `Request timed out after ${timeoutMs}ms: ${requestLabel(input)}`,
      );
    }

    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}
