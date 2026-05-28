"use client";

import { apiFetch } from "../lib/api";
import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const BACKEND_URL = getBackendUrl();
const POLL_MS = Number(process.env.NEXT_PUBLIC_SYSTEM_POLL_MS ?? "3000");

type VisionStatus = {
  ok?: boolean;
  online?: boolean;
  degraded?: boolean;
  node_url?: string;
  vision_node_url?: string;
  vision_node_fallback_url?: string | null;
  vision_node_urls?: string[];
  configured_node_urls?: string[];
  node_name?: string;
  node_id?: string;
  camera_online?: boolean;
  streaming_clients?: number;
  fps?: number | null;
  resolution?: string | null;
  last_frame_age?: number | null;
  focus_mode?: string | null;
  focus_state?: string | null;
  lens_position?: number | null;
  fault?: boolean;
  fault_code?: string;
  fault_message?: string;
  error?: string;
  detail?: string;
  message?: string;
};

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

function formatMode(value?: string | null) {
  if (!value) return "—";
  return value
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatNumber(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function sanitizeEndpoint(value?: string | null) {
  if (!value) return "Not configured";
  return value.replace(/https?:\/\//, "").replace(/\/$/, "");
}

function stateClasses(state: StatusState) {
  if (state === "good") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (state === "bad") return "border-red-500/30 bg-red-500/10 text-red-300";
  if (state === "warn") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  if (state === "active") return "border-blue-500/30 bg-blue-500/10 text-blue-300";
  return "border-neutral-700 bg-neutral-900 text-neutral-300";
}

function textStateClass(state: StatusState) {
  if (state === "good") return "text-emerald-200";
  if (state === "bad") return "text-red-200";
  if (state === "warn") return "text-amber-200";
  if (state === "active") return "text-blue-200";
  return "text-white";
}

function Field({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value: string | number;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">{label}</p>
      <p className={`mt-2 break-words text-lg font-semibold ${textStateClass(state)}`}>{value}</p>
    </div>
  );
}

export default function VisionNodePage() {
  const [vision, setVision] = useState<VisionStatus | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const loadVision = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/vision/status`, { cache: "no-store" });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        setVision({
          ok: false,
          online: false,
          degraded: true,
          error: data?.error || "Vision node unavailable",
          detail: data?.detail,
          node_url: data?.node_url,
          vision_node_url: data?.vision_node_url,
          vision_node_fallback_url: data?.vision_node_fallback_url,
          vision_node_urls: data?.vision_node_urls,
          configured_node_urls: data?.configured_node_urls,
        });
        return;
      }

      setVision(data);
      setLastError(null);
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
      setVision({ ok: false, online: false, degraded: true });
    }
  }, []);

  useEffect(() => {
    loadVision();
    const timer = window.setInterval(loadVision, Number.isFinite(POLL_MS) ? POLL_MS : 3000);
    return () => window.clearInterval(timer);
  }, [loadVision]);

  const nodeUrl = useMemo(() => {
    const candidates = [
      vision?.node_url,
      vision?.vision_node_url,
      ...(vision?.vision_node_urls || []),
      ...(vision?.configured_node_urls || []),
      vision?.vision_node_fallback_url || undefined,
    ].filter(Boolean) as string[];

    return candidates[0] || "";
  }, [vision]);

  const nodeOnline = Boolean(vision?.online);
  const cameraOnline = Boolean(vision?.camera_online ?? vision?.online);
  const nodeState: StatusState = !vision ? "neutral" : vision?.fault ? "bad" : nodeOnline ? "good" : "bad";
  const cameraState: StatusState = !vision ? "neutral" : cameraOnline ? "good" : "bad";
  const snapshotUrl = nodeUrl ? `${nodeUrl.replace(/\/$/, "")}/api/snapshot` : "";
  const statusUrl = nodeUrl ? `${nodeUrl.replace(/\/$/, "")}/api/status` : "";

  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <Link href="/vision" className="text-sm font-medium text-neutral-400 hover:text-white">
              ← Back to Environmental Vision
            </Link>
            <p className="mt-6 text-xs uppercase tracking-[0.25em] text-neutral-500">Orion Field Node</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Vision Node Direct</h1>
            <p className="mt-2 max-w-3xl text-neutral-400">
              Direct launch page for the Raspberry Pi vision node. Use this to open the local node UI,
              inspect its status contract, or grab a fresh snapshot without digging through network details.
            </p>
          </div>

          <span className={`self-start rounded-full border px-4 py-2 text-sm font-semibold md:self-end ${stateClasses(nodeState)}`}>
            {nodeOnline ? "Node Online" : vision ? "Node Offline" : "Loading"}
          </span>
        </header>

        <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">Configured Field Endpoint</p>
              <h2 className="mt-2 break-words text-2xl font-semibold text-white">
                {sanitizeEndpoint(nodeUrl)}
              </h2>
              <p className="mt-2 text-sm text-neutral-500">
                {vision?.node_name || vision?.node_id || "Raspberry Pi vision node"}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <a
                href={nodeUrl || undefined}
                target="_blank"
                className={`inline-flex items-center justify-center rounded-xl px-4 py-3 text-sm font-semibold transition ${
                  nodeUrl ? "bg-blue-600 text-white hover:bg-blue-500" : "pointer-events-none bg-neutral-800 text-neutral-500"
                }`}
              >
                Open Node UI
              </a>
              <a
                href={snapshotUrl || undefined}
                target="_blank"
                className={`inline-flex items-center justify-center rounded-xl border border-neutral-700 px-4 py-3 text-sm font-semibold transition ${
                  snapshotUrl ? "bg-neutral-900 text-neutral-100 hover:bg-neutral-800" : "pointer-events-none bg-neutral-900 text-neutral-600"
                }`}
              >
                Open Snapshot
              </a>
              <a
                href={statusUrl || undefined}
                target="_blank"
                className={`inline-flex items-center justify-center rounded-xl border border-neutral-700 px-4 py-3 text-sm font-semibold transition ${
                  statusUrl ? "bg-neutral-900 text-neutral-100 hover:bg-neutral-800" : "pointer-events-none bg-neutral-900 text-neutral-600"
                }`}
              >
                Status JSON
              </a>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Node" value={nodeOnline ? "Online" : "Offline"} state={nodeState} />
          <Field label="Camera" value={cameraOnline ? "Online" : "Offline"} state={cameraState} />
          <Field label="FPS" value={formatNumber(vision?.fps, 1)} state={Number(vision?.fps ?? 0) > 0 ? "active" : "neutral"} />
          <Field label="Resolution" value={vision?.resolution || "—"} />
          <Field label="Clients" value={vision?.streaming_clients ?? 0} state={Number(vision?.streaming_clients ?? 0) > 0 ? "active" : "neutral"} />
          <Field label="Focus" value={formatMode(vision?.focus_mode)} state={vision?.focus_mode ? "good" : "neutral"} />
          <Field label="Last Frame" value={Number.isFinite(Number(vision?.last_frame_age)) ? `${Number(vision?.last_frame_age).toFixed(2)}s ago` : "—"} state={Number(vision?.last_frame_age ?? 999) <= 3 ? "good" : "warn"} />
          <Field label="Fault" value={vision?.fault ? vision?.fault_code || "Fault" : nodeOnline ? "None" : "Unreachable"} state={vision?.fault || !nodeOnline ? "bad" : "good"} />
        </div>

        <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
          <h2 className="text-xl font-semibold text-white">Zero 2 W Runtime Boundary</h2>
          <p className="mt-2 text-sm leading-6 text-neutral-400">
            The Pi node should stay lightweight: camera lifecycle, health, snapshots, and low-rate live view.
            Orion / Jetson should own rain interpretation, lawn analysis, recording, decision logic, and AI-assisted reasoning.
          </p>

          {(vision?.error || lastError) ? (
            <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              {vision?.error || lastError}
              {vision?.detail ? ` · ${vision.detail}` : ""}
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
