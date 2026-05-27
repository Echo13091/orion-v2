"use client";

import { apiFetch } from "../lib/api";
import { getBackendUrl } from "../lib/backend";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const BACKEND_URL = getBackendUrl();

type StatusState = "good" | "bad" | "warn" | "neutral" | "active";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatMode(value?: string | null) {
  if (!value) return "—";

  return value
    .replace(/[_-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function displayValue(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
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

function dotClass(state: StatusState) {
  if (state === "good") return "bg-emerald-300";
  if (state === "bad") return "bg-red-300";
  if (state === "warn") return "bg-amber-300";
  if (state === "active") return "bg-blue-300";
  return "bg-neutral-500";
}

function Pill({ label, state = "neutral" }: { label: string; state?: StatusState }) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold",
        stateClasses(state),
      )}
    >
      <span className={cx("h-2 w-2 rounded-full", dotClass(state))} />
      {label}
    </span>
  );
}

function Field({
  label,
  value,
  state = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  state?: StatusState;
}) {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
        {label}
      </p>
      <div className={cx("mt-2 break-words text-lg font-semibold", textStateClass(state))}>
        {value}
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-950 p-5 shadow-lg">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-neutral-500">{subtitle}</p> : null}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any>(null);

  const loadCameras = useCallback(async () => {
    try {
      const res = await apiFetch(`${BACKEND_URL}/v1/cameras`, {
        cache: "no-store",
      });

      const data = await res.json().catch(() => null);
      setCameras(data);
    } catch (err) {
      setCameras({
        error: err instanceof Error ? err.message : String(err),
        summary: { total: 0, online: 0, degraded: 0, offline: 1 },
        devices: [],
      });
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(loadCameras, 0);
    const intervalTimer = window.setInterval(loadCameras, 5000);

    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(intervalTimer);
    };
  }, [loadCameras]);

  const devices = Array.isArray(cameras?.devices) ? cameras.devices : [];
  const primary = devices[0] || {};

  const health = primary?.health || "offline";

  const statusState: StatusState =
    health === "online"
      ? "good"
      : health === "offline"
        ? "bad"
        : "warn";

  const cameraReady = Boolean(primary?.camera_ready);
  const cameraEnabled = Boolean(primary?.camera_enabled);
  const wifiConnected = primary?.wifi?.status === "connected";
  const nodeUrl = primary?.node_url;
  const captureUrl = primary?.capture_url;
  const streamUrl = primary?.stream_url;
  const snapshotUrl = primary?.capture_url;

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-neutral-100">
      <div className="mx-auto max-w-6xl">
        <Link
          href="/"
          className="text-sm font-medium text-neutral-500 transition hover:text-neutral-200"
        >
          ← Back to Orion Dashboard
        </Link>

        <header className="mt-8 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-neutral-600">
              Orion Environmental Vision
            </p>
            <h1 className="mt-2 text-4xl font-bold text-white">
              Environmental Vision Node
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">
              Local ESP32-S3 camera node for environmental snapshots, visual context, and vision-node health.
            </p>
          </div>

          <Pill label={formatMode(health)} state={statusState} />
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-4">
          <Field label="Node Health" value={formatMode(health)} state={statusState} />
          <Field label="Wi-Fi" value={wifiConnected ? "Connected" : "Not connected"} state={wifiConnected ? "good" : "bad"} />
          <Field label="Camera" value={cameraReady ? "Ready" : cameraEnabled ? "Not ready" : "Disabled"} state={cameraReady ? "good" : "warn"} />
          <Field label="Native Stream" value={primary?.stream_access ? "Available" : "Unavailable"} state={primary?.stream_access ? "active" : "neutral"} />
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <Section
            title={primary?.name || "ESP32-S3 Environmental Vision Node"}
            subtitle={`${primary?.vendor || "ESP32"} · ${primary?.model || "Camera Node"}`}
            right={<Pill label={formatMode(primary?.integration_type || "local_environmental_vision")} state="active" />}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Node URL" value={nodeUrl ? <a className="text-blue-300 hover:text-blue-200" href={nodeUrl} target="_blank">{nodeUrl}</a> : "—"} />
              <Field label="Wi-Fi IP" value={displayValue(primary?.wifi?.ip)} state={wifiConnected ? "good" : "warn"} />
              <Field label="Wi-Fi SSID" value={displayValue(primary?.wifi?.ssid)} />
              <Field label="RSSI" value={primary?.wifi?.rssi !== undefined ? `${primary.wifi.rssi} dBm` : "—"} state={Number(primary?.wifi?.rssi) > -65 ? "good" : "warn"} />
              <Field label="Setup AP" value={displayValue(primary?.setup_ap?.ssid)} />
              <Field label="Setup AP IP" value={displayValue(primary?.setup_ap?.ip)} />
              <Field label="Firmware" value={displayValue(primary?.firmware_version)} />
              <Field label="Location" value={displayValue(primary?.location)} />
            </div>

            <div className="mt-5 rounded-2xl border border-neutral-800 bg-black p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                Orion Role
              </p>
              <p className="mt-2 text-lg font-semibold text-white">
                {primary?.orion_role || "Environmental vision node"}
              </p>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                {primary?.message || primary?.notes || "Local environmental camera node for Orion visual context."}
              </p>
            </div>
          </Section>

          <Section
            title="Environmental Snapshot"
            subtitle="Snapshot preview with manual stream access"
            right={<Pill label={cameraReady ? "Camera Ready" : "Camera Not Ready"} state={cameraReady ? "good" : "warn"} />}
          >
            <div className="rounded-2xl border border-neutral-800 bg-black p-5">
              <p className="text-xs uppercase tracking-[0.18em] text-neutral-500">
                Environmental Evidence Mode
              </p>
              <p className="mt-3 text-sm leading-6 text-neutral-300">
                Orion uses this ESP32-S3 as a secondary environmental observer. The dashboard does not keep a live camera connection open, so the node remains stable.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <Field label="Camera Ready" value={cameraReady ? "Yes" : "No"} state={cameraReady ? "good" : "warn"} />
                <Field label="Evidence Source" value="Snapshot capture" state="active" />
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {snapshotUrl ? (
                <a
                  href={snapshotUrl}
                  target="_blank"
                  className="rounded-xl bg-blue-600 px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-500"
                >
                  Open Snapshot
                </a>
              ) : null}

              {streamUrl ? (
                <a
                  href={streamUrl}
                  target="_blank"
                  className="rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-3 text-center text-sm font-semibold text-neutral-100 transition hover:bg-neutral-800"
                >
                  Open Stream
                </a>
              ) : null}
            </div>

            <div className="mt-5 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
              Orion should use snapshots for automation evidence. The MJPEG stream is intended for manual inspection, not low-latency FPV.
            </div>
          </Section>
        </div>

        <details className="mt-6 rounded-2xl border border-neutral-800 bg-neutral-950 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-neutral-300">
            Raw environmental vision JSON
          </summary>
          <pre className="mt-4 max-h-[420px] overflow-auto rounded-xl bg-black p-4 text-xs text-neutral-300">
            {JSON.stringify(cameras, null, 2)}
          </pre>
        </details>
      </div>
    </main>
  );
}
