import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://backend:5001";

function backendUrl(pathParts: string[], request: NextRequest) {
  const cleanBase = BACKEND_INTERNAL_URL.replace(/\/$/, "");
  const cleanPath = pathParts.map(encodeURIComponent).join("/");
  const search = request.nextUrl.search || "";

  return `${cleanBase}/v1/${cleanPath}${search}`;
}

function filteredHeaders(request: NextRequest) {
  const headers = new Headers();

  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  const controlToken = request.headers.get("x-orion-control-token");
  const authorization = request.headers.get("authorization");

  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  if (controlToken) headers.set("x-orion-control-token", controlToken);
  if (authorization) headers.set("authorization", authorization);

  return headers;
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  const method = request.method.toUpperCase();

  const init: RequestInit = {
    method,
    headers: filteredHeaders(request),
    cache: "no-store",
  };

  if (!["GET", "HEAD"].includes(method)) {
    init.body = await request.text();
  }

  const upstream = await fetch(backendUrl(params.path || [], request), init);
  const body = await upstream.text();

  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/json",
      "cache-control": "no-store",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}
